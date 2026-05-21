from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extensions import connection as PGConnection
from psycopg2.extras import execute_values

from config import PostgresSettings


def quote_pg_identifier(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def qualified_table(schema_name: str, table_name: str) -> str:
    return f"{quote_pg_identifier(schema_name)}.{quote_pg_identifier(table_name)}"


@contextmanager
def postgres_connection(settings: PostgresSettings) -> PGConnection:
    conn = psycopg2.connect(
        host=settings.host,
        port=settings.port,
        dbname=settings.database,
        user=settings.user,
        password=settings.password,
        connect_timeout=30,
    )
    try:
        yield conn
    finally:
        conn.close()


def delete_window(
    conn: PGConnection,
    schema_name: str,
    table_name: str,
    date_column: str,
    start_date: str,
    end_date: str,
) -> int:
    table = qualified_table(schema_name, table_name)
    sql = f"""
        DELETE FROM {table}
        WHERE {quote_pg_identifier(date_column)} >= %s
          AND {quote_pg_identifier(date_column)} < %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (start_date, end_date))
        return cur.rowcount


def insert_rows(
    conn: PGConnection,
    schema_name: str,
    table_name: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> int:
    if not rows:
        return 0

    table = qualified_table(schema_name, table_name)
    quoted_columns = ", ".join(quote_pg_identifier(column) for column in columns)
    sql = f"INSERT INTO {table} ({quoted_columns}) VALUES %s"

    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=len(rows))
    return len(rows)


def mysql_type_to_postgres(column: dict[str, Any]) -> str:
    data_type = str(column["data_type"]).lower()
    numeric_precision = column.get("numeric_precision")
    numeric_scale = column.get("numeric_scale")
    datetime_precision = column.get("datetime_precision")
    char_length = column.get("character_maximum_length")

    if data_type in {"tinyint", "smallint"}:
        return "smallint"
    if data_type in {"mediumint", "int", "integer"}:
        return "integer"
    if data_type == "bigint":
        return "bigint"
    if data_type in {"decimal", "numeric"}:
        if numeric_precision is not None and numeric_scale is not None:
            return f"numeric({numeric_precision},{numeric_scale})"
        return "numeric"
    if data_type in {"float", "double", "real"}:
        return "double precision"
    if data_type == "date":
        return "date"
    if data_type in {"datetime", "timestamp"}:
        if datetime_precision is not None:
            return f"timestamp({datetime_precision})"
        return "timestamp"
    if data_type == "time":
        if datetime_precision is not None:
            return f"time({datetime_precision})"
        return "time"
    if data_type == "year":
        return "integer"
    if data_type in {"varchar", "char"} and char_length and int(char_length) <= 10485760:
        return f"varchar({char_length})"
    if data_type in {"blob", "binary", "varbinary"}:
        return "bytea"
    return "text"


def build_create_table_sql(
    schema_name: str,
    table_name: str,
    columns_metadata: Sequence[dict[str, Any]],
) -> str:
    table = qualified_table(schema_name, table_name)
    lines = [f"CREATE SCHEMA IF NOT EXISTS {quote_pg_identifier(schema_name)};", "", f"CREATE TABLE IF NOT EXISTS {table} ("]
    column_lines = []
    for column in columns_metadata:
        nullable = "" if column.get("is_nullable") == "YES" else " NOT NULL"
        column_lines.append(
            f"    {quote_pg_identifier(column['column_name'])} {mysql_type_to_postgres(column)}{nullable}"
        )
    lines.append(",\n".join(column_lines))
    lines.append(");")
    lines.append("")
    lines.append(
        f"CREATE INDEX IF NOT EXISTS {quote_pg_identifier(f'idx_{table_name}_d_lancamento')}"
        f" ON {table} ({quote_pg_identifier('D. Lançamento')});"
    )
    return "\n".join(lines)


def write_create_table_sql(path: Path, sql: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sql, encoding="utf-8")


def ensure_table(conn: PGConnection, create_sql: str) -> None:
    with conn.cursor() as cur:
        cur.execute(create_sql)
