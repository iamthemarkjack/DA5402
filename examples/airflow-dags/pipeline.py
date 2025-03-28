import datetime
import pendulum
import os

import requests
from airflow.decorators import dag, task
from airflow.providers.mysql.hooks.mysql import MySqlHook
from airflow.providers.mysql.operators.mysql import MySqlOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.postgres.operators.postgres import PostgresOperator

import logging
log = logging.getLogger(__name__)

@dag(
    dag_id="a1_process-employees",
    schedule_interval="0 0 * * *",
    start_date=pendulum.datetime(2021, 1, 1, tz="UTC"),
    catchup=False,
    dagrun_timeout=datetime.timedelta(minutes=60),
    tags=['demo'],
)
def ProcessEmployees():
    create_employees_table = PostgresOperator( # MySqlOperator(
        task_id="create_employees_table",
        postgres_conn_id="tutorial_pg_conn",
        #mysql_conn_id = "nas_db",
        sql="""
            CREATE TABLE IF NOT EXISTS employees (
                \"Serial Number\" NUMERIC PRIMARY KEY,
                \"Company Name\" TEXT,
                \"Employee Markme\" TEXT,
                \"Description\" TEXT,
                \"Leave\" INTEGER
            );""",
    )

    create_employees_temp_table = PostgresOperator( # MySqlOperator(
        task_id="create_employees_temp_table",
        postgres_conn_id="tutorial_pg_conn",
        #mysql_conn_id = "nas_db",
        sql="""
            DROP TABLE IF EXISTS employees_temp;
            CREATE TABLE employees_temp (
                \"Serial Number\" NUMERIC PRIMARY KEY,
                \"Company Name\" TEXT,
                \"Employee Markme\" TEXT,
                \"Description\" TEXT,
                \"Leave\" INTEGER
            );""",
    )

    @task
    def get_data():
        # NOTE: configure this as appropriate for your airflow environment
        data_path = "/opt/airflow/dags/files/employees.csv"
        os.makedirs(os.path.dirname(data_path), exist_ok=True)

        url = "https://raw.githubusercontent.com/apache/airflow/main/docs/apache-airflow/tutorial/pipeline_example.csv"

        response = requests.request("GET", url)

        with open(data_path, "w") as file:
            file.write(response.text)

        postgres_hook = PostgresHook(postgres_conn_id="tutorial_pg_conn")
        conn = postgres_hook.get_conn()
        #mysql_hook = MySqlHook(mysql_conn_id = "nas_db")
        #conn = mysql_hook.get_conn()

        cur = conn.cursor()
        #cur.execute("LOAD DATA LOCAL INFILE '%s' INTO TABLE employees_temp COLUMNS TERMINATED BY ','" % data_path)
        with open(data_path, "r") as file:
            cur.copy_expert(
                "COPY employees_temp FROM STDIN WITH CSV HEADER DELIMITER AS ',' QUOTE '\"'",
                file,
            )
        conn.commit()

    @task
    def merge_data():
        query = """
            INSERT INTO employees
            SELECT *
            FROM (
                SELECT DISTINCT *
                FROM employees_temp
            ) t
        """
        """ON CONFLICT ("Serial Number") DO UPDATE
            SET
              "Employee Markme" = excluded."Employee Markme",
              "Description" = excluded."Description",
              "Leave" = excluded."Leave";
        """

        try:
            postgres_hook = PostgresHook(postgres_conn_id="tutorial_pg_conn")
            conn = postgres_hook.get_conn()
            #mysql_hook = MySqlHook(mysql_conn_id = "nas_db")
            #conn = mysql_hook.get_conn()
            cur = conn.cursor()
            cur.execute(query)
            conn.commit()
            return 0
        except Exception as e:
            log.error(e)
            return 1

    [create_employees_table, create_employees_temp_table] >> get_data() >> merge_data()


dag = ProcessEmployees()
