"""
DAG для генерации тестовых данных телеметрии
Можно запускать вручную для добавления тестовых данных в PostgreSQL
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.models import Connection
from airflow import settings
import random
import logging

POSTGRES_CONN_ID = 'postgres_default'

default_args = {
    'owner': 'bionicpro',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
}

dag = DAG(
    'generate_test_telemetry_data',
    default_args=default_args,
    description='Генерация тестовых данных телеметрии для демонстрации',
    schedule_interval=None,  # Только ручной запуск
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['test', 'data-generation'],
)


def generate_test_data(**context):
    """
    Генерирует тестовые данные телеметрии за последние дни
    """
    logging.info("Начало генерации тестовых данных телеметрии")
    
    # Создаем или обновляем connection, если его нет
    try:
        session = settings.Session()
        conn = session.query(Connection).filter(Connection.conn_id == POSTGRES_CONN_ID).first()
        
        if not conn:
            logging.info(f"Создание connection {POSTGRES_CONN_ID}")
            conn = Connection(
                conn_id=POSTGRES_CONN_ID,
                conn_type='postgres',
                host='postgres_telemetry',  # Имя сервиса из docker-compose
                schema='telemetry_db',
                login='telemetry_user',
                password='telemetry_password',
                port=5432
            )
            session.add(conn)
            session.commit()
            logging.info(f"Connection {POSTGRES_CONN_ID} создан")
        else:
            # Обновляем connection, если хост неправильный
            if conn.host != 'postgres_telemetry':
                logging.info(f"Обновление connection {POSTGRES_CONN_ID}")
                conn.host = 'postgres_telemetry'
                conn.schema = 'telemetry_db'
                conn.login = 'telemetry_user'
                conn.password = 'telemetry_password'
                conn.port = 5432
                session.commit()
                logging.info(f"Connection {POSTGRES_CONN_ID} обновлен")
        session.close()
    except Exception as e:
        logging.warning(f"Не удалось создать/обновить connection: {e}. Используем существующий.")
    
    postgres_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    
    # Генерируем данные за последние 7 дней
    base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    movements = ['grasp', 'release', 'flex', 'extend', 'rotate', 'pinch']
    users = [1, 2]
    prostheses = {1: 101, 2: 102}
    
    records = []
    
    for day_offset in range(7):
        current_date = base_date - timedelta(days=day_offset)
        
        # Генерируем данные для каждого пользователя
        for user_id in users:
            prosthesis_id = prostheses[user_id]
            
            # 5-10 движений в день для каждого пользователя
            num_movements = random.randint(5, 10)
            
            for movement_idx in range(num_movements):
                # Случайное время в течение дня (между 6:00 и 22:00)
                hour = random.randint(6, 22)
                minute = random.randint(0, 59)
                movement_time = current_date.replace(hour=hour, minute=minute)
                
                # Параметры движения
                sensor_id = random.randint(1, 4)
                sensor_value = round(random.uniform(0.5, 0.95), 2)
                battery_level = round(random.uniform(70.0, 85.0), 1)
                movement_type = random.choice(movements)
                duration_minutes = random.randint(1, 5)
                
                started_at = movement_time
                ended_at = movement_time + timedelta(minutes=duration_minutes)
                
                records.append((
                    user_id,
                    prosthesis_id,
                    sensor_id,
                    sensor_value,
                    movement_time,
                    battery_level,
                    movement_type,
                    started_at,
                    ended_at,
                    movement_time
                ))
    
    # Вставляем данные в базу
    if records:
        insert_query = """
        INSERT INTO telemetry_data 
        (user_id, prosthesis_id, sensor_id, sensor_value, sensor_timestamp, 
         battery_level, movement_type, started_at, ended_at, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """
        
        conn = postgres_hook.get_conn()
        cursor = conn.cursor()
        cursor.executemany(insert_query, records)
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"Сгенерировано и вставлено {len(records)} записей телеметрии")
        return len(records)
    else:
        logging.warning("Не удалось сгенерировать данные")
        return 0


generate_data_task = PythonOperator(
    task_id='generate_test_telemetry_data',
    python_callable=generate_test_data,
    dag=dag,
)

generate_data_task
