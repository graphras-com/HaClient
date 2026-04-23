## Summary

Describe the defect and the fix directly.

## Root Cause

What was wrong, and where?

## Validation

- [ ] `ruff check .`
- [ ] `mypy src/haclient/`
- [ ] `pytest --cov=haclient --cov-report=term-missing --cov-fail-under=95`
- [ ] Added or updated tests that fail without this change
- [ ] Updated docs if behavior changed

## Risk

What could still break?
