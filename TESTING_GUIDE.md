# Руководство по проверке задания

## Запуск приложения

### 1. Запуск всех сервисов

```bash
cd /Users/nataliashalaeva/YandexPractikum/Sprint9HW/architecture-bionicpro
docker compose up -d
```

Это запустит:
- Keycloak (порт 8080)
- Frontend (порт 3000)
- Reports API (порт 8000)
- ClickHouse (порты 8123, 9000)
- PostgreSQL для телеметрии (порт 5434)
- Airflow (порт 8081)
- Redis, PostgreSQL для Airflow

### 2. Инициализация Airflow (первый запуск)

```bash
# Создание администратора Airflow
docker compose run --rm airflow-webserver airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin
```

### 3. Проверка статуса сервисов

```bash
docker compose ps
```

Все сервисы должны быть в статусе "Up" или "healthy".

## Проверка задания

### ✅ Проверка 1: UI позволяет вызвать API для генерации отчётов

1. Откройте браузер: http://localhost:3000
2. Вы должны увидеть страницу входа в Keycloak
3. Войдите с учётными данными (см. ниже)
4. После входа вы увидите страницу "Отчёты о работе протеза"
5. Нажмите кнопку **"Получить отчёт"**
6. Должен выполниться запрос к API и отобразиться результат (или сообщение об отсутствии данных)

**Ожидаемый результат**: Кнопка работает, запрос отправляется, данные отображаются.

### ✅ Проверка 2: Неавторизованный пользователь не может получить отчёт

1. Откройте http://localhost:3000 в режиме инкогнито
2. Без входа попробуйте напрямую вызвать API:
   ```bash
   curl http://localhost:8000/reports
   ```
3. Должен вернуться HTTP 401 Unauthorized

**Ожидаемый результат**: Без токена запрос отклоняется с ошибкой 401.

### ✅ Проверка 3: Авторизованный пользователь видит только свои отчёты

1. Войдите в систему (см. учётные данные ниже)
2. Откройте консоль браузера (F12)
3. Нажмите "Получить отчёт"
4. В Network вкладке проверьте запрос к `/reports`
5. Проверьте, что в ответе `user_id` соответствует вашему пользователю
6. Попробуйте изменить `user_id` в URL запроса - данные не должны измениться

**Ожидаемый результат**: 
- В ответе только данные текущего пользователя
- `user_id` берётся из токена, а не из параметров запроса

### ✅ Проверка 4: Отчёты генерируются из OLAP базы (ClickHouse)

1. Проверьте подключение к ClickHouse:
   ```bash
   docker compose exec clickhouse clickhouse-client
   ```
2. В консоли ClickHouse выполните:
   ```sql
   USE reports_warehouse;
   SELECT COUNT(*) FROM prosthesis_usage_reports;
   ```
3. Получите отчёт через UI
4. Проверьте логи Reports API:
   ```bash
   docker compose logs reports-api | grep "Executing query"
   ```
5. Должны увидеть SQL-запрос к ClickHouse

**Ожидаемый результат**: 
- Запросы идут в ClickHouse (OLAP)
- Данные берутся из витрины, а не вычисляются в реальном времени

### ✅ Проверка 5: Отчёты только за обработанный Airflow период

1. В UI попробуйте запросить данные за сегодняшний день
2. Проверьте, что дата автоматически ограничивается до вчерашнего дня
3. Проверьте предупреждение в UI о доступности данных
4. Проверьте логи API:
   ```bash
   docker compose logs reports-api | grep "Limiting date_to"
   ```

**Ожидаемый результат**:
- `date_to` автоматически ограничивается до вчерашнего дня
- Показывается предупреждение о том, что данные за сегодня могут быть недоступны
- В ответе есть поле `warning` или `info` с объяснением

### ✅ Проверка 6: Обработка случая, когда данных нет в OLAP

1. Запросите данные за очень старый период (например, 2020 год)
2. Или запросите данные для пользователя, у которого нет записей
3. Проверьте ответ API - должен быть пустой массив `reports: []`
4. Проверьте, что в `summary` есть информационное сообщение

**Ожидаемый результат**:
- API возвращает пустой массив, а не ошибку
- В ответе есть объяснение, почему данных нет
- UI корректно отображает сообщение об отсутствии данных

## Учётные данные для тестирования

### Keycloak пользователи

Созданы в `keycloak/realm-export.json`:

1. **prothetic1** / **prothetic123**
   - Email: prothetic1@example.com
   - Роль: prothetic_user

2. **prothetic2** / **prothetic123**
   - Email: prothetic2@example.com
   - Роль: prothetic_user

3. **prothetic3** / **prothetic123**
   - Email: prothetic3@example.com
   - Роль: prothetic_user

### Airflow

- URL: http://localhost:8081
- Username: admin
- Password: admin

## Проверка через API напрямую

### 1. Получение токена Keycloak

```bash
# Получение токена (замените username и password)
TOKEN=$(curl -X POST http://localhost:8080/realms/reports-realm/protocol/openid-connect/token \
  -d "client_id=reports-frontend" \
  -d "username=prothetic1" \
  -d "password=prothetic123" \
  -d "grant_type=password" | jq -r '.access_token')

echo $TOKEN
```

### 2. Запрос отчёта через API

```bash
# Запрос отчёта
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports?date_from=2024-01-01&date_to=2024-01-31" | jq
```

### 3. Проверка без токена (должна быть ошибка 401)

```bash
curl http://localhost:8000/reports
# Ожидается: {"detail":"Authorization header required..."}
```

### 4. Проверка сводной статистики

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports/summary" | jq
```

## Проверка данных в ClickHouse

```bash
# Подключение к ClickHouse
docker compose exec clickhouse clickhouse-client

# В консоли ClickHouse:
USE reports_warehouse;

# Проверка наличия данных
SELECT COUNT(*) FROM prosthesis_usage_reports;

# Проверка данных конкретного пользователя
SELECT * FROM prosthesis_usage_reports WHERE user_id = 1 LIMIT 10;

# Проверка доступных дат
SELECT MIN(report_date) as min_date, MAX(report_date) as max_date 
FROM prosthesis_usage_reports;
```

## Проверка Airflow ETL

1. Откройте http://localhost:8081
2. Войдите (admin/admin)
3. Найдите DAG `reports_etl_dag`
4. Включите DAG (переключите тумблер)
5. Запустите DAG вручную (кнопка "Play")
6. Проверьте выполнение задач

## Проверка логов

```bash
# Логи Reports API
docker compose logs reports-api

# Логи Frontend
docker compose logs frontend

# Логи Airflow
docker compose logs airflow-scheduler
docker compose logs airflow-worker

# Логи ClickHouse
docker compose logs clickhouse
```

## Остановка приложения

```bash
docker compose down
```

Для полной очистки (включая данные):

```bash
docker compose down -v
```

## Возможные проблемы

### 1. Порт уже занят
```bash
# Проверьте, какие порты заняты
lsof -i :3000
lsof -i :8000
lsof -i :8080

# Остановите конфликтующие процессы или измените порты в docker-compose.yaml
```

### 2. Keycloak не запускается
```bash
# Проверьте логи
docker compose logs keycloak

# Убедитесь, что keycloak_db запущен
docker compose ps keycloak_db
```

### 3. ClickHouse недоступен
```bash
# Проверьте здоровье
curl http://localhost:8123/ping
# Должен вернуть: Ok

# Проверьте логи
docker compose logs clickhouse
```

### 4. Reports API не подключается к ClickHouse
```bash
# Проверьте переменные окружения
docker compose exec reports-api env | grep CLICKHOUSE

# Проверьте сеть Docker
docker network ls
docker network inspect architecture-bionicpro_default
```

## Чеклист проверки

- [ ] Все сервисы запущены и работают
- [ ] UI открывается и показывает страницу входа
- [ ] Можно войти через Keycloak
- [ ] Кнопка "Получить отчёт" работает
- [ ] Без авторизации API возвращает 401
- [ ] С авторизацией API возвращает данные
- [ ] Данные фильтруются по user_id из токена
- [ ] Запросы идут в ClickHouse
- [ ] Дата автоматически ограничивается до вчера
- [ ] Показываются предупреждения о недоступных данных
- [ ] Можно скачать отчёт в JSON и CSV
