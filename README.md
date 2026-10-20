# PricePilot

Explainable pricing decision-support: demand forecasting, constrained price
optimization, policy simulation, MLOps tracking, and a RAG research assistant.

> **Status:** Milestone 1 (data foundation) complete
> All profit figures will be **simulated**, never real-world impact.

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

Place the Dominick's cereal files (`wcer.csv`, `upccer.csv`) in `data/raw/cereal/`; see `docs/DATA_DICTIONARY.md` for source, terms, and table definitions.

```bash
uv run python -m pricepilot.data.pipeline --sample   # small, fast subset
uv run python -m pricepilot.data.pipeline            # full run (~10 s)
```

Outputs go to `data/processed/cereal/` (Parquet tables, `quality_report.json`, `run_log.jsonl`); rejected rows go to `data/interim/cereal/`.

## Layout

See `docs/PRD.md` for scope and `docs/DECISIONS.md` for design decisions.
Modules are added milestone by milestone; no placeholder files.

## Roadmap

0. Repository & environment
1. Data foundation  ← current
1b. Analytics engineering (dbt, metrics, data-quality monitoring)
2. Statistical model
3. Pricing engine
4. MLOps & orchestration (MLflow, Dagster)
5. API & app (Docker)
6. RAG
7. Dashboard & delivery
