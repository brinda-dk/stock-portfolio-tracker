from unittest.mock import Mock, patch

from app import create_app
from mysql.connector import IntegrityError
from services.user_service import hash_user_password


def test_homepage_loads():
    app = create_app()
    app.config["TESTING"] = True

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"Stock Portfolio Tracker" in response.data


def test_database_settings_use_expected_environment_names():
    app = create_app()

    assert set(
        ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
    ).issubset(app.config)


def test_dashboard_requires_login():
    app = create_app()

    response = app.test_client().get("/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_registration_hashes_password_and_redirects_to_login():
    app = create_app()
    connection = Mock()
    connection.cursor.return_value.lastrowid = 12

    with patch("services.database.get_db_connection", return_value=connection):
        response = app.test_client().post(
            "/register",
            data={
                "name": "Student",
                "email": "student@example.com",
                "password": "correct-password",
                "confirm_password": "correct-password",
            },
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    parameters = connection.cursor.return_value.execute.call_args.args[1]
    assert parameters[0] == "Student"
    assert parameters[1] == "student@example.com"
    assert parameters[2] != "correct-password"


def test_duplicate_registration_shows_error():
    app = create_app()
    connection = Mock()

    with (
        patch("services.database.get_db_connection", return_value=connection),
        patch(
            "services.user_service.create_user",
            side_effect=IntegrityError("duplicate email"),
        ),
    ):
        response = app.test_client().post(
            "/register",
            data={
                "name": "Student",
                "email": "student@example.com",
                "password": "correct-password",
                "confirm_password": "correct-password",
            },
        )

    assert response.status_code == 200
    assert b"already exists" in response.data


def test_login_sets_session_and_logout_clears_it():
    app = create_app()
    connection = Mock()
    connection.cursor.return_value.fetchone.return_value = {
        "user_id": 12,
        "name": "Student",
        "email": "student@example.com",
        "password_hash": hash_user_password("correct-password"),
    }

    with (
        patch("services.database.get_db_connection", return_value=connection),
        patch("services.transaction_service.get_holdings", return_value=[]),
    ):
        client = app.test_client()
        login_response = client.post(
            "/login",
            data={"email": "student@example.com", "password": "correct-password"},
        )
        dashboard_response = client.get("/dashboard")
        logout_response = client.get("/logout")
        protected_response = client.get("/dashboard")

    assert login_response.status_code == 302
    assert login_response.headers["Location"].endswith("/dashboard")
    assert dashboard_response.status_code == 200
    assert b"Welcome, Student" in dashboard_response.data
    assert logout_response.status_code == 302
    assert protected_response.headers["Location"].endswith("/login")


def test_stock_and_watchlist_routes_require_login():
    app = create_app()
    client = app.test_client()

    assert client.get("/stocks").headers["Location"].endswith("/login")
    assert client.get("/watchlist").headers["Location"].endswith("/login")
    assert client.post("/watchlist/add/1").headers["Location"].endswith("/login")
    assert client.post("/watchlist/remove/1").headers["Location"].endswith("/login")


def test_stock_explorer_search_uses_database_results():
    app = create_app()
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = [
        {
            "stock_id": 7,
            "symbol": "AAPL",
            "company_name": "Apple Inc.",
            "exchange_name": "NASDAQ",
        }
    ]

    with patch("services.database.get_db_connection", return_value=connection):
        client = client_session(app, user_id=12)
        response = client.get("/stocks?q=Apple")

    assert response.status_code == 200
    assert b"Apple Inc." in response.data
    assert b"AAPL" in response.data


def test_stock_explorer_shows_empty_database_message():
    app = create_app()
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = []

    with patch("services.database.get_db_connection", return_value=connection):
        response = client_session(app, user_id=12).get("/stocks")

    assert response.status_code == 200
    assert b"No stocks available yet" in response.data
    assert b"Add a stock" in response.data


def test_add_stock_uses_parameterized_create_and_redirects_to_transactions():
    app = create_app()
    connection = Mock()

    with (
        patch("services.database.get_db_connection", return_value=connection),
        patch("services.stock_service.create_stock", return_value=True) as create,
    ):
        response = client_session(app, user_id=12).post(
            "/stocks/add",
            data={
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "exchange_name": "NASDAQ",
            },
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/transactions")
    create.assert_called_once_with(connection, "AAPL", "Apple Inc.", "NASDAQ")


def test_add_watchlist_validates_stock_and_uses_current_user():
    app = create_app()
    connection = Mock()
    with (
        patch("services.database.get_db_connection", return_value=connection),
        patch(
            "services.stock_service.find_stock_by_id",
            return_value={
                "stock_id": 7,
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "exchange_name": "NASDAQ",
            },
        ),
        patch("services.stock_service.add_to_watchlist", return_value=True) as add,
    ):
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 12
            session["user_name"] = "Student"
        response = client.post("/watchlist/add/7")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/stocks")
    add.assert_called_once_with(connection, 12, 7)


def test_transactions_route_requires_login():
    app = create_app()

    response = app.test_client().get("/transactions")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_transaction_route_rejects_invalid_quantity_before_database_write():
    app = create_app()
    client = client_session(app, user_id=12)

    with (
        patch("services.database.get_db_connection", return_value=Mock()),
        patch("services.transaction_service.list_stocks", return_value=[]),
        patch(
            "services.transaction_service.get_transaction_history",
            return_value=[],
        ),
        patch("services.transaction_service.record_transaction") as record,
    ):
        response = client.post(
            "/transactions",
            data={
                "submission_token": "unused",
                "transaction_type": "BUY",
                "stock_id": "7",
                "quantity": "0",
                "price_per_share": "10",
                "transaction_date": "2026-11-10",
            },
        )

    assert response.status_code == 200
    record.assert_not_called()


def test_transaction_route_uses_authenticated_user_and_redirects():
    app = create_app()
    client = client_session(app, user_id=12)
    connection = Mock()

    with (
        patch("services.database.get_db_connection", return_value=connection),
        patch("services.transaction_service.list_stocks", return_value=[]),
        patch(
            "services.transaction_service.get_transaction_history",
            return_value=[],
        ),
        patch("services.transaction_service.record_transaction") as record,
    ):
        with client.session_transaction() as session:
            session["transaction_submission_token"] = "valid-token"
        response = client.post(
            "/transactions",
            data={
                "submission_token": "valid-token",
                "transaction_type": "BUY",
                "stock_id": "7",
                "quantity": "2",
                "price_per_share": "10.50",
                "transaction_date": "2026-11-10",
            },
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/transactions")
    record.assert_called_once()
    assert record.call_args.args[1:4] == (12, 7, "BUY")


def test_transaction_form_renders_stock_id_and_readable_label():
    app = create_app()
    connection = Mock()
    stocks = [
        {
            "stock_id": 7,
            "symbol": "AAPL",
            "company_name": "Apple Inc.",
            "exchange_name": "NASDAQ",
        }
    ]

    with (
        patch("services.database.get_db_connection", return_value=connection),
        patch("services.transaction_service.list_stocks", return_value=stocks),
        patch(
            "services.transaction_service.get_transaction_history",
            return_value=[],
        ),
    ):
        response = client_session(app, user_id=12).get("/transactions")

    assert response.status_code == 200
    assert b'<option value="7" data-search="AAPL Apple Inc. NASDAQ">AAPL' in response.data
    assert b"Apple Inc." in response.data
    assert b"NASDAQ" in response.data
    assert b'data-search="AAPL Apple Inc. NASDAQ"' in response.data


def client_session(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["user_name"] = "Student"
    return client
