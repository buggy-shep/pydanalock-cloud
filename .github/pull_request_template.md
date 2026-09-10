## Summary

<!-- What does this PR change? Link the feature spec: specs/NNNN-slug.md -->

## Spec-driven checklist

- [ ] Feature spec exists (`specs/NNNN-slug.md`) and has status `approved`
- [ ] Tests written before implementation (TDD), failing first
- [ ] API responses covered by recorded fixtures (no live cloud in unit tests)
- [ ] Live tests stay behind the `live` marker
- [ ] `ruff check .`, `ruff format --check .`, `mypy`, `pytest -m "not live"` pass
- [ ] Skeptic review completed: verdict `APPROVED` (or `NITS` only)
- [ ] No secrets committed (tokens, keys, credentials); placeholders only in examples
- [ ] Logs never contain tokens or keys

## Commit style

Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`).
