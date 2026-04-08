# Basket Craft Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python ETL pipeline that extracts order data from a remote MySQL database, loads it into a local Postgres container, and produces a `monthly_sales_summary` table with revenue, order count, and average order value grouped by product and month.

**Architecture:** `extract.py` connects to MySQL and loads raw rows into three Postgres staging tables (`stg_orders`, `stg_order_items`, `stg_products`). `transform.py` then runs `aggregate.sql` against Postgres to produce `monthly_sales_summary`. A shared `db.py` module owns all Postgres connection and schema-creation logic. Docker hosts Postgres on port 5433 (avoiding collision with MP01 on 5432).

**Tech Stack:** Python 3 (Anaconda venv at `.venv/`), mysql-connector-python, psycopg2-binary, python-dotenv, pytest, PostgreSQL 16 in Docker

---

## File Map

| File | Create / Modify | Responsibility |
|------|-----------------|----------------|
| `docker-compose.yml` | Create | Defines `basket_craft_db` Postgres container on port 5433 |
| `.env.example` | Create | Credential template committed to git |
| `.env` | Create (do not commit) | Real credentials loaded by python-dotenv |
| `requirements.txt` | Create | Python dependencies |
| `db.py` | Create | `get_pg_conn()` + `create_tables()` shared by extract + transform |
| `extract.py` | Create | Connect MySQL → TRUNCATE + reload three staging tables |
| `aggregate.sql` | Create | GROUP BY product + month → `monthly_sales_summary` |
| `transform.py` | Create | Open Postgres → execute `aggregate.sql` → print row count |
| `tests/test_pipeline.py` | Create | Integration tests for schema, staging counts, aggregation, idempotency |

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.env`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `requirements.txt`**

```
mysql-connector-python
psycopg2-binary
python-dotenv
pytest
```

- [ ] **Step 2: Install dependencies**

```bash
.venv/Scripts/pip install mysql-connector-python psycopg2-binary python-dotenv pytest
```

Expected: packages install with no errors. If `.venv` doesn't exist yet: `python -m venv .venv` first.

- [ ] **Step 3: Create `.env.example`**

```
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DATABASE=

PG_HOST=localhost
PG_PORT=5433
PG_DB=basket_craft
PG_USER=postgres
PG_PASSWORD=postgres
```

- [ ] **Step 4: Create `.env` with real credentials**

```
MYSQL_HOST=db.isba.co
MYSQL_PORT=3306
MYSQL_USER=analyst
MYSQL_PASSWORD=go_lions
MYSQL_DATABASE=basket_craft

PG_HOST=localhost
PG_PORT=5433
PG_DB=basket_craft
PG_USER=postgres
PG_PASSWORD=postgres
```

- [ ] **Step 5: Verify `.env` is in `.gitignore`**

Open `.gitignore`. Confirm `.env` appears in the file. If it does not, add it as a new line.

- [ ] **Step 6: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    container_name: basket_craft_db
    environment:
      POSTGRES_DB: basket_craft
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5433:5432"
    volumes:
      - pgdata_basket_craft:/var/lib/postgresql/data

volumes:
  pgdata_basket_craft:
```

- [ ] **Step 7: Start Postgres container**

```bash
docker compose up -d
```

Expected output includes `basket_craft_db  Started` or `Running`.

- [ ] **Step 8: Verify Postgres is reachable**

```bash
docker exec -it basket_craft_db psql -U postgres -d basket_craft -c "SELECT 1;"
```

Expected:
```
 ?column?
----------
        1
(1 row)
```

- [ ] **Step 9: Commit scaffolding**

```bash
git add docker-compose.yml requirements.txt .env.example
git commit -m "feat: add project scaffolding and Docker setup"
```

---

## Task 2: Shared database module (`db.py`)

**Files:**
- Create: `db.py`
- Create: `tests/test_pipeline.py` (first test only)

- [ ] **Step 1: Write the failing test for table creation**

Create `tests/test_pipeline.py`:

```python
import pytest
import psycopg2
from db import get_pg_conn, create_tables


@pytest.fixture(scope="module")
def pg_conn():
    conn = get_pg_conn()
    create_tables(conn)
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pipeline.py::test_staging_tables_exist -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Create `db.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pipeline.py::test_staging_tables_exist -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_pipeline.py
git commit -m "feat: add db.py with connection helper and schema creation"
```

---

## Task 3: Extract — MySQL to Postgres staging (`extract.py`)

**Files:**
- Create: `extract.py`
- Modify: `tests/test_pipeline.py` (add extraction tests)

- [ ] **Step 1: Add extraction tests to `tests/test_pipeline.py`**

Add the new imports at the **top** of the file (after the existing imports), then append the fixture and three tests at the bottom. The full updated file should look like this:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pipeline.py::test_load_orders_returns_rows -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'extract'`

- [ ] **Step 3: Create `extract.py`**

```python
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

    load_orders(mysql_conn, pg_conn)
    load_order_items(mysql_conn, pg_conn)
    load_products(mysql_conn, pg_conn)

    mysql_conn.close()
    pg_conn.close()
    print("Extract complete.")
```

- [ ] **Step 4: Run extraction tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pipeline.py::test_load_orders_returns_rows tests/test_pipeline.py::test_load_order_items_returns_rows tests/test_pipeline.py::test_load_products_returns_rows -v
```

Expected: all 3 PASS. If `test_load_orders_returns_rows` fails with a column error, run `DESCRIBE orders` in DBeaver and adjust the SELECT columns in `load_orders()` to match.

- [ ] **Step 5: Commit**

```bash
git add extract.py tests/test_pipeline.py
git commit -m "feat: add extract.py — MySQL to Postgres staging"
```

---

## Task 4: Transformation SQL (`aggregate.sql`)

**Files:**
- Create: `aggregate.sql`

- [ ] **Step 1: Create `aggregate.sql`**

```sql
TRUNCATE monthly_sales_summary;

INSERT INTO monthly_sales_summary (
    product_name,
    sale_month,
    total_revenue,
    order_count,
    avg_order_value
)
SELECT
    p.product_name,
    DATE_TRUNC('month', o.created_at)::DATE        AS sale_month,
    SUM(oi.price_usd)                              AS total_revenue,
    COUNT(DISTINCT o.order_id)                     AS order_count,
    ROUND(SUM(oi.price_usd) /
          COUNT(DISTINCT o.order_id), 2)           AS avg_order_value
FROM stg_orders o
JOIN stg_order_items  oi ON o.order_id    = oi.order_id
JOIN stg_products      p ON oi.product_id  = p.product_id
GROUP BY p.product_name, DATE_TRUNC('month', o.created_at)
ORDER BY sale_month, product_name;
```

- [ ] **Step 2: Manually test the SQL in psql**

Connect to Postgres and run it directly to verify no syntax errors:

```bash
docker exec -it basket_craft_db psql -U postgres -d basket_craft -f /dev/stdin < aggregate.sql
```

Expected: `INSERT 0 N` where N > 0. If N = 0, staging tables may be empty — run `extract.py` first.

- [ ] **Step 3: Commit**

```bash
git add aggregate.sql
git commit -m "feat: add aggregate.sql for monthly sales summary"
```

---

## Task 5: Transform runner (`transform.py`)

**Files:**
- Create: `transform.py`
- Modify: `tests/test_pipeline.py` (add aggregation + idempotency tests)

- [ ] **Step 1: Add aggregation tests to `tests/test_pipeline.py`**

Add `from transform import run_aggregation` to the imports at the top of the file, then append the three tests at the bottom. The final complete file:

```python
import os
import mysql.connector
import pytest
import psycopg2
from db import get_pg_conn, create_tables
from extract import load_orders, load_order_items, load_products
from transform import run_aggregation


@pytest.fixture(scope="module")
def pg_conn():
    conn = get_pg_conn()
    create_tables(conn)
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


def test_aggregation_produces_rows(pg_conn):
    count = run_aggregation(pg_conn)
    assert count > 0


def test_summary_has_required_columns(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT product_name, sale_month, total_revenue,
                   order_count, avg_order_value
            FROM monthly_sales_summary
            LIMIT 1
        """)
        row = cur.fetchone()
    assert row is not None


def test_pipeline_is_idempotent(mysql_conn, pg_conn):
    load_orders(mysql_conn, pg_conn)
    load_order_items(mysql_conn, pg_conn)
    load_products(mysql_conn, pg_conn)
    count_first = run_aggregation(pg_conn)

    load_orders(mysql_conn, pg_conn)
    load_order_items(mysql_conn, pg_conn)
    load_products(mysql_conn, pg_conn)
    count_second = run_aggregation(pg_conn)

    assert count_first == count_second
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pipeline.py::test_aggregation_produces_rows -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'transform'`

- [ ] **Step 3: Create `transform.py`**

```python
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
```

- [ ] **Step 4: Run all tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v
```

Expected: all 7 tests PASS:
```
test_staging_tables_exist          PASSED
test_load_orders_returns_rows      PASSED
test_load_order_items_returns_rows PASSED
test_load_products_returns_rows    PASSED
test_aggregation_produces_rows     PASSED
test_summary_has_required_columns  PASSED
test_pipeline_is_idempotent        PASSED
```

- [ ] **Step 5: Commit**

```bash
git add transform.py tests/test_pipeline.py
git commit -m "feat: add transform.py and full pipeline test suite"
```

---

## Task 6: End-to-end verification

**Files:** None — manual verification only.

- [ ] **Step 1: Reset and run the full pipeline from scratch**

```bash
docker compose down -v
docker compose up -d
.venv/Scripts/python.exe extract.py
.venv/Scripts/python.exe transform.py
```

Expected output:
```
Connected to MySQL
stg_orders:        N rows loaded
stg_order_items:   N rows loaded
stg_products:      N rows loaded
Extract complete.
monthly_sales_summary: N rows
Transform complete.
```

- [ ] **Step 2: Run the business query**

```bash
docker exec -it basket_craft_db psql -U postgres -d basket_craft -c "
SELECT product_name, sale_month, total_revenue, order_count, avg_order_value
FROM monthly_sales_summary
ORDER BY sale_month, product_name
LIMIT 20;
"
```

Expected: a table with one row per product per month showing revenue, order counts, and average order values. All three metrics should be non-zero.

- [ ] **Step 3: Spot-check one row**

Pick one product + month from the output. Verify total_revenue manually:

```bash
docker exec -it basket_craft_db psql -U postgres -d basket_craft -c "
SELECT SUM(oi.price_usd) AS manual_revenue
FROM stg_order_items oi
JOIN stg_orders o ON oi.order_id = o.order_id
JOIN stg_products p ON oi.product_id = p.product_id
WHERE p.product_name = '<product from step 2>'
AND DATE_TRUNC('month', o.created_at) = '<sale_month from step 2>';
"
```

Expected: `manual_revenue` matches `total_revenue` from `monthly_sales_summary`.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: complete basket-craft ETL pipeline"
```

---

## Assumptions to resolve before running

If any step fails due to a column name mismatch, run:

```bash
docker exec -it basket_craft_db psql -U postgres -d basket_craft -c "\d stg_orders"
```

Then open DBeaver, connect to `db.isba.co`, and run `DESCRIBE orders` / `DESCRIBE order_items` to compare. Update the `SELECT` statements in `extract.py` and the `CREATE TABLE` statements in `db.py` to match the real column names.
