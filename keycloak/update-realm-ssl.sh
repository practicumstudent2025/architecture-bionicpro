#!/bin/bash
# Скрипт для обновления sslRequired в realm после запуска Keycloak

set -e

echo "Ожидание запуска Keycloak..."
for i in {1..30}; do
    if curl -s http://localhost:8080/health/ready > /dev/null 2>&1; then
        echo "Keycloak готов"
        break
    fi
    echo "Ожидание... ($i/30)"
    sleep 2
done

echo "Получение токена администратора..."
TOKEN=$(curl -s -X POST "http://localhost:8080/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin" \
  -d "grant_type=password" | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "Ошибка: не удалось получить токен администратора"
  exit 1
fi

echo "Получение текущих настроек realm..."
REALM_DATA=$(curl -s -X GET "http://localhost:8080/admin/realms/reports-realm" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

if echo "$REALM_DATA" | jq -e '.error' > /dev/null 2>&1; then
  echo "Realm ещё не создан, будет создан при импорте"
  exit 0
fi

CURRENT_SSL=$(echo "$REALM_DATA" | jq -r '.sslRequired // "external"')
echo "Текущий sslRequired: $CURRENT_SSL"

if [ "$CURRENT_SSL" == "none" ]; then
  echo "✅ sslRequired уже установлен в 'none'"
  exit 0
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
