-- Valid weekly sales: one row per category, store, item and week.
select
    category,
    store,
    upc,
    week,
    units_sold,
    bundle_qty,
    bundle_price,
    bundle_price / bundle_qty as unit_price,
    bundle_price * units_sold / bundle_qty as sales_dollars,
    case
        when profit is null or profit = 0 or profit >= 100 then null
        else profit
    end as gross_margin_pct,
    promo_code,
    units_sold >= 50000 as is_units_outlier
from {{ ref('stg_dominicks__movement_classified') }}
where reject_reason is null
