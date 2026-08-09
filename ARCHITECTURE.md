# SchemaLock — Architecture

## 1. Overview

SchemaLock ships **two independent implementations** that consume the same
declarative YAML contract and must produce identical results:

- **`schemalock/`** — the reference Python implementation. Reads a declarative
  YAML contract, fires HTTP requests at a target backend with `httpx`, runs a
  fixed set of built-in checks against each response, and emits a pass/fail
  result plus an optional JSON report.
- **`rust/`** — a from-scratch Rust port of the same engine (single static
  binary, no runtime), kept behaviorally equivalent to Python via the parity
  gate in §6.

Python flow:

```
                 ┌────────────────────┐
                 │  schemalock.yaml    │
                 └─────────┬──────────┘
                            │  loaded & validated
                            ▼
                 ┌────────────────────┐
                 │  config.py          │  (dataclasses / validation,
                 │                      │   no external schema lib needed)
                 └─────────┬──────────┘
                            │  Config object
                            ▼
                 ┌────────────────────┐        ┌───────────────────┐
                 │  runner.py           │──────▶│  httpx.Client      │
                 │  (orchestrates       │        │  (real HTTP calls) │
                 │   requests + checks) │◀──────┘───────────────────┘
                 └─────────┬──────────┘
                            │  CheckResult[]
                            ▼
                 ┌────────────────────┐
                 │  checks/             │
                 │   error_envelope.py  │
                 │   auth.py            │
                 │   status_patterns.py │
                 └─────────┬──────────┘
                            │
                            ▼
                 ┌────────────────────┐
                 │  report.py           │──▶ stdout summary (pytest-style)
                 │                      │──▶ JSON report file
                 └────────────────────┘
```

## 2. Modules

### `schemalock/config.py`
- Parses `schemalock.yaml` with `PyYAML`.
- Validates structure with plain Python dataclasses (`Config`, `Endpoint`,
  `ErrorEnvelope`) rather than pulling in a heavy schema-validation dependency —
  keeps Phase 1 dependency footprint to `httpx` + `PyYAML` + stdlib.
- Raises `ConfigError` with a precise path (`endpoints[2].expect.status`) on any
  malformed input, so config mistakes are cheap to debug.

### `schemalock/runner.py`
- `Runner.run()` iterates endpoints, builds the request (method, path, headers,
  optional auth token/omission), executes it via a shared `httpx.Client`, and
  passes the response into each applicable check.
- Checks are independent and composable: each endpoint can opt into
  `error_envelope`, `auth_required`, and/or `status` checks. An endpoint failing
  one check doesn't block the others from running (all findings surface, not just
  the first).
- Network/timeout errors are captured as a distinct `CheckResult` (`ERROR`), not
  conflated with a `FAIL` assertion — a target that's simply unreachable should
  read differently in CI logs than a target that responded with the wrong shape.

### `schemalock/checks/error_envelope.py`
- Given a JSON error body and an `ErrorEnvelope` definition (`required_fields`,
  `field_types`), asserts presence and (loose) type match.
- Deliberately forgiving on *extra* fields (contracts should allow additive
  changes) but strict on missing fields or type changes (that's the breaking
  change class this tool exists to catch).

### `schemalock/checks/auth.py`
- For endpoints marked `auth_required: true`, replays the request with the
  configured auth header stripped (or replaced with an invalid token) and asserts
  the response is `401` or `403` — never `200`–`3xx`, never `404` (which would
  leak resource existence to unauthenticated callers), never `500`.

### `schemalock/checks/status_patterns.py`
- Straightforward expected-status assertion, but implemented as its own check
  module (rather than inline in the runner) so Phase 2 can extend it with
  pattern-based rules (e.g. "any 5xx must return the standard envelope") without
  touching the runner.

### `schemalock/report.py`
- `render_console(results)` — pytest-style `PASS`/`FAIL` lines with a one-line
  reason per failure, and a final summary count. Exit code is `1` if any check is
  `FAIL` or `ERROR`, `0` otherwise — CI-friendly by default, no flags required.
- `render_json(results, path)` — machine-readable report for CI artifact upload /
  future drift-detection (Phase 5).

### `schemalock/cli.py`
- Thin `argparse`-based entrypoint: `schemalock test --config <path> --base-url
  <url> [--json-report <path>] [--auth-header "Authorization: Bearer <token>"]
  [--timeout <seconds>]`.
- No hidden global state — base URL and auth are always explicit on the command
  line or config, matching the "run in CI, run on a laptop, get the same result"
  requirement.

### `rust/` (Rust port)
- A dependency-light Cargo crate that reimplements the same pipeline: YAML
  config → validated config model → `reqwest` HTTP calls → the same three check
  modules → pytest-style console output and the same JSON report shape.
- Produces a single static binary (`rust/target/release/schemalock`) so
  Wave-funded backends written in Rust can gate on contracts without a Python
  runtime in their image.
- Check logic lives in `rust/src/checks/` mirroring `schemalock/checks/`, and is
  exercised by `rust/tests/` (unit + e2e against the same bundled mock server in
  `examples/`).
- Behavioral equivalence with Python is enforced by the parity gate (§6), not by
  a shared codebase.

## 3. Data model (`schemalock.yaml`)

```yaml
name: string                     # human label, shown in report header
base_url: string                 # optional; --base-url flag overrides this
auth_header: string              # optional default, e.g. "Authorization: Bearer xyz"

error_envelopes:
  <envelope_name>:
    required_fields: [string]
    field_types: { field_name: "string"|"number"|"boolean"|"object"|"array" }

endpoints:
  - name: string
    method: GET|POST|PUT|PATCH|DELETE
    path: string                 # supports {placeholders} for path params
    body: object                 # optional request JSON body
    auth_required: bool          # default false
    expect:
      status: int | [int, ...]   # single status or list of acceptable statuses
      error_envelope: <envelope_name>   # only checked if response is 4xx/5xx
```

## 4. Why these design choices

- **httpx over requests**: native async-ready client, HTTP/2 support, and it's
  already the library named in the project brief — keeps Phase 2 (concurrent
  checks) a non-breaking upgrade.
- **Dataclasses over Pydantic for config**: Phase 1 has no need for a heavyweight
  validation dependency; keeps `pip install schemalock` fast and the dependency
  surface auditable, which matters for a security-adjacent CI tool.
- **No pytest dependency in Phase 1 core**: the CLI works standalone. Pytest-style
  *output formatting* is provided without requiring the caller's project to run
  under pytest at all — SchemaLock should work in a bare Docker CI step just as
  well as inside a Python test suite. (A real `pytest` plugin/fixture wrapper is a
  natural Phase 2/3 add-on once the core check engine is stable.)
- **Mock server bundled in `examples/`**: Phase 1 must be independently
  verifiable without a real Wave backend on hand — the example escrow/GraphQL-
  style mock server is what CI runs SchemaLock against.

## 5. Testing strategy

- `tests/` uses real `pytest` to test SchemaLock *itself* (unit tests for config
  parsing and each check module, plus one end-to-end test that boots the mock
  server as a subprocess and runs the CLI against it).
- `rust/tests/` mirrors that coverage for the Rust port, including an e2e test
  against the same mock server.
- CI (`.github/workflows/ci.yml`) runs the Python suite on every push/PR, plus a
  smoke test that runs the packaged CLI directly against the example config.
- CI (`.github/workflows/rust-ci.yml`) runs `cargo fmt`/`clippy`/`test`/`audit`
  on the Rust crate, plus the same smoke tests against the example config.
- The cross-language parity gate (below) runs on every push/PR in `ci.yml`.

## 6. Cross-language parity gate

Both implementations must produce **identical JSON reports** for the same config
and target. This is enforced by `scripts/parity_check.py`, which:

1. Boots the bundled mock server from `examples/`.
2. Runs the Python CLI and the compiled Rust binary against the *same* configs
   and fixtures (including broken-contract fixtures) with `--json-report`.
3. Asserts the two reports are byte-for-byte equal.

This gate is what keeps the Rust port honest: any change to check semantics,
error messages, or report structure in one implementation must be mirrored in
the other or CI fails.
