# 0007 — Protocol constants audit

- **Status:** approved
- **Scope:** `pydanalock.cloud` literal tables and constants (`src/`) — audit and
  provenance documentation, no behavior change

## Summary

A one-off audit of every literal table and constant in `src/pydanalock/cloud/`,
classifying each entry as a standard constant (T1), a protocol constant
observed on the wire (T2), an arbitrary opaque table (T3), or a non-public
blob (T4), and documenting the verdict for the entries that are not
self-evident. The audit result: no T3 and no T4 entries exist; the repository
holds only T1 (public standards) and T2 (observed protocol constants)
values, and no large literal tables at all.

## Motivation

The repository must not contain literal tables lifted verbatim from
non-public sources — generated vendor tables or opaque constant blobs are
not acceptable in public code, and neither are certificates, keys, or
account data. The inventory below confirms that the existing constants are
either derived from public standards or are functionally necessary values
for the public API, and marks the non-obvious ones with a provenance note in
the source so the classification survives future edits.

## Requirements

- R1 (MUST) Every provenance-relevant literal constant or multi-value
  constant in `src/` is classified into one of the tiers:
  - T1 — standard: RFC/IANA/crypto primitives;
  - T2 — protocol constant observed on the wire: IDs, tags, paths, lengths;
  - T3 — arbitrary opaque table with no public source (must not exist);
  - T4 — non-public blob: certificates, keys, account data (must not exist).
  Plain local-policy values (timeouts, margins) are listed separately in the
  inventory as local policy, not as protocol constants.
- R2 (MUST) The audit finds zero T3 and zero T4 entries. If a future change
  introduces a T3/T4 literal, it must be rejected at review time; the
  repository owns no automated guard for that.
- R3 (MUST) Non-obvious T2 constants (the public client defaults that are
  not self-evidently safe to ship) carry a short provenance comment in the
  source with method-neutral wording — a protocol constant observed on the
  wire, no source, no method, no reference to non-public material.
- R4 (MUST) Documentation wording obeys the publication policy: only
  ``observed on the wire``, ``public registry``, ``RFC ...``; no reference to
  non-public material and no statement of how the protocol was determined.
- R5 (MUST) The audit is documentation-only: no logical lines of `src/` code
  change, no behavior change, no fixture change.

## Design

Inventory (verified against `master` at 2026-09-10; line numbers refer to
the post-change sources):

| File:line | Entry | Tier | Note |
|---|---|---|---|
| `client.py:38-41` | `DEFAULT_BASE_URL`, `DEFAULT_CLIENT_ID="danalock-android"`, `DEFAULT_FIRMWARE_BASE_URL`, API paths | T2 | public endpoints and the public OAuth client id — functionally necessary for the API |
| `client.py:40` | `DEFAULT_TIMEOUT_SECONDS` | local policy | client-side I/O timeout, not a wire value |
| `auth.py:16` | `TOKEN_PATH` | T2 | vendor token endpoint path |
| `auth.py:17` | `EXPIRY_MARGIN_SECONDS` | local policy | client-side expiry guard, not a wire value |
| `auth.py:97-98` | `GRANT_PASSWORD`, `GRANT_REFRESH` | T1 | OAuth2 grant types, RFC 6749 |
| `models.py:16-17` | `SERIAL_PATTERN`, `BROADCAST_KEY_SIZE=16` | T2 | protocol format (serial shape, key size) |

No large literal tables or byte blobs were found in `src/`: audit scans show
no arbitrary multi-element numeric/byte lists, no `fromhex`/`bytes([` blobs,
and no lines longer than 200 characters. The inventory covers the
provenance-relevant module constants; plain local policy values
(`DEFAULT_TIMEOUT_SECONDS`, `EXPIRY_MARGIN_SECONDS`) are listed for
completeness and marked as such.

### Source provenance note

`DEFAULT_CLIENT_ID` and the API paths in `client.py` are the only constants
that are not self-evident in a public repository — they name the vendor's
public service and look like credentials, so they receive an inline comment
stating that they are observed public API values. `TOKEN_PATH`,
`SERIAL_PATTERN`, and `BROADCAST_KEY_SIZE` are self-evident wire-format
shapes already described by specs 0001/0002.

## Test plan

- No new tests: the audit changes only documentation and comments.
- Gate: full gate green (§3 of AGENTS.md): `ruff check .`,
  `ruff format --check .`, `mypy`, `pytest -m "not live"`.
- Diff invariant: `git diff --stat` shows `src/` changes limited to comment
  lines (no modified logical lines).

## Acceptance criteria

- Spec `0007` documents the tiers and the inventory with zero T3/T4 entries.
- Non-obvious T2 constants carry the provenance comment in `src/`.
- No logical code line changed; gates green; skeptic review without
  `BLOCKING`.

## Out of scope

- An automated guard against new T3/T4 tables (explicitly excluded).
- An internal provenance ledger (non-public source material).
- Licenses/disclaimers and publication policy wording (other plans).
- Test fixtures: synthetic and unchanged.

## Status

`approved` (audit outcome verified 2026-09-10: T3/T4 = 0; documentation-only
change).
