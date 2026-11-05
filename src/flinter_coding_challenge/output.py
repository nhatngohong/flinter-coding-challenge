"""CSV and benchmark report writing."""

import csv
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import polars as pl

from .aggregation import REPORT_COLUMNS
from .errors import OutputError


def _format_value(column: str, value: Any) -> str:
    if value is None:
        return ""
    if column in {"total_spend", "CPA"}:
        return f"{value:.2f}"
    if column == "CTR":
        return f"{value:.4f}"
    return str(value)


def _write_report(path: Path, frame: pl.DataFrame) -> Path:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(REPORT_COLUMNS)
            for row in frame.iter_rows(named=True):
                writer.writerow([_format_value(column, row[column]) for column in REPORT_COLUMNS])
        return temporary
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise OutputError(f"Could not write report {path}: {exc}") from exc


def write_reports(
    output_dir: Path, top_ctr: pl.DataFrame, top_cpa: pl.DataFrame
) -> None:
    destinations = [
        (output_dir / "top10_ctr.csv", top_ctr),
        (output_dir / "top10_cpa.csv", top_cpa),
    ]
    temporary_files: list[tuple[Path, Path]] = []
    try:
        for destination, frame in destinations:
            temporary_files.append((_write_report(destination, frame), destination))
        for temporary, destination in temporary_files:
            os.replace(temporary, destination)
    except (OSError, OutputError) as exc:
        for temporary, _ in temporary_files:
            temporary.unlink(missing_ok=True)
        if isinstance(exc, OutputError):
            raise
        raise OutputError(f"Could not replace report files: {exc}") from exc


def write_benchmark(output_dir: Path, metrics: dict[str, Any]) -> Path:
    path = output_dir / "benchmark.json"
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise OutputError(f"Could not write benchmark file {path}: {exc}") from exc
    return path
