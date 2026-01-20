#!/bin/bash
# Скрипт для исправления sslRequired в Keycloak

export KC="http://localhost:8080"
export USER="admin"
export PASS="admin"

echo "Ожидание готовности Keycloak..."
for i in {1..60}; do
    if curl -s "$KC/health/ready" > /dev/null 2>&1; then
        echo "✅ Keycloak готов"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "❌ Keycloak не запустился за 2 минуты"
        exit 1
    fi
    sleep 2
done

echo "Получение токена администратора..."
TOKEN=$(curl -s \
  -d "client_id=admin-cli" \
  -d "username=$USER" \
  -d "password=$PASS" \
  -d "grant_type=password" \
  "$KC/realms/master/protocol/openid-connect/token" | jq -r .access_token)

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "❌ Не удалось получить токен. Проверьте логи Keycloak"
  exit 1
fi

echo "✅ Token получен"

echo "Обновление reports-realm..."
curl -s -X PUT "$KC/admin/realms/reports-realm" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sslRequired":"NONE","enabled":true}' > /dev/null

echo "Проверка reports-realm:"
curl -s "$KC/admin/realms/reports-realm" \
  -H "Authorization: Bearer $TOKEN" | jq '{realm, sslRequired, enabled}'

echo ""
echo "Обновление master realm (на всякий случай)..."
curl -s -X PUT "$KC/admin/realms/master" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sslRequired":"NONE","enabled":true}' > /dev/null

echo "Проверка master realm:"
curl -s "$KC/admin/realms/master" \
  -H "Authorization: Bearer $TOKEN" | jq '{realm, sslRequired, enabled}'

echo ""
echo "✅ Готово! Теперь можно открыть http://localhost:3000"
