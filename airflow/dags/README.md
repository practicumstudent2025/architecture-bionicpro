# Airflow DAGs

## reports_etl_dag.py

ETL-процесс для подготовки витрины отчётности протезов.

### Расписание
- Запуск: ежедневно в 02:00 UTC
- Интервал: `0 2 * * *`

### Задачи

1. **extract_telemetry** - Извлечение данных телеметрии из PostgreSQL
   - Источник: таблица `telemetry_data`
   - Период: последние 24 часа (инкрементальная загрузка)

2. **extract_crm** - Извлечение данных клиентов из CRM DB
   - Источник: тестовые данные (для демонстрации)
   - Данные: пользователи, протезы, заказы
   - В продакшене: подключение к реальной CRM БД

3. **transform_and_merge** - Объединение и трансформация данных
   - Объединение по `user_id` и `prosthesis_id`
   - Агрегация метрик
   - Расчёт производных показателей

4. **load_to_clickhouse** - Загрузка в витрину ClickHouse
   - Таблица: `prosthesis_usage_reports`
   - Формат: upsert (замена существующих записей)

### Настройка подключений

В Airflow UI необходимо настроить connections:
- `postgres_default` - PostgreSQL для телеметрии

**Примечание**: CRM данные используют тестовые значения (hardcoded в DAG).
В продакшене можно добавить connection для реальной CRM БД.

### Зависимости

Установлены через `requirements.txt`:
- apache-airflow
- apache-airflow-providers-postgres
- clickhouse-driver
- pandas
