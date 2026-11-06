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
            "campaign_id": pl.Categorical,
            "date": pl.String,
            "impressions": pl.Int64,
            "clicks": pl.Int64,
            "spend": pl.Float64,
            "conversions": pl.Int64,
        },
        null_values=[""],
        ignore_errors=True,
        truncate_ragged_lines=True,
        infer_schema_length=0,
    )
    # Push down the challenge schema projection so extra CSV columns are not read.
    # All six challenge fields are needed for validation and the requested outputs.
    return typed_scan.select(REQUIRED_COLUMNS)


def validated_campaign_groups(
    path: Path | None = None, *, frame: pl.LazyFrame | None = None
) -> pl.LazyFrame:
    """Build one lazy aggregation that separates valid and rejected rows."""
    if frame is None:
        if path is None:
            raise ValueError("path or frame is required")
        frame = scan_csv(path)
    source = frame.with_columns(
        pl.col("date").str.strptime(pl.Date, format="%Y-%m-%d", strict=False).alias("_date"),
    )
    # Categorical IDs are checked after grouping to avoid per-row string work.
    date_bad = pl.col("_date").is_null()
    impressions_bad = pl.col("impressions").is_null() | (pl.col("impressions") < 0)
    clicks_bad = pl.col("clicks").is_null() | (pl.col("clicks") < 0)
    conversions_bad = pl.col("conversions").is_null() | (pl.col("conversions") < 0)
    spend_bad = (
        pl.col("spend").is_null()
        | ~pl.col("spend").is_finite()
        | (pl.col("spend") < 0)
    )
    valid = ~(
        date_bad | impressions_bad | clicks_bad | spend_bad | conversions_bad
    )
    prepared = source.with_columns(
        valid.alias("_valid"),
        date_bad.alias("_bad_date"),
        (impressions_bad | clicks_bad | conversions_bad | spend_bad).alias("_bad_metric"),
    )
    return prepared.with_columns(
        pl.when(pl.col("_valid")).then(pl.col("impressions")).otherwise(0).alias("impressions"),
        pl.when(pl.col("_valid")).then(pl.col("clicks")).otherwise(0).alias("clicks"),
        pl.when(pl.col("_valid")).then(pl.col("spend")).otherwise(0.0).alias("spend"),
        pl.when(pl.col("_valid")).then(pl.col("conversions")).otherwise(0).alias("conversions"),
    ).group_by("campaign_id").agg(
        pl.len().alias("_rows"),
        pl.col("impressions").sum().alias("total_impressions"),
        pl.col("clicks").sum().alias("total_clicks"),
        pl.col("spend").sum().alias("total_spend"),
        pl.col("conversions").sum().alias("total_conversions"),
        pl.col("_valid").sum().alias("_valid_rows"),
        (~pl.col("_valid")).sum().alias("_skipped_rows"),
        pl.col("_bad_date").sum().alias("_invalid_date_rows"),
        pl.col("_bad_metric").sum().alias("_invalid_metric_rows"),
    )
