"""
Подключение к ClickHouse через HTTP интерфейс
Используется httpx для обхода проблем с аутентификацией в native протоколе
"""

import httpx
import os
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Параметры подключения к ClickHouse
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_HTTP_PORT = int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123"))
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "reports_warehouse")


class ClickHouseHTTPClient:
    """
    Обёртка для работы с ClickHouse через HTTP интерфейс
    Эмулирует интерфейс clickhouse_driver.Client для совместимости
    """
    def __init__(self, host: str, port: int, database: str):
        self.base_url = f"http://{host}:{port}"
        self.database = database
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def execute(self, query: str) -> List[Tuple]:
        """
        Выполнение SQL запроса к ClickHouse через HTTP интерфейс
        Возвращает список кортежей (как clickhouse_driver.Client.execute)
        """
        try:
            # Используем синхронный httpx для совместимости с FastAPI
            import httpx as sync_httpx
            with sync_httpx.Client(timeout=30.0) as client:
                url = f"{self.base_url}?database={self.database}"
                response = client.post(url, content=query)
                response.raise_for_status()
                # Парсим TSV ответ от ClickHouse
                text = response.text.strip()
                if not text:
                    return []
                lines = text.split('\n')
                result = []
                for line in lines:
                    if line.strip():
                        values = line.split('\t')
                        # Преобразуем типы: пытаемся int, затем float, иначе строка
                        converted = []
                        for v in values:
                            v = v.strip()
                            try:
                                # Пробуем int
                                converted.append(int(v))
                            except ValueError:
                                try:
                                    # Пробуем float
                                    converted.append(float(v))
                                except ValueError:
                                    # Оставляем как строку
                                    converted.append(v)
                        result.append(tuple(converted))
                return result
        except Exception as e:
            logger.error(f"ClickHouse HTTP query failed: {e}, query: {query[:100]}")
            raise
    
    async def _execute_async(self, query: str) -> List[Tuple]:
        """Асинхронное выполнение запроса"""
        url = f"{self.base_url}?database={self.database}"
        response = await self.client.post(url, content=query)
        response.raise_for_status()
        lines = response.text.strip().split('\n')
        if not lines or lines == ['']:
            return []
        result = []
        for line in lines:
            if line.strip():
                values = line.split('\t')
                converted = []
                for v in values:
                    try:
                        if '.' in v:
                            converted.append(float(v))
                        else:
                            converted.append(int(v))
                    except ValueError:
                        converted.append(v)
                result.append(tuple(converted))
        return result


def get_clickhouse_client():
    """
    Создание подключения к ClickHouse через HTTP интерфейс
    Используется как dependency в FastAPI
    
    Использует HTTP интерфейс (порт 8123) вместо native протокола (9000)
    для обхода проблем с аутентификацией
    """
    try:
        client = ClickHouseHTTPClient(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_HTTP_PORT,
            database=CLICKHOUSE_DB
        )
        return client
    except Exception as e:
        logger.error(f"Failed to create ClickHouse HTTP client: {e}")
        raise
