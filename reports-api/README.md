# Reports API

FastAPI приложение для получения отчётов о работе протезов из витрины ClickHouse.

## Endpoints

### GET /health
Проверка здоровья API и подключения к ClickHouse.

### GET /reports
Получение отчётов о работе протезов.

**Параметры запроса:**
- `date_from` (опционально) - начальная дата (по умолчанию - последние 30 дней)
- `date_to` (опционально) - конечная дата (по умолчанию - сегодня)
- `prosthesis_id` (опционально) - фильтр по конкретному протезу

**Заголовки:**
- `Authorization: Bearer <token>` - токен аутентификации

**Ответ:**
```json
{
  "user_id": 1,
  "total_records": 100,
  "date_from": "2024-01-01",
  "date_to": "2024-01-31",
  "reports": [...],
  "summary": {
    "total_movements": 5000,
    "total_usage_hours": 120.5,
    "avg_battery_level": 75.2,
    "prostheses_count": 2,
    "days_covered": 30
  }
}
```

### GET /reports/summary
Получение сводной статистики (использует материализованное представление).

**Параметры запроса:**
- `date_from` (опционально)
- `date_to` (опционально)

**Заголовки:**
- `Authorization: Bearer <token>`

## Безопасность

- RBAC: пользователь видит только свои отчёты (фильтрация по `user_id`)
- Аутентификация через BFF Service
- Все запросы требуют валидный токен

## Запуск

```bash
# Через docker-compose
docker-compose up reports-api

# Или локально
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Переменные окружения

- `CLICKHOUSE_HOST` - хост ClickHouse (по умолчанию: clickhouse)
- `CLICKHOUSE_PORT` - порт ClickHouse (по умолчанию: 9000)
- `CLICKHOUSE_DB` - база данных (по умолчанию: reports_warehouse)
- `BFF_SERVICE_URL` - URL BFF Service для валидации токенов
