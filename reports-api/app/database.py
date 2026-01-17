"""
Подключение к ClickHouse
"""

from clickhouse_driver import Client
import os
import logging

logger = logging.getLogger(__name__)

# Параметры подключения к ClickHouse
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "9000"))
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "reports_warehouse")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")


def get_clickhouse_client() -> Client:
    """
    Создание подключения к ClickHouse
    Используется как dependency в FastAPI
    """
    try:
        client = Client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            database=CLICKHOUSE_DB,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD
        )
        return client
    except Exception as e:
        logger.error(f"Failed to connect to ClickHouse: {e}")
        raise
