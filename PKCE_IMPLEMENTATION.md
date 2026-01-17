# Реализация PKCE

## Изменения

### Фронтенд (App.tsx)
- PKCE добавлен: `pkceMethod: 'S256'`

### Keycloak (realm-export.json)
- `directAccessGrantsEnabled: false`
- `implicitFlowEnabled: false`
- `pkce.code.challenge.method: "S256"`

## Как работает

1. Клиент генерирует code_verifier
2. Создаёт code_challenge = SHA-256(code_verifier)
3. Отправляет code_challenge в Keycloak
4. Получает authorization code
5. Обменивает code + code_verifier на токены

## Безопасность

- Защита от перехвата authorization code
- SHA-256 для хеширования
- Небезопасные flows отключены
