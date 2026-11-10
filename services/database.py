from collections.abc import Generator
from contextlib import contextmanager

import mysql.connector
from flask import current_app
from mysql.connector import Error


def get_db_connection():
    """Create a MySQL connection using the current Flask configuration."""
    try:
        return mysql.connector.connect(
            host=current_app.config["DB_HOST"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
            database=current_app.config["DB_NAME"],
        )
    except Error as exc:
        raise RuntimeError(
            "MySQL connection failed. Check that MySQL Server is running and "
            "that DB_HOST, DB_USER, DB_PASSWORD, and DB_NAME in .env are correct."
        ) from exc


def test_database_connection() -> bool:
    """Run a small query to verify that the configured database is reachable."""
    connection = get_db_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        return cursor.fetchone() == (1,)
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


@contextmanager
def connection_scope() -> Generator:
    """Yield a connection and always close it after use."""
    connection = get_db_connection()
    try:
        yield connection
    finally:
        connection.close()
