# 0004 — Client lifecycle close methods

- **Status:** implemented
- **Scope:** `pydanalock.cloud` sync + async clients

## Summary

Adds explicit resource-release methods to both clients: `AsyncDanalockCloud.aclose()`
(async) and `DanalockCloud.close()` (sync), closing the underlying `httpx`
client. Both are idempotent.

## Motivation

Both clients create their `httpx.Client`/`httpx.AsyncClient` in the
constructor and never release it. Hosts that are done with a client (a Home
Assistant integration unloading a config entry, a script exiting) currently
leak the connection pool and the event-loop warning that httpx emits for
unclosed async clients. Hosts need a supported way to release the client's
resources.

## Requirements

- R1 (MUST) `AsyncDanalockCloud.aclose()` closes the internal
  `httpx.AsyncClient`; it must be safe to call more than once and after the
  client has processed requests.
- R2 (MUST) `DanalockCloud.close()` closes the internal `httpx.Client`;
  idempotency as in R1.
- R3 (MUST) The methods are additive: no existing public API or behavior
  changes; this is a patch-compatible feature release (`0.2.0`, SemVer
  minor: additive public methods while `0.x`).
- R4 (SHOULD) The sync `close()` does not block indefinitely: it performs a
  best-effort synchronous close of the client's resources.
- R5 (MUST) The public API version in `pydanalock.cloud.__version__` and
  `pyproject.toml` moves to `0.2.0`.

## Design

- `AsyncDanalockCloud.aclose()` delegates to `httpx.AsyncClient.aclose()`
  and keeps a flag (or relies on httpx's own close state) so repeated calls
  are no-ops instead of raising.
- `DanalockCloud.close()` delegates to `httpx.Client.close()`; httpx's
  `close()` is already safe to call repeatedly.
- No re-export changes: the methods live on the client classes.
- The clients stay usable before `close()`/`aclose()` is called; the methods
  do not invalidate tokens, storage, or the key cache.

## API

```python
class AsyncDanalockCloud:
    async def aclose(self) -> None: ...


class DanalockCloud:
    def close(self) -> None: ...
```

## Test plan

- Unit (MockTransport): after `login_password`, `aclose()` succeeds; a
  second `aclose()` is a no-op; the transport saw the request before closing.
- Sync parity: `close()` twice is safe; requests work before closing.
- Existing suite stays green (no behavior change).

## Acceptance criteria

- Unit tests green; gate green; skeptic without `BLOCKING`.

## Out of scope

- Context-manager protocol (`__aenter__`/`__await__` with `async with`);
  hosts that want it can call the close methods.
- HA integration lifecycle (consumer side).

## Status

`implemented` (spec approved with recorded decision in the phase-1
planning conversation, 2026-09-06: close methods are the precondition for
the HA integration's entry unload. Implemented 2026-09-06: idempotent
`aclose()`/`close()` merged, version 0.2.0).
