"""Execution timing and sampled process memory measurements."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Self

import psutil


class PeakMemorySampler:
    """Sample this process's resident memory while the job is running."""

    def __init__(self, interval_seconds: float = 0.05) -> None:
        self.interval_seconds = interval_seconds
        self.process = psutil.Process()
        self.peak_rss_bytes = 0
        self.peak_uss_bytes = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._phase = "startup"
        self._phase_stats: dict[str, dict[str, int]] = {}
        self._lock = threading.Lock()

    def _memory_info(self) -> tuple[int, int]:
        info = self.process.memory_full_info()
        return info.rss, info.uss

    def _sample_once(self) -> None:
        try:
            rss, uss = self._memory_info()
            with self._lock:
                self.peak_rss_bytes = max(self.peak_rss_bytes, rss)
                self.peak_uss_bytes = max(self.peak_uss_bytes, uss)
                stats = self._phase_stats.get(self._phase)
                if stats is not None:
                    stats["peak_rss_bytes"] = max(stats["peak_rss_bytes"], rss)
                    stats["peak_uss_bytes"] = max(stats["peak_uss_bytes"], uss)
        except psutil.Error:
            pass

    def _sample(self) -> None:
        while not self._stop.is_set():
            self._sample_once()
            self._stop.wait(self.interval_seconds)

    def __enter__(self) -> Self:
        self._sample_once()
        rss, uss = self._memory_info()
        self._phase_stats["startup"] = {
            "start_rss_bytes": rss,
            "peak_rss_bytes": rss,
            "start_uss_bytes": uss,
            "peak_uss_bytes": uss,
        }
        self._thread.start()
        return self

    def set_phase(self, name: str) -> None:
        """Start tracking absolute memory and growth for a named stage."""
        self._sample_once()
        rss, uss = self._memory_info()
        with self._lock:
            self._phase = name
            self._phase_stats[name] = {
                "start_rss_bytes": rss,
                "peak_rss_bytes": rss,
                "start_uss_bytes": uss,
                "peak_uss_bytes": uss,
            }

    def report(self) -> dict[str, dict[str, Any]]:
        """Return sampled per-phase peak memory and growth from each baseline."""
        result: dict[str, dict[str, Any]] = {}
        with self._lock:
            stats_snapshot = {name: dict(stats) for name, stats in self._phase_stats.items()}
        for name, stats in stats_snapshot.items():
            result[name] = {
                **stats,
                "peak_rss_mib": round(stats["peak_rss_bytes"] / 1048576, 2),
                "rss_growth_mib": round(
                    (stats["peak_rss_bytes"] - stats["start_rss_bytes"]) / 1048576,
                    2,
                ),
                "peak_uss_mib": round(stats["peak_uss_bytes"] / 1048576, 2),
                "uss_growth_mib": round(
                    (stats["peak_uss_bytes"] - stats["start_uss_bytes"]) / 1048576,
                    2,
                ),
            }
        return result

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()
        self._sample_once()
