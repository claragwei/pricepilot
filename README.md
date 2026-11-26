# PricePilot

Pricing Recommendation Simulator: demand forecasting, constrained price
optimization, policy simulation, MLOps tracking, and a RAG research assistant.

> **Status:** the pipeline design is finalized (see `docs/ARCHITECTURE.md`). Milestone 1 (data foundation) is in progress: all 28 Dominick's categories are downloaded, gzipped, and checksummed; Docker, a Snowflake trial, and dbt are installed; a local Postgres container and an empty dbt project connect; a raw loader copies the files into Postgres (all 28 categories loaded and verified: 56 tables, 175.5 million movement rows); dbt staging models (cleaning, rejects table, tests) are built for all 28 categories as views (slice 1c); the build passes with 2 expected warnings. The cereal ingest and forecaster code exist from earlier work and will be reworked.

See `docs/ARCHITECTURE.md` for the system diagram and how backtesting works.

## Business KPIs

Objective for the analysis: grow gross profit. Data: Dominick's grocery scanner data (1989–1997). 

| KPI (industry term) | Formula | Plain English | Team | Decision it supports |
|---|---|---|---|---|
| Sales $ (GMV) | Σ units × unit price | Total dollars sold | Finance | Where is volume coming from? |
| Gross profit $ | Σ sales $ × margin % | Dollars left after cost of goods | Finance, Merchandising | Which categories earn the money? |
| Gross margin % | Σ gross profit ÷ Σ sales (dollar-weighted) | Cents of profit per dollar sold | Merchandising | Is growth profitable? |
| Sales growth YoY | (sales this year ÷ sales last year) − 1 | Are we growing, and where? | Finance | Which categories to invest in |
| Promo share of sales | promo sales ÷ total sales | How much we rely on deals | Marketing | Are we over-discounting? |
| Promo lift | avg weekly units in promo weeks ÷ avg in normal weeks (same item and store) | Extra units a deal brings | Marketing, Pricing | Which deals move product? |
| Promo net profit | gross profit in promo weeks − expected gross profit at normal pricing | Did the deal make money? | Pricing, Finance | Keep, cut, or retest a promotion |
| Profit concentration | share of gross profit from the top 20% of categories | Do a few categories carry us? | Merchandising | Where is the business exposed? |
| Sales per customer (RPV) | store sales ÷ store customer count | Dollars per store visit | Marketing, Operations | Are stores monetizing traffic? |

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync                    # install pinned dependencies
uv run pytest              # tests
uv run ruff check .        # lint
uv run ruff format --check .
uv run mypy                # type-check src/
uv run pre-commit install  # optional: lint on commit
```

## Data pipeline

Raw Dominick's files live in `data/raw/<category>/` as `.csv.gz` (28 categories), with the general files in `data/raw/dominicks_general/` and hashes in `data/raw/CHECKSUMS.sha256`. The cereal ingest below still reads the older `data/raw/cereal/` layout and is replaced in Milestone 1; see `docs/DATA_DICTIONARY.md` for source, terms, and table definitions.

```bash
uv run python -m pricepilot.data.pipeline --sample   # small, fast subset
uv run python -m pricepilot.data.pipeline            # full run (~10 s)
```

Outputs go to `data/processed/cereal/` (Parquet tables, `quality_report.json`, `run_log.jsonl`); rejected rows go to `data/interim/cereal/`.

## Warehouse (Milestone 1, in progress)

Postgres runs in Docker and dbt builds the models; the dbt project is in `dbt/`.

```bash
docker compose up -d                                   # start Postgres on localhost:5433
uv run dbt debug --project-dir dbt --profiles-dir dbt  # check the connection
uv run python -m pricepilot.warehouse.load_raw --categories cer tti   # load chosen categories (default: all 28)
```

The loader writes one `raw.<file>` table per source file and a `raw._load_log` table, and it fails a file whose checksum or row count does not match.

Staging models are in `dbt/models/staging/` and cover all 28 categories (the `movement_categories` variable in `dbt/dbt_project.yml`). The movement models are views, so a full `dbt build` takes about 7 minutes:

```bash
uv run dbt deps --project-dir dbt --profiles-dir dbt    # install dbt_utils (once)
uv run dbt build --project-dir dbt --profiles-dir dbt   # build staging tables and run all tests
```

Results land in the `analytics` schema: `stg_dominicks__movement` (valid sales), `stg_dominicks__movement_rejects` (removed rows with reason), `stg_dominicks__products`. Failing test rows are stored in `analytics_dbt_test__audit`.

Snowflake credentials are read from `SNOWFLAKE_*` environment variables (see `.env.example`)

## Forecasting

The Milestone 2 demand forecaster (baselines, Poisson regression, LightGBM) is configured in `configs/forecast.yaml`.
```bash
uv run python -m pricepilot.forecast.run             # validation folds (~5 min)
uv run python -m pricepilot.forecast.run --final     # final test window; run once
```

Metrics are written to `data/processed/forecast/`.

## Layout

See `docs/ARCHITECTURE.md` for the diagrams, `docs/PRD.md` for scope, and `docs/DECISIONS.md` for design decisions. `docs/stages/` has a one-page PDF diagram per finished stage.
Modules are added milestone by milestone; no placeholder files.

## Roadmap

0. Repository & environment (done)
1. Data foundation (in progress: raw data loaded, staging models built for all 28 categories; marts and the Snowflake run next): all Dominick's categories, dbt on Snowflake (trial) and Postgres, tests and contracts
2. Forecaster: baselines, Poisson regression, LightGBM, small neural net, MLflow
2b. FreshRetailNet-50K pipeline and stockout module
3. Simulator, pricing policies (fixed price, rolling refit, Thompson, DDPG), and evaluation
4. MLOps: Airflow, registry, champion/challenger, monitoring
5. API & app: FastAPI, Streamlit, Docker
6. RAG explanations
7. Dashboard & delivery
