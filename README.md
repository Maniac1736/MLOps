# MLOps Batch Signal Job

A deterministic Python batch job that loads OHLCV data, computes a rolling
mean over `close`, generates a binary trading signal, and emits structured
metrics and detailed logs.

## Processing Rules

- Configuration is loaded from YAML and requires `seed`, `window`, and
  `version`.
- The first `window - 1` rows have no complete rolling window and are excluded
  from signal generation and the `signal_rate` denominator.
- `rows_processed` reports every validated CSV data row.
- The signal is `1` when `close > rolling_mean`; otherwise it is `0`.
- The configured NumPy seed is set before processing.

## Local Run

Python 3.9 or newer is required.

```bash
python -m venv .venv
```

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install dependencies and run the job:

```bash
python -m pip install -r requirements.txt
python run.py --input data.csv --config config.yaml --output metrics.json --log-file run.log
```

The command exits with code `0` on success and a non-zero code on failure. It
writes `metrics.json` in either case and prints the final metrics JSON to
standard output.

The input, config, output, and log paths must be distinct where a write could
overwrite a source file. Parent directories for metrics and logs are created
automatically.

## Docker Run

Run the exact assessment commands:

```bash
docker build -t mlops-task .
docker run --rm mlops-task
```

The container writes `/app/metrics.json` and `/app/run.log` during execution
and prints the final metrics JSON to standard output. The job runs as an
unprivileged container user.

To retain generated files on the host, mount an output directory:

```powershell
New-Item -ItemType Directory -Force output
docker run --rm -v "${PWD}\output:/output" mlops-task python run.py --input data.csv --config config.yaml --output /output/metrics.json --log-file /output/run.log
```

## Example Metrics

```json
{
  "version": "v1",
  "rows_processed": 10000,
  "metric": "signal_rate",
  "value": 0.4991,
  "latency_ms": 22,
  "seed": 42,
  "status": "success"
}
```

`latency_ms` varies by machine. The signal result is deterministic for the
same input and configuration.

## Validation and Error Handling

The job reports clean errors for missing or unreadable files, invalid YAML,
duplicate or missing config fields, invalid CSV structure, empty input, a
missing `close` column, non-finite or non-numeric close values, invalid rolling
windows, and write paths that could overwrite source files.
