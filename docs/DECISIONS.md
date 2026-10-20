# Decision log

| # | Date | Decision | Rationale |
|---|------|----------|-----------|
| 1 | 2026-10-16 | Python 3.12, managed with `uv` (`uv.lock` committed) | Reproducible installs, fast CI |
| 2 | 2026-10-16 | `src/` layout, hatchling build backend | Prevents accidental imports from repo root |
| 3 | 2026-10-16 | Runtime deps limited to pydantic + pyyaml in M0; others added per milestone | Avoid unnecessary dependencies |
| 4 | 2026-10-16 | Ruff (lint+format), mypy strict on `src/`, pytest | Per plan §13 |
| 5 | 2026-10-16 | Data dirs git-ignored except `.gitkeep` | Raw/generated data must never be committed |
| 6 | 2026-10-16 | Primary dataset: Dominick's cereal (not M5) | Real price variation, promotion codes, and gross margin (cost); M5 has little price variation and no cost |
| 7 | 2026-10-16 | Weekly grain instead of the plan's daily grain | Source data is weekly |
| 8 | 2026-10-16 | DuckDB for the pipeline; SQL kept in `sql/` files, Python only orchestrates | Fast local SQL on 6.6M rows, no server; shows SQL skills |
| 9 | 2026-10-16 | Reject rows with `OK = 0`, invalid, or implausible values; report counts by reason; fail if reject rate > 40% | Source authors exclude `OK = 0`; guard against a broken input |
| 10 | 2026-10-16 | `no_sale_recorded` rows excluded in M1 | Cannot distinguish zero demand from not stocked; revisit in M2 |
| 11 | 2026-10-16 | Unit cost = price × (1 − margin/100); margin 0 or ≥ 100 → null | Per the manual; 0 is likely a missing code |
| 12 | 2026-10-16 | `source_version` = category plus movement-file checksum; sample runs write to separate `_sample` directories | Traceable inputs; sample never overwrites full outputs |
| 13 | 2026-10-19 | Add Milestone 1b: port `sql/` to dbt on DuckDB (`dbt-duckdb`), with tests, docs, semantic-layer metrics, and freshness/volume/reconciliation checks | Analytics-engineering skills in target job postings; existing SQL layout ports directly; stays $0 |
| 14 | 2026-10-19 | Dagster for orchestration and MLflow for tracking/registry, both in Milestone 4; Docker in Milestone 5 | Free, run locally; cover orchestration and MLOps requirements |
| 15 | 2026-10-19 | Snowflake, Databricks, GCP, and ads/recommendation ranking out of scope | Paid or cloud setup conflicts with $0 constraint; ranking needs user-level data the PRD excludes |
| 16 | 2026-10-19 | Second data source with entity resolution is a stretch goal, after the core | Avoid inventing a matching problem; only worthwhile if sources overlap |
