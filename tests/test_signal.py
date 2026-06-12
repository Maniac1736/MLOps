import unittest

import pandas as pd

from run import ValidationError, calculate_signal_rate


class SignalCalculationTests(unittest.TestCase):
    def test_warmup_rows_are_excluded_from_rate(self) -> None:
        data = pd.DataFrame({"close": [1.0, 2.0, 3.0, 2.0]})

        self.assertAlmostEqual(calculate_signal_rate(data, window=3), 0.5)

    def test_values_equal_to_rolling_mean_generate_zero(self) -> None:
        data = pd.DataFrame({"close": [2.0, 2.0, 2.0]})

        self.assertEqual(calculate_signal_rate(data, window=2), 0.0)

    def test_increasing_values_generate_signals_after_warmup(self) -> None:
        data = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]})

        self.assertEqual(calculate_signal_rate(data, window=2), 1.0)

    def test_window_equal_to_row_count_has_one_valid_signal(self) -> None:
        data = pd.DataFrame({"close": [1.0, 2.0, 3.0]})

        self.assertEqual(calculate_signal_rate(data, window=3), 1.0)

    def test_window_larger_than_dataset_is_rejected(self) -> None:
        data = pd.DataFrame({"close": [1.0, 2.0]})

        with self.assertRaisesRegex(
            ValidationError,
            "cannot exceed row count",
        ):
            calculate_signal_rate(data, window=3)

    def test_non_positive_window_is_rejected(self) -> None:
        data = pd.DataFrame({"close": [1.0, 2.0]})

        for window in (0, -1):
            with self.subTest(window=window):
                with self.assertRaisesRegex(
                    ValidationError,
                    "Rolling window must be a positive integer",
                ):
                    calculate_signal_rate(data, window=window)

    def test_boolean_window_is_rejected(self) -> None:
        data = pd.DataFrame({"close": [1.0, 2.0]})

        with self.assertRaisesRegex(
            ValidationError,
            "Rolling window must be a positive integer",
        ):
            calculate_signal_rate(data, window=True)


if __name__ == "__main__":
    unittest.main()
