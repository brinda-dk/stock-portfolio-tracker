from collections import defaultdict
from datetime import date
from decimal import Decimal
from secrets import token_urlsafe

from mysql.connector import MySQLConnection


ZERO = Decimal("0")


def new_submission_token() -> str:
    return token_urlsafe(24)


def list_stocks(connection: MySQLConnection):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT stock_id, symbol, company_name, exchange_name
            FROM stocks
            ORDER BY symbol
            """
        )
        return cursor.fetchall()
    finally:
        cursor.close()


def record_transaction(
    connection: MySQLConnection,
    user_id: int,
    stock_id: int,
    transaction_type: str,
    quantity: Decimal,
    price_per_share: Decimal,
    transaction_date: date,
) -> None:
    """Record a transaction after locking and validating the user's holding."""
    if transaction_type not in {"BUY", "SELL"}:
        raise ValueError("Transaction type must be BUY or SELL.")
    if (
        not quantity.is_finite()
        or not price_per_share.is_finite()
        or quantity <= ZERO
        or price_per_share <= ZERO
    ):
        raise ValueError("Quantity and price must both be greater than zero.")

    cursor = None
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT stock_id
            FROM stocks
            WHERE stock_id = %s
            FOR UPDATE
            """,
            (stock_id,),
        )
        if cursor.fetchone() is None:
            raise ValueError("The selected stock does not exist.")

        cursor.execute(
            """
            SELECT transaction_type, quantity, price_per_share
            FROM transactions
            WHERE user_id = %s AND stock_id = %s
            ORDER BY transaction_date, transaction_id
            FOR UPDATE
            """,
            (user_id, stock_id),
        )
        current_quantity, current_cost = _calculate_position(cursor.fetchall())
        if transaction_type == "SELL" and quantity > current_quantity:
            raise ValueError(
                f"You can sell at most {current_quantity:.6f} shares of this stock."
            )

        cursor.execute(
            """
            INSERT INTO transactions (
                user_id, stock_id, transaction_type, quantity,
                price_per_share, transaction_date
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                stock_id,
                transaction_type,
                quantity,
                price_per_share,
                transaction_date,
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()


def get_transaction_history(connection: MySQLConnection, user_id: int, filters=None):
    filters = filters or {}
    clauses = ["t.user_id = %s"]
    parameters = [user_id]

    stock_id = filters.get("stock_id")
    if stock_id is not None:
        clauses.append("t.stock_id = %s")
        parameters.append(stock_id)
    transaction_type = filters.get("transaction_type")
    if transaction_type in {"BUY", "SELL"}:
        clauses.append("t.transaction_type = %s")
        parameters.append(transaction_type)
    transaction_date = filters.get("transaction_date")
    if transaction_date is not None:
        clauses.append("t.transaction_date = %s")
        parameters.append(transaction_date)

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            f"""
            SELECT t.transaction_id, t.stock_id, s.symbol, s.company_name,
                   t.transaction_type, t.quantity, t.price_per_share,
                   t.transaction_date
            FROM transactions AS t
            INNER JOIN stocks AS s ON s.stock_id = t.stock_id
            WHERE {' AND '.join(clauses)}
            ORDER BY t.transaction_date DESC, t.transaction_id DESC
            """,
            tuple(parameters),
        )
        return cursor.fetchall()
    finally:
        cursor.close()


def get_holdings(connection: MySQLConnection, user_id: int):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT t.stock_id, s.symbol, s.company_name, t.transaction_type,
                   t.quantity, t.price_per_share, t.transaction_date,
                   t.transaction_id
            FROM transactions AS t
            INNER JOIN stocks AS s ON s.stock_id = t.stock_id
            WHERE t.user_id = %s
            ORDER BY t.stock_id, t.transaction_date, t.transaction_id
            """,
            (user_id,),
        )
        transactions = cursor.fetchall()
        cursor.execute(
            """
            SELECT hp.stock_id, hp.close_price, hp.price_date
            FROM historical_prices AS hp
            INNER JOIN (
                SELECT stock_id, MAX(price_date) AS latest_date
                FROM historical_prices
                GROUP BY stock_id
            ) AS latest
                ON latest.stock_id = hp.stock_id
               AND latest.latest_date = hp.price_date
            """
        )
        prices = {row["stock_id"]: row for row in cursor.fetchall()}
    finally:
        cursor.close()

    grouped = defaultdict(list)
    for transaction in transactions:
        grouped[transaction["stock_id"]].append(transaction)

    holdings = []
    for stock_transactions in grouped.values():
        position = _position_from_transactions(stock_transactions)
        if position["current_quantity"] <= ZERO:
            continue
        stock_id = stock_transactions[0]["stock_id"]
        latest_price = prices.get(stock_id)
        current_price = latest_price["close_price"] if latest_price else None
        market_value = (
            position["current_quantity"] * current_price
            if current_price is not None
            else None
        )
        unrealized = (
            market_value - position["remaining_cost_basis"]
            if market_value is not None
            else None
        )
        holdings.append(
            {
                "stock_id": stock_id,
                "symbol": stock_transactions[0]["symbol"],
                "company_name": stock_transactions[0]["company_name"],
                "bought_quantity": position["bought_quantity"],
                "sold_quantity": position["sold_quantity"],
                "current_quantity": position["current_quantity"],
                "average_cost": (
                    position["remaining_cost_basis"]
                    / position["current_quantity"]
                ),
                "remaining_cost_basis": position["remaining_cost_basis"],
                "current_price": current_price,
                "price_date": latest_price["price_date"] if latest_price else None,
                "market_value": market_value,
                "unrealized_profit_loss": unrealized,
                "realized_profit_loss": position["realized_profit_loss"],
            }
        )
    return holdings


def _calculate_position(transactions):
    position = _position_from_transactions(transactions)
    return position["current_quantity"], position["remaining_cost_basis"]


def _position_from_transactions(transactions):
    quantity = ZERO
    cost_basis = ZERO
    bought_quantity = ZERO
    sold_quantity = ZERO
    realized_profit_loss = ZERO

    for transaction in transactions:
        transaction_quantity = Decimal(str(transaction["quantity"]))
        price = Decimal(str(transaction["price_per_share"]))
        if transaction["transaction_type"] == "BUY":
            quantity += transaction_quantity
            cost_basis += transaction_quantity * price
            bought_quantity += transaction_quantity
        else:
            average_cost = cost_basis / quantity if quantity else ZERO
            quantity -= transaction_quantity
            cost_basis -= transaction_quantity * average_cost
            sold_quantity += transaction_quantity
            realized_profit_loss += transaction_quantity * (price - average_cost)

    return {
        "bought_quantity": bought_quantity,
        "sold_quantity": sold_quantity,
        "current_quantity": quantity,
        "remaining_cost_basis": cost_basis,
        "realized_profit_loss": realized_profit_loss,
    }
