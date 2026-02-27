#!/bin/bash
set -e

echo "=== Airflow Init Script ==="

python << END
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Параметры подключения к стандартной базе postgres
conn = psycopg2.connect(
    host="postgres",
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    database="postgres"
)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()

dbname = os.environ.get("AIRFLOW_POSTGRES_DB", "airflow_db")
print(f"Checking if database '{dbname}' exists...")
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
exists = cur.fetchone()
if not exists:
    print(f"Creating database '{dbname}'...")
    cur.execute(f'CREATE DATABASE {dbname} OWNER {os.environ["POSTGRES_USER"]}')
else:
    print(f"Database '{dbname}' already exists.")
cur.close()
conn.close()
END

echo "Running Airflow database migrations..."
airflow db migrate

if ! airflow users list | grep -q "${_AIRFLOW_WWW_USER_USERNAME:-airflow}"; then
    echo "Creating admin user..."
    airflow users create \
        --username "${_AIRFLOW_WWW_USER_USERNAME:-airflow}" \
        --password "${_AIRFLOW_WWW_USER_PASSWORD:-airflow}" \
        --firstname Admin \
        --lastname User \
        --role Admin \
        --email admin@example.com
fi

echo "Airflow init completed successfully."
