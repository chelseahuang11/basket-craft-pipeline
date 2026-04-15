import os
import psycopg2
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()


def get_rds_conn():
    return psycopg2.connect(
        host=os.getenv('RDS_HOST'),
        port=int(os.getenv('RDS_PORT', 5432)),
        dbname=os.getenv('RDS_DATABASE'),
        user=os.getenv('RDS_USER'),
        password=os.getenv('RDS_PASSWORD'),
        connect_timeout=30,
    )


def get_snowflake_conn():
    return snowflake.connector.connect(
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        role=os.getenv('SNOWFLAKE_ROLE'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA'),
    )


def get_tables(rds_conn):
    """Discover all tables in the RDS public schema."""
    with rds_conn.cursor() as cur:
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        return [row[0] for row in cur.fetchall()]


def load_table(rds_conn, sf_conn, table):
    """Read table from RDS into a DataFrame and load into Snowflake raw schema."""
    # Read full table from RDS
    df = pd.read_sql(f'SELECT * FROM {table}', rds_conn)

    # Uppercase all column names so write_pandas creates them as native Snowflake
    # uppercase identifiers (unquoted). Lowercase columns would be stored quoted
    # ("order_item_id"), making them case-sensitive and unreachable by dbt's SQL.
    df.columns = [c.upper() for c in df.columns]

    # Truncate target table in Snowflake before loading (idempotency)
    with sf_conn.cursor() as cur:
        cur.execute(f'TRUNCATE TABLE IF EXISTS {table}')

    # write_pandas serializes to Parquet, stages, and fires COPY INTO internally
    success, nchunks, nrows, _ = write_pandas(
        conn=sf_conn,
        df=df,
        table_name=table.upper(),   # Snowflake stores unquoted names in uppercase
        database=os.getenv('SNOWFLAKE_DATABASE').upper(),
        schema=os.getenv('SNOWFLAKE_SCHEMA').upper(),
        auto_create_table=True,
        overwrite=True,
    )

    print(f'{table:<25} {nrows:>8} rows loaded', flush=True)
    return nrows


if __name__ == '__main__':
    try:
        rds_conn = get_rds_conn()
        print('Connected to RDS', flush=True)
    except Exception as e:
        print(f'RDS connection failed: {e}')
        raise SystemExit(1)

    try:
        sf_conn = get_snowflake_conn()
        print('Connected to Snowflake', flush=True)
    except Exception as e:
        print(f'Snowflake connection failed: {e}')
        raise SystemExit(1)

    tables = get_tables(rds_conn)
    print(f'\nLoading {len(tables)} tables into Snowflake basket_craft.raw...\n', flush=True)

    total_rows = 0
    for table in tables:
        rows = load_table(rds_conn, sf_conn, table)
        total_rows += rows

    rds_conn.close()
    sf_conn.close()
    print(f'\nDone. {total_rows:,} total rows loaded into Snowflake.', flush=True)
