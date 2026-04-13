# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Python Environment

Use a Python virtual environment to manage dependencies. The venv is at `.venv/`. Always use the venv interpreter explicitly:

```bash
.venv/Scripts/python.exe          # run scripts
.venv/Scripts/pip install <pkg>   # install packages
```

## Common Commands

```bash
# Start/stop Postgres container
docker compose up -d
docker compose down

# Run the full pipeline
.venv/Scripts/python.exe extract.py
.venv/Scripts/python.exe transform.py

# Run all tests
.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v

# Run a single test
.venv/Scripts/python.exe -m pytest tests/test_pipeline.py::test_staging_tables_exist -v

# Connect to Postgres via psql
docker exec -it basket_craft_db psql -U postgres -d basket_craft
```

## Architecture

This is a two-step ETL pipeline:

1. **`extract.py`** — connects to the remote MySQL source (`db.isba.co/basket_craft`), reads `orders`, `order_items`, and `products`, then TRUNCATEs and reloads three Postgres staging tables (`stg_orders`, `stg_order_items`, `stg_products`).
2. **`transform.py`** — executes `aggregate.sql` against Postgres to populate `monthly_sales_summary` (revenue, order count, avg order value grouped by product and month).

Shared connection and schema logic lives in **`db.py`** (`get_pg_conn()`, `create_tables()`). Both scripts import from it.

## Database

- **Source:** MySQL at `db.isba.co:3306`, database `basket_craft`
- **Destination:** Postgres 16 in Docker, port `5433` (avoids collision with other local Postgres instances on 5432), database `basket_craft`
- **Container name:** `basket_craft_db`
- **Connection string:** `postgresql://postgres:postgres@localhost:5433/basket_craft`

## Credentials

All credentials are loaded from `.env` via `python-dotenv`. Never hardcode them. `.env` is gitignored. Use `.env.example` as the template.

## Tests

`tests/test_pipeline.py` contains 7 integration tests that hit the live MySQL and Postgres databases. They run in order and share module-scoped fixtures (`pg_conn`, `mysql_conn`). The idempotency test runs the full pipeline twice and takes ~4 minutes. `conftest.py` at the project root anchors pytest's import path so `from db import ...` works correctly.
