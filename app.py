import os
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import wraps

import click
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from mysql.connector import IntegrityError

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["DB_HOST"] = os.getenv("DB_HOST", "localhost")
    app.config["DB_USER"] = os.getenv("DB_USER", "root")
    app.config["DB_PASSWORD"] = os.getenv("DB_PASSWORD", "")
    app.config["DB_NAME"] = os.getenv("DB_NAME", "stock_portfolio")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or os.urandom(32)

    def login_required(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped_view

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not name or not email or not password or not confirm_password:
                flash("All fields are required.", "danger")
            elif "@" not in email or "." not in email.rsplit("@", 1)[-1]:
                flash("Enter a valid email address.", "danger")
            elif len(password) < 8:
                flash("Password must be at least 8 characters.", "danger")
            elif password != confirm_password:
                flash("Passwords do not match.", "danger")
            else:
                from services.database import get_db_connection
                from services.user_service import create_user

                connection = get_db_connection()
                try:
                    create_user(connection, email, password, name)
                except IntegrityError:
                    flash("An account with that email already exists.", "danger")
                else:
                    flash("Registration successful. Please log in.", "success")
                    return redirect(url_for("login"))
                finally:
                    connection.close()

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not email or not password:
                flash("Email and password are required.", "danger")
            else:
                from services.database import get_db_connection
                from services.user_service import (
                    find_user_by_email,
                    verify_user_password,
                )

                connection = get_db_connection()
                try:
                    user = find_user_by_email(connection, email)
                finally:
                    connection.close()

                if user and verify_user_password(user["password_hash"], password):
                    session.clear()
                    session["user_id"] = user["user_id"]
                    session["user_name"] = user["name"]
                    return redirect(url_for("dashboard"))
                flash("Invalid email or password.", "danger")

        return render_template("login.html")

    @app.get("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("home"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        from services.database import get_db_connection
        from services.analytics_service import portfolio_analytics
        from services.transaction_service import get_holdings

        connection = get_db_connection()
        try:
            holdings = get_holdings(connection, session["user_id"])
        finally:
            connection.close()
        analytics = portfolio_analytics(holdings)
        return render_template(
            "dashboard.html",
            user_name=session["user_name"],
            holdings=holdings,
            total_cost=analytics["total_invested"],
            total_value=analytics["current_value"],
            unrealized=analytics["unrealized"],
            realized=analytics["realized"],
            analytics=analytics,
        )

    @app.route("/historical-prices", methods=["GET", "POST"])
    @login_required
    def historical_prices():
        from services.analytics_service import (
            calculate_sma,
            import_historical_csv,
            list_historical_prices,
            prepare_chart_data,
        )
        from services.database import get_db_connection
        from services.transaction_service import list_stocks

        selected_stock = request.values.get("stock_id", "").strip()
        start_text = request.values.get("start_date", "").strip()
        end_text = request.values.get("end_date", "").strip()
        error = None
        start_date = end_date = None
        if start_text:
            try:
                start_date = date.fromisoformat(start_text)
            except ValueError:
                error = "Start date must be a valid date."
        if end_text:
            try:
                end_date = date.fromisoformat(end_text)
            except ValueError:
                error = "End date must be a valid date."
        if start_date and end_date and start_date > end_date:
            error = "Start date cannot be after end date."

        if request.method == "POST":
            upload = request.files.get("price_file")
            if upload is None or not upload.filename.lower().endswith(".csv"):
                flash("Choose a CSV file to import.", "danger")
            else:
                connection = get_db_connection()
                try:
                    imported = import_historical_csv(connection, upload.read())
                except ValueError as exc:
                    flash(str(exc), "danger")
                else:
                    flash(f"Imported {imported} historical price record(s).", "success")
                finally:
                    connection.close()

        connection = get_db_connection()
        try:
            stocks = list_stocks(connection)
            prices = []
            if error is None and selected_stock.isdigit():
                prices = list_historical_prices(
                    connection,
                    int(selected_stock),
                    start_date,
                    end_date,
                )
        finally:
            connection.close()
        if error:
            flash(error, "danger")
        chart_data = prepare_chart_data(prices)
        return render_template(
            "historical_prices.html",
            stocks=stocks,
            prices=prices,
            chart_data=chart_data,
            selected_stock=selected_stock,
            start_date=start_text,
            end_date=end_text,
            sma20=calculate_sma(prices, 20),
            sma50=calculate_sma(prices, 50),
        )

    @app.get("/analytics")
    @login_required
    def analytics():
        from services.analytics_service import portfolio_analytics
        from services.database import get_db_connection
        from services.transaction_service import get_holdings

        connection = get_db_connection()
        try:
            holdings = get_holdings(connection, session["user_id"])
        finally:
            connection.close()
        return render_template(
            "analytics.html",
            analytics=portfolio_analytics(holdings),
            holdings=holdings,
        )

    @app.route("/transactions", methods=["GET", "POST"])
    @login_required
    def transactions():
        from services.database import get_db_connection
        from services.transaction_service import (
            get_transaction_history,
            list_stocks,
            new_submission_token,
            record_transaction,
        )

        if "transaction_submission_token" not in session:
            session["transaction_submission_token"] = new_submission_token()

        if request.method == "POST":
            submitted_token = request.form.get("submission_token", "")
            transaction_type = request.form.get("transaction_type", "").upper()
            stock_id_text = request.form.get("stock_id", "")
            quantity_text = request.form.get("quantity", "").strip()
            price_text = request.form.get("price_per_share", "").strip()
            transaction_date_text = request.form.get("transaction_date", "").strip()

            if submitted_token != session.get("transaction_submission_token"):
                flash("This transaction form has already been submitted.", "warning")
            else:
                error = None
                try:
                    stock_id = int(stock_id_text)
                    quantity = Decimal(quantity_text)
                    price = Decimal(price_text)
                    transaction_date = date.fromisoformat(transaction_date_text)
                except (InvalidOperation, TypeError, ValueError):
                    error = "Enter a valid stock, quantity, price, and date."

                if error is None and transaction_type not in {"BUY", "SELL"}:
                    error = "Choose either Buy or Sell."
                elif error is None and (
                    not quantity.is_finite()
                    or not price.is_finite()
                    or quantity <= 0
                    or price <= 0
                ):
                    error = "Quantity and price must both be greater than zero."

                if error:
                    flash(error, "danger")
                else:
                    connection = get_db_connection()
                    try:
                        record_transaction(
                            connection,
                            session["user_id"],
                            stock_id,
                            transaction_type,
                            quantity,
                            price,
                            transaction_date,
                        )
                    except ValueError as exc:
                        flash(str(exc), "danger")
                    else:
                        session.pop("transaction_submission_token", None)
                        flash("Transaction recorded successfully.", "success")
                        return redirect(url_for("transactions"))
                    finally:
                        connection.close()

        connection = get_db_connection()
        try:
            stocks = list_stocks(connection)
            filters = {}
            stock_filter = request.args.get("stock_id", "").strip()
            type_filter = request.args.get("transaction_type", "").upper()
            date_filter = request.args.get("transaction_date", "").strip()
            if stock_filter.isdigit():
                filters["stock_id"] = int(stock_filter)
            if type_filter in {"BUY", "SELL"}:
                filters["transaction_type"] = type_filter
            if date_filter:
                try:
                    filters["transaction_date"] = date.fromisoformat(date_filter)
                except ValueError:
                    flash("The history date filter is invalid.", "danger")
            history = get_transaction_history(
                connection,
                session["user_id"],
                filters,
            )
        finally:
            connection.close()
        return render_template(
            "transactions.html",
            stocks=stocks,
            history=history,
            today=date.today().isoformat(),
            filters=request.args,
            submission_token=session["transaction_submission_token"],
        )

    @app.get("/stocks")
    @login_required
    def stock_explorer():
        from services.database import get_db_connection
        from services.stock_service import search_stocks

        search_term = request.args.get("q", "").strip()
        stocks = []
        if len(search_term) > 100:
            flash("Search text must be 100 characters or fewer.", "danger")
        else:
            connection = get_db_connection()
            try:
                stocks = search_stocks(connection, search_term)
            finally:
                connection.close()
        return render_template(
            "stocks.html",
            stocks=stocks,
            search_term=search_term,
            has_searched=bool(search_term),
        )

    @app.post("/stocks/add")
    @login_required
    def add_stock():
        from services.database import get_db_connection
        from services.stock_service import create_stock

        symbol = request.form.get("symbol", "").strip().upper()
        company_name = request.form.get("company_name", "").strip()
        exchange_name = request.form.get("exchange_name", "").strip().upper()

        if (
            not symbol
            or not company_name
            or not exchange_name
            or len(symbol) > 20
            or len(company_name) > 255
            or len(exchange_name) > 100
            or not symbol.replace(".", "").replace("-", "").isalnum()
        ):
            flash("Enter a valid symbol, company name, and exchange.", "danger")
            return redirect(url_for("stock_explorer"))

        connection = get_db_connection()
        try:
            if create_stock(connection, symbol, company_name, exchange_name):
                flash(f"{symbol} was added to the stock database.", "success")
            else:
                flash(f"{symbol} already exists in the stock database.", "warning")
        finally:
            connection.close()
        return redirect(url_for("transactions"))

    @app.get("/watchlist")
    @login_required
    def watchlist():
        from services.database import get_db_connection
        from services.stock_service import get_user_watchlist

        connection = get_db_connection()
        try:
            entries = get_user_watchlist(connection, session["user_id"])
        finally:
            connection.close()
        return render_template("watchlist.html", entries=entries)

    @app.post("/watchlist/add/<int:stock_id>")
    @login_required
    def add_watchlist(stock_id: int):
        from services.database import get_db_connection
        from services.stock_service import add_to_watchlist, find_stock_by_id

        connection = get_db_connection()
        try:
            stock = find_stock_by_id(connection, stock_id)
            if stock is None:
                flash("That stock could not be found.", "danger")
            elif add_to_watchlist(connection, session["user_id"], stock_id):
                flash(f"{stock['symbol']} was added to your watchlist.", "success")
            else:
                flash(f"{stock['symbol']} is already on your watchlist.", "warning")
        finally:
            connection.close()
        return redirect(url_for("stock_explorer"))

    @app.post("/watchlist/remove/<int:stock_id>")
    @login_required
    def remove_watchlist(stock_id: int):
        from services.database import get_db_connection
        from services.stock_service import remove_from_watchlist

        connection = get_db_connection()
        try:
            removed = remove_from_watchlist(
                connection,
                session["user_id"],
                stock_id,
            )
        finally:
            connection.close()
        if removed:
            flash("Stock removed from your watchlist.", "success")
        else:
            flash("That stock was not in your watchlist.", "warning")
        return redirect(url_for("watchlist"))

    @app.cli.command("test-db")
    def test_db():
        """Check the configured MySQL connection."""
        from services.database import test_database_connection

        try:
            if test_database_connection():
                click.echo("MySQL connection successful.")
            else:
                raise click.ClickException(
                    "MySQL responded, but the connection test query failed."
                )
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
