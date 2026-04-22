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
# Start/stop local Postgres container
docker compose up -d
docker compose down

# Run the local pipeline (MySQL → Docker Postgres → monthly_sales_summary)
.venv/Scripts/python.exe extract.py
.venv/Scripts/python.exe transform.py

# Load all 8 raw tables into AWS RDS
.venv/Scripts/python.exe extract_rds.py

# Load all 8 raw tables from RDS into Snowflake
.venv/Scripts/python.exe load_snowflake.py

# Run dbt (uses run_dbt.py wrapper to inject .env credentials)
.venv/Scripts/python.exe run_dbt.py run        # build all models in Snowflake
.venv/Scripts/python.exe run_dbt.py test       # run data tests
.venv/Scripts/python.exe run_dbt.py docs generate  # generate lineage graph
.venv/Scripts/python.exe run_dbt.py docs serve     # serve docs at localhost:8080

# Run all tests
.venv/Scripts/python.exe -m pytest tests/test_pipeline.py -v

# Connect to local Postgres via psql
docker exec -it basket_craft_db psql -U postgres -d basket_craft
```

## Architecture

This project has two destinations:

**Local pipeline (Session 01):**
1. **`extract.py`** — connects to MySQL (`db.isba.co/basket_craft`), reads `orders`, `order_items`, and `products`, reloads three Postgres staging tables (`stg_orders`, `stg_order_items`, `stg_products`).
2. **`transform.py`** — executes `aggregate.sql` against local Postgres to populate `monthly_sales_summary`.

Shared connection and schema logic lives in **`db.py`** (`get_pg_conn()`, `create_tables()`).

**Cloud pipeline (Session 02):**
3. **`extract_rds.py`** — loads all 8 raw Basket Craft tables from MySQL into AWS RDS as-is (no transformations). Resumable: skips tables whose row count already matches MySQL.

**Snowflake pipeline (Session 03):**
4. **`load_snowflake.py`** — reads all 8 raw tables from RDS and loads them into `basket_craft.raw` in Snowflake using `write_pandas`. Truncates each target table before loading (idempotent). All column names are uppercased (Snowflake native casing). Credentials from `.env` (`SNOWFLAKE_*` variables).

**dbt project (Session 04):**
5. **`basket_craft/`** — dbt Core project that transforms raw Snowflake tables into a star schema in `basket_craft.analytics`.
   - **Staging models** (`models/staging/`): one model per raw source — `stg_orders`, `stg_order_items`, `stg_products`, `stg_customers`. Each renames/casts one source table; no JOINs or calculations. Materialized as tables.
   - **Mart models** (`models/marts/`): `fct_order_items` (fact table, order-line grain, 40K rows), `dim_customers` (31K rows), `dim_products` (4 rows), `dim_date` (3,653-day spine from 2020).
   - **Tests** (`models/marts/_schema.yml`): `unique` + `not_null` on `fct_order_items.order_item_id`.
   - **`~/.dbt/profiles.yml`** lives outside the repo and reads all credentials from `.env` via `env_var()`. Never commit it.
   - **`run_dbt.py`** — wrapper script that injects `.env` into the shell environment before calling dbt (dbt does not auto-load `.env`).

## Database

- **Source:** MySQL at `db.isba.co:3306`, database `basket_craft`
- **Local destination:** Postgres 16 in Docker, port `5433`, database `basket_craft`, container `basket_craft_db`
- **Cloud destination:** AWS RDS PostgreSQL at `basket-craft-db.cqfauycsyk1q.us-east-1.rds.amazonaws.com:5432`, database `basket_craft`, user `student`
- **Snowflake destination:** `basket_craft.raw` schema (raw) and `basket_craft.analytics` schema (dbt models), account `RSMLWYI-DUC27378`, warehouse `basket_craft_wh`
- **Local connection string:** `postgresql://postgres:postgres@localhost:5433/basket_craft`
- **RDS connection string:** `postgresql://student:<password>@basket-craft-db.cqfauycsyk1q.us-east-1.rds.amazonaws.com:5432/basket_craft` (password in `.env`)

## Credentials

All credentials are loaded from `.env` via `python-dotenv`. Never hardcode them. `.env` is gitignored. Use `.env.example` as the template.

## Tests

`tests/test_pipeline.py` contains 7 integration tests that hit the live MySQL and Postgres databases. They run in order and share module-scoped fixtures (`pg_conn`, `mysql_conn`). The idempotency test runs the full pipeline twice and takes ~4 minutes. `conftest.py` at the project root anchors pytest's import path so `from db import ...` works correctly.
