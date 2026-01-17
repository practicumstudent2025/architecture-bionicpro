# Настройка ETL-процесса с Airflow

## Обзор

ETL-процесс объединяет данные телеметрии из PostgreSQL и данные клиентов из CRM DB, загружая их в витрину отчётности ClickHouse.

## Структура витрины

### Таблица `prosthesis_usage_reports`

Основная таблица витрины с партиционированием по дате:
- `user_id`, `prosthesis_id` - идентификаторы
- `report_date`, `report_hour` - временные метки
- Данные телеметрии (движения, батарея, датчики)
- Данные из CRM (имя, email, модель протеза)
- Агрегированные метрики

### Материализованное представление `daily_prosthesis_reports`

Ежедневные агрегаты для быстрых отчётов.

## Запуск

### 1. Инициализация Airflow

```bash
# Создание пользователя Airflow
docker-compose run --rm airflow-webserver airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin
```

### 2. Настройка подключений в Airflow UI

Откройте http://localhost:8081 и настройте connections:

**postgres_default** (PostgreSQL для телеметрии):
- Host: `postgres_telemetry`
- Port: `5432`
- Schema: `telemetry_db`
- Login: `telemetry_user`
- Password: `telemetry_password`

**oracle_crm** (Oracle для CRM):
- Host: `oracle_crm` (или реальный хост)
- Port: `1521`
- Schema: `crm_schema`
- Login: `crm_user`
- Password: `crm_password`

### 3. Запуск DAG

1. Откройте Airflow UI: http://localhost:8081
2. Найдите DAG `reports_etl_dag`
3. Включите DAG (переключите тумблер)
4. DAG будет запускаться ежедневно в 02:00 UTC

### 4. Проверка данных в ClickHouse

```bash
# Подключение к ClickHouse
docker-compose exec clickhouse clickhouse-client

# Проверка данных
USE reports_warehouse;
SELECT * FROM prosthesis_usage_reports LIMIT 10;
SELECT COUNT(*) FROM prosthesis_usage_reports;
```

## Расписание

- **Интервал**: Ежедневно в 02:00 UTC
- **Cron**: `0 2 * * *`
- **Инкрементальная загрузка**: Загружаются данные за последние 24 часа

## Мониторинг

- Логи задач: Airflow UI → DAG → Task Instance → Log
- Метрики: Airflow UI → Admin → Metrics
- Уведомления: Настроены email уведомления при ошибках

## Структура ETL

1. **extract_telemetry** - Извлечение из PostgreSQL
2. **extract_crm** - Извлечение из CRM DB
3. **transform_and_merge** - Объединение и трансформация
4. **load_to_clickhouse** - Загрузка в витрину
