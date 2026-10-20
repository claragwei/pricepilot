# AGENTS.md

PricePilot is an explainable pricing decision-support project: demand forecasting, constrained price optimization, policy simulation, MLOps tracking, and a RAG research assistant. It is research-grade and simulation-based. Scope is in `docs/PRD.md`, decisions in `docs/DECISIONS.md`, and data definitions in `docs/DATA_DICTIONARY.md`.

## Status
Milestone 1 (data foundation) is ready for review. Milestones: 0 repo, 1 data, 1b dbt/metrics/data-quality monitoring, 2 model, 3 pricing, 4 MLOps and Dagster, 5 API/app (Docker), 6 RAG, 7 dashboard.

## Setup and checks
Python 3.12, managed with `uv`. Run before finishing any change:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

Pipeline: `uv run python -m pricepilot.data.pipeline [--sample]`. Raw data (`data/raw/cereal/`) is git-ignored and not redistributable.

## Layout
- `src/pricepilot/`: reusable, tested logic (`config.py`, `data/` for ingest, validate, transform, load, pipeline).
- `sql/staging/`, `sql/marts/`: DuckDB SQL; Python only orchestrates.
- `configs/`: YAML config. No hardcoded paths in code.
- `tests/unit/`, `tests/integration/`: pytest.
- Notebooks are for exploration only.

## Hard rules (set by the owner)
- Never run `git commit`, `git push`, or create remotes. The owner commits and pushes. Leave changes uncommitted.
- The owner approves all changes. Propose before large or structural edits; stop at each milestone for review.
- Never invent results, metrics, or passing tests. Report commands run and their real output.
- No paid services, no secrets in files, no personal customer data.
- Label simulated outcomes as simulated, never as real impact. Never call observational price coefficients causal.

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
