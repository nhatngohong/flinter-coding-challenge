"""Command-line entry point."""

import argparse
import json
import logging
import time
from pathlib import Path

import polars as pl

from .aggregation import aggregate_campaigns, benchmark_csv_read, select_top_reports
from .benchmark import PeakMemorySampler
from .config import PROJECT_ROOT, load_config, validate_config
from .errors import ChallengeError
from .logging_config import configure_logging
from .output import write_benchmark, write_reports

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate campaign performance from a large CSV using Polars."
    )
    parser.add_argument("--input", help="Input CSV path; overrides INPUT_CSV_PATH.")
    parser.add_argument("--output", help="Output directory; overrides OUTPUT_DIR.")
    parser.add_argument(
        "--env-file", type=Path, default=PROJECT_ROOT / ".env",
        help="Environment file (default: project .env).",
    )
    parser.add_argument(
        "--skip-read-benchmark", action="store_true",
        help="Skip the separate CSV scan/parse timing pass.",
    )
    parser.add_argument("--verbose", action="store_true", help="Show debug logs.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    configure_logging(args.verbose)
    total_started = time.perf_counter()

    try:
        config = load_config(args.env_file.resolve(), args.input, args.output)
        validate_config(config)
        input_size_bytes = config.input_csv.stat().st_size

        with PeakMemorySampler() as memory:
            read_rows = None
            read_seconds = None
            if not args.skip_read_benchmark:
                memory.set_phase("csv_read_parse_benchmark")
                read_rows, read_seconds = benchmark_csv_read(config.input_csv)

            memory.set_phase("campaign_aggregation")
            aggregation = aggregate_campaigns(config.input_csv)
            memory.set_phase("sort_and_top10")
            sort_started = time.perf_counter()
            top_ctr, top_cpa = select_top_reports(aggregation.campaigns)
            sort_top10_seconds = time.perf_counter() - sort_started

            if read_rows is not None and read_rows != aggregation.rows_read:
                logger.warning(
                    "CSV scanner counted %d rows, while validation accounted for %d; "
                    "malformed structural rows may be counted differently.",
                    read_rows, aggregation.rows_read,
                )
            if aggregation.skipped_rows:
                logger.warning(
                    "Skipped %d invalid row(s): %d invalid campaign ID(s), "
                    "%d invalid date(s), %d row(s) with invalid metric values.",
                    aggregation.skipped_rows,
                    aggregation.invalid_campaign_rows,
                    aggregation.invalid_date_rows,
                    aggregation.invalid_metric_rows,
                )
            else:
                logger.info("No invalid rows were skipped.")

            memory.set_phase("output_writing")
            write_started = time.perf_counter()
            write_reports(config.output_dir, top_ctr, top_cpa)
            write_seconds = time.perf_counter() - write_started

        total_seconds = time.perf_counter() - total_started
        benchmark = {
            "input_file": str(config.input_csv),
            "input_size_bytes": input_size_bytes,
            "polars_version": pl.__version__,
            "polars_max_threads": pl.thread_pool_size(),
            "rows_read": aggregation.rows_read,
            "rows_skipped": aggregation.skipped_rows,
            "campaigns_ranked": aggregation.campaigns.height,
            "top_ctr_rows": top_ctr.height,
            "top_cpa_rows": top_cpa.height,
            "csv_read_parse_pass_seconds": read_seconds,
            "aggregation_seconds_including_its_csv_scan": aggregation.aggregate_seconds,
            "sort_and_top10_seconds": sort_top10_seconds,
            "output_write_seconds": write_seconds,
            "total_execution_seconds": total_seconds,
            "sampled_peak_process_rss_bytes": memory.peak_rss_bytes,
            "sampled_peak_process_rss_mib": round(memory.peak_rss_bytes / (1024 * 1024), 2),
            "sampled_peak_process_uss_bytes": memory.peak_uss_bytes,
            "sampled_peak_process_uss_mib": round(memory.peak_uss_bytes / (1024 * 1024), 2),
            "sampled_memory_by_phase": memory.report(),
            "note": (
                "CSV read timing is a separate streaming scan/parse pass. Aggregation "
                "also scans the CSV because Polars fuses scan and aggregation in its "
                "lazy query. Total includes the benchmark pass. Peak RSS is sampled "
                "every 50 ms. RSS can include shared or mapped pages; USS estimates "
                "unique process memory."
            ),
        }
        benchmark_path = write_benchmark(config.output_dir, benchmark)
        logger.info("Wrote %d CTR rows to %s", top_ctr.height, config.output_dir / "top10_ctr.csv")
        logger.info("Wrote %d CPA rows to %s", top_cpa.height, config.output_dir / "top10_cpa.csv")
        logger.info("Benchmark details saved to %s", benchmark_path)
        print(json.dumps(benchmark, indent=2))
        return 0
    except ChallengeError as exc:
        logger.error("%s", exc)
        return 2
    except Exception:
        logger.exception("Unexpected failure while processing the input.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
