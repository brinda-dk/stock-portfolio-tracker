from mysql.connector import IntegrityError, MySQLConnection


def search_stocks(connection: MySQLConnection, search_term: str):
    """Return stocks matching a symbol or company name."""
    cursor = connection.cursor(dictionary=True)
    try:
        pattern = f"%{search_term}%"
        cursor.execute(
            """
            SELECT stock_id, symbol, company_name, exchange_name
            FROM stocks
            WHERE symbol LIKE %s OR company_name LIKE %s
            ORDER BY symbol
            """,
            (pattern, pattern),
        )
        return cursor.fetchall()
    finally:
        cursor.close()


def find_stock_by_id(connection: MySQLConnection, stock_id: int):
    """Return one stock by its validated numeric identifier."""
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT stock_id, symbol, company_name, exchange_name
            FROM stocks
            WHERE stock_id = %s
            """,
            (stock_id,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()


def get_user_watchlist(connection: MySQLConnection, user_id: int):
    """Return only the authenticated user's watchlist entries."""
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT w.watchlist_id, w.added_at,
                   s.stock_id, s.symbol, s.company_name, s.exchange_name
            FROM watchlists AS w
            INNER JOIN stocks AS s ON s.stock_id = w.stock_id
            WHERE w.user_id = %s
            ORDER BY w.added_at DESC, s.symbol
            """,
            (user_id,),
        )
        return cursor.fetchall()
    finally:
        cursor.close()


def add_to_watchlist(
    connection: MySQLConnection,
    user_id: int,
    stock_id: int,
) -> bool:
    """Add a stock for one user; return False when it is already saved."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO watchlists (user_id, stock_id)
            VALUES (%s, %s)
            """,
            (user_id, stock_id),
        )
        connection.commit()
        return True
    except IntegrityError:
        connection.rollback()
        return False
    finally:
        cursor.close()


def remove_from_watchlist(
    connection: MySQLConnection,
    user_id: int,
    stock_id: int,
) -> bool:
    """Remove a stock only when it belongs to the authenticated user."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            DELETE FROM watchlists
            WHERE user_id = %s AND stock_id = %s
            """,
            (user_id, stock_id),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
