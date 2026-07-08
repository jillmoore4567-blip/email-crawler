# Contributing

Thanks for contributing.

## Development Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

## Quality Gates

Run these before opening a PR:

```powershell
ruff check src tests
mypy --config-file mypy.ini
pytest -q
```

## Commit Messages

Use short, imperative messages.

- `fix: handle empty seed file`
- `docs: clarify migration notes`
- `test: add regression for snapshot diff`

Recommended style:

- `<type>: <summary>`
- Keep subject around 72 chars.
- Explain why in the commit body when useful.

## Pull Request Expectations

- Keep changes scoped and focused.
- Include tests when behavior changes.
- Update docs when CLI, config, schema, or output changes.
- Describe validation commands and outcomes in the PR body.
- Do not include secrets or sensitive data in logs/artifacts.
