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
-- Данные за последние 3 дня для тестирования ETL процесса
INSERT INTO telemetry_data (user_id, prosthesis_id, sensor_id, sensor_value, sensor_timestamp, battery_level, movement_type, started_at, ended_at, created_at)
VALUES
    -- Данные за вчера (для текущего запуска DAG)
    (1, 101, 1, 0.85, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '2 hours', 75.5, 'grasp', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '2 hours', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '2 hours 1 minute', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '2 hours'),
    (1, 101, 2, 0.92, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '3 hours', 75.0, 'release', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '3 hours', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '3 hours 2 minutes', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '3 hours'),
    (1, 101, 1, 0.88, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '4 hours', 74.5, 'grasp', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '4 hours', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '4 hours 1 minute', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '4 hours'),
    (1, 101, 2, 0.90, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '5 hours', 74.0, 'flex', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '5 hours', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '5 hours 3 minutes', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '5 hours'),
    
    -- Данные для второго пользователя за вчера
    (2, 102, 1, 0.78, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '2 hours', 80.0, 'flex', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '2 hours', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '2 hours 5 minutes', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '2 hours'),
    (2, 102, 2, 0.88, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '3 hours', 79.5, 'extend', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '3 hours', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '3 hours 2 minutes', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '3 hours'),
    (2, 102, 1, 0.82, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '6 hours', 79.0, 'grasp', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '6 hours', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '6 hours 1 minute', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '6 hours'),
    (2, 102, 2, 0.85, CURRENT_DATE - INTERVAL '1 day' + INTERVAL '8 hours', 78.5, 'release', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '8 hours', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '8 hours 2 minutes', CURRENT_DATE - INTERVAL '1 day' + INTERVAL '8 hours'),
    
    -- Данные за позавчера (для тестирования)
    (1, 101, 1, 0.83, CURRENT_DATE - INTERVAL '2 days' + INTERVAL '2 hours', 76.0, 'grasp', CURRENT_DATE - INTERVAL '2 days' + INTERVAL '2 hours', CURRENT_DATE - INTERVAL '2 days' + INTERVAL '2 hours 1 minute', CURRENT_DATE - INTERVAL '2 days' + INTERVAL '2 hours'),
    (2, 102, 1, 0.80, CURRENT_DATE - INTERVAL '2 days' + INTERVAL '3 hours', 81.0, 'flex', CURRENT_DATE - INTERVAL '2 days' + INTERVAL '3 hours', CURRENT_DATE - INTERVAL '2 days' + INTERVAL '3 hours 4 minutes', CURRENT_DATE - INTERVAL '2 days' + INTERVAL '3 hours'),
    
    -- Данные за сегодня (для будущих запусков)
    (1, 101, 1, 0.90, CURRENT_DATE + INTERVAL '2 hours', 73.0, 'grasp', CURRENT_DATE + INTERVAL '2 hours', CURRENT_DATE + INTERVAL '2 hours 1 minute', CURRENT_DATE + INTERVAL '2 hours'),
    (2, 102, 1, 0.79, CURRENT_DATE + INTERVAL '2 hours', 77.0, 'flex', CURRENT_DATE + INTERVAL '2 hours', CURRENT_DATE + INTERVAL '2 hours 3 minutes', CURRENT_DATE + INTERVAL '2 hours')
ON CONFLICT DO NOTHING;
