# 0009 — PyPI publication of pydanalock-cloud

- **Status:** approved
- **Scope:** distribution metadata, build/publish CI, Trusted Publishing,
  TestPyPI dry run

## Summary

Publish the `pydanalock-cloud` distribution (import namespace `pydanalock.cloud`)
to PyPI from a public CI pipeline using Trusted Publishing, with a mandatory
TestPyPI dry run before the first production release. No runtime API changes.

## Motivation

The library is consumed by the Home Assistant integration, which currently
vendors a copy. Home Assistant's `dependency-transparency` quality-scale rule
requires a dependency to be on PyPI, built and published from a public CI, and
to have a version matching a tagged release. Publishing also lets downstream
users install it directly (`pip install pydanalock-cloud`).

## Requirements

- R1 (MUST) `[project].name` is `pydanalock-cloud` and `version` is `0.5.0`
  (the version is superseded by spec 0010: 0.5.1).
  `pyproject.toml` declares `[project.urls]` (`Homepage`, `Repository`,
  `Issues`, `Changelog`, all under `buggy-shep/pydanalock-cloud`) and a
  `release` optional-dependency group (`build>=1.2`, `twine>=5`).
- R2 (MUST) The wheel contains `pydanalock/cloud/*` including `py.typed` and
  no test or cache files; the sdist contains `LICENSE`, `README.md`,
  `pyproject.toml`, and `src/`.
- R3 (MUST) The version is single-sourced: a test asserts
  `tomllib.load("pyproject.toml")["project"]["version"]` equals
  `pydanalock.cloud.__version__`.
- R4 (MUST) `.github/workflows/ci.yml` runs a `build` job
  (`python -m build` + `twine check dist/*`) on push to `master` and on pull
  requests, and cancels superseded runs via `concurrency`.
- R5 (MUST) A `publish.yml` workflow triggers on GitHub Release
  (`types: [published]`), builds the artifacts once, uploads them, and publishes
  with `pypa/gh-action-pypi-publish@release/v1` using OIDC Trusted Publishing
  (`environment: pypi`, `permissions: id-token: write`). It must not run on
  pull requests.
- R6 (MUST) A `testpypi.yml` workflow (`workflow_dispatch`) publishes the same
  artifacts to TestPyPI (`environment: testpypi`,
  `repository-url: https://test.pypi.org/legacy/`). A successful TestPyPI dry
  run is required before the first production release.
- R7 (MUST) `README.md` documents installation (`pip install pydanalock-cloud`),
  shows PyPI and CI badges, and links the sibling library as
  `buggy-shep/pydanalock-ble`.
- R8 (MUST) No secrets, real device data, or rename provenance appear in the
  package or the repository (the latter is handled by the scrub change).
- R9 (MUST) The gate (ruff check, ruff format --check, mypy, pytest
  `-m "not live"`) is green; the wheel installs into a clean environment and
  its test run passes.

## Design

- Build backend stays hatchling with src-layout (`packages = ["src/pydanalock"]`).
- Publication uses PyPI Trusted Publishing: the PyPI project is created by a
  pending publisher (owner `buggy-shep`, repository `pydanalock-cloud`, workflow
  `publish.yml`, environment `pypi`). The TestPyPI publisher uses
  `testpypi.yml` / `testpypi`.
- Releases are cut by pushing a `vX.Y.Z` tag and publishing a GitHub Release;
  the tag must equal `[project].version`.
- The build job is shared by `ci.yml`/`publish.yml`; publish consumes the
  uploaded artifact rather than rebuilding.

## API

No public API change.

## Test plan

- `tests/test_package.py::test_version_matches_pyproject` (R3).
- Local: `python -m build`, `twine check dist/*`, inspect sdist/wheel contents,
  install the wheel into a clean venv and run `pytest -m "not live"`.
- CI: `build` job green on the pull request.
- TestPyPI dry run: workflow green, page renders, and
  `pip install -i https://test.pypi.org/simple/ --extra-index-url
  https://pypi.org/simple/ pydanalock-cloud==0.5.0` imports `0.5.0`.

## Acceptance criteria

- R1–R9 hold.
- TestPyPI dry run succeeds and the production release publishes `0.5.0` via
  Trusted Publishing from the public CI with no long-lived credentials.

## Out of scope

- Publishing `pydanalock-ble` and devendoring it from the integration.
- Devendoring this library from the Home Assistant integration.
- HACS/store metadata and repository branding beyond the README badges.

## Status

`approved`
