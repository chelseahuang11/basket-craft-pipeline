with source as (
    select * from {{ source('raw', 'products') }}
),

renamed as (
    select
        product_id,
        created_at          as product_created_at,
        product_name,
        description         as product_description
    from source
)

select * from renamed
