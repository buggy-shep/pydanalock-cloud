# AGENTS.md — pydanalock-cloud

Working agreement for humans and AI agents contributing to this repository.

## 1. Role in the group

This repository is part of a group of projects that build a self-hosted
control stack for Danalock V3 smart locks:

| Repository | Role | Visibility | Language |
|---|---|---|---|
| `pydanalock-ble` | BLE client library for the Danalock V3 lock | public | English |
| `pydanalock-cloud` (this repo) | Cloud API client (OAuth2, devices, keys) | public | English |
| `danalock-ble-ha-integration` | Home Assistant custom integration, consumes both libraries | public | English |

`pydanalock-ble` and `pydanalock-cloud` are independent of each other; key
material is passed between them as opaque bytes (group contract type
`DeviceKey`: serial, login_blob, broadcast_key, validity, permissions). This
repository is the producer side of `DeviceKey`.

## 2. Language

All repository text is English: code, comments, docstrings, documentation,
commit messages, and review notes.

## 3. Stack and commands

- Python >= 3.11, hatchling, src-layout (`src/pydanalock/cloud/`), PEP 420
  namespace package `pydanalock` shared with `pydanalock-ble`.
- Runtime dependency: `httpx>=0.27`; dev tools: pytest, pytest-asyncio, ruff,
  mypy (strict for `src/`).

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/pytest -m "not live"
```

Live tests (real cloud, real credentials) carry the `live` marker and are run
manually only: `.venv/bin/pytest -m live`. Credentials come from the
environment: `DANALOCK_USERNAME`, `DANALOCK_PASSWORD`.

## 4. Spec-driven development (SDD)

- Every feature starts with a spec in `specs/NNNN-slug.md` (zero-padded
  number, short slug). Status lifecycle: `draft → approved → implemented →
  superseded`.
- Implementation without an `approved` spec is forbidden. Specs marked
  "implementation pending research" must not be implemented until they move to
  `approved`.
- Spec template: Summary / Motivation / Requirements (MUST/SHOULD) / Design /
  API / Test plan / Acceptance criteria / Out of scope / Status.
- Moving a spec from `draft` to `approved` is a reviewable change (PR or
  recorded decision in the conversation).

## 5. Test-driven development (TDD)

- Tests are written first and must fail before the implementation exists.
- API responses are covered by recorded fixtures via an httpx mock transport;
  unit tests never touch the production API.
- A merge requires a fully green run of all gate commands (§3).

## 6. Git process

- Default branch: `master`. Direct commits to `master` are forbidden (the
  initial scaffold import is the only exception).
- One feature = one branch `feat/NNNN-slug` containing the spec, the tests,
  and the implementation together.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`,
  `test:`, `chore:`, `refactor:`).
- Merge into `master` only after the review gate (§7), squash-merge, then
  delete the feature branch.

## 7. Review gate (mandatory)

A feature branch may merge into `master` only when both hold:

1. A full local run is green (§3/§5).
2. A skeptic review returns no `BLOCKING` findings. Invoke the skeptic agent
   (Task tool, subagent `skeptic`, definition in `.kilo/agent/skeptic.md`)
   with a prompt such as:

   > Review branch `feat/NNNN-slug` against its spec `specs/NNNN-slug.md`
   > (diff base: `master`). Follow the checklist in
   > `.kilo/agent/skeptic.md` and answer in the verdict format
   > (`BLOCKING: ...` / `NITS: ...` / `APPROVED`).

`BLOCKING` findings forbid the merge; fix and re-review.

## 8. Secrets and safety

- Your own device and account data are confidential: never include them in
  this public repository — in code, docs, examples, fixtures, or commit
  history. This covers lock serial numbers, device addresses, key material,
  and account data (usernames, passwords, tokens). Use synthetic
  placeholders (`<serial>`, `<username>`); real values live only in
  environment variables or gitignored `*.local.json` files.
- Never log tokens, keys, or Authorization headers; tests must verify log
  redaction where logging is involved.

## 9. Publication policy (public repository)

- Do not copy text or material from non-public sources into this repo.
- Public documentation is an English description of API behavior. Cite only
  this repository's own specs; do not name non-public or third-party sources,
  and do not state or claim how the API was determined.
- Everything in this repo is English (§2); keep the disclaimers in place
  (unofficial, not affiliated with Danalock AS, own devices only).

## 10. References

- Specs: `specs/` (0001 OAuth2 authentication is the first deliverable).
- Group contract: `DeviceKey` (specs 0002/0003).
- Python >= 3.11; versioning: SemVer, 0.x while the API is unstable.
