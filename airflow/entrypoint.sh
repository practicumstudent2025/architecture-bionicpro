#!/bin/bash
set -e

# Ожидание готовности PostgreSQL
echo "Waiting for PostgreSQL to be ready..."
until airflow db check 2>/dev/null; do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 2
done
echo "PostgreSQL is ready!"

# Инициализация базы данных Airflow (если ещё не инициализирована)
echo "Checking if Airflow database is initialized..."
if ! airflow db check 2>/dev/null; then
    echo "Database not initialized. Initializing..."
    airflow db init
    echo "Database initialized successfully"
    
    # Создание пользователя admin только при первой инициализации
    echo "Creating admin user..."
    airflow users create \
        --username admin \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@example.com \
        --password admin || echo "Admin user may already exist"
    echo "Admin user setup complete"
fi

# Выполнение оригинальной команды
exec "$@"
