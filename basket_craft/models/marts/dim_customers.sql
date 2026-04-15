{{ config(materialized='table') }}

with customers as (
    select * from {{ ref('stg_customers') }}
)

select
    customer_id,
    first_name,
    last_name,
    email,
    billing_street_address,
    billing_city,
    billing_state,
    billing_postal_code,
    billing_country,
    shipping_street_address,
    shipping_city,
    shipping_state,
    shipping_postal_code,
    shipping_country,
    customer_created_at
from customers
