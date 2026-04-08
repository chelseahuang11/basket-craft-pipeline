# Basket Craft Pipeline — Design Spec
_Date: 2026-04-08_

## Business Goal

Produce a monthly sales dashboard answering:
- **Total revenue** by product category and month
- **Order count** by product category and month
- **Average order value** by product category and month

---

## Pipeline Diagram

```
SOURCE                EXTRACT              LOAD (STAGING)       TRANSFORM            DESTINATION
──────                ───────              ──────────────       ─────────            ───────────

MySQL DB              extract.py           stg_orders           aggregate.sql        PostgreSQL
(db.isba.co)    ──►  SELECT from     ──►  stg_order_items ──►  GROUP BY        ──►  (Docker :5433)
basket_craft          orders,              stg_products         product + month
                      order_items,
                      products                                                       monthly_sales_summary
                                                                                     • product_name
                                                                                     • sale_month
                                                                                     • total_revenue
                                                                                     • order_count
                                                                                     • avg_order_value
```

**Run sequence (manual):**
```bash
docker compose up -d
.venv/Scripts/python.exe extract.py
.venv/Scripts/python.exe transform.py
```

---

## File Structure

```
basket-craft-pipeline/
├── docker-compose.yml       # Spins up basket_craft_db Postgres container
├── .env                     # Credentials — NOT committed to git
├── .env.example             # Variable names only — committed as template
├── .gitignore               # .env already listed
│
├── extract.py               # Connects to MySQL; truncates + reloads staging tables
├── transform.py             # Connects to Postgres; runs aggregate.sql
├── aggregate.sql            # GROUP BY logic → monthly_sales_summary
│
└── requirements.txt         # mysql-connector-python, psycopg2-binary, python-dotenv
```

### Script responsibilities

| File | Responsibility |
|------|----------------|
| `extract.py` | Open MySQL connection → SELECT orders, order_items, products → TRUNCATE + INSERT into Postgres staging tables → print row counts |
| `transform.py` | Open Postgres connection → execute aggregate.sql → print row count of monthly_sales_summary |
| `aggregate.sql` | TRUNCATE monthly_sales_summary → INSERT via JOIN + GROUP BY |

---

## Table Schemas

### Staging tables (raw MySQL extract)

```sql
-- Assumption: adjust column names if DESCRIBE orders differs
CREATE TABLE IF NOT EXISTS stg_orders (
    order_id            INT PRIMARY KEY,
    created_at          TIMESTAMP,
    website_session_id  INT,
    user_id             INT,
    primary_product_id  INT,
    items_purchased     INT,
    price_usd           NUMERIC(10,2),
    cogs_usd            NUMERIC(10,2)
);

-- Assumption: adjust column names if DESCRIBE order_items differs
CREATE TABLE IF NOT EXISTS stg_order_items (
    order_item_id   INT PRIMARY KEY,
    created_at      TIMESTAMP,
    order_id        INT,
    product_id      INT,
    is_primary_item SMALLINT,
    price_usd       NUMERIC(10,2),
    cogs_usd        NUMERIC(10,2)
);

-- Confirmed from DESCRIBE products
CREATE TABLE IF NOT EXISTS stg_products (
    product_id   INT PRIMARY KEY,
    created_at   TIMESTAMP,
    product_name TEXT
    -- description omitted: not needed for dashboard
);
```

### Aggregated summary table (dashboard target)

```sql
CREATE TABLE IF NOT EXISTS monthly_sales_summary (
    product_name     TEXT,
    sale_month       DATE,           -- first day of month, e.g. 2023-01-01
    total_revenue    NUMERIC(12,2),
    order_count      INT,
    avg_order_value  NUMERIC(10,2),
    PRIMARY KEY (product_name, sale_month)
);
```

### aggregate.sql

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

---

## Docker & Credential Configuration

### docker-compose.yml

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
      - "5433:5432"          # 5433 avoids collision with MP01 on 5432
    volumes:
      - pgdata_basket_craft:/var/lib/postgresql/data

volumes:
  pgdata_basket_craft:
```

### .env (not committed)

```
# MySQL source
MYSQL_HOST=db.isba.co
MYSQL_PORT=3306
MYSQL_USER=analyst
MYSQL_PASSWORD=go_lions
MYSQL_DATABASE=basket_craft

# Postgres destination
PG_HOST=localhost
PG_PORT=5433
PG_DB=basket_craft
PG_USER=postgres
PG_PASSWORD=postgres
```

### .env.example (committed)

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

---

## Error Handling & Testing Strategy

### extract.py error handling
- Wrap MySQL connection in `try/except` — print clear message on auth failure or unreachable host
- Validate row counts after each staging insert — abort if any staging table is empty
- Use a transaction per table — all rows load or none do

### transform.py error handling
- Wrap `aggregate.sql` execution in `try/except` — roll back on failure
- Print final row count of `monthly_sales_summary` after load

### Manual testing checklist

| Check | Command |
|-------|---------|
| MySQL connection works | Run `extract.py` — look for "Connected" or error message |
| Staging tables populated | `SELECT COUNT(*) FROM stg_orders;` in psql |
| Aggregation ran | `SELECT * FROM monthly_sales_summary LIMIT 5;` |
| Numbers look right | Spot-check one product/month against raw staging data |
| Pipeline is idempotent | Run full pipeline twice — row counts must be identical |

---

## Assumptions to Verify

- `orders` and `order_items` column names match the staging schema above — run `DESCRIBE orders; DESCRIBE order_items;` to confirm
- `product_name` is used as the product category dimension (no separate `category` column in `products`)
- `price_usd` in `order_items` is the per-item sale price used for revenue calculation
