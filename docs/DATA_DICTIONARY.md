# Data dictionary

## Source and terms
Dominick's Finer Foods scanner data, James M. Kilts Center for Marketing, University of Chicago Booth School of Business. Cereals category (`wcer.csv`, `upccer.csv`), downloaded from the Kilts Center Dominick's page; documented in the Dominick's Data Manual and Codebook.

- Provided for **academic research purposes only**; any publication using it must acknowledge the Kilts Center.
- Historical data (1989–1997); the products are not for sale.
- Raw files are not redistributed: `data/raw/` is git-ignored. Obtain them from the Kilts Center and place them in `data/raw/cereal/`.
- Week numbers map to dates through the manual's decode table, saved as `data/reference/week_decode.csv`.
- The manual lists 6,417,055 cereal observations; the CSV contains 6,602,582. The difference is unexplained.

### Source file checksums
Recorded by the pipeline in `data/processed/cereal/run_log.jsonl` for the full run (`source_version` `cereal-a204106f6dff`). A re-downloaded file should match before it is used.

| File | Bytes | SHA-256 |
|---|---|---|
| `wcer.csv` | 458,400,475 | `a204106f6dff8a6cfb83444c23b0c8aad8cb069862496db443e3815511b8fcd3` |
| `upccer.csv` | 25,932 | `affa589f080ab18a2edb2fa8f4cfb52b9212dec353bb49778e57f2b2403c5c6c` |
| `week_decode.csv` (reference) | 11,812 | `12aa6f5fc9bfc95ba220e3a6f027d2f3a2e3f71882fc79e502e0725ef2597154` |

Check a file with `shasum -a 256 data/raw/cereal/wcer.csv`.

## Grain
Dominick's records are **weekly**, not daily. Week 1 starts 1989-09-14; weeks run Thursday to Wednesday. All fact tables have one row per item (UPC), store, and week.

## Tables (`data/processed/cereal/*.parquet`)

### fact_sales
| Field | Meaning |
|---|---|
| week, week_start | Database week number and its start date |
| item_id, store_id | UPC and store number |
| units_sold | Items sold (not bundles) |
| source_version | `<category>-<first 12 chars of movement file SHA-256>` |

### fact_prices
| Field | Meaning |
|---|---|
| week, week_start, item_id, store_id | Same key as fact_sales |
| sell_price | Per-unit price (`PRICE / QTY`) |
| bundle_qty | Items in a bundle deal (1 for 99.9% of rows) |
| promo_code | Source `SALE` code: B bonus buy, C coupon, S price reduction, G and L undocumented; null if unset |
| gross_margin_pct | Source `PROFIT`: gross margin in percent |
| unit_cost | `sell_price × (1 − margin/100)`; null when margin is 0 or ≥ 100 |
| price_source | Always `dominicks_movement` |

### dim_product
`item_id, description, size, case_pack, commodity_code, item_number, category`. No department or attribute data in the source.

### dim_calendar
`week, week_start, week_end, year, month, event, holiday_flag` (events from the manual's decode table).

## Row rules
A movement row is rejected, with its reason written to `data/interim/cereal/rejected_movement.parquet`, when:

| Reason | Rule |
|---|---|
| flagged_not_ok | Source `OK = 0` (suspect data; the data authors exclude these) |
| missing_value | Null price, units, or bundle quantity |
| no_sale_recorded | Price 0 and units 0 |
| invalid_value | Price ≤ 0 with units > 0, negative units, or bundle quantity < 1 |
| implausible_price | Unit price outside `price_bounds` in `configs/data.yaml` |

## Known limitations
- **No stockout information.** Every zero-unit row has a zero price, so "no demand" cannot be told apart from "not stocked". `no_sale_recorded` rows are excluded here; Milestone 2 must define how zero-demand weeks are treated.
- **Promotion codes are incomplete** (per the manual): an absent code does not mean no promotion. Measured on the 16,177 item-store series with at least 100 observed weeks (4,006,767 rows), taking a dip as a price at or below 90% of the series' median over 13 neighboring observed rows: 4.2% of rows are dips, and 91% of series have at least one (median 8 weeks, median price 0.75 of the local median). A dip carries a code in 81% of cases (B 68,808, S 60,399, none 33,130, G 7,766, C 2); 46% of coded rows are dips, against 0.9% of uncoded rows. Median price also rises 13% between a series' first and last 52 weeks, so max/min price ratios mix promotions with drift. Neighbor windows are by row, so gaps in a series make them approximate.
- **Cost is average acquisition cost**, not replacement cost (see the manual). 53,057 accepted rows have a negative margin (cost above price); they are kept.
- **Whole weeks are absent from the source.** 33 of the 399 weeks have no movement rows at all (219, 262–265, 284–309, 370–371); the rejected-rows file has none for them either. Lags and seasonal features are missing across these gaps, and rolling windows are defined by calendar week, not by row.
- **Many zero-sale rows are excluded.** `no_sale_recorded` accounts for 1,753,521 rejected rows (against 141,285 flagged `OK = 0`), so the accepted panel (4,707,776 rows) is sparse and forecasts apply to observed weeks only.
- Margin of exactly 0 is treated as unreliable (1,246 rows have null `unit_cost`).
- UPC file encoding is Latin-1.

---

# FreshRetailNet-50K (downloaded and profiled; not yet ingested)

## Source and terms
`Dingdong-Inc/FreshRetailNet-50K` on Hugging Face (release 1.0, 2025-05-08; technical report arXiv 2505.16319). License CC BY 4.0; credit Dingdong-Inc. Files in `data/raw/freshretailnet50k/` (git-ignored): `train.parquet` (4.5M rows, 106 MB), `eval.parquet` (350k rows, 8 MB), `README.md`.

## Contents (profiled 2026-10-26)
- 50,000 store-product series (898 stores, 865 perishable products, 18 cities), one row per series per day: 90 training days (2024-03-28 to 2024-06-25) plus a 7-day eval split (2024-06-26 to 2024-07-02) on the same series.
- Fields: city, store, and product hierarchy IDs; `sale_amount` and 24 hourly `hours_sale` values (both globally normalized, so not raw units); `hours_stock_status` (24 hourly flags; 1 means out of stock, confirmed because hourly sales are near zero when it is 1); `stock_hour6_22_cnt` (out-of-stock hours between 06:00 and 22:00, matches the hourly flags exactly); `discount` (rate; 1.0 means no discount); `holiday_flag`; `activity_flag`; weather fields.

## Findings
- **Discount variation is strong.** 97% of series have at least one discounted day, the median series is discounted on 53% of days, and 90% of series span more than 5 discount points. About 51% of all rows have `discount < 1`.
- **`activity_flag` explains most but not all discounts.** Flagged rows (38%) are discounted 98% of the time with a mean rate of 0.80; unflagged rows are discounted 24% of the time.
- **Stockouts are common.** 44% of series-days have at least one out-of-stock hour, 17% have eight or more, and 4% have sixteen or more. Stockout frequency is similar across discount bands. Daily sales on stockout days are not lower than on other days (mean 1.04 vs 0.99), so daily totals understate demand on those days.
- **Descriptive price response.** Within series, on days with no stockout hours, the slope of log sales on log discount is about -1.6 (-2.3 on days without the activity flag). This is observational and descriptive, not causal: discounts coincide with activities and stockouts select days.

## Known limitations
- 90 days of history, so no yearly seasonality and few backtest folds.
- No absolute price, base price, or cost: only a discount rate, so profit needs an assumed base price and margin, labeled as an assumption.
- Units are normalized by an unstated coefficient.
- 17,339 rows (0.36%) have `discount <= 0` and 34 have `discount > 1`; treat them as invalid or outliers.
- One retailer, fresh perishables, 2024.
