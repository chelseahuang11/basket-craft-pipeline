{{ config(materialized='table') }}

with order_items as (
    select * from {{ ref('stg_order_items') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
)

select
    -- primary key
    order_items.order_item_id,

    -- foreign keys
    orders.customer_id,
    order_items.product_id,
    orders.order_created_at as order_date,

    -- order context
    order_items.order_id,
    orders.website_session_id,
    orders.primary_product_id,
    orders.items_purchased,
    order_items.is_primary_item,

    -- measures
    order_items.item_price_usd,
    order_items.item_cogs_usd,
    order_items.item_price_usd - order_items.item_cogs_usd as item_gross_profit_usd,

    -- timestamps
    order_items.order_item_created_at
from order_items
left join orders on order_items.order_id = orders.order_id
