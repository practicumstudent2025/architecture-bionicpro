## Архитектурное решение: Управление учётными данными

### Компоненты

1. **BFF Service** — Backend for Frontend, токены IdP не передаются фронтенду
2. **Identity Provider Gateway** — унификация доступа к разным IdP (Keycloak, Azure AD, AWS Cognito)
3. **Token Service** — хранение и управление токенами
4. **Local Identity Store** — локальное хранение учётных записей
5. **Regional IdP** — региональные провайдеры по странам

### Поток аутентификации

Пользователь → Frontend → BFF → IdP Gateway → Regional IdP → BFF → Token Service → Session cookie

**Безопасность**: токены IdP только на бэкенде, фронтенд получает session cookies.

## Реализованные задачи

### Задача 1: Управление учётными данными
Архитектурное решение с BFF, IdP Gateway, Token Service. См. `ARCHITECTURE_IDENTITY.md`

### Задача 2: PKCE для безопасности
- Authorization Code Grant + PKCE добавлен во фронтенд
- Конфигурация Keycloak обновлена (небезопасные flows отключены)
- См. `PKCE_IMPLEMENTATION.md`

### Задача 3: Сервис отчётов
- Архитектура ETL-процесса через Apache Airflow
- Витрина отчётности в ClickHouse (OLAP)
- Reports API для генерации и предоставления отчётов
- Объединение данных из PostgreSQL и CRM DB
- RBAC контроль доступа (пользователь видит только свои отчёты)
- См. `ARCHITECTURE_REPORTS.md` и `architecture-reports-service.drawio`
