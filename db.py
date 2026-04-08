import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_pg_conn():
    """Return a live psycopg2 connection to the local Postgres container."""
    return psycopg2.connect(
        host=os.getenv('PG_HOST', 'localhost'),
        port=int(os.getenv('PG_PORT', 5433)),
        dbname=os.getenv('PG_DB', 'basket_craft'),
        user=os.getenv('PG_USER', 'postgres'),
        password=os.getenv('PG_PASSWORD', 'postgres')
    )


def create_tables(conn):
    """Create all staging and summary tables if they do not exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stg_orders (
                order_id            INT PRIMARY KEY,
                created_at          TIMESTAMP,
                website_session_id  INT,
                user_id             INT,
                primary_product_id  INT,
                items_purchased     INT,
                price_usd           NUMERIC(10,2),
                cogs_usd            NUMERIC(10,2)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stg_order_items (
                order_item_id   INT PRIMARY KEY,
                created_at      TIMESTAMP,
                order_id        INT,
                product_id      INT,
                is_primary_item SMALLINT,
                price_usd       NUMERIC(10,2),
                cogs_usd        NUMERIC(10,2)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stg_products (
                product_id   INT PRIMARY KEY,
                created_at   TIMESTAMP,
                product_name TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS monthly_sales_summary (
                product_name    TEXT,
                sale_month      DATE,
                total_revenue   NUMERIC(12,2),
                order_count     INT,
                avg_order_value NUMERIC(10,2),
                PRIMARY KEY (product_name, sale_month)
            )
        """)
        conn.commit()
