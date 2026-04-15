# Snowflake Loader Design

**Date:** 2026-04-15  
**Project:** basket-craft-pipeline  
**Session:** 03 — RDS to Snowflake

---

## Goal

Write a Python script (`load_snowflake.py`) that reads all 8 raw Basket Craft tables from AWS RDS PostgreSQL and loads them into the `basket_craft.raw` schema in Snowflake. This is the third hop in the pipeline: MySQL → RDS (Session 02) → Snowflake (Session 03).

---

## Architecture

```
RDS PostgreSQL (psycopg2 + pandas)
  └─► pandas DataFrame (columns lowercased)
        └─► write_pandas (Snowflake COPY INTO)
              └─► basket_craft.raw.<table_name>
```

---

## Design Decisions

### Which tables
All 8 raw Basket Craft tables, discovered dynamically from RDS via `information_schema.tables`. No hardcoded table list — consistent with `extract_rds.py`.

### Memory strategy
Full table loaded into a pandas DataFrame before writing to Snowflake. The largest table (`website_pageviews`, 1.1M rows) fits comfortably in RAM. No chunking needed.

### Idempotency
TRUNCATE each Snowflake target table before loading. Running the script twice produces the same result. Append mode is not used — truncate-and-reload is simpler and safer.

### Column name casing
All column names are lowercased (`df.columns = [c.lower() for c in df.columns]`) before passing to `write_pandas`. Snowflake uppercases unquoted identifiers by default; keeping everything lowercase avoids case-sensitivity failures in dbt (Session 04).

### Credentials
All credentials read from `.env` via `python-dotenv`. No hardcoded values. Variables used:
- `RDS_HOST`, `RDS_PORT`, `RDS_USER`, `RDS_PASSWORD`, `RDS_DATABASE`
- `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`

---

## File Map

| File | Action | Description |
|------|--------|-------------|
| `load_snowflake.py` | Create | Main loader script |
| `requirements.txt` | Update | Add `snowflake-connector-python[pandas]` |

---

## Script Structure

```python
# Connections
get_rds_conn()       # psycopg2 connection using RDS_* env vars
get_snowflake_conn() # snowflake.connector connection using SNOWFLAKE_* env vars

# Per-table logic
load_table(rds_conn, sf_conn, table)
  1. SELECT * FROM <table> into pandas DataFrame
  2. Lowercase all column names
  3. TRUNCATE target table in Snowflake (if exists)
  4. write_pandas(df, table_name, schema='raw', database='basket_craft')
  5. Print row count confirmation

# Main
  - Connect to RDS and Snowflake
  - Discover tables from RDS information_schema
  - Loop: load_table for each
  - Print summary
```

---

## Success Criteria

- All 8 tables present in `basket_craft.raw` in Snowflake
- Row counts match RDS source exactly
- Script is idempotent (re-running produces same result)
- No credentials in code
- All identifiers lowercase
