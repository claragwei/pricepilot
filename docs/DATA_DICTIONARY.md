# Data dictionary

## Source and terms
Dominick's Finer Foods scanner data, James M. Kilts Center for Marketing, University of Chicago Booth School of Business. Cereals category (`wcer.csv`, `upccer.csv`), downloaded from the Kilts Center Dominick's page; documented in the Dominick's Data Manual and Codebook.

- Provided for **academic research purposes only**; any publication using it must acknowledge the Kilts Center.
- Historical data (1989–1997); the products are not for sale.
- Raw files are not redistributed: `data/raw/` is git-ignored. Obtain them from the Kilts Center and place them in `data/raw/cereal/`.
- Week numbers map to dates through the manual's decode table, saved as `data/reference/week_decode.csv`.
- The manual lists 6,417,055 cereal observations; the CSV contains 6,602,582. The difference is unexplained.

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
- **Promotion codes are incomplete** (per the manual): an absent code does not mean no promotion.
- **Cost is average acquisition cost**, not replacement cost (see the manual). 53,057 accepted rows have a negative margin (cost above price); they are kept.
- Margin of exactly 0 is treated as unreliable (1,246 rows have null `unit_cost`).
- UPC file encoding is Latin-1.
