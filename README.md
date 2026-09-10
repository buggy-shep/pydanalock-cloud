# pydanalock-cloud

[![PyPI version](https://img.shields.io/pypi/v/pydanalock-cloud.svg)](https://pypi.org/project/pydanalock-cloud/)
[![CI](https://github.com/buggy-shep/pydanalock-cloud/actions/workflows/ci.yml/badge.svg)](https://github.com/buggy-shep/pydanalock-cloud/actions/workflows/ci.yml)

Unofficial Python client for the Danalock cloud API: OAuth2 authentication,
device listing, and retrieval of the per-device key material (login token
blob, broadcast key) used by BLE clients such as
[pydanalock-ble](https://github.com/buggy-shep/pydanalock-ble).

> **Disclaimer.** This project is unofficial and is not affiliated with,
> endorsed by, or sponsored by Danalock AS or Poly-Control. It is built for
> interoperability with devices you own. Use it at your own risk; only control
> devices you are authorized to control.

## Install

```bash
pip install pydanalock-cloud
```

## Status

OAuth2 authentication, device/key retrieval, forced key refresh, client
lifecycle, and latest firmware lookup are implemented (specs 0001–0006);
0.x — the API may still change. See [`specs/`](specs/) for the
specifications and their status.

Capabilities:

- OAuth2 authentication (refresh + password grants) with pluggable token
  storage — [spec 0001](specs/0001-oauth2-auth.md)
- Device listing and key retrieval with automatic refresh —
  [spec 0002](specs/0002-devices-keys.md)
- Public sync + async client API (`DanalockCloud`, `AsyncDanalockCloud`,
  `DeviceKey`) — [spec 0003](specs/0003-client-api.md)
- Client lifecycle close methods — [spec 0004](specs/0004-client-lifecycle.md)
- Forced key refetch (`get_key(..., force=True)`) —
  [spec 0005](specs/0005-key-refetch-force.md)
- Latest firmware lookup (unauthenticated firmware service; the download
  URL in the result is a short-lived signed link and must not be
  persisted) — [spec 0006](specs/0006-firmware-latest.md)

## Requirements

- Python >= 3.11
- [httpx](https://pypi.org/project/httpx/) >= 0.27

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/pytest -m "not live"
```

Live tests against the production API stay behind the `live` marker and are
run manually only, with credentials from the environment
(`DANALOCK_USERNAME`, `DANALOCK_PASSWORD`).

## License

[MIT](LICENSE)
