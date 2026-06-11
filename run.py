"""Run a deterministic batch signal-generation job."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


LOGGER_NAME = "mlops_task"
REQUIRED_CONFIG_FIELDS = ("seed", "window", "version")


class ValidationError(ValueError):
    """Raised when an input does not satisfy the job contract."""


@dataclass(frozen=True)
class JobConfig:
    seed: int
    window: int
    version: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a rolling-mean trading signal and summary metrics."
    )
    parser.add_argument("--input", required=True, help="Path to the OHLCV CSV file.")
    parser.add_argument("--config", required=True, help="Path to the YAML config file.")
    parser.add_argument("--output", required=True, help="Path for metrics JSON.")
    parser.add_argument("--log-file", required=True, help="Path for detailed job logs.")
    return parser.parse_args()


def configure_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logger.addHandler(handler)
    return logger


def read_yaml(config_path: Path) -> Any:
    if not config_path.is_file():
        raise ValidationError(f"Config file not found: {config_path}")

    try:
        with config_path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValidationError(f"Unable to read valid YAML config: {exc}") from exc


def load_config(config_path: Path) -> JobConfig:
    raw_config = read_yaml(config_path)
    if not isinstance(raw_config, dict):
        raise ValidationError("Config must be a YAML mapping.")

    missing = [field for field in REQUIRED_CONFIG_FIELDS if field not in raw_config]
    if missing:
        raise ValidationError(
            f"Config is missing required field(s): {', '.join(missing)}"
        )

    seed = raw_config["seed"]
    window = raw_config["window"]
    version = raw_config["version"]

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValidationError("Config field 'seed' must be an integer.")
    if not 0 <= seed <= 2**32 - 1:
        raise ValidationError("Config field 'seed' must be between 0 and 4294967295.")
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise ValidationError("Config field 'window' must be a positive integer.")
    if not isinstance(version, str) or not version.strip():
        raise ValidationError("Config field 'version' must be a non-empty string.")

    return JobConfig(seed=seed, window=window, version=version.strip())


def best_effort_version(config_path: Path) -> str:
    try:
        raw_config = read_yaml(config_path)
    except ValidationError:
        return "unknown"

    if isinstance(raw_config, dict):
        version = raw_config.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()
    return "unknown"


def load_dataset(input_path: Path) -> pd.DataFrame:
    if not input_path.is_file():
        raise ValidationError(f"Input file not found: {input_path}")

    try:
        if input_path.stat().st_size == 0:
            raise ValidationError(f"Input file is empty: {input_path}")
        data = pd.read_csv(input_path, on_bad_lines="error")
    except ValidationError:
        raise
    except pd.errors.EmptyDataError as exc:
        raise ValidationError(f"Input file is empty: {input_path}") from exc
    except (pd.errors.ParserError, UnicodeError, OSError) as exc:
        raise ValidationError(f"Unable to read valid CSV input: {exc}") from exc

    if data.empty:
        raise ValidationError("Input CSV contains no data rows.")
    if "close" not in data.columns:
        raise ValidationError("Input CSV is missing required column: close")

    numeric_close = pd.to_numeric(data["close"], errors="coerce")
    if numeric_close.isna().any() or not np.isfinite(numeric_close).all():
        raise ValidationError("Column 'close' must contain only finite numeric values.")

    data = data.copy()
    data["close"] = numeric_close.astype(float)
    return data


def calculate_signal_rate(data: pd.DataFrame, window: int) -> float:
    if window > len(data):
        raise ValidationError(
            f"Config window ({window}) cannot exceed row count ({len(data)})."
        )

    rolling_mean = data["close"].rolling(window=window, min_periods=window).mean()
    valid_rows = rolling_mean.notna()
    signals = (data.loc[valid_rows, "close"] > rolling_mean[valid_rows]).astype(
        np.int8
    )
    return float(signals.mean())


def write_metrics(output_path: Path, metrics: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(metrics, file, indent=2)
            file.write("\n")
        temporary_path.replace(output_path)
    except (OSError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Unable to write metrics file '{output_path}': {exc}") from exc


def close_logging(logger: logging.Logger) -> None:
    for handler in logger.handlers[:]:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)


def execute_job(args: argparse.Namespace) -> int:
    started_at = time.perf_counter()
    config_path = Path(args.config)
    output_path = Path(args.output)
    logger = configure_logging(Path(args.log_file))
    version = best_effort_version(config_path)

    logger.info("Job start")

    try:
        config = load_config(config_path)
        version = config.version
        np.random.seed(config.seed)
        logger.info(
            "Config loaded and validated | seed=%d | window=%d | version=%s",
            config.seed,
            config.window,
            config.version,
        )

        data = load_dataset(Path(args.input))
        logger.info("Dataset loaded and validated | rows=%d", len(data))

        logger.info("Computing rolling mean | window=%d", config.window)
        logger.info(
            "Generating binary signal | warmup_rows_excluded=%d",
            config.window - 1,
        )
        signal_rate = calculate_signal_rate(data, config.window)

        latency_ms = int(round((time.perf_counter() - started_at) * 1000))
        metrics = {
            "version": config.version,
            "rows_processed": len(data),
            "metric": "signal_rate",
            "value": round(signal_rate, 4),
            "latency_ms": latency_ms,
            "seed": config.seed,
            "status": "success",
        }
        logger.info(
            "Metrics summary | rows_processed=%d | signal_rate=%.4f | latency_ms=%d",
            metrics["rows_processed"],
            metrics["value"],
            metrics["latency_ms"],
        )
        write_metrics(output_path, metrics)
        logger.info("Job end | status=success")
        print(json.dumps(metrics))
        return 0
    except Exception as exc:
        error_metrics = {
            "version": version,
            "status": "error",
            "error_message": str(exc),
        }
        logger.error("Job failed | error=%s", exc, exc_info=True)
        try:
            write_metrics(output_path, error_metrics)
        except Exception as write_exc:
            logger.critical("Metrics output failed | error=%s", write_exc, exc_info=True)
            error_metrics["error_message"] = (
                f"{error_metrics['error_message']}; {write_exc}"
            )
        logger.info("Job end | status=error")
        print(json.dumps(error_metrics))
        return 1
    finally:
        close_logging(logger)


def main() -> int:
    return execute_job(parse_args())


if __name__ == "__main__":
    sys.exit(main())
