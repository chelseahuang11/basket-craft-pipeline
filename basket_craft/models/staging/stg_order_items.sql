with source as (
    select * from {{ source('raw', 'order_items') }}
),

renamed as (
    select
        order_item_id,
        created_at          as order_item_created_at,
        order_id,
        product_id,
        is_primary_item,
        price_usd           as item_price_usd,
        cogs_usd            as item_cogs_usd
    from source
)

select * from renamed
