# ✅ Проверка задания - Инструкция

## 🚀 Приложение запущено!

Все сервисы должны быть доступны через 1-2 минуты после запуска.

## 📋 Быстрая проверка всех требований

### 1️⃣ UI вызывает API для генерации отчётов

**Шаги:**
1. Откройте **http://localhost:3000**
2. Войдите: **prothetic1** / **prothetic123**
3. Нажмите кнопку **"Получить отчёт"**
4. Проверьте в консоли браузера (F12 → Network):
   - Запрос к `http://localhost:8000/reports`
   - Статус 200 или информационное сообщение

**✅ Ожидаемый результат:** Отчёт загружается и отображается в UI

---

### 2️⃣ Неавторизованный пользователь не может получить отчёт

**Проверка через curl:**
```bash
curl http://localhost:8000/reports
```

**✅ Ожидаемый результат:** 
```json
{"detail":"Authorization header required. Expected format: 'Authorization: Bearer <token>'"}
```

**Проверка в UI:**
- Выйдите из системы (logout)
- Попробуйте получить отчёт
- **✅ Ожидаемый результат:** Страница входа или сообщение об ошибке

---

### 3️⃣ Авторизованный пользователь видит только свои отчёты

**Шаги:**
1. Войдите как **prothetic1** (user_id = 1)
2. Получите отчёт
3. Проверьте ответ API

**Проверка через curl:**
```bash
# Получение токена
TOKEN=$(curl -s -X POST http://localhost:8080/realms/reports-realm/protocol/openid-connect/token \
  -d "client_id=reports-frontend" \
  -d "username=prothetic1" \
  -d "password=prothetic123" \
  -d "grant_type=password" | jq -r '.access_token')

# Запрос отчёта
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports" | jq '.reports[] | .user_id' | sort -u
```

**✅ Ожидаемый результат:** Все `user_id` в ответе равны `1` (или соответствуют пользователю из токена)

---

### 4️⃣ Отчёты генерируются из OLAP (ClickHouse)

**Проверка подключения:**
```bash
curl http://localhost:8123/ping
# Должно вернуть: Ok
```

**Проверка данных:**
```bash
docker compose exec clickhouse clickhouse-client -q \
  "USE reports_warehouse; SELECT COUNT(*) FROM prosthesis_usage_reports;"
```

**Проверка в логах API:**
```bash
docker compose logs reports-api | grep -i clickhouse
```

**✅ Ожидаемый результат:** 
- ClickHouse доступен
- Запросы идут в ClickHouse (не вычисляются в реальном времени)
- Данные предварительно агрегированы

---

### 5️⃣ Отчёты только за обработанный Airflow период

**Проверка в UI:**
1. Попробуйте выбрать **сегодняшнюю дату** в фильтре
2. **✅ Ожидаемый результат:** Дата автоматически ограничивается до вчерашнего дня

**Проверка через API:**
```bash
TOKEN=$(curl -s -X POST http://localhost:8080/realms/reports-realm/protocol/openid-connect/token \
  -d "client_id=reports-frontend" \
  -d "username=prothetic1" \
  -d "password=prothetic123" \
  -d "grant_type=password" | jq -r '.access_token')

# Запрос с сегодняшней датой
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports?date_from=2024-01-01&date_to=$(date +%Y-%m-%d)" | jq '.summary'
```

**✅ Ожидаемый результат:** 
- `date_to` в ответе ограничена до вчерашнего дня
- В `summary.info` есть предупреждение о доступности данных

**Проверка в логах:**
```bash
docker compose logs reports-api | grep -i "Limiting date_to"
```

---

### 6️⃣ Обработка случая, когда данных нет в OLAP

**Проверка:**
```bash
TOKEN=$(curl -s -X POST http://localhost:8080/realms/reports-realm/protocol/openid-connect/token \
  -d "client_id=reports-frontend" \
  -d "username=prothetic1" \
  -d "password=prothetic123" \
  -d "grant_type=password" | jq -r '.access_token')

# Запрос за очень старый период
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/reports?date_from=2020-01-01&date_to=2020-01-31" | jq
```

**✅ Ожидаемый результат:**
```json
{
  "reports": [],
  "summary": {
    "total_reports": 0,
    "info": "No data available for the requested period. Data is processed daily by Airflow at 02:00 UTC."
  }
}
```

---

## 📊 Проверка Airflow ETL

### Настройка Airflow (если ещё не настроен):

1. **Создание пользователя:**
```bash
docker compose exec airflow-webserver airflow users create \
  --username admin --firstname Admin --lastname User \
  --role Admin --email admin@example.com --password admin
```

2. **Откройте Airflow UI:** http://localhost:8081
   - Логин: **admin** / **admin**

3. **Включите DAG:**
   - Найдите `reports_etl_dag`
   - Переключите тумблер в положение "ON"

4. **Запустите DAG вручную (для теста):**
   - Нажмите на DAG → "Trigger DAG"

5. **Проверьте выполнение:**
   - Откройте DAG → Graph View
   - Все задачи должны быть зелёными (success)

---

## 🔍 Дополнительные проверки

### Проверка PKCE (Задание 1, Задача 2)

**В консоли браузера (F12 → Network):**
1. Войдите в систему
2. Найдите запрос к Keycloak
3. Проверьте параметры:
   - Должен быть `code_challenge`
   - Должен быть `code_challenge_method: S256`

**✅ Ожидаемый результат:** PKCE параметры присутствуют в запросе

---

### Проверка архитектурных диаграмм

**Файлы:**
- ✅ `architecture-identity-management.drawio` - Задание 1, Задача 1
- ✅ `architecture-reports-service.drawio` - Задание 2, Задача 1

**✅ Ожидаемый результат:** Диаграммы открываются в draw.io и содержат все необходимые компоненты

---

## 📝 Итоговый чеклист

- [x] Задание 1, Задача 1: Диаграмма управления учётными данными
- [x] Задание 1, Задача 2: PKCE реализован во фронтенде и Keycloak
- [x] Задание 2, Задача 1: Диаграмма сервиса отчётов
- [x] Задание 2, Задача 2: Airflow DAG с ETL процессом
- [x] Задание 2, Задача 3: Backend API на Python (FastAPI)
- [x] Задание 2, Задача 4: RBAC - только свои отчёты
- [x] Задание 2, Задача 5: UI кнопка получения отчёта
- [x] UI вызывает API
- [x] Неавторизованные пользователи не могут получить отчёт
- [x] Авторизованные пользователи видят только свои отчёты
- [x] Запросы идут в OLAP (ClickHouse)
- [x] Ограничение дат до обработанного периода
- [x] Обработка случая отсутствия данных

---

## 🛑 Остановка приложения

```bash
cd /Users/nataliashalaeva/YandexPractikum/Sprint9HW/architecture-bionicpro
docker compose down
```

---

## 📞 Проблемы?

**Проверка логов:**
```bash
# Все сервисы
docker compose logs

# Конкретный сервис
docker compose logs reports-api
docker compose logs frontend
docker compose logs keycloak
docker compose logs airflow-webserver
```

**Перезапуск сервиса:**
```bash
docker compose restart reports-api
```
