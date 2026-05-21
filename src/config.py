from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def _required(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in (None, "") else int(value)


def _optional(name: str) -> str | None:
    value = os.getenv(name)
    return None if value in (None, "") else value


@dataclass(frozen=True)
class MySQLSettings:
    host: str
    port: int
    database: str
    user: str
    password: str
    charset: str
    source_table: str
    date_column: str


@dataclass(frozen=True)
class PostgresSettings:
    host: str
    port: int
    database: str
    user: str
    password: str
    schema_name: str
    table_name: str


@dataclass(frozen=True)
class TelegramSettings:
    token: str | None
    chat_id: str | None


@dataclass(frozen=True)
class Settings:
    mysql: MySQLSettings
    postgres: PostgresSettings
    telegram: TelegramSettings
    chunk_size: int
    log_level: str


def get_settings() -> Settings:
    return Settings(
        mysql=MySQLSettings(
            host=_required("MYSQL_HOST"),
            port=_int_env("MYSQL_PORT", 3306),
            database=_required("MYSQL_DATABASE"),
            user=_required("MYSQL_USER"),
            password=_required("MYSQL_PASSWORD"),
            charset=os.getenv("MYSQL_CHARSET", "latin1"),
            source_table=os.getenv("MYSQL_SOURCE_TABLE", "505_previsao_impostos_saida"),
            date_column=os.getenv("DATE_COLUMN", "D. Lançamento"),
        ),
        postgres=PostgresSettings(
            host=_required("POSTGRES_HOST"),
            port=_int_env("POSTGRES_PORT", 5438),
            database=_required("POSTGRES_DATABASE"),
            user=_required("POSTGRES_USER"),
            password=_required("POSTGRES_PASSWORD"),
            schema_name=os.getenv("POSTGRES_SCHEMA", "raw"),
            table_name=os.getenv("POSTGRES_TABLE", "tb_505_previsao_impostos_saida"),
        ),
        telegram=TelegramSettings(
            token=_optional("TELEGRAM_TOKEN"),
            chat_id=_optional("TELEGRAM_CHAT_ID"),
        ),
        chunk_size=_int_env("CHUNK_SIZE", 5000),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
