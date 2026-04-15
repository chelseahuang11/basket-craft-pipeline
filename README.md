# Basket Craft Pipeline

An ETL pipeline that extracts order data from a remote MySQL database, loads it into a local PostgreSQL container, and produces a `monthly_sales_summary` table with revenue, order count, and average order value grouped by product and month.

## What It Does

```
MySQL (db.isba.co)          Local PostgreSQL (Docker)
─────────────────           ────────────────────────────────────────
orders              ──►     stg_orders
order_items         ──►     stg_order_items      ──►  monthly_sales_summary
products            ──►     stg_products
```

1. **Extract** — `extract.py` pulls all rows from three MySQL tables into Postgres staging tables
2. **Transform** — `transform.py` runs `aggregate.sql` to group sales by product and month

## Setup

**Prerequisites:** Python 3, Docker Desktop

**1. Clone and create a virtual environment**
```bash
git clone https://github.com/chelseahuang11/basket-craft-pipeline.git
cd basket-craft-pipeline
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

**2. Add credentials**

Copy `.env.example` to `.env` and fill in the MySQL credentials:
```bash
cp .env.example .env
```

```
MYSQL_HOST=db.isba.co
MYSQL_PORT=3306
MYSQL_USER=<your_user>
MYSQL_PASSWORD=<your_password>
MYSQL_DATABASE=basket_craft

PG_HOST=localhost
PG_PORT=5433
PG_DB=basket_craft
PG_USER=postgres
PG_PASSWORD=postgres
```

**3. Start Postgres**
```bash
docker compose up -d
```

## Running the Pipeline

```bash
.venv/Scripts/python.exe extract.py
.venv/Scripts/python.exe transform.py
```

Expected output:
```
Connected to MySQL
stg_orders:        32313 rows loaded
stg_order_items:   40025 rows loaded
stg_products:          4 rows loaded
Extract complete.
monthly_sales_summary: 94 rows
Transform complete.
```

## Running Tests

```bash
.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v
```

7 integration tests covering table creation, staging loads, aggregation output, column structure, and pipeline idempotency. Tests hit live databases — the full suite takes ~4 minutes.

## AWS RDS (Session 02)

The raw Basket Craft tables are also loaded into a cloud PostgreSQL database on AWS RDS.

- **Endpoint:** `basket-craft-db.cqfauycsyk1q.us-east-1.rds.amazonaws.com`
- **Port:** `5432`
- **Database:** `basket_craft`
- **Username:** `student`

To load all 8 raw tables from MySQL into RDS:

```bash
.venv/Scripts/python.exe extract_rds.py
```

The script is resumable — if interrupted, re-running it skips tables that already have the correct row count.

| Table | Rows |
|---|---|
| employees | 20 |
| order_item_refunds | 1,731 |
| order_items | 40,025 |
| orders | 32,313 |
| products | 4 |
| users | 31,696 |
| website_pageviews | 1,188,124 |
| website_sessions | 472,871 |

## Querying the Local Results

```bash
docker exec -it basket_craft_db psql -U postgres -d basket_craft
```

```sql
SELECT product_name, sale_month, total_revenue, order_count, avg_order_value
FROM monthly_sales_summary
ORDER BY sale_month, product_name
LIMIT 20;
```
