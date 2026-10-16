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
- Customer-level personal data or customer-level price discrimination.
- Paid APIs/compute, multi-agent architecture, Kubernetes, production feature stores.
- Claiming real revenue gains from simulated outcomes.

## Success metrics (tracked separately, never blended)
Data pipeline (ingest success, freshness, invalid/duplicate rates) · Model (MAE, RMSE,
WAPE, lift vs. seasonal-naive, segment performance) · Pricing policy (simulated
profit/revenue, stockouts, price-change stats, sensitivity) · RAG (Recall@k, citation
correctness, faithfulness, unsupported-answer rate) · App (API success/latency).

## Constraints
$0 budget; everything runs locally; cloud/BI are optional extras.

Full plan lives in the project brief; later PRD revisions will be tracked in git.
