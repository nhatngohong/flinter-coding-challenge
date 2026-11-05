"""Flinter coding challenge project package."""

import os

# Set this before any package module imports Polars and initializes its pool.
os.environ["POLARS_MAX_THREADS"] = "4"

__version__ = "0.1.0"
