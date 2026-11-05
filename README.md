# Flinter Coding Challenge

Python CLI that aggregates advertising performance by campaign and writes CTR and CPA rankings using Polars.

## Before you start: add the CSV

Place the challenge dataset named `ad_data.csv` in the project root, alongside `Dockerfile` and `pyproject.toml`. The Docker build copies this file into the image, so the build will fail if it is missing. The same file is the default input for local runs.

## Run with Docker

Install and start Docker Desktop or Docker Engine with the Docker Compose plugin, then run this from the project root:

```sh
docker compose up --build
```

The image bundles `ad_data.csv`; you do not need to mount or provide the input at runtime. Compose mounts the host `results/` folder at `/output` in the container. After the container exits, retrieve `top10_ctr.csv`, `top10_cpa.csv`, and `benchmark.json` from `results/`. Rebuild the image after replacing the CSV.

## Prerequisites

- Python 3.10 or newer and pip for local runs
- Docker Desktop or Docker Engine with the Docker Compose plugin for container runs

## Install and configure

From the project directory, create a virtual environment and install the package:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

For development tools and tests, install `python -m pip install -e ".[dev]"`.

If `.env` does not exist, copy `.env.example` to `.env`. Set the input and output paths there. Relative paths resolve from the project directory:

```env
INPUT_CSV_PATH=ad_data.csv
OUTPUT_DIR=results
```

## Run locally

```powershell
python -m flinter_coding_challenge.cli
```

Override either configured path when needed:

```powershell
flinter-challenge --input path\to\ad_data.csv --output results
```

The CLI also accepts `--env-file path` and `--skip-read-benchmark`. The latter skips the extra CSV scan used to time parsing. `--verbose` enables debug logging.

## Input and outputs

The input may be a CSV or gzip-compressed CSV (`.csv.gz`) and must have these columns:

| Column | Expected value |
|---|---|
| `campaign_id` | Nonblank string |
| `date` | Date in `YYYY-MM-DD` format |
| `impressions` | Nonnegative integer |
| `clicks` | Nonnegative integer |
| `spend` | Finite, nonnegative number in USD |
| `conversions` | Nonnegative integer |

The program aggregates across dates. Invalid rows are skipped and summarized in the log. Campaigns with zero total impressions are omitted; campaigns with zero conversions are omitted from the CPA ranking.

The output directory is created if needed, and existing output files are replaced:

- `top10_ctr.csv`: up to 10 campaigns with highest CTR, ordered by CTR descending.
- `top10_cpa.csv`: up to 10 campaigns with lowest CPA, ordered by CPA ascending.

Ties are broken by ascending `campaign_id`. Both files contain `campaign_id`, `total_impressions`, `total_clicks`, `total_spend`, `total_conversions`, `CTR`, and `CPA`. CTR is formatted to 4 decimal places; CPA and total spend to 2. A campaign with zero conversions has a blank CPA in the CTR file.

## Libraries

| Library | Purpose |
|---|---|
| Polars | Lazy CSV scanning, validation, campaign aggregation, calculations, and ranking |
| python-dotenv | Load local input/output settings from `.env` |
| psutil | Sample process RSS and USS for benchmark reporting |
| pytest (development) | Unit and integration tests |
| Ruff (development) | Python linting |
| setuptools | Build and editable-install backend |

The application also uses Python standard-library modules for CLI parsing, CSV/JSON output, logging, paths, timing, and threading.

## Verified benchmark

Measured on the included `ad_data.csv` on a Windows host using Python 3.14.5, Polars 2.1.0, and the configured 4-thread Polars pool:

| Measure | Result |
|---|---:|
| Input size | 1,043,304,870 bytes (1.04 GB) |
| Rows processed | 26,843,544 |
| Rows skipped | 0 |
| CSV scan/parse timing pass | 0.151 s |
| Aggregation, including its CSV scan | 1.884 s |
| Sort and top-10 selection | 0.001 s |
| Output writing | 0.009 s |
| Total execution | 2.100 s |
| Peak RSS | 1,046.77 MiB |
| Peak USS | 623.23 MiB |

Total time includes the separate streaming scan used to measure CSV parsing; aggregation reads the CSV again. RSS and USS were sampled every 50 ms, so a brief transient peak may be missed. The CPU model, physical memory, and storage details were not recorded; system hardware inventory was unavailable during measurement. The complete phase metrics are in `results/benchmark.json`.
