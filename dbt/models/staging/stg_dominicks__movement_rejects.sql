-- Rows removed from staging, with the reason, so nothing is dropped silently.
select
    category,
    store,
    upc,
    week,
    units_sold,
    bundle_price,
    ok,
    reject_reason
from {{ ref('stg_dominicks__movement_classified') }}
where reject_reason is not null
