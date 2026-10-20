# PricePilot — working rules

## Hard rules (set by the owner)
- Never run `git commit`, `git push`, or create remotes. The owner commits and pushes. Leave changes uncommitted.
- The owner approves all changes. Propose before large or structural edits; stop at each milestone for review.
- Never invent results, metrics, or passing tests. Report commands run and their real output.
- No paid services, no secrets in files, no personal customer data.
- Do not label simulated outcomes as real impact; never call observational price coefficients causal.

## Code conventions
- Each file starts with a short module docstring: what the file does, in one or two lines.
- Each function gets a short docstring stating what it does. No inline comments unless the logic is non-obvious. No changelog or status comments in code.
- Typed functions, small modules, config in `configs/` instead of hardcoded paths.
- Python 3.12 via `uv`. Before finishing a change: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`.
- Add dependencies only when a milestone needs them. No empty placeholder files.
- Notebooks for exploration only; reusable logic goes in tested modules under `src/pricepilot/`.

## Project docs
- `docs/DECISIONS.md` is the decision log: append a row for each architectural or analytical decision.
- Full scope lives in `docs/PRD.md`; milestones are 0–7 (repo, data, model, pricing, MLOps, API/app, RAG, dashboard).
