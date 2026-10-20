-- Per-unit shelf price and estimated unit cost: one row per item, store, and week.
-- Margin of 0 or >= 100 is treated as unreliable, so unit_cost is left null.
create or replace table fact_prices as
select
    week,
    week_start,
    item_id,
    store_id,
    unit_price as sell_price,
    bundle_qty,
    promo_code,
    gross_margin_pct,
    case
        when gross_margin_pct is null or gross_margin_pct = 0 or gross_margin_pct >= 100 then null
        else unit_price * (1 - gross_margin_pct / 100)
    end as unit_cost,
    'dominicks_movement' as price_source
from stg_movement
where reject_reason is null
order by item_id, store_id, week
