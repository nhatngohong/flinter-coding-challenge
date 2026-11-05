"""Unit tests for campaign aggregation, rates, and ranking."""

import polars as pl
import pytest

from flinter_coding_challenge.aggregation import aggregate_campaigns, select_top_reports


def test_duplicate_campaigns_are_summed_and_rates_use_totals(tmp_path, write_csv):
    path = write_csv(
        tmp_path / "ads.csv",
        [
            ["A", "2025-01-01", 1000, 100, "10.00", 2],
            ["A", "2025-01-02", 3000, 300, "30.00", 8],
            ["B", "2025-01-01", 1000, 50, "15.00", 3],
        ],
    )

    result = aggregate_campaigns(path)

    campaign_a = result.campaigns.filter(pl.col("campaign_id") == "A").row(
        0, named=True
    )
    assert campaign_a["total_impressions"] == 4000
    assert campaign_a["total_clicks"] == 400
    assert campaign_a["total_spend"] == pytest.approx(40.0)
    assert campaign_a["total_conversions"] == 10
    assert campaign_a["CTR"] == pytest.approx(0.1)
    assert campaign_a["CPA"] == pytest.approx(4.0)
    assert result.rows_read == 3
    assert result.skipped_rows == 0


def test_zero_impressions_campaign_is_excluded_and_zero_conversions_has_no_cpa(
    tmp_path, write_csv
):
    path = write_csv(
        tmp_path / "edge-cases.csv",
        [
            ["ZERO-IMP", "2025-01-01", 0, 0, "0.00", 0],
            ["NO-CONV", "2025-01-01", 100, 20, "2.00", 0],
            ["WITH-CONV", "2025-01-01", 100, 10, "8.00", 2],
        ],
    )

    result = aggregate_campaigns(path)
    top_ctr, top_cpa = select_top_reports(result.campaigns)

    assert set(result.campaigns.get_column("campaign_id").to_list()) == {
        "NO-CONV", "WITH-CONV"
    }
    no_conv = result.campaigns.filter(pl.col("campaign_id") == "NO-CONV").row(
        0, named=True
    )
    assert no_conv["CTR"] == pytest.approx(0.2)
    assert no_conv["CPA"] is None
    assert top_ctr.get_column("campaign_id").to_list()[0] == "NO-CONV"
    assert "NO-CONV" not in top_cpa.get_column("campaign_id").to_list()


def test_invalid_rows_are_skipped_and_reason_counts_are_reported(tmp_path, write_csv):
    path = write_csv(
        tmp_path / "invalid-rows.csv",
        [
            ["GOOD", "2025-01-01", 100, 10, "5.00", 1],
            ["", "2025-01-01", 100, 10, "5.00", 1],
            ["BAD-DATE", "2025-02-30", 100, 10, "5.00", 1],
            ["BAD-IMP", "2025-01-01", "not-an-int", 10, "5.00", 1],
            ["BAD-CLICKS", "2025-01-01", 100, -1, "5.00", 1],
            ["BAD-SPEND", "2025-01-01", 100, 10, "NaN", 1],
            ["BAD-CONV", "2025-01-01", 100, 10, "5.00", -1],
            ["BAD-MISSING", "2025-01-01", 100, 10, "", 1],
        ],
    )

    result = aggregate_campaigns(path)

    assert result.rows_read == 8
    assert result.skipped_rows == 7
    assert result.invalid_campaign_rows == 1
    assert result.invalid_date_rows == 1
    assert result.invalid_metric_rows == 5
    assert result.campaigns.get_column("campaign_id").to_list() == ["GOOD"]


def test_top_ten_sort_orders_and_cutoffs_are_correct(tmp_path, write_csv):
    rows = [
        [f"C{i:02d}", "2025-01-01", 1000, 100 + i, str(100 + i), 10]
        for i in range(1, 13)
    ]
    result = aggregate_campaigns(write_csv(tmp_path / "rankings.csv", rows))

    top_ctr, top_cpa = select_top_reports(result.campaigns)

    assert top_ctr.get_column("campaign_id").to_list() == [
        "C12", "C11", "C10", "C09", "C08", "C07", "C06", "C05", "C04", "C03"
    ]
    assert top_cpa.get_column("campaign_id").to_list() == [
        "C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10"
    ]
    assert top_ctr.height == top_cpa.height == 10


def test_ties_use_ascending_campaign_id_and_fewer_than_ten_are_kept(
    tmp_path, write_csv
):
    tied_rows = [
        [f"CMP{i:02d}", "2025-01-01", 100, 50, "10.00", 10]
        for i in range(12)
    ]
    tied = aggregate_campaigns(write_csv(tmp_path / "ties.csv", tied_rows))
    tied_ctr, tied_cpa = select_top_reports(tied.campaigns)
    expected_ties = [f"CMP{i:02d}" for i in range(10)]
    assert tied_ctr.get_column("campaign_id").to_list() == expected_ties
    assert tied_cpa.get_column("campaign_id").to_list() == expected_ties

    few_rows = [
        ["ONLY-A", "2025-01-01", 100, 10, "3.00", 1],
        ["ONLY-B", "2025-01-01", 100, 20, "2.00", 1],
    ]
    few = aggregate_campaigns(write_csv(tmp_path / "few.csv", few_rows))
    few_ctr, few_cpa = select_top_reports(few.campaigns)
    assert few_ctr.height == few_cpa.height == 2


def test_header_only_input_returns_empty_campaigns(tmp_path, write_csv):
    result = aggregate_campaigns(write_csv(tmp_path / "empty.csv", []))
    top_ctr, top_cpa = select_top_reports(result.campaigns)

    assert result.rows_read == 0
    assert result.skipped_rows == 0
    assert result.campaigns.is_empty()
    assert top_ctr.is_empty()
    assert top_cpa.is_empty()
