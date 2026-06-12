from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from run import ValidationError, load_dataset


class DatasetValidationTests(unittest.TestCase):
    def load_text(self, content: str):
        with TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "data.csv"
            input_path.write_text(content, encoding="utf-8")
            return load_dataset(input_path)

    def test_missing_input_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "missing.csv"

            with self.assertRaisesRegex(ValidationError, "Input file not found"):
                load_dataset(input_path)

    def test_empty_file_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "Input file is empty"):
            self.load_text("")

    def test_header_only_file_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "contains no data rows",
        ):
            self.load_text("close\n")

    def test_missing_close_column_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "missing required column: close",
        ):
            self.load_text("open\n1.0\n")

    def test_malformed_csv_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "Unable to read valid CSV input",
        ):
            self.load_text('close\n"1.0\n')

    def test_non_numeric_close_value_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "finite numeric values",
        ):
            self.load_text("close\nnot-a-number\n")

    def test_non_finite_close_value_is_rejected(self) -> None:
        for value in ("NaN", "inf", "-inf"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValidationError,
                    "finite numeric values",
                ):
                    self.load_text(f"close\n{value}\n")

    def test_numeric_close_values_are_normalized_to_float(self) -> None:
        data = self.load_text("close,volume\n1,10\n2.5,20\n")

        self.assertEqual(data["close"].tolist(), [1.0, 2.5])
        self.assertEqual(str(data["close"].dtype), "float64")


if __name__ == "__main__":
    unittest.main()
