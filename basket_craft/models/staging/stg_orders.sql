with source as (
    select * from {{ source('raw', 'orders') }}
),

renamed as (
    select
        order_id,
        created_at          as order_created_at,
        website_session_id,
        user_id             as customer_id,
        primary_product_id,
        items_purchased,
        price_usd           as order_price_usd,
        cogs_usd            as order_cogs_usd
    from source
)

select * from renamed
