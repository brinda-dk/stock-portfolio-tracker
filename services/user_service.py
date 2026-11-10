from mysql.connector import MySQLConnection
from werkzeug.security import check_password_hash, generate_password_hash


def hash_user_password(password: str) -> str:
    """Return a secure one-way hash suitable for storing in MySQL."""
    return generate_password_hash(password)


def verify_user_password(password_hash: str, password: str) -> bool:
    """Check a plain-text password against a stored hash."""
    return check_password_hash(password_hash, password)


def create_user(
    connection: MySQLConnection,
    email: str,
    password: str,
    name: str,
) -> int:
    """Insert a user with a hashed password using a parameterized query."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (name, email, password_hash)
            VALUES (%s, %s, %s)
            """,
            (name, email, hash_user_password(password)),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        cursor.close()


def find_user_by_email(connection: MySQLConnection, email: str):
    """Find one user by email using a parameterized query."""
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT user_id, name, email, password_hash
            FROM users
            WHERE email = %s
            """,
            (email,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
