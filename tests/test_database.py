from unittest.mock import Mock

from mysql.connector import IntegrityError
from services.user_service import (
    create_user,
    hash_user_password,
    verify_user_password,
)
from services.stock_service import (
    add_to_watchlist,
    get_user_watchlist,
    search_stocks,
)


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
