# PricePilot

Explainable pricing decision-support: demand forecasting, constrained price
optimization, policy simulation, MLOps tracking, and a RAG research assistant.

> **Status:** the pipeline design is finalized (see `docs/ARCHITECTURE.md`). Milestone 1 (data foundation) is in progress: all 28 Dominick's categories are downloaded, gzipped, and checksummed; Docker, a Snowflake trial, and dbt are installed; a local Postgres container and an empty dbt project connect (`dbt debug` passes); the dbt models are not built yet. The cereal ingest and forecaster code exist from earlier work and will be reworked.
> All profit figures will be **simulated**, never real-world impact.

See `docs/ARCHITECTURE.md` for the system diagram and how backtesting works.

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
```

Snowflake credentials are read from `SNOWFLAKE_*` environment variables (see `.env.example`); nothing secret is stored in the repo.

## Forecasting

The Milestone 2 demand forecaster (baselines, Poisson regression, LightGBM) is configured in `configs/forecast.yaml`.
```bash
uv run python -m pricepilot.forecast.run             # validation folds (~5 min)
uv run python -m pricepilot.forecast.run --final     # final test window; run once
```

Metrics are written to `data/processed/forecast/`.

## Layout

See `docs/ARCHITECTURE.md` for the diagrams, `docs/PRD.md` for scope, and `docs/DECISIONS.md` for design decisions.
Modules are added milestone by milestone; no placeholder files.

## Roadmap

0. Repository & environment (done)
1. Data foundation (in progress: raw data and tools ready, dbt models next): all Dominick's categories, dbt on Snowflake (trial) and Postgres, tests and contracts
2. Forecaster: baselines, Poisson regression, LightGBM, small neural net, MLflow
2b. FreshRetailNet-50K pipeline and stockout module
3. Simulator, pricing policies (fixed price, rolling refit, Thompson, DDPG), and evaluation
4. MLOps: Airflow, registry, champion/challenger, monitoring
5. API & app: FastAPI, Streamlit, Docker
6. RAG explanations
7. Dashboard & delivery
