# Pull Request

## Summary

Describe the change in 2-4 bullet points.

- [ ] Item 1
- [ ] Item 2

## Type of change

- [ ] Bug fix
- [ ] Documentation update
- [ ] Performance improvement
- [ ] New backward-compatible feature
- [ ] Breaking change (requires maintainer approval)

## Validation

List commands you ran and their outcomes.

```powershell
ruff check src tests
mypy --config-file mypy.ini
pytest -q
```

## Release impact

- [ ] No user-facing change
- [ ] Requires CHANGELOG update
- [ ] Requires docs update
- [ ] Requires migration notes

## Checklist

- [ ] I kept the change scoped and focused.
- [ ] I added/updated tests when behavior changed.
- [ ] I updated docs/examples when CLI/config/output changed.
- [ ] I removed secrets/sensitive data from artifacts and logs.
