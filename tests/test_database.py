from unittest.mock import Mock

from services.user_service import (
    create_user,
    hash_user_password,
    verify_user_password,
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
