"""Shared CSV fixture helpers."""

import csv
import gzip
from pathlib import Path
from typing import Iterable, Sequence

import pytest

CSV_COLUMNS = [
    "campaign_id", "date", "impressions", "clicks", "spend", "conversions"
]


@pytest.fixture
def write_csv():
    """Write rows to a CSV or gzip CSV and return its path."""

    def _write_csv(
        path: Path,
        rows: Iterable[Sequence[object]],
        columns: Sequence[str] = CSV_COLUMNS,
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "wt", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            writer.writerows(rows)
        return path

    return _write_csv
