from db import get_pg_conn


def run_aggregation(pg_conn):
    """Execute aggregate.sql and return the row count of monthly_sales_summary."""
    with open('aggregate.sql', 'r') as f:
        sql = f.read()
    with pg_conn.cursor() as cur:
        cur.execute(sql)
        pg_conn.commit()
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM monthly_sales_summary")
        count = cur.fetchone()[0]
    print(f"monthly_sales_summary: {count} rows")
    return count


if __name__ == "__main__":
    try:
        pg_conn = get_pg_conn()
    except Exception as e:
        print(f"Postgres connection failed: {e}")
        raise SystemExit(1)

    try:
        count = run_aggregation(pg_conn)
        if count == 0:
            print("WARNING: monthly_sales_summary is empty — check staging tables")
    except Exception as e:
        pg_conn.rollback()
        print(f"Aggregation failed: {e}")
        raise SystemExit(1)
    finally:
        pg_conn.close()

    print("Transform complete.")
