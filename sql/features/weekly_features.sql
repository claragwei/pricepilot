create or replace temp table forecast_features as
with joined as (
    select
        s.item_id,
        s.store_id,
        s.WEEK as week,
        s.units_sold::double as units,
        p.sell_price::double as sell_price,
        p.promo_code,
        p.gross_margin_pct::double as gross_margin_pct,
        (p.promo_code is not null)::int as promo_any
    from read_parquet($sales_path) as s
    join read_parquet($prices_path) as p using (item_id, store_id, WEEK)
),
windowed as (
    select
        item_id,
        store_id,
        week,
        units,
        sell_price,
        promo_code,
        promo_any,
        sum(units) over w_h as lag_h,
        sum(units) over w_h1 as lag_h1,
        sum(units) over w_h3 as lag_h3,
        sum(units) over w_season as lag_season,
        avg(units) over w_recent4 as mean4,
        avg(units) over w_recent13 as mean13,
        median(sell_price) over w_recent13 as median_price13,
        sum(sell_price) over w_h as price_lag,
        sum(promo_any) over w_h as promo_lag,
        avg(promo_any) over w_recent13 as promo_share13,
        sum(gross_margin_pct) over w_h as margin_lag,
        count(*) over w_past as n_prior
    from joined
    window
        w_h as (
            partition by item_id, store_id order by week
            range between {horizon} preceding and {horizon} preceding
        ),
        w_h1 as (
            partition by item_id, store_id order by week
            range between {horizon_p1} preceding and {horizon_p1} preceding
        ),
        w_h3 as (
            partition by item_id, store_id order by week
            range between {horizon_p3} preceding and {horizon_p3} preceding
        ),
        w_season as (
            partition by item_id, store_id order by week
            range between {season_lag} preceding and {season_lag} preceding
        ),
        w_recent4 as (
            partition by item_id, store_id order by week
            range between {horizon_p3} preceding and {horizon} preceding
        ),
        w_recent13 as (
            partition by item_id, store_id order by week
            range between {horizon_p12} preceding and {horizon} preceding
        ),
        w_past as (
            partition by item_id, store_id order by week
            range between unbounded preceding and {horizon} preceding
        )
)
select
    w.week,
    w.item_id,
    w.store_id,
    w.units as y,
    w.lag_h::double as lag_h,
    w.lag_h1::double as lag_h1,
    w.lag_h3::double as lag_h3,
    w.lag_season::double as lag_season,
    w.mean4::double as mean4,
    w.mean13::double as mean13,
    w.sell_price as price_t,
    w.price_lag::double as price_lag,
    w.sell_price / nullif(w.median_price13, 0) as price_rel,
    w.sell_price / nullif(w.price_lag, 0) - 1 as price_change,
    coalesce(w.promo_code = 'B', false)::int::double as promo_b,
    coalesce(w.promo_code = 'S', false)::int::double as promo_s,
    coalesce(w.promo_code = 'C', false)::int::double as promo_c,
    coalesce(w.promo_code = 'G', false)::int::double as promo_g,
    w.promo_any::double as promo_any,
    w.promo_lag::double as promo_lag,
    w.promo_share13::double as promo_share13,
    w.margin_lag::double as margin_lag,
    w.n_prior::double as n_prior,
    extract(week from c.week_start)::double as week_of_year,
    extract(month from c.week_start)::double as month,
    coalesce(c.holiday_flag::int, 0)::double as holiday_flag
from windowed as w
join read_parquet($calendar_path) as c on c.week = w.week
order by w.week, w.item_id, w.store_id
