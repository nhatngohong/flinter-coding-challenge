"""Load environment settings and resolve project paths."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .errors import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppConfig:
    input_csv: Path
    output_dir: Path


def _resolve_path(value: str, *, base: Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def load_config(
    env_file: Path,
    input_override: str | None = None,
    output_override: str | None = None,
) -> AppConfig:
    """Load .env values, applying command-line overrides when supplied."""
    if env_file.exists():
        load_dotenv(env_file, override=True)
    input_value = input_override or os.getenv("INPUT_CSV_PATH")
    output_value = output_override or os.getenv("OUTPUT_DIR")
    if not input_value:
        raise ConfigurationError(
            f"INPUT_CSV_PATH is missing in {env_file}; set it or pass --input."
        )
    if not output_value:
        raise ConfigurationError(
            f"OUTPUT_DIR is missing in {env_file}; set it or pass --output."
        )
    return AppConfig(
        input_csv=_resolve_path(input_value, base=PROJECT_ROOT),
        output_dir=_resolve_path(output_value, base=PROJECT_ROOT),
    )


def validate_config(config: AppConfig) -> None:
    if not config.input_csv.exists():
        raise ConfigurationError(f"Input CSV does not exist: {config.input_csv}")
    if not config.input_csv.is_file():
        raise ConfigurationError(f"Input path is not a file: {config.input_csv}")
    try:
        config.output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(
            f"Cannot create output directory {config.output_dir}: {exc}"
        ) from exc
