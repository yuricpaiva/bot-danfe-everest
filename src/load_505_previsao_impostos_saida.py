from __future__ import annotations

import argparse
import logging
import sys
import time

from config import ROOT_DIR, get_settings
from db_mysql import get_table_columns, get_table_columns_metadata, iter_rows_by_date_window, mysql_connection
from db_postgres import (
    build_create_table_sql,
    delete_window,
    ensure_table,
    insert_rows,
    postgres_connection,
    write_create_table_sql,
)
from telegram_notifier import TelegramNotifier


LOGGER = logging.getLogger("load_505_previsao_impostos_saida")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sincroniza a tabela MySQL 505_previsao_impostos_saida para PostgreSQL por janela de data."
    )
    parser.add_argument("--data-inicio", required=True, help="Inicio da janela, inclusivo. Ex: 2025-01-01")
    parser.add_argument("--data-fim", required=True, help="Fim da janela, exclusivo. Ex: 2025-02-01")
    parser.add_argument("--create-table", action="store_true", help="Cria a tabela destino antes da carga.")
    parser.add_argument(
        "--write-create-sql",
        action="store_true",
        help="Atualiza sql/create_tb_505_previsao_impostos_saida.sql usando a estrutura lida do MySQL.",
    )
    return parser.parse_args()


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def refresh_window(start_date: str, end_date: str, create_table: bool, write_create_sql: bool) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    telegram = TelegramNotifier(settings.telegram)

    started_at = time.perf_counter()
    total_inserted = 0
    deleted = 0
    sql_path = ROOT_DIR / "sql" / "create_tb_505_previsao_impostos_saida.sql"

    LOGGER.info("Iniciando refresh da janela [%s, %s)", start_date, end_date)
    LOGGER.info("Origem MySQL: %s.%s", settings.mysql.database, settings.mysql.source_table)
    LOGGER.info("Destino PostgreSQL: %s.%s", settings.postgres.schema_name, settings.postgres.table_name)

    try:
        with mysql_connection(settings.mysql) as mysql_conn:
            columns = get_table_columns(mysql_conn, settings.mysql.database, settings.mysql.source_table)
            if settings.mysql.date_column not in columns:
                raise RuntimeError(f"Coluna de data nao encontrada na origem: {settings.mysql.date_column}")

            if create_table or write_create_sql:
                metadata = get_table_columns_metadata(mysql_conn, settings.mysql.database, settings.mysql.source_table)
                create_sql = build_create_table_sql(settings.postgres.schema_name, settings.postgres.table_name, metadata)
                if write_create_sql:
                    write_create_table_sql(sql_path, create_sql)
                    LOGGER.info("SQL de criacao atualizado em %s", sql_path)
                    if not create_table:
                        elapsed = time.perf_counter() - started_at
                        LOGGER.info("Encerrando apos gerar o DDL. Use --create-table para criar e carregar a janela.")
                        telegram.send(
                            "\n".join(
                                [
                                    "[SUCESSO] DDL gerado",
                                    f"Origem: {settings.mysql.database}.{settings.mysql.source_table}",
                                    f"Destino: {settings.postgres.schema_name}.{settings.postgres.table_name}",
                                    f"Arquivo: {sql_path}",
                                    "Linhas adicionadas: 0",
                                    f"Tempo: {elapsed:.2f}s",
                                ]
                            )
                        )
                        return
            else:
                create_sql = None

            with postgres_connection(settings.postgres) as pg_conn:
                try:
                    if create_table and create_sql:
                        ensure_table(pg_conn, create_sql)
                        LOGGER.info("Tabela destino verificada/criada")

                    deleted = delete_window(
                        pg_conn,
                        settings.postgres.schema_name,
                        settings.postgres.table_name,
                        settings.mysql.date_column,
                        start_date,
                        end_date,
                    )
                    LOGGER.info("Registros apagados no PostgreSQL para a janela: %s", deleted)

                    for rows in iter_rows_by_date_window(
                        mysql_conn,
                        settings.mysql.source_table,
                        columns,
                        settings.mysql.date_column,
                        start_date,
                        end_date,
                        settings.chunk_size,
                    ):
                        inserted = insert_rows(
                            pg_conn,
                            settings.postgres.schema_name,
                            settings.postgres.table_name,
                            columns,
                            rows,
                        )
                        total_inserted += inserted
                        LOGGER.info("Chunk inserido: %s linhas; acumulado: %s", inserted, total_inserted)

                    pg_conn.commit()
                except Exception:
                    pg_conn.rollback()
                    LOGGER.exception("Rollback executado no PostgreSQL.")
                    raise
    except Exception as exc:
        elapsed = time.perf_counter() - started_at
        LOGGER.exception("Falha na carga.")
        telegram.send(
            "\n".join(
                [
                    "[FALHA] Refresh 505_previsao_impostos_saida",
                    f"Origem: {settings.mysql.database}.{settings.mysql.source_table}",
                    f"Destino: {settings.postgres.schema_name}.{settings.postgres.table_name}",
                    f"Janela: [{start_date}, {end_date})",
                    f"Linhas adicionadas antes da falha: {total_inserted}",
                    f"Motivo: {type(exc).__name__}: {exc}",
                    f"Tempo ate a falha: {elapsed:.2f}s",
                ]
            )
        )
        raise

    elapsed = time.perf_counter() - started_at
    LOGGER.info("Refresh concluido. Linhas inseridas: %s. Tempo: %.2fs", total_inserted, elapsed)
    telegram.send(
        "\n".join(
            [
                "[SUCESSO] Refresh 505_previsao_impostos_saida",
                f"Origem: {settings.mysql.database}.{settings.mysql.source_table}",
                f"Destino: {settings.postgres.schema_name}.{settings.postgres.table_name}",
                f"Janela: [{start_date}, {end_date})",
                f"Registros apagados no destino: {deleted}",
                f"Linhas adicionadas: {total_inserted}",
                f"Tempo: {elapsed:.2f}s",
            ]
        )
    )


def main() -> None:
    args = parse_args()
    refresh_window(args.data_inicio, args.data_fim, args.create_table, args.write_create_sql)


if __name__ == "__main__":
    main()
