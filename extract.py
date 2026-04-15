import os
import mysql.connector
from dotenv import load_dotenv
from db import get_pg_conn, create_tables

load_dotenv()


def get_mysql_conn():
    """Return a live mysql-connector connection to the remote basket_craft DB."""
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE')
    )


def load_orders(mysql_conn, pg_conn):
    """SELECT all orders from MySQL and reload stg_orders in Postgres."""
    with mysql_conn.cursor() as cur:
        cur.execute("""
            SELECT order_id, created_at, website_session_id, user_id,
                   primary_product_id, items_purchased, price_usd, cogs_usd
            FROM orders
        """)
        rows = cur.fetchall()
    with pg_conn.cursor() as cur:
        cur.execute("TRUNCATE stg_orders")
        cur.executemany(
            "INSERT INTO stg_orders VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            rows
        )
        pg_conn.commit()
    print(f"stg_orders:      {len(rows):>6} rows loaded")
    return len(rows)


def load_order_items(mysql_conn, pg_conn):
    """SELECT all order_items from MySQL and reload stg_order_items in Postgres."""
    with mysql_conn.cursor() as cur:
        cur.execute("""
            SELECT order_item_id, created_at, order_id, product_id,
                   is_primary_item, price_usd, cogs_usd
            FROM order_items
        """)
        rows = cur.fetchall()
    with pg_conn.cursor() as cur:
        cur.execute("TRUNCATE stg_order_items")
        cur.executemany(
            "INSERT INTO stg_order_items VALUES (%s,%s,%s,%s,%s,%s,%s)",
            rows
        )
        pg_conn.commit()
    print(f"stg_order_items: {len(rows):>6} rows loaded")
    return len(rows)


def load_products(mysql_conn, pg_conn):
    """SELECT all products from MySQL and reload stg_products in Postgres."""
    with mysql_conn.cursor() as cur:
        cur.execute("SELECT product_id, created_at, product_name FROM products")
        rows = cur.fetchall()
    with pg_conn.cursor() as cur:
        cur.execute("TRUNCATE stg_products")
        cur.executemany(
            "INSERT INTO stg_products VALUES (%s,%s,%s)",
            rows
        )
        pg_conn.commit()
    print(f"stg_products:    {len(rows):>6} rows loaded")
    return len(rows)


if __name__ == "__main__":
    try:
        mysql_conn = get_mysql_conn()
        print("Connected to MySQL")
    except Exception as e:
        print(f"MySQL connection failed: {e}")
        raise SystemExit(1)

    pg_conn = get_pg_conn()
    create_tables(pg_conn)
    pg_conn.commit()

    load_orders(mysql_conn, pg_conn)
    load_order_items(mysql_conn, pg_conn)
    load_products(mysql_conn, pg_conn)

    mysql_conn.close()
    pg_conn.close()
    print("Extract complete.")
