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
- **CRM DB** (Oracle) — данные пользователей и протезов

### ETL-процесс
1. **Extract**: данные из PostgreSQL и CRM DB
2. **Transform**: объединение по user_id/prosthesis_id, агрегация, расчёт метрик
3. **Load**: загрузка в ClickHouse (upsert)

### Поток запроса отчёта
Пользователь → Frontend → Reports API → BFF (RBAC) → ClickHouse → Форматирование → PDF/CSV

**Безопасность**: пользователь видит только свои отчёты (фильтрация по user_id).

**Диаграмма**: `architecture-reports-service.drawio`

### Реализация ETL (Задача 2)

**Airflow DAG**: `airflow/dags/reports_etl_dag.py`
- Расписание: ежедневно в 02:00 UTC (`0 2 * * *`)
- Задачи: extract_telemetry, extract_crm, transform_and_merge, load_to_clickhouse

**Витрина ClickHouse**: `clickhouse/init.sql`
- Таблица: `prosthesis_usage_reports` (партиционирование по дате)
- Материализованное представление: `daily_prosthesis_reports`
- Оптимизация: ORDER BY (user_id, prosthesis_id, report_date) для быстрого доступа

**Настройка**: см. `ETL_SETUP.md`
