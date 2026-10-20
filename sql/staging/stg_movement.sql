-- Movement rows with dates attached, per-unit price derived, and a reject reason (null = accepted).
create or replace table stg_movement as
select
    m.store as store_id,
    m.upc as item_id,
    m.week,
    c.week_start,
    m.move as units_sold,
    m.qty as bundle_qty,
    m.price / m.qty as unit_price,
    m.profit as gross_margin_pct,
    nullif(trim(m.sale), '') as promo_code,
    case
        when m.ok = 0 then 'flagged_not_ok'
        when m.price is null or m.move is null or m.qty is null then 'missing_value'
        when m.price <= 0 and m.move = 0 then 'no_sale_recorded'
        when m.price <= 0 or m.move < 0 or m.qty < 1 then 'invalid_value'
        when m.price / m.qty not between $min_price and $max_price then 'implausible_price'
    end as reject_reason
from raw_movement m
left join dim_calendar c on c.week = m.week
