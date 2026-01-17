-- Инициализация базы данных телеметрии
-- Создание таблиц для хранения данных от протезов

CREATE DATABASE IF NOT EXISTS telemetry_db;

\c telemetry_db;

-- Таблица телеметрии протезов
CREATE TABLE IF NOT EXISTS telemetry_data (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    prosthesis_id INTEGER NOT NULL,
    sensor_id INTEGER,
    sensor_value FLOAT,
    sensor_timestamp TIMESTAMP,
    battery_level FLOAT,
    movement_type VARCHAR(50),
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_user_id ON telemetry_data(user_id);
CREATE INDEX IF NOT EXISTS idx_prosthesis_id ON telemetry_data(prosthesis_id);
CREATE INDEX IF NOT EXISTS idx_created_at ON telemetry_data(created_at);
CREATE INDEX IF NOT EXISTS idx_user_prosthesis_date ON telemetry_data(user_id, prosthesis_id, created_at);

-- Вставка тестовых данных для демонстрации
INSERT INTO telemetry_data (user_id, prosthesis_id, sensor_id, sensor_value, sensor_timestamp, battery_level, movement_type, started_at, ended_at, created_at)
VALUES
    (1, 101, 1, 0.85, NOW() - INTERVAL '1 hour', 75.5, 'grasp', NOW() - INTERVAL '1 hour', NOW() - INTERVAL '59 minutes', NOW() - INTERVAL '1 hour'),
    (1, 101, 2, 0.92, NOW() - INTERVAL '1 hour', 75.5, 'release', NOW() - INTERVAL '50 minutes', NOW() - INTERVAL '49 minutes', NOW() - INTERVAL '50 minutes'),
    (2, 102, 1, 0.78, NOW() - INTERVAL '2 hours', 80.0, 'flex', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '1 hour 59 minutes', NOW() - INTERVAL '2 hours'),
    (2, 102, 2, 0.88, NOW() - INTERVAL '2 hours', 80.0, 'extend', NOW() - INTERVAL '1 hour 50 minutes', NOW() - INTERVAL '1 hour 49 minutes', NOW() - INTERVAL '1 hour 50 minutes'),
    (1, 101, 1, 0.90, NOW() - INTERVAL '30 minutes', 74.0, 'grasp', NOW() - INTERVAL '30 minutes', NOW() - INTERVAL '29 minutes', NOW() - INTERVAL '30 minutes')
ON CONFLICT DO NOTHING;
