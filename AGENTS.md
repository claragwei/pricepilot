# AGENTS.md

PricePilot is an explainable pricing decision-support project: demand forecasting, constrained price optimization, policy simulation, MLOps tracking, and a RAG research assistant. It is research-grade and simulation-based. Scope is in `docs/PRD.md`, decisions in `docs/DECISIONS.md`, and data definitions in `docs/DATA_DICTIONARY.md`.

## Status
The pipeline design is finalized and building has not started. Existing code (cereal ingest, dunnhumby ingest, forecaster) is from earlier work; the dunnhumby code and the saved-models and input-check code are to be removed when building starts. The build sequence and who does each step are in `docs/ARCHITECTURE.md`. Milestones: 0 repo, 1 data (dbt on Snowflake trial and Postgres), 2 forecaster, 2b FreshRetailNet, 3 simulator and pricing, 4 MLOps and Airflow, 5 API/app (Docker), 6 RAG, 7 dashboard and delivery. Approvals are per step: explain, then wait for the owner's go-ahead.

## Setup and checks
Python 3.12, managed with `uv`. Run before finishing any change:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

Pipelines: `uv run python -m pricepilot.data.pipeline [--sample]` (Dominick's cereal). Forecaster: `uv run python -m pricepilot.forecast.run [--final]` (config in `configs/forecast.yaml`; the final test is run once). Raw data under `data/raw/` is git-ignored and not redistributable.

## Layout
- `src/pricepilot/`: reusable, tested logic (`config.py`, `data/` for ingest, validate, transform, load, and pipeline; `forecast/` for features, baselines, models, metrics, and the backtest).
- `sql/staging/`, `sql/marts/`, `sql/features/`: DuckDB SQL; Python only orchestrates.
- `configs/`: YAML config (`data.yaml`, `forecast.yaml`). No hardcoded paths in code.
- `tests/unit/`, `tests/integration/`: pytest.
- Notebooks are for exploration only.

## Hard rules (set by the owner)
- Never run `git commit`, `git push`, or create remotes. The owner commits and pushes. Leave changes uncommitted.
- The owner approves all changes. Propose before large or structural edits; stop at each milestone for review.
- Never invent results, metrics, or passing tests. Report commands run and their real output.
- No paid services, no secrets in files, no directly identifying personal data. Pseudonymous customer or household IDs from licensed datasets may be used for aggregation and segmentation.
- Label simulated outcomes as simulated, never as real impact. Never call observational price coefficients causal.
- Dataset licensing and terms are not a decision criterion or blocker: this is a student, non-commercial portfolio project. Credit sources and keep raw files out of git, but do not raise licensing as a reason to limit design or the public demo.

## Code conventions
- Each file starts with a short module docstring; each function gets a short docstring.
- No inline comments unless the logic is non-obvious. No changelog or status comments.
- Typed functions (mypy strict on `src/`), small modules, line length 100.
- Add dependencies only when a milestone needs them. No empty placeholder files.
- Append a row to `docs/DECISIONS.md` for each architectural or analytical decision.

## Data caveats to respect
- Grain is weekly, one row per item, store, and week.
- No stockout information: zero-unit rows cannot be told apart from "not stocked".
- Promotion codes are incomplete; an absent code does not mean no promotion.
- Source is licensed for academic research; keep the Kilts Center acknowledgement.
