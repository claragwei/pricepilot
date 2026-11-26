# Interview prep

What to know, say, and be able to defend for each part of PricePilot. Updated when a milestone finishes. Every claim here is either something that was run (with the command) or marked as planned. Do not state a planned item as done.

## The 60-second pitch
PricePilot is an explainable pricing decision-support system built on real retail scanner data (Dominick's, 28 categories). It forecasts weekly demand, simulates alternative pricing policies, and recommends prices within business limits. Forecast accuracy is measured on real data. Everything about pricing policies is **simulated** and labeled that way, and price effects estimated from observational data are never called causal.

## Status
| Milestone | State |
|---|---|
| 0 Repository and environment | Done |
| 1 Data foundation (dbt, Postgres, Snowflake) | In progress: raw data loaded and verified, staging models built for all 28 categories; marts and the Snowflake run still to do |
| 2 to 7 | Planned |

## Milestone 0: repository and environment (done)
Committed as `b5abe1d` (2026-10-16). Source: that commit and decisions 1 to 5 in `docs/DECISIONS.md`.

### What was built
- **Reproducible Python environment:** Python 3.12 pinned in `.python-version`, dependencies managed by `uv`, and `uv.lock` committed so every install gets identical versions (decision 1).
- **`src/` layout with a hatchling build:** code lives in `src/pricepilot/`, so tests import the installed package and not stray files in the repo root (decision 2).
- **Minimal dependencies:** only pydantic and pyyaml at first; everything else is added when a milestone needs it (decision 3).
- **Quality gates:** Ruff for linting and formatting, mypy in strict mode on `src/`, and pytest (decision 4).
- **Config pattern:** `src/pricepilot/config.py` loads YAML settings into typed pydantic models, with `tests/unit/test_config.py` covering it. Settings live in `configs/`, not in code.
- **CI:** `.github/workflows/ci.yml` runs on every pull request and push to `main`. It installs from the lockfile (`uv sync --frozen`), then runs ruff, ruff format check, mypy, and pytest.
- **Pre-commit:** `.pre-commit-config.yaml` runs Ruff before each commit.
- **Data hygiene:** `.gitignore` excludes `data/raw`, `data/interim`, `data/processed`, parquet and database files, `.env`, and MLflow output. Empty `.gitkeep` files keep the folders in git (decision 5). `.env.example` shows which environment variables exist without containing secrets.
- **Docs:** the PRD (scope, success criteria) and the decision log.

### How it was verified
- The same four checks CI runs, run locally: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`. In this session they pass on the current repo: ruff clean, 29 files formatted, mypy clean on 15 source files, 34 tests passed. I did not re-run the repo as it was at the M0 commit.
- `uv sync --frozen` in CI fails if `pyproject.toml` and `uv.lock` disagree, which catches dependency drift.

### Concepts to be able to explain
- **Lockfile:** pins exact versions of every dependency, so a build today matches a build in six months.
- **`src/` layout:** prevents tests from passing only because they imported local files that wouldn't ship.
- **Strict typing (mypy):** catches wrong argument types and missing return values before runtime.
- **Linting vs. formatting:** lint finds likely bugs and style problems; the formatter makes layout automatic so reviews focus on logic.
- **CI:** an automatic gate on every change, so a broken main branch is hard to produce.
- **Config separate from code:** change settings (paths, thresholds) without editing logic, and validate them with a typed schema at load time.
- **Never commit data or secrets:** raw data is large and often licensed; secrets in git history are very hard to remove.
- **Decision log:** a table of what was chosen, when, and why, so you can explain a choice months later.

### Questions you should be ready for
- *Why uv and a lockfile?* Reproducible, fast installs, and CI uses the same versions as your laptop.
- *Why mypy strict this early?* Cheaper to keep a small codebase fully typed than to retrofit it.
- *What does your CI do, and what would break it?* Lint, format, types, tests. A type error, a failing test, or a lockfile that doesn't match `pyproject.toml` fails it.
- *How do you keep secrets and data out of the repo?* `.gitignore` for data and `.env`, a committed `.env.example` with placeholders, and credentials in local profiles.
- *Why add dependencies per milestone?* Smaller attack surface, faster installs, and each dependency has a reason you can state.

## Milestone 1 so far: raw layer and environment

### What was built
- **Raw layer:** 28 categories x 2 files (UPC = product descriptions, movement = weekly units, price, margin, promo per product per store), plus customer-count and store-demographics files. Stored gzipped, unchanged, in `data/raw/<category>/`, git-ignored.
- **Checksums:** `data/raw/CHECKSUMS.sha256` holds the SHA-256 of each original file.
- **Tools:** Docker Desktop (Postgres will run in a container), a Snowflake trial account, and `dbt-core`, `dbt-postgres`, `dbt-snowflake`.
- **Clean-up:** removed a simulated dataset (dunnhumby) and hand-built model-saving, lineage, and input-check code, because dbt tests and MLflow replace them (decisions 30 and 48).

### How it was verified (real commands)
| Check | Command | What it proved |
|---|---|---|
| Archives not corrupt | `unzip -tq file.zip` | Each download finished intact |
| Duplicates | `cmp a b` | Copies were byte-identical, safe to drop |
| File type | `file`, `xxd` header | The `.SD2` files are SAS V6 datasets, not audio and not CSV |
| Compression correct | decompress each `.gz`, recompute SHA-256, compare to the recorded hash | 58 of 58 matched |
| Environment | `docker --version`, `docker info` | Docker daemon is running |
| Code still healthy | `ruff check`, `ruff format --check`, `mypy`, `pytest` | Lint clean, types clean, 34 tests passed |

### Slice 1a: Postgres container and dbt skeleton
- **Built:** `docker-compose.yml` (Postgres 16, bound to localhost only, with a healthcheck and a named volume), a minimal dbt project in `dbt/`, and `dbt/profiles.yml` with a Postgres target and a Snowflake target. All credentials come from environment variables.
- **Verified:** `docker compose up -d`, the container reported `healthy`, and `uv run dbt debug --project-dir dbt --profiles-dir dbt` ended with "Connection test: OK" and "All checks passed!". The Snowflake target has not been tested yet.
- **A real problem and how it was handled:** port 5432 was already in use by a process I couldn't identify, and `docker compose up` failed with "address already in use". I didn't kill it; I moved the project to port 5433 and recorded it as decision 52.
- **Concepts:** a healthcheck tells you the database is ready for connections, not just that the container started; a named volume keeps data when the container is recreated; binding to `127.0.0.1` keeps the database off the network; `env_var()` in dbt keeps secrets out of files.

### Slice 1b: raw loader into Postgres
- **Built:** `pricepilot.warehouse.load_raw` streams each gzipped CSV into a Postgres table with `COPY`. `stream.py` does the reading: it matches columns by header name, drops the two hex columns, hashes the bytes, and counts rows. Settings are in `configs/warehouse.yaml`.
- **Checks built into the loader:** the decompressed SHA-256 must equal the recorded checksum, and the table's row count must equal the rows read. If either fails, that file's load rolls back. Every load is logged in `raw._load_log`.
- **Verified (cereal and bathroom tissues, real run):** loaded 6,602,582 rows (`wcer`), 1,627,284 (`wtti`), 490 (`upccer`), and 128 (`upctti`). Row counts match `gzip -dc | wc -l` minus the header for all four. A source row for `wtti` (store 14, UPC 3700060311, weeks 343 to 345) matches the table value for value. Cereal loaded in 9.2 s, tissues in 2.2 s. 
- **Full load (all 28 categories):** 56 tables loaded, 175,521,485 movement rows, 13 GB in Postgres. An independent line count of every source file (`gzip -dc | wc -l` minus the header, run separately from the loader) matched the load log for all 56 tables. A `wgro` source row (UPC-first column order) also matched its table row.
- **A real failure and the fix:** the first full run stopped at `upcptw` with `value "1112141" is out of range for type smallint` in the `WSTART` column. The loader failed loudly and rolled that file back, as designed. `WSTART` is mostly blank with a few odd values, so I widened its type to `integer` instead of interpreting it, and re-ran the remaining categories. Lesson: guessing column types from the first rows is risky, and a loud failure is better than silent truncation.
- **Tests:** 6 unit tests for the stream, and 2 integration tests against the real Postgres container (types and counts, and rollback on a checksum mismatch). The integration tests skip with a message if Postgres isn't running.
- **A real trap avoided:** movement files come in three column orders (`UPC` first in four categories, `PRICE` before `QTY` in two). Loading by position would have swapped columns silently, with no error. Tissues has the `PRICE`-before-`QTY` order, and its loaded values are correct.
- **Concepts:** `COPY` is the fast bulk-load path in Postgres; streaming means a 458 MB file never sits in memory; verifying hash and row count in the same transaction means a bad file never becomes a table; header-based column mapping is how you survive inconsistent exports.
- **Questions to be ready for:** *How do you know the load is correct?* Hash, row count against an independent `wc -l`, and a spot check of a source row. *Why drop columns in the raw layer?* They duplicate PRICE and PROFIT, would cost about 5 GB, and the original files remain.

### Slice 1c: staging models (cleaning), piloted on cereal and tissues, then all 28 categories
- **Built:** dbt models in `dbt/models/staging/`. `stg_dominicks__movement_classified` (a view) tags every raw row with a reject reason. `stg_dominicks__movement` keeps valid rows and adds unit price, sales dollars (`price * move / qty`, from the manual) and a margin that is null when missing, 0 or 100 and above. `stg_dominicks__movement_rejects` keeps the removed rows with the reason. `stg_dominicks__products` comes from the UPC files. Rules are decisions 54 to 56.
- **Why these rules:** the manual says `OK = 0` is "trash". Among `OK = 1` rows, price > 0 and `MOVE` > 0 hold for exactly the same rows in cereal and tissues, so zero price means no sale recorded; we do not fill those weeks (decision 25). Missing values are left null, not imputed.
- **Verified (real run):** `dbt build` gave PASS=22 WARN=1 ERROR=0 (3 table models, 1 view, 18 data tests, 1 unit test). Clean rows: cereal 4,707,776 and tissues 1,149,973, equal to independent counts on the raw tables of `ok = 1 and price > 0 and move > 0`. Rejected: cereal 1,753,521 no sale and 141,285 `OK = 0`; tissues 450,425 and 26,886. A test checks that kept plus rejected rows equal all classified rows.
- **The warning:** the promo code test warns on 2 values, `G` (11,228 rows) and `L` (1 row), which are not in the manual's list of B, C and S. They are kept as given.
- **Tests used:** `unique_combination_of_columns` (one row per category, store, item, week), `not_null`, `relationships` (every movement UPC is in the products table), `expression_is_true` (price and units above 0, margin below 100), `accepted_values` with severity warn, a singular test for per-reason reject-share limits, and a unit test with four mock rows (normal, bundle at 3 for $2, no sale, `OK = 0`).
- **All 28 categories (real run):** `dbt build` took 441 s and gave PASS=20 WARN=1 ERROR=1 at first. Staged clean rows total 96,717,530 and rejected rows 78,803,955, which sum to the raw total of 175,521,485. Every category's clean count equals an independent count on the raw table (`ok = 1 and price > 0 and move > 0`, store and week present).
- **Two real findings from the wider run:** (1) 1,259 blank rows (only a UPC) in `coo`, `cra` and `sna` failed the `OK` not-null test; cereal and tissues had none. They now get their own reject reason, `incomplete_row`. (2) 77,498 clean rows in `sha` and `tbr` have a UPC missing from the source UPC files (466 and 60 UPCs); I checked that the loaded `upcsha` table has the same 2,713 rows as the source file. The link test now warns and the rows are kept. The promo-code warning now also shows codes `M` and `N`.
- **Why views:** free disk was about 20 GB and full tables would take about 15 GB. Views keep the same rules and tests but re-scan the raw tables, so the tests are slow (the unique-row test took 322 s). One setting switches back to tables.
- **Open items:** 1 pilot row is flagged as a units outlier and I have not looked at it; the reject-share limits held but are still first guesses; the Snowflake run is not done; negative margins (82,752 rows in the pilot) are kept and I have not confirmed they mean selling below cost; the 105-row gap between the 77,498 failing rows and the 77,603 clean rows with missing UPCs is not explained.
- **Questions to be ready for:** *Why not delete rejected rows?* They go to a rejects table so counts reconcile and a rule change can be audited. *Why not impute?* A made-up price or demand looks like real data; missing weeks cannot be told from unstocked items. *Why per-reason limits instead of one threshold?* In many categories most weeks legitimately have no sale, so one limit fails good data.

### Concepts to be able to explain
- **Raw / landing layer (bronze):** keep source data untouched so any number can be traced back. Cleaning happens in later layers.
- **Checksum:** a hash of a file's bytes. Same hash means same content. It detects corruption and proves a re-download matches.
- **Why gzip:** about 11x smaller (11 GB to 0.9 GB here). DuckDB reads `.csv.gz` directly.
- **Docker:** runs the database in an isolated, reproducible container so CI and other people get the same environment.
- **Why Postgres and Snowflake both:** Postgres is free, local, and permanent, and CI uses it. Snowflake is a cloud warehouse on a 30-day trial, used to show the same dbt models running there. Nothing downstream depends on the trial (decision 51).
- **Why replace custom code with dbt and MLflow:** standard tools are what teams use, and they replace code that would otherwise need maintaining.
- **Secrets:** credentials live only in the local dbt profile outside the repo.

### Questions you should be ready for
- *Why did you gzip and checksum the raw files?* Integrity and reproducibility: you can prove the stored copy matches what was downloaded, and re-downloads can be verified.
- *How did you know the files were valid?* Archive tests, file-type inspection, duplicate comparison, and a full round-trip hash comparison.
- *You found files that weren't what you expected. What happened?* 13 UPC downloads were SAS binaries instead of CSV. I identified the format from its header, then re-downloaded the CSV versions and checked them before keeping them.
- *Why not use the dunnhumby data?* Simulated, with almost no price variation (92% of series never change price), so it can't support demand-response work.
- *Why is licensing not a blocker?* Student, non-commercial portfolio project (decision 23). Sources are credited and raw files stay out of git.

## Forecasting design (planned, with early code in the repo)
Design decisions to defend. These describe the plan in `docs/ARCHITECTURE.md`, not finished results.
- **Time-based validation:** expanding-window folds, never random splits, because future data must not train a model scored on the past.
- **Leakage rule:** for horizon h, lags and rolling windows use only weeks up to t minus h. Price and promo for the target week are treated as planned inputs. Tests are planned that check future rows never change earlier features.
- **Final test:** the last 52 weeks, run once.
- **Models:** three no-fit baselines, Poisson regression, LightGBM with a Poisson objective, and a small neural net.
- **Metrics:** WAPE (weighted absolute percentage error), MAE, RMSE, bias, and lift against the best baseline. Segments: promo vs. no promo, volume decile.
- **Success bar:** the best model's final-test WAPE at least 10% below the best baseline's. Say plainly if it isn't met.
- **Price effects:** a log-log fit with item and store effects is observational and never causal. A double machine learning (DML) study on simulated data with known truth shows how much bias the observational fit has.

## Simulation and policy evaluation (planned)
- **Simulated:** the demand generator, shopper segments, rival rules, and every policy result. Price sensitivity is an assumption swept over a range.
- **Policies:** fixed price, rolling refit, Thompson sampling, DDPG, with price limits and a fallback price.
- **Evaluation:** regret and profit with paired seeds, A/B and switchback tests, intervals that must exclude zero.
- **Never say:** "increases revenue by X%". Say: "in simulation, under assumed price sensitivities, policy A earned more profit than B in N of M settings".

## MLOps, serving, RAG, delivery (planned)
Fill in with commands, results, and questions as each milestone finishes.

## What to say when asked what you'd do in a job
- Keep the raw layer immutable, verify it with checksums, and gate every stage with tests that fail the run.
- Version data, config, seeds, library versions, and git state for each model run.
- Separate offline accuracy from decision quality, and label simulated results as simulated.
