{{ config(materialized='table') }}

with products as (
    select * from {{ ref('stg_products') }}
)

select
    product_id,
    product_name,
    product_description,
    product_created_at
from products
