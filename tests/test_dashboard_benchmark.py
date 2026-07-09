from __future__ import annotations

from email_crawler.dashboard_benchmark import has_regression, run_dashboard_benchmarks


def test_dashboard_benchmark_thresholds() -> None:
    results = run_dashboard_benchmarks(sizes=[1000, 5000, 10000], iterations=5)

    failures = has_regression(results, threshold_ms=200.0)

    assert failures == []
