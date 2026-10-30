# Architecture

The decided design for the full project (decisions 19 to 50 in [DECISIONS.md](DECISIONS.md)). Almost all of it is planned and not yet built. Everything from the simulator down is **simulated**; its results are never real-world impact.

**What exists today:** a DuckDB ingest for Dominick's cereal, forecaster code with its tests, and the docs. The dunnhumby ingest and the earlier saved-models and input-check code are to be removed when building starts (decisions 30 and 48).

## System overview

```
SOURCES (data/raw, git-ignored, gzipped, checksummed)
+-----------------------------+      +-----------------------------+
| Dominick's                  |      | FreshRetailNet-50K          |
| 28 categories + traffic     |      | stockouts, daily and hourly |
| + demographics + stores     |      | (second pipeline)           |
+--------------+--------------+      +--------------+--------------+
               |                                    |
               +------------------+-----------------+
                                  v
          +--------------------------------------------+
          | INGEST + CLEAN   dbt on Snowflake (trial)  |
          | and Postgres (Docker), same models; tests, |
          | schema contracts, metric layer, JSON report|
          +---------------------+----------------------+
                                v
          +--------------------------------------------+
          | FEATURE TABLE                              |
          | one shared definition for training and     |
          | serving, versioned per data version        |
          +----------+-----------------------+---------+
                     |                       |
                     v                       v
   +----------------------------+   +-----------------------------------+
   | FORECASTER                 |   | SIMULATOR (simulated)             |
   | baselines, Poisson,        |   | known-truth generator, confounded |
   | LightGBM, small neural net |   | prices, inventory, rival rules    |
   | backtest + final test      |   +-----------------+-----------------+
   +-------------+--------------+                     v
                 |                 +-----------------------------------+
                 |                 | PRICING POLICIES (simulated)      |
                 |                 | fixed price, rolling refit,       |
                 |                 | Thompson sampling, DDPG;          |
                 |                 | price limits + fallback price     |
                 |                 +-----------------+-----------------+
                 |                                   v
                 |                 +-----------------------------------+
                 |                 | POLICY EVALUATION (simulated)     |
                 |                 | regret, profit, paired seeds,     |
                 |                 | A/B + switchback, DML bias study  |
                 |                 +-----------------+-----------------+
                 +-------------------+---------------+
                                     v
          +--------------------------------------------+
          | MLOPS                                      |
          | MLflow tracking + registry, Airflow,       |
          | drift + error monitoring, rollback,        |
          | champion/challenger, CI                    |
          +---------------------+----------------------+
                                v
          +--------------------------------------------+
          | SERVE + DELIVER                            |
          | FastAPI in Docker, Streamlit app,          |
          | Tableau Public dashboard, LLM explanations |
          | Streamlit Cloud app + GitHub Pages case    |
          | study                                      |
          +--------------------------------------------+
```

## Backtesting and model validation

```
 feature table for horizon h, one row per item-store-week
   |
   v
 leakage rule: lags and windows use only weeks <= t - h
               target-week price and promo are planned inputs
   |
   v
 time-based folds (expanding window, never random)
 train on labels through min(train_end, test_start - h)
   |
   +--> validation folds, set in configs/forecast.yaml
   +- - > final test: the last 52 weeks, run once
   |
   v   for each fold
 +--------------+   +--------------------+   +-------------+   +-----------+
 | 3 baselines  |   | Poisson regression |   | LightGBM    |   | small     |
 | no fitting   |   | 1M sampled rows    |   | Poisson     |   | neural    |
 |              |   |                    |   | objective   |   | net       |
 +------+-------+   +---------+----------+   +------+------+   +-----+-----+
        |                     |                     |                |
        +---------------------+----------+----------+----------------+
                                          v
 metrics:  WAPE, MAE, RMSE, bias, item-week WAPE, lift vs best baseline
 segments: promo vs no promo, volume decile
                                          v
 logged:   an MLflow run with settings, data version, metrics, and models
 bar:      best model's final-test WAPE at least 10% below the best baseline
 checks:   tests that future units never change earlier features;
           fold windows are ordered and disjoint
 price:    log-log fit with item and store effects (observational, never
           causal); DML studied on simulated data
```

## Build sequence

The sequence is in priority order. The 2026-11-16 target does not limit scope (decision 44); whatever is unfinished on that date continues after it. Per decision 33, before each step I explain it in plain terms and wait for your go-ahead.

| Step | What | Who | Done when |
|---|---|---|---|
| 0a | Download the Dominick's files: for each of the 28 categories the `upcXXX.csv` and `wXXX.csv` files, plus the customer count, demographics, and store files, and re-download cereal. Put them in `data/raw/<category>/` and `data/raw/dominicks_general/`, in batches, checking free disk space | You | Files are in place; I verify each against its checksum |
| 0b | Install Docker Desktop (needs your password) | You | `docker --version` works |
| 0c | Create a Snowflake trial account (no payment details). Credentials go only in your local dbt profile, never in the repo and never to me | You | You can sign in to Snowsight |
| 0d | Remove the dunnhumby code and the earlier saved-models and input-check code; add the dbt and Postgres dependencies | Me, after your OK | Tests pass without them |
| 1 | Data foundation: gzip raw files, Postgres in Docker, a dbt project that runs on both Postgres and Snowflake with staging and mart models for all categories and the general files, tests and schema contracts, a load of the raw files into Snowflake, the metric layer, the JSON quality report, a parity check against the old SQL, then the old SQL is deleted; CI runs lint, types, tests, and a dbt build on fixtures | Me | `dbt build` passes on the full data and the data dictionary is updated |
| 2 | Forecaster: the shared feature definition, a versioned feature table, MLflow tracking, baselines, Poisson regression, LightGBM, the small neural net, the backtest, a model card, the log-log fit, and the final test run once | Me | Backtest reproduces; final test judged against the 10% bar |
| 2b | FreshRetailNet-50K pipeline in the same pattern, and a stockout and censored-demand module | Me | Pipeline passes its checks |
| 3 | Simulator, policies, and evaluation: the known-truth generator with confounded prices, inventory, and rival rules; fixed price, rolling refit, Thompson sampling, and DDPG; the reward and limits; regret and profit comparisons with paired seeds; A/B and switchback tests; the DML bias study | Me | The success criterion is judged; all outputs labeled simulated |
| 4 | MLOps: Airflow runs ingest, features, training, and evaluation; the MLflow registry with champion/challenger; drift and error monitoring on replayed windows; the rollback rule | Me | A scheduled run finishes end to end |
| 5 | Serve: FastAPI with typed schemas and latency and success tracking, Docker images, the fallback price, and the Streamlit app | Me | The app runs in Docker |
| 6 | LLM explanations with a local open model, explaining and citing results only; Recall@k, citation correctness, and faithfulness measured | Me | Retrieval metrics reported |
| 7 | Delivery: the Tableau Public dashboard on aggregated simulated data, the hosted Streamlit app, the GitHub Pages case study, the README with results and diagrams | Me and you | Public links work |

## What you do yourself
- Download the data (step 0a), install Docker Desktop (step 0b), and create the Snowflake trial account (step 0c).
- Commit and push; I never run git commit or push.
- Create the free accounts for Streamlit Community Cloud, GitHub Pages, and Tableau Public when step 7 comes.
- Record the 2-3 minute walkthrough video.
- Decide H4, the resume framing, once results exist.

## Pipeline stage checklist
Checked against the six standard data science pipeline stages. Everything below is planned unless marked built.

| Stage | Plan |
|---|---|
| 0. The question | Success criteria are fixed in the PRD: a 10% WAPE bar for the forecaster and a simulated-profit bar for the policy |
| 1. Collection | Raw layer unchanged and gzipped, with checksums recorded and verified on re-download |
| 2. Cleaning | dbt tests, versioned schema contracts, checksum and date-range freshness checks, and the JSON quality report; a failed check stops the run |
| 3. Features | One shared definition for training and serving, saved and versioned per data version, with point-in-time correctness tested |
| 4. Training | Baselines, Poisson regression, LightGBM, and a small neural net, every run tracked in MLflow |
| 5. Evaluation | Rolling-origin backtest, final test run once, segment slices, and simulated policy evaluation |
| 6. Deployment and monitoring | FastAPI in Docker, drift and error monitoring on replayed history with written thresholds, rollback, and champion/challenger |
| Governance | Data version, config, seeds, library versions, and git state logged for every run; schema contracts between stages |

Choices made on purpose: Snowflake runs on its time-limited trial and Postgres is the permanent target, so downstream stages read local exports of the built tables and nothing depends on the trial (decision 51); batch processing only, since the data is historical (decision 21); a versioned SQL feature table in place of a feature store; no access-control workflow beyond git history, since this is a one-person project; and monitoring runs on replayed historical windows because there is no live data.

## What is real and what is simulated
- **Real data:** Dominick's scanner data (forecaster inputs and accuracy results) and FreshRetailNet-50K stockout data.
- **Simulated:** the simulator, the shopper segments, the rival rules, and every policy result built on them. The simulator's price sensitivity is an assumption, swept over a range, because price effects estimated from observational data are biased.
- **Descriptive only:** any price-response estimate from the real data is observational and is never called causal.

See [DECISIONS.md](DECISIONS.md) for the reasoning behind each choice and [OPEN_DECISIONS.md](OPEN_DECISIONS.md) for what is still undecided.
