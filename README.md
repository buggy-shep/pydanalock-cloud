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

### Known cloud API surface

The cloud API is much larger than the implemented subset. The table below
summarises how much of the known surface is covered here; the full per-endpoint
catalogue is [spec 0011](specs/0011-cloud-api-surface.md), which is the source
of truth for these numbers.

| Domain | Known | Implemented |
|---|---|---|
| Auth and tokens | 7 | 1 |
| Devices and key material | 9 | 2 |
| Firmware | 4 | 1 |
| Enrollment, discovery, and device management | 10 | 0 |
| Users and account | 11 | 0 |
| Legacy platform (`ekey/v2`) | 8 | 0 |
| Legacy locks and advertisements (`ekey/v3`) | 7 | 0 |
| Bridge | 2 | 0 |
| Invitations | 2 | 0 |
| PIN-code aliases | 3 | 0 |
| Support | 1 | 0 |
| **Total** | **64** | **4** |

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
