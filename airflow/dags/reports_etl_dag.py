"""
ETL DAG для подготовки витрины отчётности
Объединяет данные телеметрии из PostgreSQL и данные клиентов из CRM DB
Запускается ежедневно в 02:00 UTC
"""

from datetime import datetime, timedelta, date
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
# OracleHook удалён - для демонстрации используем тестовые данные
# В продакшене можно добавить: from airflow.providers.oracle.hooks.oracle import OracleHook
from airflow.providers.http.hooks.http import HttpHook
from airflow.models import Connection
from airflow import settings
from sqlalchemy import text
import pandas as pd
from clickhouse_driver import Client
import json
import logging

# Параметры подключений
POSTGRES_CONN_ID = 'postgres_default'
# ORACLE_CONN_ID удалён - для демонстрации используем тестовые данные
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
                logging.info(f"Обновление connection {POSTGRES_CONN_ID} (было: {conn.host})")
                conn.host = 'postgres_telemetry'
                conn.schema = 'telemetry_db'
                conn.login = 'telemetry_user'
                conn.password = 'telemetry_password'
                conn.port = 5432
                session.commit()
                logging.info(f"Connection {POSTGRES_CONN_ID} обновлен")
        session.close()
    except Exception as e:
        logging.warning(f"Не удалось создать/обновить connection: {e}")
    
    # Создаем hook напрямую с правильными параметрами для надежности
    # Это гарантирует, что мы всегда используем правильный хост
    postgres_hook = PostgresHook(
        host='postgres_telemetry',
        schema='telemetry_db',
        login='telemetry_user',
        password='telemetry_password',
        port=5432
    )
    
    # Вычисляем дату для инкрементальной загрузки (вчерашний день)
    # В Airflow 2.7.0 используем logical_date или data_interval_start вместо execution_date
    execution_date_raw = context.get('logical_date') or context.get('data_interval_start') or context.get('execution_date')
    
    # Преобразуем Proxy объект в обычный datetime
    # Простой способ - преобразовать в строку и обратно, или использовать str() и parse
    try:
        if execution_date_raw is not None:
            # Пытаемся получить реальное значение из Proxy
            if hasattr(execution_date_raw, '_target'):
                execution_date = execution_date_raw._target
            elif hasattr(execution_date_raw, '__wrapped__'):
                execution_date = execution_date_raw.__wrapped__
            else:
                execution_date = execution_date_raw
        else:
            execution_date = datetime.now()
        
        # Если все еще не datetime, преобразуем
        if not isinstance(execution_date, datetime):
            if isinstance(execution_date, str):
                from dateutil import parser
                execution_date = parser.parse(execution_date)
            else:
                # Последняя попытка - преобразовать через строку
                execution_date = datetime.fromisoformat(str(execution_date).replace('Z', '+00:00'))
    except Exception as e:
        logging.warning(f"Не удалось преобразовать execution_date: {e}. Используем текущую дату.")
        execution_date = datetime.now()
    
    start_date = execution_date - timedelta(days=1)
    end_date = execution_date
    
    # Преобразуем в строки для SQL (PostgreSQL лучше работает со строками)
    start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
    end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')
    
    logging.info(f"Извлечение данных за период: {start_date_str} - {end_date_str}")
    
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
    WHERE created_at >= :start_date AND created_at < :end_date
    GROUP BY user_id, prosthesis_id, DATE(created_at), DATE_TRUNC('hour', created_at)
    ORDER BY user_id, prosthesis_id, report_date, report_hour
    """
    
    # Используем get_sqlalchemy_engine() для получения данных в pandas DataFrame
    # В Airflow 2.7.0 метод get_pandas_sql() не существует, используем get_sqlalchemy_engine()
    engine = postgres_hook.get_sqlalchemy_engine()
    # Используем text() для правильной обработки именованных параметров
    # Передаем строки вместо datetime объектов для избежания проблем с Proxy
    df = pd.read_sql(
        text(query),
        engine,
        params={'start_date': start_date_str, 'end_date': end_date_str}
    )
    
    logging.info(f"Извлечено {len(df)} записей телеметрии")
    
    # Логируем пример данных для проверки
    if len(df) > 0:
        logging.info(f"Пример данных из PostgreSQL: report_date={df.iloc[0]['report_date']} (тип: {type(df.iloc[0]['report_date'])})")
        logging.info(f"Диапазон report_date: {df['report_date'].min()} - {df['report_date'].max()}")
    
    # Сохраняем в XCom для следующего шага
    # Используем date_format='iso' для правильной сериализации дат
    context['ti'].xcom_push(key='telemetry_data', value=df.to_json(orient='records', date_format='iso'))
    
    return df.shape[0]


def extract_crm_data(**context):
    """
    Extract: Извлечение данных клиентов из CRM DB
    
    Для демонстрации используем тестовые данные.
    В продакшене здесь будет подключение к Oracle через OracleHook.
    Альтернатива: можно использовать PostgreSQL для хранения CRM данных.
    """
    logging.info("Начало извлечения данных из CRM DB")
    
    # Для демонстрации: используем тестовые данные
    # В продакшене здесь будет:
    # oracle_hook = OracleHook(oracle_conn_id='oracle_crm')
    # или PostgreSQL для CRM:
    # postgres_hook = PostgresHook(postgres_conn_id='postgres_crm')
    
    # Тестовые данные для демонстрации
    # Соответствуют структуре данных из CRM (пользователи, протезы, заказы)
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
    
    logging.info(f"Извлечено {len(df)} записей из CRM (тестовые данные)")
    
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
    
    # Восстанавливаем даты после чтения из JSON
    if 'report_date' in df_telemetry.columns:
        df_telemetry['report_date'] = pd.to_datetime(df_telemetry['report_date']).dt.date
    if 'report_hour' in df_telemetry.columns:
        df_telemetry['report_hour'] = pd.to_datetime(df_telemetry['report_hour'])
    
    # Логируем для диагностики
    if len(df_telemetry) > 0:
        logging.info(f"Данные телеметрии после загрузки: report_date={df_telemetry.iloc[0]['report_date']} (тип: {type(df_telemetry.iloc[0]['report_date'])})")
    
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
    # Используем date_format='iso' для правильной сериализации дат
    # Это гарантирует, что даты будут правильно восстановлены при чтении
    json_str = df_merged.to_json(orient='records', date_format='iso')
    context['ti'].xcom_push(key='transformed_data', value=json_str)
    
    # Логируем пример данных для проверки
    if len(df_merged) > 0:
        logging.info(f"Пример данных перед сохранением: report_date={df_merged.iloc[0]['report_date']}, report_hour={df_merged.iloc[0]['report_hour']}")
    
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
    
    # Восстанавливаем даты после чтения из JSON
    # pd.read_json может вернуть строки вместо date объектов
    if 'report_date' in df.columns:
        df['report_date'] = pd.to_datetime(df['report_date']).dt.date
    if 'report_hour' in df.columns:
        df['report_hour'] = pd.to_datetime(df['report_hour'])
    if 'crm_order_date' in df.columns:
        df['crm_order_date'] = pd.to_datetime(df['crm_order_date']).dt.date
    if 'crm_manufacturing_date' in df.columns:
        df['crm_manufacturing_date'] = pd.to_datetime(df['crm_manufacturing_date']).dt.date
    
    # Логируем информацию о данных для диагностики
    logging.info(f"Получено {len(df)} записей для загрузки в ClickHouse")
    if len(df) > 0:
        logging.info(f"Колонки в DataFrame: {list(df.columns)}")
        logging.info(f"Первая запись report_date (до преобразования): {df.iloc[0]['report_date']} (тип: {type(df.iloc[0]['report_date'])})")
        logging.info(f"Первая запись report_hour (до преобразования): {df.iloc[0]['report_hour']} (тип: {type(df.iloc[0]['report_hour'])})")
        if len(df) > 1:
            logging.info(f"Диапазон report_date в данных: {df['report_date'].min()} - {df['report_date'].max()}")
        
        # Проверяем, что даты действительно восстановились
        if isinstance(df.iloc[0]['report_date'], str):
            logging.warning(f"report_date все еще строка после восстановления! Значение: {df.iloc[0]['report_date']}")
    
    # Подключаемся к ClickHouse
    client = Client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB,
        user='default',
        password=''
    )
    
    # Дефолтная дата для необязательных полей (ClickHouse не принимает None для Date)
    DEFAULT_DATE = date(1900, 1, 1)
    DEFAULT_DATETIME = datetime(1900, 1, 1, 0, 0, 0)
    
    # Функция для преобразования дат в правильный формат для ClickHouse
    def convert_to_date(value, default_date=DEFAULT_DATE):
        """Преобразует значение в date объект для ClickHouse, всегда возвращает валидную дату"""
        if pd.isna(value) or value is None:
            return default_date
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return pd.to_datetime(value).date()
            except:
                return default_date
        if isinstance(value, (int, float)):
            # Если это timestamp
            try:
                return datetime.fromtimestamp(value).date()
            except:
                return default_date
        return default_date
    
    def convert_to_datetime(value, default_datetime=DEFAULT_DATETIME):
        """Преобразует значение в datetime объект для ClickHouse, всегда возвращает валидный datetime"""
        if pd.isna(value) or value is None:
            return default_datetime
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str):
            try:
                return pd.to_datetime(value)
            except:
                return default_datetime
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value)
            except:
                return default_datetime
        return default_datetime
    
    # Подготавливаем данные для вставки
    records = []
    for idx, row in df.iterrows():
        # Логируем исходные значения для первых нескольких записей
        if idx < 3:
            logging.info(f"Запись #{idx} ДО преобразования:")
            logging.info(f"  report_date={row['report_date']} (тип: {type(row['report_date'])})")
            logging.info(f"  report_hour={row['report_hour']} (тип: {type(row['report_hour'])})")
            logging.info(f"  crm_order_date={row.get('crm_order_date', 'N/A')} (тип: {type(row.get('crm_order_date', None))})")
        
        # Преобразуем даты в правильный формат
        # ВАЖНО: используем реальные даты из данных, а не дефолтные
        # Дефолтные даты только для необязательных полей (CRM)
        report_date = convert_to_date(row['report_date'], default_date=None)  # Не используем дефолт для обязательного поля
        if report_date is None or report_date == DEFAULT_DATE:
            # Если получили дефолт, значит данные неправильные - логируем и используем реальную дату из данных
            logging.warning(f"Запись #{idx}: report_date получил дефолтное значение! Исходное значение: {row['report_date']}")
            # Пытаемся извлечь дату напрямую
            if isinstance(row['report_date'], str):
                try:
                    report_date = pd.to_datetime(row['report_date']).date()
                    logging.info(f"  Восстановлено из строки: {report_date}")
                except:
                    report_date = DEFAULT_DATE
            elif isinstance(row['report_date'], (int, float)):
                try:
                    report_date = datetime.fromtimestamp(row['report_date']).date()
                    logging.info(f"  Восстановлено из timestamp: {report_date}")
                except:
                    report_date = DEFAULT_DATE
            else:
                report_date = DEFAULT_DATE
        
        report_hour = convert_to_datetime(row['report_hour'], default_datetime=None)
        if report_hour is None or report_hour == DEFAULT_DATETIME:
            logging.warning(f"Запись #{idx}: report_hour получил дефолтное значение! Исходное значение: {row['report_hour']}")
            if isinstance(row['report_hour'], str):
                try:
                    report_hour = pd.to_datetime(row['report_hour'])
                    logging.info(f"  Восстановлено из строки: {report_hour}")
                except:
                    report_hour = DEFAULT_DATETIME
            else:
                report_hour = DEFAULT_DATETIME
        
        # Для необязательных полей используем дефолт если пусто
        crm_order_date = convert_to_date(row.get('crm_order_date', None))
        crm_manufacturing_date = convert_to_date(row.get('crm_manufacturing_date', None))
        
        # Логируем преобразованные значения для первых записей
        if idx < 3:
            logging.info(f"Запись #{idx} ПОСЛЕ преобразования:")
            logging.info(f"  report_date={report_date} (тип: {type(report_date)})")
            logging.info(f"  report_hour={report_hour} (тип: {type(report_hour)})")
        
        # Финальная проверка на всякий случай (не должна сработать, но для безопасности)
        assert report_date is not None, "report_date must not be None"
        assert report_hour is not None, "report_hour must not be None"
        assert crm_order_date is not None, "crm_order_date must not be None"
        assert crm_manufacturing_date is not None, "crm_manufacturing_date must not be None"
        
        record = (
            int(row['user_id']),
            int(row['prosthesis_id']),
            report_date,
            report_hour,
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
            crm_order_date,
            crm_manufacturing_date,
            float(row['avg_movements_per_hour']) if pd.notna(row['avg_movements_per_hour']) else 0.0,
            int(row['peak_activity_hour']) if pd.notna(row['peak_activity_hour']) else 0,
            1,  # total_usage_days
            datetime.now(),
            datetime.now()
        )
        records.append(record)
    
    # Детальная диагностика перед вставкой
    logging.info(f"Подготовлено {len(records)} записей для вставки в ClickHouse")
    
    # Проверяем каждую запись на наличие None в датах
    # Порядок полей в record (0-based):
    # 0: user_id, 1: prosthesis_id, 2: report_date, 3: report_hour,
    # 4-11: телеметрия и датчики, 12-14: CRM строки,
    # 15: crm_order_date, 16: crm_manufacturing_date,
    # 17-19: метрики, 20: created_at, 21: updated_at
    problematic_records = []
    for idx, record in enumerate(records):
        # Проверяем даты
        if record[2] is None or not isinstance(record[2], date):
            problematic_records.append((idx, 2, 'report_date', record[2], type(record[2])))
        if record[15] is None or not isinstance(record[15], date):
            problematic_records.append((idx, 15, 'crm_order_date', record[15], type(record[15])))
        if record[16] is None or not isinstance(record[16], date):
            problematic_records.append((idx, 16, 'crm_manufacturing_date', record[16], type(record[16])))
        # Проверяем datetime
        if record[3] is None or not isinstance(record[3], datetime):
            problematic_records.append((idx, 3, 'report_hour', record[3], type(record[3])))
        if record[20] is None or not isinstance(record[20], datetime):
            problematic_records.append((idx, 20, 'created_at', record[20], type(record[20])))
        if record[21] is None or not isinstance(record[21], datetime):
            problematic_records.append((idx, 21, 'updated_at', record[21], type(record[21])))
    
    if problematic_records:
        logging.error(f"Найдено {len(problematic_records)} проблемных значений дат/времени:")
        for rec_idx, pos, field_name, value, value_type in problematic_records[:10]:  # Показываем первые 10
            logging.error(f"  Запись #{rec_idx}, позиция {pos} ({field_name}): значение={value}, тип={value_type}")
        
        # Исправляем проблемные записи
        logging.info("Исправляю проблемные записи...")
        fixed_records = []
        for idx, record in enumerate(records):
            record_list = list(record)
            # Исправляем report_date (позиция 2)
            if record_list[2] is None or not isinstance(record_list[2], date):
                record_list[2] = DEFAULT_DATE
            # Исправляем report_hour (позиция 3)
            if record_list[3] is None or not isinstance(record_list[3], datetime):
                record_list[3] = DEFAULT_DATETIME
            # Исправляем crm_order_date (позиция 15)
            if record_list[15] is None or not isinstance(record_list[15], date):
                record_list[15] = DEFAULT_DATE
            # Исправляем crm_manufacturing_date (позиция 16)
            if record_list[16] is None or not isinstance(record_list[16], date):
                record_list[16] = DEFAULT_DATE
            # Исправляем created_at (позиция 20)
            if record_list[20] is None or not isinstance(record_list[20], datetime):
                record_list[20] = datetime.now()
            # Исправляем updated_at (позиция 21)
            if record_list[21] is None or not isinstance(record_list[21], datetime):
                record_list[21] = datetime.now()
            fixed_records.append(tuple(record_list))
        records = fixed_records
        logging.info(f"Исправлено {len(problematic_records)} проблемных значений")
    
    # Вставка данных (upsert через ReplacingMergeTree или DELETE + INSERT)
    if records:
        # Логируем структуру первой записи для проверки
        logging.info(f"Структура первой записи (для проверки порядка полей):")
        logging.info(f"  user_id={records[0][0]}, prosthesis_id={records[0][1]}")
        logging.info(f"  report_date={records[0][2]} (тип: {type(records[0][2])})")
        logging.info(f"  report_hour={records[0][3]} (тип: {type(records[0][3])})")
        logging.info(f"  crm_order_date={records[0][15]} (тип: {type(records[0][15])})")
        logging.info(f"  crm_manufacturing_date={records[0][16]} (тип: {type(records[0][16])})")
        logging.info(f"  created_at={records[0][20]} (тип: {type(records[0][20])})")
        logging.info(f"  updated_at={records[0][21]} (тип: {type(records[0][21])})")
        
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
