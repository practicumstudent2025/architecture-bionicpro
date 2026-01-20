#!/bin/bash
# Скрипт для исправления настройки sslRequired в Keycloak realm

echo "Ожидание запуска Keycloak..."
sleep 10

echo "Получение токена администратора..."
TOKEN=$(curl -s -X POST "http://localhost:8080/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin" \
  -d "grant_type=password" | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "Ошибка: не удалось получить токен"
  exit 1
fi

echo "Получение текущих настроек realm..."
REALM_DATA=$(curl -s -X GET "http://localhost:8080/admin/realms/reports-realm" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

if [ -z "$REALM_DATA" ] || echo "$REALM_DATA" | jq -e '.error' > /dev/null 2>&1; then
  echo "Ошибка: realm не найден или недоступен"
  exit 1
fi

echo "Обновление sslRequired на 'none'..."
UPDATED_REALM=$(echo "$REALM_DATA" | jq '.sslRequired = "none"')

RESULT=$(curl -s -X PUT "http://localhost:8080/admin/realms/reports-realm" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$UPDATED_REALM")

if echo "$RESULT" | jq -e '.error' > /dev/null 2>&1; then
  echo "Ошибка при обновлении: $RESULT"
  exit 1
fi

echo "Проверка обновления..."
sleep 2
curl -s "http://localhost:8080/realms/reports-realm" | jq '{realm, sslRequired}'

echo "✅ Настройка sslRequired обновлена на 'none'"
