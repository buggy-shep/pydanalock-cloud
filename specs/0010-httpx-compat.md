# 0010 — relax httpx constraint for Home Assistant compatibility

- **Status:** approved
- **Scope:** runtime dependency range, version 0.5.1

## Summary

Widen the runtime dependency from `httpx>=0.28` to `httpx>=0.27` so the
distribution can be installed as a Home Assistant custom-integration
requirement. Version becomes 0.5.1. No API or code change.

## Motivation

Home Assistant 2025.1.4 (and the pinned
`pytest-homeassistant-custom-component==0.13.205`) requires `httpx==0.27.2`.
A requirement of `httpx>=0.28` makes `pip` resolution fail when Home
Assistant installs `pydanalock-cloud`, so the integration could not depend on
the published distribution — defeating the `dependency-transparency` rule.

The library uses only stable `httpx` API: its own suite and the HA integration
suite both pass with `httpx==0.27.2`.

## Requirements

- R1 (MUST) `[project].dependencies` contains `httpx>=0.27` (no upper bound).
- R2 (MUST) `[project].version` is `0.5.1`, and
  `pydanalock.cloud.__version__` is `0.5.1` (single-source test holds).
- R3 (MUST) The gate is green on `httpx==0.27.2` and on `httpx>=0.28`.
- R4 (MUST) No public API or behavior change.

## Design

Widen the version range only. `httpx` 0.27 and 0.28 differ in features not
used here; the existing MockTransport-based tests cover the client surface.

## API

No change.

## Test plan

- Run `ruff check`, `ruff format --check`, `mypy`, `pytest -m "not live"` in the
  project environment (httpx >=0.28).
- Run the suite against an isolated environment with `httpx==0.27.2`.
- Downstream: the Home Assistant integration installs
  `pydanalock-cloud==0.5.1` into an environment pinned to `httpx==0.27.2`.

## Acceptance criteria

- R1–R4 hold.
- `pydanalock-cloud==0.5.1` installs and imports alongside `httpx==0.27.2`.

## Out of scope

- Other dependency changes, code changes, or API changes.
- De-vendoring in the Home Assistant integration (spec 0014).

## Status

`approved`
