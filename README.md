# BionicPRO - Архитектурные решения

## Задача 1: Управление учётными данными

### Компоненты
- **BFF Service** — токены IdP не передаются фронтенду, только session cookies
- **Identity Provider Gateway** — унификация доступа к IdP (Keycloak, Azure AD, AWS Cognito)
- **Token Service** — хранение и управление токенами (AES-256)
- **Local Identity Store** — локальное хранение учётных записей (PostgreSQL)
- **Regional IdP** — региональные провайдеры по странам

### Поток аутентификации
Пользователь → Frontend → BFF → IdP Gateway → Regional IdP → BFF → Token Service → Session cookie

**Безопасность**: токены IdP только на бэкенде, фронтенд получает session cookies.

**Диаграмма**: `architecture-identity-management.drawio`

## Задача 2: PKCE для безопасности

### Изменения
- **Frontend**: `pkceMethod: 'S256'` в App.tsx
- **Keycloak**: PKCE включён, небезопасные flows отключены

### Как работает
1. Клиент генерирует code_verifier
2. Создаёт code_challenge = SHA-256(code_verifier)
3. Отправляет code_challenge в Keycloak
4. Получает authorization code
5. Обменивает code + code_verifier на токены

**Безопасность**: защита от перехвата authorization code.

## Задача 3: Сервис отчётов

### Компоненты
- **Frontend Web** (React) — просмотр и скачивание отчётов (PDF/CSV)
- **Reports API** (SpringBoot) — генерация отчётов, RBAC контроль доступа
- **ClickHouse** (OLAP) — витрина отчётности
- **Apache Airflow** — ETL-процесс (ежедневно в 02:00 UTC)
- **PostgreSQL** — телеметрия протезов
- **CRM DB** — данные пользователей и протезов (тестовые данные для демонстрации)

### ETL-процесс
1. **Extract**: данные из PostgreSQL и CRM DB
2. **Transform**: объединение по user_id/prosthesis_id, агрегация, расчёт метрик
3. **Load**: загрузка в ClickHouse (upsert)

### Поток запроса отчёта
Пользователь → Frontend → Reports API → BFF (RBAC) → ClickHouse → Форматирование → PDF/CSV

**Безопасность**: пользователь видит только свои отчёты (фильтрация по user_id).

**Диаграмма**: `architecture-reports-service.drawio`

## Реализация ETL

### Airflow DAG
**Файл**: `airflow/dags/reports_etl_dag.py`
- **Расписание**: ежедневно в 02:00 UTC (`0 2 * * *`)
- **Задачи**:
  1. `extract_telemetry` — извлечение из PostgreSQL
  2. `extract_crm` — извлечение из CRM DB
  3. `transform_and_merge` — объединение и трансформация
  4. `load_to_clickhouse` — загрузка в витрину

### Витрина ClickHouse
**Файл**: `clickhouse/init.sql`
- **Таблица**: `prosthesis_usage_reports` (партиционирование по дате)
- **Материализованное представление**: `daily_prosthesis_reports`
- **Оптимизация**: ORDER BY (user_id, prosthesis_id, report_date) для быстрого доступа

### Настройка и запуск

#### 1. Инициализация Airflow
```bash
docker-compose run --rm airflow-webserver airflow users create \
    --username admin --firstname Admin --lastname User \
    --role Admin --email admin@example.com --password admin
```

#### 2. Настройка подключений в Airflow UI
Откройте http://localhost:8081 и настройте connections:

**postgres_default** (PostgreSQL для телеметрии):
- Host: `postgres_telemetry`, Port: `5432`, Schema: `telemetry_db`
- Login: `telemetry_user`, Password: `telemetry_password`

**Примечание**: Для демонстрации CRM данные используются тестовые (hardcoded в DAG).
В продакшене можно добавить подключение к реальной CRM БД через Airflow connections.

#### 3. Запуск DAG
1. Откройте Airflow UI: http://localhost:8081
2. Найдите DAG `reports_etl_dag`
3. Включите DAG (переключите тумблер)
4. DAG будет запускаться ежедневно в 02:00 UTC

#### 4. Проверка данных в ClickHouse
```bash
docker-compose exec clickhouse clickhouse-client
USE reports_warehouse;
SELECT * FROM prosthesis_usage_reports LIMIT 10;
```

### Расписание и мониторинг
- **Интервал**: Ежедневно в 02:00 UTC
- **Инкрементальная загрузка**: данные за последние 24 часа
- **Логи**: Airflow UI → DAG → Task Instance → Log
- **Метрики**: Airflow UI → Admin → Metrics

## Reports API (Задача 3)

### Реализация
**Файл**: `reports-api/app/main.py`
- **Framework**: FastAPI (Python)
- **Endpoints**:
  - `GET /health` - проверка здоровья API
  - `GET /reports` - получение отчётов (с фильтрацией по датам и протезу)
  - `GET /reports/summary` - сводная статистика (использует материализованное представление)

### Особенности
- **RBAC**: фильтрация по `user_id` - пользователь видит только свои данные
- **Быстрый доступ**: запросы к предварительно агрегированным данным в ClickHouse
- **Аутентификация**: через заголовок `Authorization: Bearer <token>`
- **Сводная статистика**: автоматический расчёт метрик (движения, батарея, использование)

### Запуск
```bash
# Через docker-compose
docker-compose up reports-api

# API доступен на http://localhost:8000
# Документация: http://localhost:8000/docs
```

### Пример запроса
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/reports?date_from=2024-01-01&date_to=2024-01-31"
```
