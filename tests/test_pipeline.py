import pytest
import psycopg2
from db import get_pg_conn, create_tables


@pytest.fixture(scope="module")
def pg_conn():
    conn = get_pg_conn()
    create_tables(conn)
    conn.commit()
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
