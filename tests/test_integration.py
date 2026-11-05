"""End-to-end tests from CSV input through report files."""

import pytest

from flinter_coding_challenge.aggregation import (
    REPORT_COLUMNS,
    aggregate_campaigns,
    select_top_reports,
)
from flinter_coding_challenge.config import AppConfig, validate_config
from flinter_coding_challenge.errors import ConfigurationError, InputDataError
from flinter_coding_challenge.output import write_reports
from flinter_coding_challenge.validation import scan_csv


def run_pipeline(input_path, output_dir):
    result = aggregate_campaigns(input_path)
    top_ctr, top_cpa = select_top_reports(result.campaigns)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_reports(output_dir, top_ctr, top_cpa)
    return result


@pytest.mark.parametrize("compressed", [False, True], ids=["csv", "gzip"])
def test_csv_to_both_output_files(tmp_path, write_csv, compressed):
    suffix = ".csv.gz" if compressed else ".csv"
    input_path = tmp_path / f"ads{suffix}"
    output_dir = tmp_path / "nested" / "results"
    rows = [
        ["A", "2025-01-01", 1000, 100, "10.00", 2],
        ["A", "2025-01-02", 3000, 300, "30.00", 8],
        ["B", "2025-01-01", 1000, 50, "15.00", 3],
        ["D", "2025-01-01", 100, 20, "2.00", 0],
        ["ZERO", "2025-01-01", 0, 0, "0.00", 0],
    ]
    write_csv(input_path, rows)
    (output_dir / "top10_ctr.csv").parent.mkdir(parents=True, exist_ok=True)
    (output_dir / "top10_ctr.csv").write_text("old report\n", encoding="utf-8")
    (output_dir / "top10_cpa.csv").write_text("old report\n", encoding="utf-8")

    result = run_pipeline(input_path, output_dir)

    expected_header = ",".join(REPORT_COLUMNS)
    assert result.rows_read == 5
    assert result.skipped_rows == 0
    assert (output_dir / "top10_ctr.csv").read_text(encoding="utf-8") == (
        expected_header + "\n"
        "D,100,20,2.00,0,0.2000,\n"
        "A,4000,400,40.00,10,0.1000,4.00\n"
        "B,1000,50,15.00,3,0.0500,5.00\n"
    )
    assert (output_dir / "top10_cpa.csv").read_text(encoding="utf-8") == (
        expected_header + "\n"
        "A,4000,400,40.00,10,0.1000,4.00\n"
        "B,1000,50,15.00,3,0.0500,5.00\n"
    )


def test_empty_csv_writes_header_only_reports(tmp_path, write_csv):
    input_path = write_csv(tmp_path / "empty.csv", [])
    output_dir = tmp_path / "results"

    run_pipeline(input_path, output_dir)

    expected = ",".join(REPORT_COLUMNS) + "\n"
    assert (output_dir / "top10_ctr.csv").read_text(encoding="utf-8") == expected
    assert (output_dir / "top10_cpa.csv").read_text(encoding="utf-8") == expected


def test_missing_input_file_is_reported(tmp_path):
    config = AppConfig(input_csv=tmp_path / "missing.csv", output_dir=tmp_path / "out")

    with pytest.raises(ConfigurationError, match="does not exist"):
        validate_config(config)


def test_missing_required_column_is_reported(tmp_path, write_csv):
    path = write_csv(
        tmp_path / "missing-column.csv",
        [],
        columns=["campaign_id", "date", "impressions", "clicks", "spend"],
    )

    with pytest.raises(InputDataError, match="conversions"):
        scan_csv(path)


def test_zero_byte_csv_is_reported_as_invalid_input(tmp_path):
    path = tmp_path / "zero-bytes.csv"
    path.write_bytes(b"")

    with pytest.raises(InputDataError):
        scan_csv(path)
