from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from email_crawler.dashboard_benchmark import THRESHOLD_MS, has_regression, run_dashboard_benchmarks


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark dashboard performance with synthetic datasets")
    parser.add_argument(
        "--sizes",
        default="1000,5000,10000",
        help="Comma-separated dataset sizes (default: 1000,5000,10000)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=7,
        help="Median sample count per operation (default: 7)",
    )
    parser.add_argument(
        "--threshold-ms",
        type=float,
        default=THRESHOLD_MS,
        help="Per-operation latency threshold in milliseconds (default: 200)",
    )
    parser.add_argument(
        "--output",
        default="output/benchmarks/dashboard_latest.json",
        help="Output JSON file path",
    )
    args = parser.parse_args()

    sizes = [int(item.strip()) for item in args.sizes.split(",") if item.strip()]
    results = run_dashboard_benchmarks(sizes=sizes, iterations=max(3, args.iterations))

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold_ms": args.threshold_ms,
        "results": [item.as_dict() for item in results],
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    failures = has_regression(results, threshold_ms=args.threshold_ms)
    print(json.dumps(payload, indent=2))
    if failures:
        print("Dashboard benchmark threshold failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Dashboard benchmark threshold check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
