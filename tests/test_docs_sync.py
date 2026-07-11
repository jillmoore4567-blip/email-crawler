from __future__ import annotations

from pathlib import Path

from email_crawler.cli import build_parser


README_PATH = Path(__file__).resolve().parents[1] / "README.md"
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "src" / "email_crawler" / "migrations"
CHANGELOG_PATH = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
RELEASE_CHECKLIST_PATH = Path(__file__).resolve().parents[1] / "docs" / "RELEASE_CHECKLIST.md"
BENCHMARK_BASELINE_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "baseline.json"


def test_readme_contains_required_engineering_sections() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    required_sections = [
        "# Email Extractor & Website Crawler",
        "## Why This Project",
        "## Architecture",
        "## Installation",
        "## Quick Start",
        "## Live Monitoring",
        "## Configuration",
        "## Reports And Outputs",
        "## Database And Migrations",
        "## Testing And CI",
        "## Benchmarks",
        "## Screenshots",
        "## Contributing",
        "## License",
    ]
    for section in required_sections:
        assert section in text

    lowered = text.lower()
    assert "authorized asset inventory" in lowered
    assert "defensive testing" in lowered


def test_readme_mentions_all_migration_files() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    for migration_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        assert migration_file.name in text


def test_readme_cli_options_do_not_drift_for_core_flags() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    parser = build_parser()
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
        if option.startswith("--")
    }
    required_core_flags = {
        "--seeds",
        "--max-pages",
        "--max-depth",
        "--allow-domain",
        "--out-stats",
        "--out-sqlite",
        "--out-html",
        "--out-snapshot-diff",
        "--incremental",
        "--resume",
    }

    # Ensure docs include the most operationally important options.
    assert required_core_flags.issubset(option_strings)
    for flag in required_core_flags:
        assert flag in text


def test_release_docs_and_baseline_exist() -> None:
    assert CHANGELOG_PATH.exists()
    assert RELEASE_CHECKLIST_PATH.exists()
    assert BENCHMARK_BASELINE_PATH.exists()
