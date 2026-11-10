import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from mysql.connector import IntegrityError, MySQLConnection


def calculate_sma(prices, period: int):
    """Return date/value pairs for a simple moving average over valid closes."""
    if period <= 0:
        raise ValueError("SMA period must be positive.")
    ordered = sorted(
        (
            {"price_date": item["price_date"], "close_price": Decimal(str(item["close_price"]))}
            for item in prices
            if item.get("price_date") is not None
            and item.get("close_price") is not None
        ),
        key=lambda item: item["price_date"],
    )
    result = []
    for index in range(period - 1, len(ordered)):
        window = ordered[index - period + 1 : index + 1]
        result.append(
            {
                "price_date": ordered[index]["price_date"],
                "value": sum((item["close_price"] for item in window), Decimal("0"))
                / period,
            }
        )
    return result


def prepare_chart_data(prices):
    """Prepare chronologically ordered close, SMA20, and SMA50 chart series."""
    ordered = sorted(prices, key=lambda item: item["price_date"])
    sma20 = {item["price_date"]: item["value"] for item in calculate_sma(ordered, 20)}
    sma50 = {item["price_date"]: item["value"] for item in calculate_sma(ordered, 50)}
    return {
        "labels": [item["price_date"].isoformat() for item in ordered],
        "close": [float(item["close_price"]) for item in ordered],
        "sma20": [float(sma20[item["price_date"]]) if item["price_date"] in sma20 else None for item in ordered],
        "sma50": [float(sma50[item["price_date"]]) if item["price_date"] in sma50 else None for item in ordered],
    }


def list_historical_prices(
    connection: MySQLConnection,
    stock_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
):
    clauses = ["hp.stock_id = %s"]
    parameters = [stock_id]
    if start_date is not None:
        clauses.append("hp.price_date >= %s")
        parameters.append(start_date)
    if end_date is not None:
        clauses.append("hp.price_date <= %s")
        parameters.append(end_date)

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            f"""
            SELECT hp.price_id, hp.stock_id, s.symbol, s.company_name,
                   hp.price_date, hp.open_price, hp.high_price,
                   hp.low_price, hp.close_price, hp.volume
            FROM historical_prices AS hp
            INNER JOIN stocks AS s ON s.stock_id = hp.stock_id
            WHERE {' AND '.join(clauses)}
            ORDER BY hp.price_date
            """,
            tuple(parameters),
        )
        return cursor.fetchall()
    finally:
        cursor.close()


def import_historical_csv(connection: MySQLConnection, file_bytes: bytes) -> int:
    """Validate and atomically import rows with the existing schema columns."""
    try:
        text = file_bytes.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("CSV must be valid UTF-8 with a header row.") from exc

    required = {
        "stock_id",
        "price_date",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
    }
    if not rows or not required.issubset(rows[0].keys()):
        raise ValueError(
            "CSV headers must be: stock_id, price_date, open_price, "
            "high_price, low_price, close_price, volume."
        )

    parsed = []
    seen = set()
    for row_number, row in enumerate(rows, start=2):
        try:
            stock_id = int(row["stock_id"])
            price_date = date.fromisoformat(row["price_date"].strip())
            open_price = Decimal(row["open_price"])
            high_price = Decimal(row["high_price"])
            low_price = Decimal(row["low_price"])
            close_price = Decimal(row["close_price"])
            volume = int(row["volume"])
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid value on CSV row {row_number}.") from exc
        values = (open_price, high_price, low_price, close_price)
        if (
            stock_id <= 0
            or any(not value.is_finite() or value < 0 for value in values)
            or volume < 0
            or (stock_id, price_date) in seen
        ):
            raise ValueError(f"Invalid or duplicate record on CSV row {row_number}.")
        seen.add((stock_id, price_date))
        parsed.append(
            (stock_id, price_date, open_price, high_price, low_price, close_price, volume)
        )

    cursor = None
    try:
        connection.start_transaction()
        cursor = connection.cursor()
        for row in parsed:
            cursor.execute(
                """
                INSERT INTO historical_prices (
                    stock_id, price_date, open_price, high_price,
                    low_price, close_price, volume
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                row,
            )
        connection.commit()
        return len(parsed)
    except IntegrityError as exc:
        connection.rollback()
        raise ValueError(
            "Import rejected because a stock ID is invalid or a date already exists."
        ) from exc
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()


def portfolio_analytics(holdings):
    total_invested = sum(
        (holding["remaining_cost_basis"] for holding in holdings),
        Decimal("0"),
    )
    realized = sum(
        (holding["realized_profit_loss"] for holding in holdings),
        Decimal("0"),
    )
    has_complete_prices = bool(holdings) and all(
        holding["market_value"] is not None for holding in holdings
    )
    current_value = (
        sum((holding["market_value"] for holding in holdings), Decimal("0"))
        if has_complete_prices
        else None
    )
    unrealized = current_value - total_invested if current_value is not None else None
    return_percentage = (
        ((realized + unrealized) / total_invested) * Decimal("100")
        if total_invested and unrealized is not None
        else None
    )
    return {
        "total_invested": total_invested,
        "current_value": current_value,
        "unrealized": unrealized,
        "realized": realized,
        "return_percentage": return_percentage,
    }
