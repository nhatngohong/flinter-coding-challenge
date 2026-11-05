"""CSV scanning and row validation expressions."""

from pathlib import Path

import polars as pl

from .errors import InputDataError

REQUIRED_COLUMNS = (
    "campaign_id", "date", "impressions", "clicks", "spend", "conversions"
)


def scan_csv(path: Path) -> pl.LazyFrame:
    """Validate the header, then scan using compact, explicit column types."""
    try:
        header_scan = pl.scan_csv(
            path,
            infer_schema_length=0,
            null_values=[""],
            ignore_errors=True,
            truncate_ragged_lines=True,
            low_memory=True,
        )
        columns = header_scan.collect_schema().names()
    except Exception as exc:
        raise InputDataError(f"Could not read CSV header from {path}: {exc}") from exc
    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        raise InputDataError("CSV is missing required column(s): " + ", ".join(missing))
    typed_scan = pl.scan_csv(
        path,
        schema_overrides={
            "campaign_id": pl.String,
            "date": pl.String,
            "impressions": pl.Int64,
            "clicks": pl.Int64,
            "spend": pl.Float64,
            "conversions": pl.Int64,
        },
        null_values=[""],
        ignore_errors=True,
        truncate_ragged_lines=True,
        low_memory=True,
    )
    # Push down the challenge schema projection so extra CSV columns are not read.
    # All six challenge fields are needed for validation and the requested outputs.
    return typed_scan.select(REQUIRED_COLUMNS)


def validated_campaign_groups(path: Path) -> pl.LazyFrame:
    """Build one lazy aggregation that separates valid and rejected rows."""
    source = scan_csv(path).with_columns(
        pl.col("impressions").alias("_impressions"),
        pl.col("clicks").alias("_clicks"),
        pl.col("spend").alias("_spend"),
        pl.col("conversions").alias("_conversions"),
        pl.col("date").str.strptime(pl.Date, format="%Y-%m-%d", strict=False).alias("_date"),
    )
    campaign_bad = (
        pl.col("campaign_id").is_null()
        | (pl.col("campaign_id").str.strip_chars() == "")
    )
    date_bad = pl.col("_date").is_null()
    impressions_bad = pl.col("_impressions").is_null() | (pl.col("_impressions") < 0)
    clicks_bad = pl.col("_clicks").is_null() | (pl.col("_clicks") < 0)
    conversions_bad = pl.col("_conversions").is_null() | (pl.col("_conversions") < 0)
    spend_bad = (
        pl.col("_spend").is_null()
        | ~pl.col("_spend").is_finite()
        | (pl.col("_spend") < 0)
    )
    valid = ~(
        campaign_bad | date_bad | impressions_bad | clicks_bad | spend_bad | conversions_bad
    )
    prepared = source.with_columns(
        valid.alias("_valid"),
        pl.when(valid).then(pl.col("campaign_id")).otherwise(
            pl.lit(None, dtype=pl.String)
        ).alias("_campaign_key"),
        campaign_bad.alias("_bad_campaign"),
        date_bad.alias("_bad_date"),
        (impressions_bad | clicks_bad | conversions_bad | spend_bad).alias("_bad_metric"),
    )
    return prepared.group_by("_campaign_key").agg(
        pl.when(pl.col("_valid")).then(pl.col("_impressions")).otherwise(None)
        .sum().fill_null(0).alias("total_impressions"),
        pl.when(pl.col("_valid")).then(pl.col("_clicks")).otherwise(None)
        .sum().fill_null(0).alias("total_clicks"),
        pl.when(pl.col("_valid")).then(pl.col("_spend")).otherwise(None)
        .sum().fill_null(0.0).alias("total_spend"),
        pl.when(pl.col("_valid")).then(pl.col("_conversions")).otherwise(None)
        .sum().fill_null(0).alias("total_conversions"),
        pl.col("_valid").sum().alias("_valid_rows"),
        (~pl.col("_valid")).sum().alias("_skipped_rows"),
        pl.col("_bad_campaign").sum().alias("_invalid_campaign_rows"),
        pl.col("_bad_date").sum().alias("_invalid_date_rows"),
        pl.col("_bad_metric").sum().alias("_invalid_metric_rows"),
    )
