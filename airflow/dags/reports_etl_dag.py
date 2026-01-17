"""
ETL DAG для подготовки витрины отчётности
Объединяет данные телеметрии из PostgreSQL и данные клиентов из CRM DB
Запускается ежедневно в 02:00 UTC
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.oracle.hooks.oracle import OracleHook
from airflow.providers.http.hooks.http import HttpHook
import pandas as pd
from clickhouse_driver import Client
import json
import logging

# Параметры подключений
POSTGRES_CONN_ID = 'postgres_default'
ORACLE_CONN_ID = 'oracle_crm'
CLICKHOUSE_HOST = 'clickhouse'
CLICKHOUSE_PORT = 9000
CLICKHOUSE_DB = 'reports_warehouse'

# Настройки DAG
default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'reports_etl_dag',
    default_args=default_args,
    description='ETL для витрины отчётности протезов',
    schedule_interval='0 2 * * *',  # Ежедневно в 02:00 UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['etl', 'reports', 'prosthesis'],
)


def extract_telemetry_data(**context):
    """
    Extract: Извлечение данных телеметрии из PostgreSQL
    """
    logging.info("Начало извлечения данных телеметрии из PostgreSQL")
    
    postgres_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    
    # Вычисляем дату для инкрементальной загрузки (вчерашний день)
    execution_date = context['execution_date']
    start_date = execution_date - timedelta(days=1)
    end_date = execution_date
    
    query = """
    SELECT 
        user_id,
        prosthesis_id,
        DATE(created_at) as report_date,
        DATE_TRUNC('hour', created_at) as report_hour,
        COUNT(*) as movements_count,
        AVG(battery_level) as battery_level_avg,
        MIN(battery_level) as battery_level_min,
        MAX(battery_level) as battery_level_max,
        SUM(EXTRACT(EPOCH FROM (ended_at - started_at)) / 3600) as usage_hours,
        json_agg(
            json_build_object(
                'sensor_id', sensor_id,
                'value', sensor_value,
                'timestamp', sensor_timestamp
            )
        ) as sensor_data
    FROM telemetry_data
    WHERE created_at >= %s AND created_at < %s
    GROUP BY user_id, prosthesis_id, DATE(created_at), DATE_TRUNC('hour', created_at)
    ORDER BY user_id, prosthesis_id, report_date, report_hour
    """
    
    df = postgres_hook.get_pandas_sql(query, parameters=[start_date, end_date])
    
    logging.info(f"Извлечено {len(df)} записей телеметрии")
    
    # Сохраняем в XCom для следующего шага
    context['ti'].xcom_push(key='telemetry_data', value=df.to_json(orient='records'))
    
    return df.shape[0]


def extract_crm_data(**context):
    """
    Extract: Извлечение данных клиентов из CRM DB
    Для демонстрации используем мок-данные или PostgreSQL
    В продакшене здесь будет подключение к Oracle
    """
    logging.info("Начало извлечения данных из CRM DB")
    
    # Для демонстрации: используем тестовые данные
    # В продакшене здесь будет OracleHook
    try:
        # Попытка подключения к Oracle (если настроено)
        oracle_hook = OracleHook(oracle_conn_id=ORACLE_CONN_ID)
        query = """
        SELECT 
            u.user_id,
            u.name as crm_user_name,
            u.email as crm_user_email,
            p.prosthesis_id,
            p.model as crm_prosthesis_model,
            p.serial_number as crm_prosthesis_serial,
            o.order_date as crm_order_date,
            p.manufacturing_date as crm_manufacturing_date
        FROM users u
        INNER JOIN prostheses p ON u.user_id = p.user_id
        LEFT JOIN orders o ON p.order_id = o.order_id
        WHERE p.status = 'active'
        """
        conn = oracle_hook.get_conn()
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=columns)
        cursor.close()
        conn.close()
    except Exception as e:
        logging.warning(f"Не удалось подключиться к Oracle: {e}. Используются тестовые данные.")
        # Тестовые данные для демонстрации
        df = pd.DataFrame([
            {
                'user_id': 1,
                'crm_user_name': 'Иван Иванов',
                'crm_user_email': 'ivan@example.com',
                'prosthesis_id': 101,
                'crm_prosthesis_model': 'BionicPRO-2024',
                'crm_prosthesis_serial': 'BP-2024-001',
                'crm_order_date': '2024-01-15',
                'crm_manufacturing_date': '2024-02-01'
            },
            {
                'user_id': 2,
                'crm_user_name': 'Петр Петров',
                'crm_user_email': 'petr@example.com',
                'prosthesis_id': 102,
                'crm_prosthesis_model': 'BionicPRO-2024',
                'crm_prosthesis_serial': 'BP-2024-002',
                'crm_order_date': '2024-01-20',
                'crm_manufacturing_date': '2024-02-10'
            }
        ])
    
    logging.info(f"Извлечено {len(df)} записей из CRM")
    
    # Сохраняем в XCom
    context['ti'].xcom_push(key='crm_data', value=df.to_json(orient='records'))
    
    return df.shape[0]


def transform_and_merge_data(**context):
    """
    Transform: Объединение и трансформация данных
    """
    logging.info("Начало трансформации данных")
    
    # Получаем данные из предыдущих шагов
    ti = context['ti']
    telemetry_json = ti.xcom_pull(key='telemetry_data', task_ids='extract_telemetry')
    crm_json = ti.xcom_pull(key='crm_data', task_ids='extract_crm')
    
    # Загружаем в DataFrame
    df_telemetry = pd.read_json(telemetry_json, orient='records')
    df_crm = pd.read_json(crm_json, orient='records')
    
    # Объединяем данные по user_id и prosthesis_id
    df_merged = df_telemetry.merge(
        df_crm,
        on=['user_id', 'prosthesis_id'],
        how='left'
    )
    
    # Трансформации
    # 1. Обработка дат
    df_merged['report_date'] = pd.to_datetime(df_merged['report_date']).dt.date
    df_merged['report_hour'] = pd.to_datetime(df_merged['report_hour'])
    df_merged['crm_order_date'] = pd.to_datetime(df_merged['crm_order_date']).dt.date
    df_merged['crm_manufacturing_date'] = pd.to_datetime(df_merged['crm_manufacturing_date']).dt.date
    
    # 2. Агрегация данных датчиков
    df_merged['sensor_data_avg'] = df_merged['sensor_data'].apply(
        lambda x: json.dumps({
            'avg': sum([s['value'] for s in x]) / len(x) if x else 0,
            'count': len(x)
        }) if isinstance(x, list) else '{}'
    )
    
    df_merged['sensor_data_peak'] = df_merged['sensor_data'].apply(
        lambda x: json.dumps({
            'peak': max([s['value'] for s in x]) if x else 0,
            'timestamp': max([s['timestamp'] for s in x]) if x else None
        }) if isinstance(x, list) else '{}'
    )
    
    # 3. Расчёт метрик
    df_merged['avg_movements_per_hour'] = df_merged['movements_count'] / df_merged['usage_hours'].replace(0, 1)
    df_merged['peak_activity_hour'] = df_merged['report_hour'].dt.hour
    df_merged['total_usage_days'] = 1  # Будет пересчитано при агрегации
    
    # 4. Заполнение пропущенных значений
    df_merged['battery_level_avg'] = df_merged['battery_level_avg'].fillna(0)
    df_merged['battery_level_min'] = df_merged['battery_level_min'].fillna(0)
    df_merged['battery_level_max'] = df_merged['battery_level_max'].fillna(0)
    df_merged['usage_hours'] = df_merged['usage_hours'].fillna(0)
    
    # 5. Удаляем временные колонки
    df_merged = df_merged.drop(columns=['sensor_data'], errors='ignore')
    
    logging.info(f"Трансформировано {len(df_merged)} записей")
    
    # Сохраняем для загрузки
    context['ti'].xcom_push(key='transformed_data', value=df_merged.to_json(orient='records'))
    
    return df_merged.shape[0]


def load_to_clickhouse(**context):
    """
    Load: Загрузка данных в ClickHouse витрину
    """
    logging.info("Начало загрузки данных в ClickHouse")
    
    # Получаем трансформированные данные
    ti = context['ti']
    transformed_json = ti.xcom_pull(key='transformed_data', task_ids='transform_and_merge')
    
    df = pd.read_json(transformed_json, orient='records')
    
    # Подключаемся к ClickHouse
    client = Client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB,
        user='default',
        password=''
    )
    
    # Подготавливаем данные для вставки
    records = []
    for _, row in df.iterrows():
        record = (
            int(row['user_id']),
            int(row['prosthesis_id']),
            row['report_date'],
            row['report_hour'],
            int(row['movements_count']) if pd.notna(row['movements_count']) else 0,
            float(row['battery_level_avg']) if pd.notna(row['battery_level_avg']) else 0.0,
            float(row['battery_level_min']) if pd.notna(row['battery_level_min']) else 0.0,
            float(row['battery_level_max']) if pd.notna(row['battery_level_max']) else 0.0,
            float(row['usage_hours']) if pd.notna(row['usage_hours']) else 0.0,
            str(row['sensor_data_avg']),
            str(row['sensor_data_peak']),
            str(row['crm_user_name']) if pd.notna(row['crm_user_name']) else '',
            str(row['crm_user_email']) if pd.notna(row['crm_user_email']) else '',
            str(row['crm_prosthesis_model']) if pd.notna(row['crm_prosthesis_model']) else '',
            str(row['crm_prosthesis_serial']) if pd.notna(row['crm_prosthesis_serial']) else '',
            row['crm_order_date'] if pd.notna(row['crm_order_date']) else None,
            row['crm_manufacturing_date'] if pd.notna(row['crm_manufacturing_date']) else None,
            float(row['avg_movements_per_hour']) if pd.notna(row['avg_movements_per_hour']) else 0.0,
            int(row['peak_activity_hour']) if pd.notna(row['peak_activity_hour']) else 0,
            1,  # total_usage_days
            datetime.now(),
            datetime.now()
        )
        records.append(record)
    
    # Вставка данных (upsert через ReplacingMergeTree или DELETE + INSERT)
    if records:
        query = """
        INSERT INTO reports_warehouse.prosthesis_usage_reports VALUES
        """
        
        client.execute(query, records)
        logging.info(f"Загружено {len(records)} записей в ClickHouse")
    else:
        logging.warning("Нет данных для загрузки")
    
    client.disconnect()
    
    return len(records)


# Определение задач
extract_telemetry_task = PythonOperator(
    task_id='extract_telemetry',
    python_callable=extract_telemetry_data,
    dag=dag,
)

extract_crm_task = PythonOperator(
    task_id='extract_crm',
    python_callable=extract_crm_data,
    dag=dag,
)

transform_task = PythonOperator(
    task_id='transform_and_merge',
    python_callable=transform_and_merge_data,
    dag=dag,
)

load_task = PythonOperator(
    task_id='load_to_clickhouse',
    python_callable=load_to_clickhouse,
    dag=dag,
)

# Определение зависимостей
[extract_telemetry_task, extract_crm_task] >> transform_task >> load_task
