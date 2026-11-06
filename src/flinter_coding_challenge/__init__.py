"""Flinter coding challenge project package."""

import os

# Set this before any package module imports Polars and initializes its pool.
os.environ.setdefault("POLARS_MAX_THREADS", "4")
os.environ.setdefault("POLARS_CSV_CHUNK_SIZE", str(4 * 1024 * 1024))
os.environ.setdefault("POLARS_CSV_CHUNK_PREFETCH_LIMIT", "2")
os.environ.setdefault("POLARS_IDEAL_MORSEL_SIZE", "50000")

__version__ = "0.1.0"
