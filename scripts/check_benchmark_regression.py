from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check benchmark output for regressions")
    parser.add_argument(
        "--baseline",
        default="benchmarks/baseline.json",
        help="Path to benchmark baseline configuration",
    )
    parser.add_argument(
        "--latest",
        default="output/benchmarks/latest.json",
        help="Path to latest benchmark result",
    )
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    latest_path = Path(args.latest)

    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline file not found: {baseline_path}")
    if not latest_path.exists():
        raise FileNotFoundError(f"Latest benchmark file not found: {latest_path}")

    baseline = load_json(baseline_path)
    latest = load_json(latest_path)

    throughput = float(latest.get("throughput_pages_per_second", 0.0) or 0.0)
    memory_peak = int(latest.get("memory_peak_bytes", 0) or 0)
    sqlite_size = int(latest.get("sqlite_size_bytes", 0) or 0)

    perf = latest.get("performance", {}) if isinstance(latest.get("performance"), dict) else {}
    aggregate = perf.get("aggregate", {}) if isinstance(perf.get("aggregate"), dict) else {}
    avg_fetch = float(aggregate.get("avg_fetch_time_ms", 0.0) or 0.0)
    requests_completed = int(aggregate.get("requests_completed", 0) or 0)

    failures: list[str] = []

    min_throughput = float(baseline.get("minimum_throughput_pages_per_second", 0.0) or 0.0)
    max_memory = int(baseline.get("maximum_memory_peak_bytes", 0) or 0)
    max_sqlite = int(baseline.get("maximum_sqlite_size_bytes", 0) or 0)
    max_fetch_ms = float(baseline.get("maximum_avg_fetch_time_ms", 0.0) or 0.0)
    min_requests = int(baseline.get("minimum_requests_completed", 0) or 0)

    if throughput < min_throughput:
        failures.append(
            f"throughput_pages_per_second regression: {throughput:.3f} < {min_throughput:.3f}"
        )
    if max_memory > 0 and memory_peak > max_memory:
        failures.append(f"memory_peak_bytes regression: {memory_peak} > {max_memory}")
    if max_sqlite > 0 and sqlite_size > max_sqlite:
        failures.append(f"sqlite_size_bytes regression: {sqlite_size} > {max_sqlite}")
    if max_fetch_ms > 0 and avg_fetch > max_fetch_ms:
        failures.append(f"avg_fetch_time_ms regression: {avg_fetch:.3f} > {max_fetch_ms:.3f}")
    if requests_completed < min_requests:
        failures.append(f"requests_completed regression: {requests_completed} < {min_requests}")

    if failures:
        print("Benchmark regression check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Benchmark regression check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
