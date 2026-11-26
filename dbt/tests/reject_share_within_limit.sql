-- Fails when a category rejects more rows for one reason than the configured limit.
with totals as (
    select category, count(*) as n from {{ ref('stg_dominicks__movement_classified') }} group by 1
),
rejects as (
    select category, reject_reason, count(*) as n
    from {{ ref('stg_dominicks__movement_rejects') }}
    group by 1, 2
)

select
    r.category,
    r.reject_reason,
    r.n::numeric / t.n as reject_share
from rejects r
join totals t using (category)
where (r.reject_reason = 'ok_flag_zero' and r.n::numeric / t.n > {{ var('max_reject_share_ok_flag_zero') }})
   or (r.reject_reason = 'no_sale_recorded' and r.n::numeric / t.n > {{ var('max_reject_share_no_sale_recorded') }})
