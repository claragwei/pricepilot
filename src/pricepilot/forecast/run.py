"""Forecast entry point: run the validation backtest, or the one-time final test with --final."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import duckdb

from pricepilot.config import ForecastConfig, data_dir, load_forecast_config
from pricepilot.forecast.backtest import run_backtest


def write_json(payload: dict[str, Any], path: Path) -> None:
    """Write a JSON file via a temp file so reruns replace it safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
    os.replace(tmp, path)


def summary_lines(results: dict[str, Any]) -> list[str]:
    """Format pooled metrics per horizon and model as plain text."""
    lines = []
    for horizon, result in results["horizons"].items():
        lines.append(f"horizon {horizon} week(s), {result['pooled']['n']} scored rows")
        for name, s in result["pooled"]["models"].items():
            lines.append(
                f"  {name:<15} WAPE {s['wape']:.3f}  item-week WAPE {s['item_week_wape']:.3f}"
                f"  bias {s['bias']:+.3f}"
                f"  lift vs seasonal-naive {s['lift_vs_seasonal_naive']:+.1%}"
            )
    return lines


def run(
    cfg: ForecastConfig, input_dir: Path, output_dir: Path, final: bool, rerun_final: bool = False
) -> dict[str, Any]:
    """Run the validation folds, or the final test once, and write the metrics file."""
    target = output_dir / ("final_metrics.json" if final else "validation_metrics.json")
    if final and target.exists() and not rerun_final:
        raise FileExistsError(f"{target} exists; the final test is run once (use --rerun-final)")
    folds = [cfg.final_test] if final else cfg.folds
    con = duckdb.connect()
    try:
        results = run_backtest(con, cfg, input_dir, folds)
    finally:
        con.close()
    results["split"] = "final" if final else "validation"
    write_json(results, target)
    return results


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final", action="store_true", help="score the final test window")
    parser.add_argument("--rerun-final", action="store_true", help="overwrite an earlier final run")
    args = parser.parse_args(argv)
    cfg = load_forecast_config()
    try:
        results = run(
            cfg,
            data_dir() / cfg.input_dir,
            data_dir() / cfg.output_dir,
            final=args.final,
            rerun_final=args.rerun_final,
        )
    except FileExistsError as exc:
        print(exc, file=sys.stderr)
        return 1
    print("\n".join(summary_lines(results)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
