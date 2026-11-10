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

    with patch("services.database.get_db_connection", return_value=connection):
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


def client_session(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["user_name"] = "Student"
    return client
