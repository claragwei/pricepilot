-- Every raw movement row, tagged with why it is rejected (null reject_reason = keep).
with unioned as (
    {% for c in var('movement_categories') %}
    select
        '{{ c }}' as category,
        store, upc, week, move, qty, price, profit, sale, ok
    from {{ source('raw', 'w' ~ c) }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
)

select
    category,
    store,
    upc,
    week,
    move as units_sold,
    qty as bundle_qty,
    price as bundle_price,
    profit,
    nullif(trim(sale), '') as promo_code,
    ok,
    case
        when store is null or week is null or ok is null then 'incomplete_row'
        when ok = 0 then 'ok_flag_zero'
        when price is null or price <= 0 or move is null or move <= 0 then 'no_sale_recorded'
    end as reject_reason
from unioned
