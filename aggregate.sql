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
JOIN stg_order_items  oi ON o.order_id   = oi.order_id
JOIN stg_products      p ON oi.product_id = p.product_id
GROUP BY p.product_name, DATE_TRUNC('month', o.created_at)
ORDER BY sale_month, product_name;
