from __future__ import annotations

import asyncio
import json
import tracemalloc
from pathlib import Path
from time import perf_counter

from aiohttp import web

from email_crawler.crawler import AsyncOsintCrawler, CrawlConfig
from email_crawler.io_utils import write_stats_json
from email_crawler.storage import compare_run_with_previous, persist_results_sqlite


async def _start_static_site(site_root: Path, port: int) -> web.AppRunner:
    app = web.Application()
    app.router.add_static("/", str(site_root), show_index=True)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    return runner


async def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    site_root = repo_root / "test_site"
    out_dir = repo_root / "output" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)

    port = 8019
    seed = f"http://127.0.0.1:{port}/index.html"
    db_path = out_dir / "benchmark.db"

    runner = await _start_static_site(site_root, port)
    tracemalloc.start()
    started = perf_counter()
    try:
        crawler = AsyncOsintCrawler(
            CrawlConfig(
                max_pages_per_seed=40,
                max_depth=4,
                concurrency=16,
                allowed_domains=("127.0.0.1",),
                collect_whois=False,
                collect_tls=False,
                collect_subdomains=False,
            )
        )
        results = await crawler.crawl_many([seed])
        run_id = persist_results_sqlite(results, str(db_path), config_payload={"benchmark": True})
        snapshot_diff = compare_run_with_previous(str(db_path), run_id)
        stats = write_stats_json(results, str(out_dir / "stats.json"), snapshot_diff=snapshot_diff)
        duration_seconds = perf_counter() - started
        current_mem, peak_mem = tracemalloc.get_traced_memory()

        pages = stats.get("pages_crawled", 0)
        benchmark_payload = {
            "seed": seed,
            "duration_seconds": round(duration_seconds, 4),
            "pages_crawled": pages,
            "throughput_pages_per_second": round(pages / max(duration_seconds, 1e-6), 4),
            "memory_current_bytes": current_mem,
            "memory_peak_bytes": peak_mem,
            "sqlite_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
            "performance": stats.get("performance", {}),
        }
        (out_dir / "latest.json").write_text(json.dumps(benchmark_payload, indent=2), encoding="utf-8")
        print(json.dumps(benchmark_payload, indent=2))
    finally:
        tracemalloc.stop()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
