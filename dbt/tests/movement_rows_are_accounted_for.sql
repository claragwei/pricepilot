-- Fails for any category where clean rows + rejected rows differ from all classified rows.
with classified as (
    select category, count(*) as n from {{ ref('stg_dominicks__movement_classified') }} group by 1
),
clean as (
    select category, count(*) as n from {{ ref('stg_dominicks__movement') }} group by 1
),
rejected as (
    select category, count(*) as n from {{ ref('stg_dominicks__movement_rejects') }} group by 1
)

select
    c.category,
    c.n as classified_rows,
    coalesce(k.n, 0) + coalesce(r.n, 0) as kept_plus_rejected
from classified c
left join clean k using (category)
left join rejected r using (category)
where c.n <> coalesce(k.n, 0) + coalesce(r.n, 0)
