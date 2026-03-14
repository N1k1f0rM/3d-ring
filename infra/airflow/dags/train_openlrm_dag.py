import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from train.openlrm.train_lrm import train

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def train_wrapper(**context):
    config_path = "/opt/airflow/project/configs/OpenLRM/train/default.yaml"
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config {config_path} not found.")
    run_id = train(config_path)
    context["task_instance"].xcom_push(key="run_id", value=run_id)


with DAG(
    dag_id="train_openlrm",
    default_args=default_args,
    description="Train OpenLRM model with Hydra config",
    schedule_interval=None,
    catchup=False,
    tags=["training", "openlrm"],
) as dag:

    train_task = PythonOperator(
        task_id="run_training",
        python_callable=train_wrapper,
        provide_context=True,
    )
