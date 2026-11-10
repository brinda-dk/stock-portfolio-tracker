import os
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
        return render_template("dashboard.html", user_name=session["user_name"])

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
