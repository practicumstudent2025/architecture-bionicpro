FROM apache/airflow:2.7.0

USER airflow

# Копирование requirements
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Копирование entrypoint скрипта
COPY entrypoint.sh /entrypoint.sh
USER root
RUN chmod +x /entrypoint.sh
USER airflow

# Копирование DAG файлов
COPY dags/ /opt/airflow/dags/

# Использование entrypoint для автоматической инициализации
ENTRYPOINT ["/entrypoint.sh"]
