-- One row per Dominick's database week, from the manual's week decode table.
create or replace table dim_calendar as
select
    week,
    week_start,
    week_end,
    year(week_start) as year,
    month(week_start) as month,
    event,
    event is not null as holiday_flag
from raw_week_decode
order by week
