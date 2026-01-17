# Быстрая проверка задания

## 🚀 Запуск (5 минут)

```bash
cd /Users/nataliashalaeva/YandexPractikum/Sprint9HW/architecture-bionicpro

# 1. Запуск всех сервисов
docker compose up -d

# 2. Ожидание запуска (30-60 секунд)
sleep 60

# 3. Инициализация Airflow (только первый раз)
docker compose run --rm airflow-webserver airflow users create \
    --username admin --firstname Admin --lastname User \
    --role Admin --email admin@example.com --password admin

# 4. Проверка статуса
docker compose ps
```

## ✅ Проверка 1: UI вызывает API (2 минуты)

1. Откройте: **http://localhost:3000**
2. Войдите: **prothetic1** / **prothetic123**
3. Нажмите **"Получить отчёт"**
4. ✅ Должен выполниться запрос и показаться результат

## ✅ Проверка 2: Без авторизации - ошибка 401 (30 секунд)

```bash
curl http://localhost:8000/reports
```

✅ Должно вернуть: `{"detail":"Authorization header required..."}`

## ✅ Проверка 3: Только свои отчёты (2 минуты)

1. Войдите как **prothetic1**
2. Откройте консоль браузера (F12 → Network)
3. Нажмите "Получить отчёт"
4. Проверьте запрос к `/reports`
5. ✅ В ответе `user_id` должен быть из токена, не из URL

## ✅ Проверка 4: Данные из ClickHouse OLAP (1 минута)

```bash
# Проверка подключения
curl http://localhost:8123/ping
# Должно вернуть: Ok

# Проверка данных
docker compose exec clickhouse clickhouse-client -q "USE reports_warehouse; SELECT COUNT(*) FROM prosthesis_usage_reports;"
```

✅ Должно показать количество записей (может быть 0, если ETL ещё не запускался)

## ✅ Проверка 5: Ограничение дат (1 минута)

1. В UI попробуйте выбрать сегодняшнюю дату
2. ✅ Дата должна автоматически ограничиться до вчера
3. ✅ Должно показаться предупреждение о доступности данных

## ✅ Проверка 6: Нет данных в OLAP (1 минута)

1. Запросите данные за 2020 год
2. ✅ API должен вернуть пустой массив, а не ошибку
3. ✅ Должно быть информационное сообщение

## 📋 Учётные данные

- **Keycloak**: prothetic1 / prothetic123
- **Airflow**: admin / admin (http://localhost:8081)

## 🔍 Проверка через API напрямую

```bash
# 1. Получение токена
TOKEN=$(curl -s -X POST http://localhost:8080/realms/reports-realm/protocol/openid-connect/token \
  -d "client_id=reports-frontend" \
  -d "username=prothetic1" \
  -d "password=prothetic123" \
  -d "grant_type=password" | jq -r '.access_token')

# 2. Запрос отчёта
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports" | jq

# 3. Проверка без токена (должна быть ошибка)
curl http://localhost:8000/reports
```

## 🛑 Остановка

```bash
docker compose down
```

## 📊 Все проверки в одной команде

```bash
# Проверка всех сервисов
echo "=== Проверка сервисов ==="
docker compose ps

echo -e "\n=== Проверка API без токена (должна быть 401) ==="
curl -s http://localhost:8000/reports | jq

echo -e "\n=== Проверка ClickHouse ==="
curl -s http://localhost:8123/ping

echo -e "\n=== Проверка Keycloak ==="
curl -s http://localhost:8080/realms/reports-realm | jq -r '.realm'
```
