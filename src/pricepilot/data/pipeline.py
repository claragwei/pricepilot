"""Pipeline entry point: extract, validate, transform, and load the category data.

Run with: uv run python -m pricepilot.data.pipeline [--sample]
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from pricepilot.config import DataConfig, data_dir, load_data_config
from pricepilot.data import ingest, load, transform, validate


class PipelineError(Exception):
    """Raised when a required data-quality check fails."""


@dataclass
class RunResult:
    """Outcome of a successful pipeline run."""

    source_version: str
    row_counts: dict[str, int]
    report: validate.QualityReport
    output_dir: Path


def run(cfg: DataConfig, root: Path | None = None, sample: bool = False) -> RunResult:
    """Run the full pipeline; raise PipelineError if a required check fails."""
    root = root or data_dir()
    suffix = "_sample" if sample else ""
    output_dir = root / (cfg.output_dir + suffix)
    rejects_dir = root / (cfg.rejects_dir + suffix)
    started = datetime.now(UTC)
    t0 = time.perf_counter()

    sources = ingest.locate_sources(cfg, root)
    version = sources.source_version + ("-sample" if sample else "")
    report = validate.QualityReport(source_version=version)
    record: dict[str, object] = {
        "started_at": started.isoformat(),
        "source_version": version,
        "sample": sample,
        "sources": sources.manifest,
    }

    con = duckdb.connect()
    try:
        ingest.register_raw(con, sources, cfg, sample)
        transform.build_dimensions(con, cfg)
        report.checks += validate.validate_inputs(con)
        if not report.failed_required():
            transform.build_staging(con, cfg)
            transform.build_facts(con, version)
            report.checks += validate.validate_outputs(con, cfg)
            report.stats = validate.collect_stats(con)
        failed = report.failed_required()
        counts: dict[str, int] = {}
        if not failed:
            counts = load.load_tables(con, output_dir)
            counts["rejected_movement"] = load.write_rejects(con, rejects_dir)
        record.update(
            status="failed" if failed else "success",
            duration_s=round(time.perf_counter() - t0, 3),
            input_rows=report.stats.get("input_rows"),
            output_rows=counts,
            failed_checks=[c.name for c in failed],
        )
        load.write_report(report, output_dir)
        load.append_run_log(record, output_dir)
    finally:
        con.close()

    if failed:
        details = "; ".join(f"{c.name}: {c.detail}" for c in failed)
        raise PipelineError(f"Required data-quality checks failed: {details}")
    return RunResult(version, counts, report, output_dir)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Run the PricePilot data pipeline.")
    parser.add_argument("--sample", action="store_true", help="process only the configured sample")
    args = parser.parse_args(argv)
    try:
        result = run(load_data_config(), sample=args.sample)
    except (ingest.IngestError, PipelineError) as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1
    print(f"Pipeline succeeded: {result.source_version}")
    for table, n in result.row_counts.items():
        print(f"  {table}: {n} rows")
    print(f"Output: {result.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
