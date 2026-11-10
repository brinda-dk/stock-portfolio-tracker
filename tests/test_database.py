from unittest.mock import Mock

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from mysql.connector import IntegrityError
from services.user_service import (
    create_user,
    hash_user_password,
    verify_user_password,
)
from services.stock_service import (
    add_to_watchlist,
    create_stock,
    get_user_watchlist,
    search_stocks,
)
from services.transaction_service import (
    get_holdings,
    record_transaction,
)
from services.analytics_service import (
    calculate_sma,
    import_historical_csv,
    portfolio_analytics,
    prepare_chart_data,
)


def test_sma_sorts_dates_and_returns_only_complete_windows():
    prices = [
        {"price_date": date(2026, 1, 3), "close_price": Decimal("30")},
        {"price_date": date(2026, 1, 1), "close_price": Decimal("10")},
        {"price_date": date(2026, 1, 2), "close_price": Decimal("20")},
    ]

    result = calculate_sma(prices, 2)

    assert result == [
        {"price_date": date(2026, 1, 2), "value": Decimal("15")},
        {"price_date": date(2026, 1, 3), "value": Decimal("25")},
    ]


def test_sma_ignores_missing_closes_and_handles_insufficient_data():
    prices = [
        {"price_date": date(2026, 1, 1), "close_price": Decimal("10")},
        {"price_date": date(2026, 1, 2), "close_price": None},
    ]

    assert calculate_sma(prices, 2) == []


def test_chart_data_contains_close_and_sma_series_in_date_order():
    prices = [
        {"price_date": date(2026, 1, 2), "close_price": Decimal("20")},
        {"price_date": date(2026, 1, 1), "close_price": Decimal("10")},
    ]

    assert prepare_chart_data(prices) == {
        "labels": ["2026-01-01", "2026-01-02"],
        "close": [10.0, 20.0],
        "sma20": [None, None],
        "sma50": [None, None],
    }


def test_portfolio_analytics_does_not_fabricate_value_without_prices():
    holdings = [
        {
            "remaining_cost_basis": Decimal("1000"),
            "market_value": None,
            "unrealized_profit_loss": None,
            "realized_profit_loss": Decimal("25"),
        }
    ]

    result = portfolio_analytics(holdings)

    assert result["total_invested"] == Decimal("1000")
    assert result["current_value"] is None
    assert result["unrealized"] is None
    assert result["realized"] == Decimal("25")
    assert result["return_percentage"] is None


def test_historical_csv_import_is_parameterized_and_atomic():
    connection = Mock()
    csv_bytes = (
        b"stock_id,price_date,open_price,high_price,low_price,close_price,volume\n"
        b"7,2026-01-01,10,12,9,11,1000\n"
    )

    assert import_historical_csv(connection, csv_bytes) == 1

    connection.start_transaction.assert_called_once()
    connection.commit.assert_called_once()
    query, parameters = connection.cursor.return_value.execute.call_args.args
    assert "INSERT INTO historical_prices" in query
    assert parameters == (7, date(2026, 1, 1), Decimal("10"), Decimal("12"), Decimal("9"), Decimal("11"), 1000)


def test_historical_csv_rejects_duplicate_rows_before_database_write():
    connection = Mock()
    csv_bytes = (
        b"stock_id,price_date,open_price,high_price,low_price,close_price,volume\n"
        b"7,2026-01-01,10,12,9,11,1000\n"
        b"7,2026-01-01,10,12,9,11,1000\n"
    )

    try:
        import_historical_csv(connection, csv_bytes)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("Duplicate historical rows should be rejected")

    connection.start_transaction.assert_not_called()


def test_password_is_hashed_and_can_be_verified():
    password_hash = hash_user_password("correct-password")

    assert password_hash != "correct-password"
    assert verify_user_password(password_hash, "correct-password")
    assert not verify_user_password(password_hash, "wrong-password")


def test_create_user_uses_parameterized_query():
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.lastrowid = 7

    user_id = create_user(connection, "student@example.com", "secret", "Student")

    assert user_id == 7
    query, parameters = cursor.execute.call_args.args
    assert "VALUES (%s, %s, %s)" in query
    assert parameters[0] == "Student"
    assert parameters[1] == "student@example.com"
    assert parameters[2] != "secret"
    connection.commit.assert_called_once()


def test_search_stocks_uses_parameterized_symbol_and_company_filters():
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = []

    search_stocks(connection, "apple")

    query, parameters = connection.cursor.return_value.execute.call_args.args
    assert "symbol LIKE %s OR company_name LIKE %s" in query
    assert parameters == ("%apple%", "%apple%")


def test_watchlist_query_is_scoped_to_user():
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = []

    get_user_watchlist(connection, 42)

    query, parameters = connection.cursor.return_value.execute.call_args.args
    assert "WHERE w.user_id = %s" in query
    assert parameters == (42,)


def test_duplicate_watchlist_entry_rolls_back_without_success():
    connection = Mock()
    connection.cursor.return_value.execute.side_effect = IntegrityError(
        "duplicate entry"
    )

    assert not add_to_watchlist(connection, 42, 7)
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_create_stock_uses_actual_stock_columns():
    connection = Mock()

    assert create_stock(connection, "AAPL", "Apple Inc.", "NASDAQ")

    query, parameters = connection.cursor.return_value.execute.call_args.args
    assert "INSERT INTO stocks (symbol, company_name, exchange_name)" in query
    assert parameters == ("AAPL", "Apple Inc.", "NASDAQ")
    connection.commit.assert_called_once()


def test_buy_transaction_commits_parameterized_insert():
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {"stock_id": 7}
    cursor.fetchall.return_value = []

    record_transaction(
        connection,
        42,
        7,
        "BUY",
        Decimal("2.5"),
        Decimal("100.25"),
        date(2026, 11, 10),
    )

    connection.start_transaction.assert_called_once()
    connection.commit.assert_called_once()
    query, parameters = cursor.execute.call_args_list[-1].args
    assert "INSERT INTO transactions" in query
    assert parameters[:3] == (42, 7, "BUY")


def test_sell_transaction_rejects_oversell_and_rolls_back():
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {"stock_id": 7}
    cursor.fetchall.return_value = [
        {
            "transaction_type": "BUY",
            "quantity": Decimal("2"),
            "price_per_share": Decimal("100"),
        }
    ]

    try:
        record_transaction(
            connection,
            42,
            7,
            "SELL",
            Decimal("3"),
            Decimal("110"),
            date(2026, 11, 10),
        )
    except ValueError as exc:
        assert "at most" in str(exc)
    else:
        raise AssertionError("Oversell should be rejected")

    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
    assert len(cursor.execute.call_args_list) == 2


def test_failed_insert_rolls_back_without_commit():
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = {"stock_id": 7}
    cursor.fetchall.return_value = []
    cursor.execute.side_effect = [
        None,
        None,
        RuntimeError("insert failed"),
    ]

    try:
        record_transaction(
            connection,
            42,
            7,
            "BUY",
            Decimal("1"),
            Decimal("10"),
            date(2026, 11, 10),
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Failed insert should raise")

    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_record_transaction_rejects_invalid_stock_id():
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchone.return_value = None

    try:
        record_transaction(
            connection,
            42,
            999,
            "BUY",
            Decimal("1"),
            Decimal("10"),
            date(2026, 11, 10),
        )
    except ValueError as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("Invalid stock should be rejected")

    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_holdings_calculate_buy_sell_weighted_average():
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchall.side_effect = [
        [
            {
                "stock_id": 7,
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "transaction_type": "BUY",
                "quantity": Decimal("10"),
                "price_per_share": Decimal("100"),
                "transaction_date": date(2026, 1, 1),
                "transaction_id": 1,
            },
            {
                "stock_id": 7,
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "transaction_type": "BUY",
                "quantity": Decimal("10"),
                "price_per_share": Decimal("120"),
                "transaction_date": date(2026, 1, 2),
                "transaction_id": 2,
            },
            {
                "stock_id": 7,
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "transaction_type": "SELL",
                "quantity": Decimal("5"),
                "price_per_share": Decimal("130"),
                "transaction_date": date(2026, 1, 3),
                "transaction_id": 3,
            },
        ],
        [
            {
                "stock_id": 7,
                "close_price": Decimal("125"),
                "price_date": date(2026, 1, 4),
            }
        ],
    ]

    holdings = get_holdings(connection, 42)

    assert holdings[0]["current_quantity"] == Decimal("15")
    assert holdings[0]["remaining_cost_basis"] == Decimal("1650")
    assert holdings[0]["average_cost"] == Decimal("110")
    assert holdings[0]["realized_profit_loss"] == Decimal("100")
    assert holdings[0]["market_value"] == Decimal("1875")
    assert holdings[0]["unrealized_profit_loss"] == Decimal("225")


def test_requested_buy_buy_sell_sequence_calculates_expected_holding():
    connection = Mock()
    cursor = connection.cursor.return_value
    cursor.fetchall.side_effect = [
        [
            {
                "stock_id": 7,
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "transaction_type": "BUY",
                "quantity": Decimal("10"),
                "price_per_share": Decimal("100"),
                "transaction_date": date(2026, 1, 1),
                "transaction_id": 1,
            },
            {
                "stock_id": 7,
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "transaction_type": "BUY",
                "quantity": Decimal("5"),
                "price_per_share": Decimal("120"),
                "transaction_date": date(2026, 1, 2),
                "transaction_id": 2,
            },
            {
                "stock_id": 7,
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "transaction_type": "SELL",
                "quantity": Decimal("4"),
                "price_per_share": Decimal("130"),
                "transaction_date": date(2026, 1, 3),
                "transaction_id": 3,
            },
        ],
        [],
    ]

    holding = get_holdings(connection, 42)[0]

    assert holding["current_quantity"] == Decimal("11")
    currency_precision = Decimal("0.01")
    assert holding["remaining_cost_basis"].quantize(
        currency_precision, rounding=ROUND_HALF_UP
    ) == Decimal("1173.33")
    assert holding["average_cost"].quantize(
        currency_precision, rounding=ROUND_HALF_UP
    ) == Decimal("106.67")
    assert holding["realized_profit_loss"].quantize(
        currency_precision, rounding=ROUND_HALF_UP
    ) == Decimal("93.33")
