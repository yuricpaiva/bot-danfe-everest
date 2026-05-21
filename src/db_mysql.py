from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import SSCursor

from config import MySQLSettings


def quote_mysql_identifier(identifier: str, escape_percent: bool = False) -> str:
    quoted = identifier.replace("`", "``")
    if escape_percent:
        quoted = quoted.replace("%", "%%")
    return f"`{quoted}`"


@contextmanager
def mysql_connection(settings: MySQLSettings) -> Iterator[Connection]:
    conn = pymysql.connect(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        database=settings.database,
        charset=settings.charset,
        cursorclass=SSCursor,
        autocommit=True,
        read_timeout=3600,
        write_timeout=3600,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SET SESSION TRANSACTION READ ONLY")
        yield conn
    finally:
        conn.close()


def get_table_columns(conn: Connection, database: str, table_name: str) -> list[str]:
    sql = """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
    """
    with conn.cursor() as cur:
        cur.execute(sql, (database, table_name))
        return [row[0] for row in cur.fetchall()]


def get_table_columns_metadata(conn: Connection, database: str, table_name: str) -> list[dict[str, Any]]:
    sql = """
        SELECT
            COLUMN_NAME,
            DATA_TYPE,
            COLUMN_TYPE,
            IS_NULLABLE,
            NUMERIC_PRECISION,
            NUMERIC_SCALE,
            DATETIME_PRECISION,
            CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
    """
    with conn.cursor() as cur:
        cur.execute(sql, (database, table_name))
        rows = cur.fetchall()

    keys = [
        "column_name",
        "data_type",
        "column_type",
        "is_nullable",
        "numeric_precision",
        "numeric_scale",
        "datetime_precision",
        "character_maximum_length",
    ]
    return [dict(zip(keys, row)) for row in rows]


def iter_rows_by_date_window(
    conn: Connection,
    table_name: str,
    columns: Sequence[str],
    date_column: str,
    start_date: str,
    end_date: str,
    chunk_size: int,
) -> Iterator[list[tuple[Any, ...]]]:
    quoted_columns = ", ".join(quote_mysql_identifier(column, escape_percent=True) for column in columns)
    sql = f"""
        SELECT {quoted_columns}
        FROM {quote_mysql_identifier(table_name, escape_percent=True)}
        WHERE {quote_mysql_identifier(date_column, escape_percent=True)} >= %s
          AND {quote_mysql_identifier(date_column, escape_percent=True)} < %s
        ORDER BY {quote_mysql_identifier(date_column, escape_percent=True)}
    """
    with conn.cursor() as cur:
        cur.execute(sql, (start_date, end_date))
        while True:
            rows = cur.fetchmany(chunk_size)
            if not rows:
                break
            yield rows
