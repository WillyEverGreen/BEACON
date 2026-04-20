## Summary

<!-- What does this PR do? One or two sentences. -->

## Type of Change

- [ ] Bug fix
- [ ] New accessibility rule / detector
- [ ] Engine improvement
- [ ] Dashboard / UI change
- [ ] Documentation update
- [ ] Dependency update
- [ ] Other (describe below)

## Pre-Push Checklist

- [ ] python -m pytest tests/unit/ -q - all tests pass
- [ ] python -m py_compile app/config.py app/audit/scan_mode_runner.py - no syntax errors
- [ ] lembic current - migrations at head
- [ ] .env is NOT staged
- [ ] No hardcoded max_pages added to pp/services/ or pp/routers/
- [ ] BEACON findings are never deleted, suppressed, or downgraded by this change

## Related Issues

Closes #

## Notes for Reviewer

<!-- Tricky parts, known limitations, follow-up work. -->
