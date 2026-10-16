# PricePilot

Explainable pricing decision-support: demand forecasting, constrained price
optimization, policy simulation, MLOps tracking, and a RAG research assistant.

> **Status:** Milestone 0 (repository foundation). Nothing here recommends real prices.
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

## Layout

See `docs/PRD.md` for scope and `docs/DECISIONS.md` for design decisions.
Modules are added milestone by milestone; no placeholder files.

## Roadmap

0. Repository & environment  ← current
1. Data foundation
2. Statistical model
3. Pricing engine
4. MLOps
5. API & app
6. RAG
7. Dashboard & delivery
