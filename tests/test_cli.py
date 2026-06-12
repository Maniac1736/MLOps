from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_SCRIPT = PROJECT_ROOT / "run.py"


class CliIntegrationTests(unittest.TestCase):
    def run_job(self, root: Path, input_content: str) -> subprocess.CompletedProcess:
        config = root / "config.yaml"
        input_csv = root / "data.csv"
        output = root / "metrics.json"
        log_file = root / "run.log"
        config.write_text(
            'seed: 42\nwindow: 3\nversion: "v1"\n',
            encoding="utf-8",
        )
        input_csv.write_text(input_content, encoding="utf-8")

        return subprocess.run(
            [
                sys.executable,
                str(RUN_SCRIPT),
                "--input",
                str(input_csv),
                "--config",
                str(config),
                "--output",
                str(output),
                "--log-file",
                str(log_file),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_success_writes_metrics_logs_and_stdout(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            result = self.run_job(root, "close\n1.0\n2.0\n3.0\n2.0\n")

            self.assertEqual(result.returncode, 0, result.stderr)
            stdout_metrics = json.loads(result.stdout)
            file_metrics = json.loads(
                (root / "metrics.json").read_text(encoding="utf-8")
            )
            self.assertEqual(stdout_metrics, file_metrics)
            self.assertEqual(
                set(file_metrics),
                {
                    "version",
                    "rows_processed",
                    "metric",
                    "value",
                    "latency_ms",
                    "seed",
                    "status",
                },
            )
            self.assertEqual(file_metrics["rows_processed"], 4)
            self.assertEqual(file_metrics["value"], 0.5)
            self.assertEqual(file_metrics["status"], "success")

            log_text = (root / "run.log").read_text(encoding="utf-8")
            for expected_message in (
                "Job start",
                "Config loaded and validated",
                "Dataset loaded and validated | rows=4",
                "Computing rolling mean | window=3",
                "Generating binary signal | warmup_rows_excluded=2",
                "Metrics summary",
                "Job end | status=success",
            ):
                with self.subTest(expected_message=expected_message):
                    self.assertIn(expected_message, log_text)

    def test_failure_writes_error_metrics_logs_and_stdout(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)

            result = self.run_job(root, "open\n1.0\n")

            self.assertEqual(result.returncode, 1)
            stdout_metrics = json.loads(result.stdout)
            file_metrics = json.loads(
                (root / "metrics.json").read_text(encoding="utf-8")
            )
            self.assertEqual(stdout_metrics, file_metrics)
            self.assertEqual(
                set(file_metrics),
                {"version", "status", "error_message"},
            )
            self.assertEqual(file_metrics["version"], "v1")
            self.assertEqual(file_metrics["status"], "error")
            self.assertIn("missing required column", file_metrics["error_message"])

            log_text = (root / "run.log").read_text(encoding="utf-8")
            self.assertIn("Job failed", log_text)
            self.assertIn("ValidationError", log_text)
            self.assertIn("Job end | status=error", log_text)

    def test_provided_dataset_produces_reproducible_results(self) -> None:
        stable_fields = {
            "version",
            "rows_processed",
            "metric",
            "value",
            "seed",
            "status",
        }

        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            results = []

            for run_number in (1, 2):
                output = root / f"metrics-{run_number}.json"
                log_file = root / f"run-{run_number}.log"
                result = subprocess.run(
                    [
                        sys.executable,
                        str(RUN_SCRIPT),
                        "--input",
                        str(PROJECT_ROOT / "data.csv"),
                        "--config",
                        str(PROJECT_ROOT / "config.yaml"),
                        "--output",
                        str(output),
                        "--log-file",
                        str(log_file),
                    ],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                results.append(json.loads(output.read_text(encoding="utf-8")))

            first_stable_result = {
                field: results[0][field] for field in stable_fields
            }
            second_stable_result = {
                field: results[1][field] for field in stable_fields
            }
            self.assertEqual(first_stable_result, second_stable_result)
            self.assertEqual(
                first_stable_result,
                {
                    "version": "v1",
                    "rows_processed": 10000,
                    "metric": "signal_rate",
                    "value": 0.4991,
                    "seed": 42,
                    "status": "success",
                },
            )


if __name__ == "__main__":
    unittest.main()
