-- Создание витрины отчётности для сервиса отчётов
-- Структура оптимизирована для быстрого доступа по user_id

CREATE DATABASE IF NOT EXISTS reports_warehouse;

-- Основная таблица витрины отчётности
-- Партиционирование по дате для оптимизации запросов
CREATE TABLE IF NOT EXISTS reports_warehouse.prosthesis_usage_reports
(
    -- Идентификаторы
    user_id UInt64,
    prosthesis_id UInt64,
    
    -- Временная метка (партиционирование)
    report_date Date,
    report_hour DateTime,
    
    -- Данные телеметрии (агрегированные)
    movements_count UInt32,
    battery_level_avg Float32,
    battery_level_min Float32,
    battery_level_max Float32,
    usage_hours Float32,
    
    -- Данные датчиков (JSON для гибкости)
    sensor_data_avg String,  -- Средние значения миосигналов
    sensor_data_peak String,  -- Пиковые значения
    
    -- Данные из CRM
    crm_user_name String,
    crm_user_email String,
    crm_prosthesis_model String,
    crm_prosthesis_serial String,
    crm_order_date Date,
    crm_manufacturing_date Date,
    
    -- Агрегированные метрики
    avg_movements_per_hour Float32,
    peak_activity_hour UInt8,  -- Час пиковой активности (0-23)
    total_usage_days UInt16,
    
    -- Метаданные
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, prosthesis_id, report_date, report_hour)
SETTINGS index_granularity = 8192;

-- Индексы для быстрого поиска (встроены в ORDER BY)
-- ORDER BY (user_id, prosthesis_id, report_date, report_hour) обеспечивает быстрый поиск

-- Представление для ежедневных агрегатов (для быстрых отчётов)
CREATE MATERIALIZED VIEW IF NOT EXISTS reports_warehouse.daily_prosthesis_reports
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(report_date)
ORDER BY (user_id, prosthesis_id, report_date)
AS SELECT
    user_id,
    prosthesis_id,
    report_date,
    sum(movements_count) as total_movements,
    avg(battery_level_avg) as avg_battery_level,
    sum(usage_hours) as total_usage_hours,
    max(crm_user_name) as crm_user_name,
    max(crm_prosthesis_model) as crm_prosthesis_model,
    max(updated_at) as updated_at
FROM reports_warehouse.prosthesis_usage_reports
GROUP BY user_id, prosthesis_id, report_date;
