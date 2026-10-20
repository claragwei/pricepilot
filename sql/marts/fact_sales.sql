-- Units sold: one row per item, store, and week (accepted rows only).
create or replace table fact_sales as
select
    week,
    week_start,
    item_id,
    store_id,
    units_sold,
    cast($source_version as varchar) as source_version
from stg_movement
where reject_reason is null
order by item_id, store_id, week
