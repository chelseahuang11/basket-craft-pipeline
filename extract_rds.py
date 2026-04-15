import io
import csv
import os
import time
import mysql.connector
import psycopg2
from dotenv import load_dotenv

load_dotenv()

MYSQL_TO_PG = {
    'int':        'INTEGER',
    'bigint':     'BIGINT',
    'smallint':   'SMALLINT',
    'tinyint':    'SMALLINT',
    'varchar':    'TEXT',
    'char':       'TEXT',
    'text':       'TEXT',
    'mediumtext': 'TEXT',
    'longtext':   'TEXT',
    'decimal':    'NUMERIC',
    'numeric':    'NUMERIC',
    'float':      'DOUBLE PRECISION',
    'double':     'DOUBLE PRECISION',
    'date':       'DATE',
    'datetime':   'TIMESTAMP',
    'timestamp':  'TIMESTAMP',
    'bit':        'SMALLINT',
}


def get_mysql_conn():
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE')
    )


def get_rds_conn():
    return psycopg2.connect(
        host=os.getenv('RDS_HOST'),
        port=int(os.getenv('RDS_PORT', 5432)),
        dbname=os.getenv('RDS_DATABASE'),
        user=os.getenv('RDS_USER'),
        password=os.getenv('RDS_PASSWORD'),
        connect_timeout=30,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )


def get_column_defs(mysql_conn, table):
    with mysql_conn.cursor() as cur:
        cur.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, COLUMN_KEY
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, (os.getenv('MYSQL_DATABASE'), table))
        return cur.fetchall()


def create_table_in_rds(rds_conn, table, col_defs):
    cols = []
    for col_name, data_type, col_key in col_defs:
        pg_type = MYSQL_TO_PG.get(data_type.lower(), 'TEXT')
        pk = ' PRIMARY KEY' if col_key == 'PRI' else ''
        cols.append(f'    {col_name} {pg_type}{pk}')
    ddl = f'CREATE TABLE {table} (\n' + ',\n'.join(cols) + '\n)'
    with rds_conn.cursor() as cur:
        cur.execute(f'DROP TABLE IF EXISTS {table}')
        cur.execute(ddl)
        rds_conn.commit()


def rds_row_count(rds_conn, table):
    """Return current row count for table in RDS, or -1 if table doesn't exist."""
    try:
        with rds_conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            return cur.fetchone()[0]
    except psycopg2.Error:
        rds_conn.rollback()
        return -1


def load_table_copy(mysql_conn, rds_conn, table, col_defs):
    """Load all rows using COPY FROM — faster and more reliable than INSERT for large tables."""
    col_names = [c[0] for c in col_defs]
    cols_str = ', '.join(col_names)

    print(f'{table:<25} fetching from MySQL...', flush=True)
    with mysql_conn.cursor() as mysql_cur:
        mysql_cur.execute(f'SELECT {cols_str} FROM `{table}`')
        rows = mysql_cur.fetchall()

    # Write rows to an in-memory CSV buffer (handles NULLs and special chars)
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    for row in rows:
        writer.writerow(['' if v is None else v for v in row])
    buf.seek(0)

    print(f'{table:<25} loading {len(rows)} rows into RDS...', flush=True)
    for attempt in range(3):
        try:
            with rds_conn.cursor() as cur:
                cur.copy_expert(
                    f"COPY {table} ({cols_str}) FROM STDIN WITH (FORMAT CSV, NULL '')",
                    buf
                )
            rds_conn.commit()
            break
        except psycopg2.OperationalError as e:
            if attempt == 2:
                raise
            print(f'  connection dropped, reconnecting (attempt {attempt + 1})...', flush=True)
            time.sleep(2)
            rds_conn = get_rds_conn()
            buf.seek(0)

    print(f'{table:<25} {len(rows):>8} rows loaded', flush=True)
    return len(rows), rds_conn


if __name__ == '__main__':
    try:
        mysql_conn = get_mysql_conn()
        print('Connected to MySQL', flush=True)
    except Exception as e:
        print(f'MySQL connection failed: {e}')
        raise SystemExit(1)

    try:
        rds_conn = get_rds_conn()
        print('Connected to RDS', flush=True)
    except Exception as e:
        print(f'RDS connection failed: {e}')
        raise SystemExit(1)

    with mysql_conn.cursor() as cur:
        cur.execute('SHOW TABLES')
        tables = [r[0] for r in cur.fetchall()]

    # Check MySQL row counts upfront
    mysql_counts = {}
    with mysql_conn.cursor() as cur:
        for table in tables:
            cur.execute(f'SELECT COUNT(*) FROM `{table}`')
            mysql_counts[table] = cur.fetchone()[0]

    print(f'\nLoading {len(tables)} tables into RDS...\n', flush=True)

    for table in tables:
        rds_count = rds_row_count(rds_conn, table)
        if rds_count == mysql_counts[table]:
            print(f'{table:<25} {rds_count:>8} rows already loaded, skipping', flush=True)
            continue

        col_defs = get_column_defs(mysql_conn, table)
        create_table_in_rds(rds_conn, table, col_defs)
        _, rds_conn = load_table_copy(mysql_conn, rds_conn, table, col_defs)

    mysql_conn.close()
    rds_conn.close()
    print('\nExtract to RDS complete.', flush=True)
