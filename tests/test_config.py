from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from run import JobConfig, ValidationError, load_config


class ConfigValidationTests(unittest.TestCase):
    def load_text(self, content: str) -> JobConfig:
        with TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "config.yaml"
            config_path.write_text(content, encoding="utf-8")
            return load_config(config_path)

    def test_valid_config_is_loaded_and_version_is_trimmed(self) -> None:
        config = self.load_text(
            'seed: 42\nwindow: 5\nversion: "  v1  "\n'
        )

        self.assertEqual(config, JobConfig(seed=42, window=5, version="v1"))

    def test_config_must_be_a_mapping(self) -> None:
        for content in ("", "- seed\n- window\n", "42\n"):
            with self.subTest(content=content):
                with self.assertRaisesRegex(
                    ValidationError,
                    "Config must be a YAML mapping",
                ):
                    self.load_text(content)

    def test_all_required_fields_are_reported(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            r"seed, window, version",
        ):
            self.load_text("{}\n")

    def test_duplicate_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "found duplicate key",
        ):
            self.load_text(
                'seed: 1\nseed: 2\nwindow: 5\nversion: "v1"\n'
            )

    def test_seed_must_be_an_integer_in_numpy_range(self) -> None:
        invalid_seeds = ("true", "1.5", "-1", "4294967296")

        for seed in invalid_seeds:
            with self.subTest(seed=seed):
                with self.assertRaises(ValidationError):
                    self.load_text(
                        f'seed: {seed}\nwindow: 5\nversion: "v1"\n'
                    )

    def test_window_must_be_a_positive_integer(self) -> None:
        invalid_windows = ("true", "1.5", "0", "-1")

        for window in invalid_windows:
            with self.subTest(window=window):
                with self.assertRaisesRegex(
                    ValidationError,
                    "window.*positive integer",
                ):
                    self.load_text(
                        f'seed: 42\nwindow: {window}\nversion: "v1"\n'
                    )

    def test_version_must_be_a_non_empty_string(self) -> None:
        for version in ('""', '"   "', "1"):
            with self.subTest(version=version):
                with self.assertRaisesRegex(
                    ValidationError,
                    "version.*non-empty string",
                ):
                    self.load_text(
                        f"seed: 42\nwindow: 5\nversion: {version}\n"
                    )


if __name__ == "__main__":
    unittest.main()
