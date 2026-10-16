# Decision log

| # | Date | Decision | Rationale |
|---|------|----------|-----------|
| 1 | 2026-10-16 | Python 3.12, managed with `uv` (`uv.lock` committed) | Reproducible installs, fast CI |
| 2 | 2026-10-16 | `src/` layout, hatchling build backend | Prevents accidental imports from repo root |
| 3 | 2026-10-16 | Runtime deps limited to pydantic + pyyaml in M0; others added per milestone | Avoid unnecessary dependencies |
| 4 | 2026-10-16 | Ruff (lint+format), mypy strict on `src/`, pytest | Per plan §13 |
| 5 | 2026-10-16 | Data dirs git-ignored except `.gitkeep` | Raw/generated data must never be committed |
