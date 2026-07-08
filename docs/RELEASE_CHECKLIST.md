# Release Checklist

## Pre-Release Gates
- [ ] All tests pass (`pytest -q`).
- [ ] Lint is clean (`ruff check src tests`).
- [ ] Staged strict type checks pass (`mypy --config-file mypy.ini`).
- [ ] Documentation sync tests pass (`pytest -q tests/test_docs_sync.py`).
- [ ] Migration tests pass (`pytest -q tests/test_storage_history.py tests/test_migration_fixture_smoke.py`).
- [ ] Benchmark and regression checks pass (`python scripts/benchmark_synthetic.py` and `python scripts/check_benchmark_regression.py`).

## Versioning and Notes
- [ ] Project version is bumped in [pyproject.toml](../pyproject.toml).
- [ ] Changelog is updated in [CHANGELOG.md](../CHANGELOG.md).
- [ ] Migration notes are included for schema-impacting changes.

## Packaging and Installability
- [ ] Build artifacts are generated (`python -m build`).
- [ ] Artifacts validate with twine (`python -m twine check dist/*`).
- [ ] Wheel install succeeds in a clean environment.
- [ ] CLI smoke check succeeds from wheel install (`email-crawler --help`).

## Release Publication
- [ ] Release tag is created (for example, `v1.0.0`).
- [ ] Release notes are published with scope and compatibility guarantees.
- [ ] Supported Python versions and platform assumptions are documented.
