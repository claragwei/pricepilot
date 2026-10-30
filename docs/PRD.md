# PricePilot — Product Requirements (initial)

## Problem
Retail pricing must balance demand, seasonality, promotions, inventory and profit.
Static rules miss demand shifts; unconstrained optimizers recommend unrealistic prices;
ML models can look good offline yet be unreliable when data changes.

## Product
An explainable decision-support system that ingests historical retail data, forecasts
demand, simulates alternative pricing policies, recommends prices within configurable
business constraints, and explains recommendations with cited evidence.

## Personas
- **Pricing analyst** — compare model vs. current price, understand assumptions.
- **Business/product manager** — configure constraints, compare strategies, judge risk.
- **Data scientist** — evaluate models, inspect features, investigate drift.

## Non-goals (v1)
- Automatically changing real prices.
- Claiming causal price elasticity from observational data.
- Directly identifying personal data or customer-level price discrimination.
- Paid APIs/compute, multi-agent architecture, Kubernetes, production feature stores.
- Claiming real revenue gains from simulated outcomes.

## Success metrics (tracked separately, never blended)
Data pipeline (ingest success, freshness, invalid/duplicate rates) · Model (MAE, RMSE,
WAPE, lift vs. seasonal-naive, segment performance) · Pricing policy (simulated
profit/revenue, stockouts, price-change stats, sensitivity) · RAG (Recall@k, citation
correctness, faithfulness, unsupported-answer rate) · App (API success/latency).

## Success criteria
- **Forecaster:** the best model's WAPE on the final test is at least 10% lower than the best baseline's.
- **Pricing policy:** DDPG earns higher simulated profit than the best baseline policy in most settings of the assumed price-sensitivity sweep, with paired seeds and an interval that excludes zero. Always labeled simulated.
- **Target finish date:** 2026-11-16, a target and not a limit on scope (decision 44).

## Milestones
0. Repository and environment (done).
1. Data foundation: all-category Dominick's intake in dbt on Snowflake (trial) and Postgres (Docker), with tests, schema contracts, a metric layer, the JSON quality report, and CI.
2. Forecaster: shared feature definition, baselines, Poisson regression, LightGBM, a small neural net, MLflow tracking, rolling-origin backtest, and a final test run once.
2b. FreshRetailNet-50K pipeline and a stockout and censored-demand module.
3. Simulator, pricing policies, and evaluation: known-truth simulator with confounded prices, inventory, and rival rules; fixed price, rolling refit, Thompson sampling, and DDPG; regret and profit comparisons; A/B and switchback tests; a DML bias study.
4. MLOps: Airflow, MLflow registry with champion/challenger, drift and error monitoring on replayed history, rollback.
5. API and app: FastAPI and Streamlit in Docker.
6. RAG: LLM explanations with a local open model, citing results only.
7. Dashboard and delivery: Tableau Public, hosted demo, case study, README, and video.

Order and owners are in `docs/ARCHITECTURE.md`. Stretch, after the above: a second data source with entity resolution, and an
optional PySpark local-mode job that rebuilds one mart and reconciles it to the dbt output
(not a cluster deployment).
Databricks and GCP are out of scope; the README may note how the work maps to them. Snowflake is used on its free trial only (decision 51).

## Data
Dominick's scanner data (weekly, expanding from cereal to every category with a CSV file) is the primary real dataset. FreshRetailNet-50K supplies stockouts and censored demand. Pricing policies are trained and evaluated in a simulator calibrated to the real data, and their results are labeled simulated. See `docs/ARCHITECTURE.md`.

## Constraints
$0 budget. Everything runs locally except free hosting tiers for the public demo (Streamlit Community Cloud, GitHub Pages, Tableau Public). Snowflake is used on its free trial only, with no payment details entered.

Full plan lives in the project brief; later PRD revisions will be tracked in git.
