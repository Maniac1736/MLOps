from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import unittest

import pandas as pd

from run import (
    calculate_signal_rate,
    close_logging,
    configure_logging,
    execute_job,
)


class LoggingTests(unittest.TestCase):
    def test_reconfiguring_logger_closes_previous_handler(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            logger = configure_logging(root / "first.log")
            first_handler = logger.handlers[0]

            logger = configure_logging(root / "second.log")

            self.assertIsNone(first_handler.stream)
            self.assertEqual(len(logger.handlers), 1)
            close_logging(logger)


class SignalCalculationTests(unittest.TestCase):
    def test_warmup_rows_are_excluded(self) -> None:
        data = pd.DataFrame({"close": [1.0, 2.0, 3.0, 2.0]})

        self.assertAlmostEqual(calculate_signal_rate(data, window=3), 0.5)


class JobTests(unittest.TestCase):
    def test_log_setup_failure_still_writes_error_metrics(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = root / "config.yaml"
            input_csv = root / "data.csv"
            output = root / "metrics.json"
            log_parent = root / "not-a-directory"
            config.write_text('seed: 42\nwindow: 2\nversion: "v1"\n', encoding="utf-8")
            input_csv.write_text("close\n1.0\n2.0\n", encoding="utf-8")
            log_parent.write_text("blocking file", encoding="utf-8")

            exit_code = execute_job(
                SimpleNamespace(
                    input=str(input_csv),
                    config=str(config),
                    output=str(output),
                    log_file=str(log_parent / "run.log"),
                )
            )
            metrics = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(exit_code, 1)
            self.assertEqual(metrics["status"], "error")
            self.assertIn("not-a-directory", metrics["error_message"])

    def test_missing_close_writes_error_metrics(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = root / "config.yaml"
            input_csv = root / "data.csv"
            output = root / "metrics.json"
            log_file = root / "run.log"
            config.write_text('seed: 42\nwindow: 2\nversion: "v1"\n', encoding="utf-8")
            input_csv.write_text("open\n1.0\n", encoding="utf-8")

            exit_code = execute_job(
                SimpleNamespace(
                    input=str(input_csv),
                    config=str(config),
                    output=str(output),
                    log_file=str(log_file),
                )
            )
            metrics = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(exit_code, 1)
            self.assertEqual(metrics["status"], "error")
            self.assertIn("missing required column", metrics["error_message"])


if __name__ == "__main__":
    unittest.main()
