# Как проверить задание

## 🚀 Быстрый старт

```bash
cd /Users/nataliashalaeva/YandexPractikum/Sprint9HW/architecture-bionicpro

# 1. Запуск всех сервисов
docker compose up -d

# 2. Ожидание запуска (1-2 минуты)
# Проверка статуса
docker compose ps
```

## ✅ Проверка всех требований

### 1. UI вызывает API для генерации отчётов

1. Откройте **http://localhost:3000**
2. Войдите: **prothetic1** / **prothetic123**
3. Нажмите **"Получить отчёт"**
4. ✅ Должен выполниться запрос к API

**Проверка в консоли браузера (F12 → Network)**:
- Запрос к `http://localhost:8000/reports`
- Статус 200 или сообщение об отсутствии данных

### 2. Неавторизованный пользователь не может получить отчёт

```bash
# Без токена - должна быть ошибка 401
curl http://localhost:8000/reports
```

✅ Ожидается: `{"detail":"Authorization header required..."}`

### 3. Авторизованный пользователь видит только свои отчёты

1. Войдите как **prothetic1**
2. Получите отчёт
3. Проверьте ответ - в нём должен быть только `user_id: 1` (или соответствующий вашему пользователю)

**Проверка через API**:
```bash
# Получение токена
TOKEN=$(curl -s -X POST http://localhost:8080/realms/reports-realm/protocol/openid-connect/token \
  -d "client_id=reports-frontend" \
  -d "username=prothetic1" \
  -d "password=prothetic123" \
  -d "grant_type=password" | jq -r '.access_token')

# Запрос отчёта
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports" | jq '.user_id'
```

✅ `user_id` должен соответствовать пользователю из токена

### 4. Отчёты генерируются из OLAP (ClickHouse)

```bash
# Проверка подключения к ClickHouse
curl http://localhost:8123/ping
# Должно вернуть: Ok

# Проверка данных в ClickHouse
docker compose exec clickhouse clickhouse-client -q \
  "USE reports_warehouse; SELECT COUNT(*) FROM prosthesis_usage_reports;"
```

✅ Запросы должны идти в ClickHouse, а не вычисляться в реальном времени

### 5. Отчёты только за обработанный Airflow период

1. В UI попробуйте выбрать **сегодняшнюю дату**
2. ✅ Дата должна автоматически ограничиться до **вчерашнего дня**
3. ✅ Должно показаться предупреждение о доступности данных

**Проверка в логах API**:
```bash
docker compose logs reports-api | grep "Limiting date_to"
```

### 6. Обработка случая, когда данных нет в OLAP

1. Запросите данные за **2020 год** (или очень старый период)
2. ✅ API должен вернуть пустой массив `reports: []`
3. ✅ В ответе должно быть информационное сообщение в `summary.info`

## 📋 Учётные данные

- **Keycloak**: prothetic1 / prothetic123
- **Airflow UI**: http://localhost:8081 (admin / admin)

## 🔍 Проверка через curl

```bash
# 1. Получение токена
TOKEN=$(curl -s -X POST http://localhost:8080/realms/reports-realm/protocol/openid-connect/token \
  -d "client_id=reports-frontend" \
  -d "username=prothetic1" \
  -d "password=prothetic123" \
  -d "grant_type=password" | jq -r '.access_token')

# 2. Проверка health
curl http://localhost:8000/health | jq

# 3. Получение отчёта
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports" | jq

# 4. Проверка без токена (должна быть 401)
curl http://localhost:8000/reports
```

## 📊 Проверка данных

```bash
# ClickHouse
docker compose exec clickhouse clickhouse-client
USE reports_warehouse;
SELECT * FROM prosthesis_usage_reports LIMIT 5;

# PostgreSQL телеметрия
docker compose exec postgres_telemetry psql -U telemetry_user -d telemetry_db -c \
  "SELECT COUNT(*) FROM telemetry_data;"
```

## 🛑 Остановка

```bash
docker compose down
```
