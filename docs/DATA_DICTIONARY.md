# Data dictionary

Datasets documented here, current first:

1. Dominick's scanner data, all 28 categories (the current pipeline: Postgres and dbt).
2. Dominick's general files `ccount` and `demo` (profiled, not yet loaded).
3. FreshRetailNet-50K (profiled, not yet ingested).
4. Legacy cereal-only pipeline (the first version, kept until it is reworked).

Numbers in sections 1 and 2 were measured on the loaded warehouse; a number labeled "cereal profile" was measured on cereal only and does not describe the other categories.

---

# Dominick's scanner data (all 28 categories)

## Source and terms
Dominick's Finer Foods scanner data, James M. Kilts Center for Marketing, University of Chicago Booth School of Business. All 28 categories with a movement file were downloaded from the Kilts Center Dominick's page; documented in the Dominick's Data Manual and Codebook (`docs/Dominicks-Manual-and-Codebook_KiltsCenter.pdf`).

- Provided for **academic research purposes only**; any publication using it must acknowledge the Kilts Center.
- Historical data (1989–1997)
- Category codes (three letters, also the folder names): ana, bat, ber, bjc, cer, che, cig, coo, cra, cso, did, fec, frd, fre, frj, fsf, gro, lnd, oat, ptw, sdr, sha, sna, soa, tbr, tna, tpa, tti. 
- `data/raw/CHECKSUMS.sha256` has 58 lines, one SHA-256 per source file, computed on the decompressed file. The loader compares each file to it (decision 53).
- Week numbers map to dates through the manual's decode table, saved as `data/reference/week_decode.csv`. Staging does not use it yet, so the warehouse holds week numbers only.

## Folder layout
| Path | Contents |
|---|---|
| `data/raw/<category>/` | `w<category>.csv.gz` (weekly movement) and `upc<category>.csv.gz` (product descriptions) |
| `data/raw/dominicks_general/` | `ccount.dta.gz` (store customer counts) and `demo.dta.gz` (store demographics) |
| `data/raw/freshretailnet50k/` | FreshRetailNet-50K files |
| `data/reference/week_decode.csv` | Week number to date and event table from the manual |
| `data/processed/cereal`, `data/interim/cereal` | Output of the legacy cereal pipeline only (see the last section) |

## Pipeline at a glance
| Layer | Object | What it holds | Rows |
|---|---|---|---|
| Raw | `raw.w<category>` (28 tables) | Movement files loaded one to one | 175,521,485 |
| Raw | `raw.upc<category>` (28 tables) | Product files loaded one to one | 18,117 |
| Staging | `analytics.stg_dominicks__movement_classified` (view) | Every raw movement row with a `reject_reason` (nulls are keep) | 175,521,485 |
| Staging | `analytics.stg_dominicks__movement` (view) | Kept rows: valid weekly sales | 96,717,530 (55.1%) |
| Staging | `analytics.stg_dominicks__movement_rejects` (view) | Removed rows with the reason | 78,803,955 (44.9%) |
| Staging | `analytics.stg_dominicks__products` (table) | Product descriptions, one row per category and UPC | 18,117 |

Kept plus rejected equals loaded (96,717,530 + 78,803,955 = 175,521,485); the dbt test `movement_rows_are_accounted_for` enforces this for every category separately (clean plus rejected rows must equal classified rows). The raw tables, the loader log `raw._load_log`, and the loader are described in decision 53.

## Staged tables
Grain of `stg_dominicks__movement`: one row per category, store, UPC, and week. The key is unique.

### stg_dominicks__movement
| Field | Meaning |
|---|---|
| category | Three-letter category code |
| store, upc, week | Store number, product code, and database week number (week 1 starts 1989-09-14; weeks run Thursday to Wednesday) |
| units_sold | Items sold (not bundles); always above 0 |
| bundle_qty | Items in a bundle deal; 1 except in 1,245,809 rows (1.3%) |
| bundle_price | Price of one bundle |
| unit_price | `bundle_price / bundle_qty` |
| sales_dollars | `bundle_price × units_sold / bundle_qty` |
| gross_margin_pct | Source `PROFIT`: gross margin in percent; null when missing, 0, or 100 and above; negative values are kept |
| promo_code | Source `SALE` code, kept as given |
| is_units_outlier | `units_sold` of 50,000 or more; flagged, not dropped (2 rows) |

### stg_dominicks__products
`category, upc, com_code, description, size, case_pack, nitem`. No department or attribute data in the source. The source files are Latin-1 encoded.

### stg_dominicks__movement_rejects
`category, store, upc, week, units_sold, bundle_price, ok, reject_reason`: the rows removed from `stg_dominicks__movement`, so nothing is dropped silently.

## Row rules
Each raw movement row gets the first reason that applies:

| Reason | Rule | Rows |
|---|---|---|
| incomplete_row | Store, week, or `OK` is missing | 1,259 |
| ok_flag_zero | Source `OK = 0` (suspect data; the source authors exclude these) | 2,586,985 (1.5% of loaded rows) |
| no_sale_recorded | Price or `MOVE` is missing or 0 or below | 76,215,711 (43.4% of loaded rows) |
| (none) | Row is kept | 96,717,530 |

Build limits (decision 55): a build fails if one category rejects more than 10% of its rows for `ok_flag_zero` or more than 85% for `no_sale_recorded`.

## Known limitations
- **No stockout information.** On cereal and tissues, price above 0 and units above 0 hold for exactly the same `OK = 1` rows, so zero price means no sale recorded and "no demand" cannot be told apart from "not stocked" (decision 54). Milestone 2 must define how zero-demand weeks are treated.
- **Zero-sale rows dominate the raw files.** 43.4% of loaded rows are `no_sale_recorded`, so the kept panel is sparse and any forecast applies to observed weeks only.
- **Promotion codes are incomplete** (per the manual): an absent code does not mean no promotion. Over all kept rows, `promo_code` is: none 79,302,061 (82.0%); B bonus buy 12,804,974 (13.2%); S price reduction 4,232,966 (4.4%); G 164,948 (0.17%); L 132,287 (0.14%); C coupon 78,498 (0.08%); N 1,070; M 726. The manual lists only B, C, and S; G, L, M, and N occur but are undocumented. *Cereal profile:* on the 16,177 item-store series with at least 100 observed weeks (4,006,767 rows), taking a dip as a price at or below 90% of the series' median over 13 neighboring observed rows, 4.2% of rows are dips and 91% of series have at least one. A dip carries a code in 81% of cases (B 68,808, S 60,399, none 33,130, G 7,766, C 2); 46% of coded rows are dips, against 0.9% of uncoded rows. Median price also rises 13% between a series' first and last 52 weeks, so max/min price ratios mix promotions with drift.
- **Cost is average acquisition cost**, not replacement cost (see the manual). Over all kept rows, 2,155,207 (2.2%) have a negative margin (cost above price) and are kept; 44,460 (0.05%) have a null margin. Gross profit therefore covers only rows with a valid margin, and any KPI built on it should report that coverage.
- **Missing weeks.** Across all 28 categories together, only week 219 has no kept rows (398 of 399 weeks present). Individual categories have more gaps; *cereal profile:* 33 of 399 weeks have no rows (219, 262–265, 284–309, 370–371). Lags and seasonal features are missing across gaps, and rolling windows are defined by calendar week, not by row. Missing weeks are not filled in.
- **Some UPCs are missing from the product files.** 77,498 clean movement rows in `sha` and `tbr` have a UPC absent from the source UPC files (466 UPCs in `sha`, 60 in `tbr`); the rows keep valid prices and units and the UPC-link test warns instead of failing (decision 57).
- **Store coverage.** The staged data has 93 distinct stores across all 28 categories. The 1,259 `incomplete_row` rejects (coo 774, cra 200, sna 285) each have only a UPC, so they carry no store, week, or `OK` value (decision 57).

---

# Dominick's general files: `ccount` and `demo` 

Stata files in `data/raw/dominicks_general/`, for profiling only. They feed the sales-per-customer KPI and the store-tier dimension (decisions 58 and 59).

## `ccount` (customer count file)
One row per store and day, 327,045 rows, 61 columns: `store`, `date`, `week`, `custcoun` (customer count), and dollar sales and coupon-redemption columns by department (`grocery`, `groccoup`, `dairy`, ...). The units of the department columns were not checked against the manual.

- 326,235 rows have a store above 0; they cover 132 stores. 324,652 rows have a customer count (131 stores).
- **`week` is partly invalid.** Its minimum among rows with a customer count is -4668. Only 270,589 rows have a store, a customer count, and a week from 1 to 399; they give 39,501 store-weeks. No store-day is duplicated among them.
- `custcoun` per day: median 2,703, mean 2,848, maximum 162,510, so outliers need a rule before any ratio is computed.
- `date` is blank in the first rows checked, so the week column is the only usable time key.
- Store overlap with the staged movement data (93 stores across all 28 categories, the same 93 found in the earlier three-category check): all 93 appear in `ccount`.

## `demo` (store demographics)
One row per store, 107 stores (108 rows read; one has no store ID), 510 columns, including `zone`, `scluster`, `income`, `educ`, `poverty`, `weekvol`, `urban`, and the price-tier columns `priclow`, `pricmed`, `prichigh`.

- `income`, `educ`, and `poverty` are filled for 97 of 107 stores; `weekvol` for 85; the price-tier columns for all 107.
- `zone` has 15 distinct values (1 to 16), with zone 2 the largest (29 stores) and zone 1 next (15).
- `income` ranges 9.87 to 11.24, which looks like a log scale; not confirmed in the manual.
- Store overlap with the staged movement data: 86 of the 93 stores appear in `demo`.

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

---

# Legacy: cereal-only pipeline (the first version; to be reworked)

This section documents the files the original cereal-only Python pipeline writes (`python -m pricepilot.data.pipeline`). The current design is the warehouse pipeline in the first section, and this one is replaced when Milestone 1 finishes. Its row rules differ from the dbt rules above, and every number below is for cereal only.

## Source
Cereals category (`wcer.csv`, `upccer.csv`), read from `data/raw/cereal/`.

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
Weekly, one row per item (UPC), store, and week, in every fact table.

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

## Cereal measurements
- `no_sale_recorded` accounts for 1,753,521 rejected rows (against 141,285 flagged `OK = 0`), so the accepted panel (4,707,776 rows) is sparse. These match the dbt counts for category `cer` (1,894,806 rejected in total).
- 53,057 accepted rows have a negative margin (cost above price); they are kept.
- Margin of exactly 0 is treated as unreliable (1,246 rows have null `unit_cost`).
