import os
import mysql.connector
import pytest
import psycopg2
from db import get_pg_conn, create_tables
from extract import load_orders, load_order_items, load_products


@pytest.fixture(scope="module")
def pg_conn():
    conn = get_pg_conn()
    create_tables(conn)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def mysql_conn():
    conn = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE')
    )
    yield conn
    conn.close()


def test_staging_tables_exist(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN (
                'stg_orders', 'stg_order_items',
                'stg_products', 'monthly_sales_summary'
            )
        """)
        tables = {row[0] for row in cur.fetchall()}
    assert tables == {
        'stg_orders', 'stg_order_items',
        'stg_products', 'monthly_sales_summary'
    }


def test_load_orders_returns_rows(mysql_conn, pg_conn):
    count = load_orders(mysql_conn, pg_conn)
    assert count > 0


def test_load_order_items_returns_rows(mysql_conn, pg_conn):
    count = load_order_items(mysql_conn, pg_conn)
    assert count > 0


def test_load_products_returns_rows(mysql_conn, pg_conn):
    count = load_products(mysql_conn, pg_conn)
    assert count > 0
