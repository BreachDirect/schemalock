# SchemaLock

**Declarative API contract test harness for Stellar backend services.**

[![Python CI](https://github.com/BreachDirect/schemalock/actions/workflows/ci.yml/badge.svg)](https://github.com/BreachDirect/schemalock/actions/workflows/ci.yml)
[![Rust CI](https://github.com/BreachDirect/schemalock/actions/workflows/rust-ci.yml/badge.svg)](https://github.com/BreachDirect/schemalock/actions/workflows/rust-ci.yml)
[![Python](https://img.shields.io/badge/python-3.9+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/rust-1.86+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![License](https://img.shields.io/badge/license-MIT-blue)](#license)
[![PyPI](https://img.shields.io/badge/pypi-schemalock-blue)](https://pypi.org/)

Stellar Wave backends (escrow services, marketplaces, trust/reputation APIs)
keep shipping the same two classes of regression: **error response shapes
drifting between releases**, and **auth boundaries that silently stop being
enforced**. SchemaLock is a small, fast, CI-friendly tool that locks those
contracts down with a single YAML file — no full DAST scanner, no bespoke
per-repo test boilerplate.

```yaml
# schemalock.yaml
name: "Escrow API contract"
base_url: "http://127.0.0.1:8000"
auth_header: "Authorization: Bearer valid-token"

error_envelopes:
  standard:
    required_fields: ["error", "message", "code"]
    field_types: { error: "boolean", message: "string", code: "string" }

endpoints:
  - name: get_missing_escrow_is_404_not_leaked
    method: GET
    path: /escrows/{id}
    path_params: { id: does-not-exist }
    auth_required: true
    expect:
      status: 404
      error_envelope: standard
```

```bash
schemalock test --config schemalock.yaml --base-url http://127.0.0.1:8000
```

```
SchemaLock — Escrow API contract

PASSED  get_missing_escrow_is_404_not_leaked :: status — got 404, expected one of [404]
PASSED  get_missing_escrow_is_404_not_leaked :: error_envelope — envelope 'standard' shape stable
PASSED  get_missing_escrow_is_404_not_leaked :: auth_required — unauthenticated request correctly rejected with 401

12 checks: 12 passed, 0 failed, 0 errored
```

Exit code is `0` when every check passes, `1` otherwise — drop it straight into a
CI step.

---

## What it checks

- **Status code contract** — each endpoint gets its expected status (or one of
  several acceptable statuses), so a `400`-instead-of-`409` regression fails CI
  immediately.
- **Error envelope stability** — required fields and field types on error
  responses are asserted; additive fields are allowed, missing fields or type
  drift fail the check.
- **Auth boundary enforcement** — endpoints marked `auth_required: true` are
  replayed with no credentials and must return `401`/`403` — never a silent
  `200` (auth bypass) or a `404` (which leaks resource existence to
  unauthenticated callers).

Every check is independent: an endpoint failing one check doesn't block the
others, so all findings surface in a single run.

---

## Install

### Python (canonical implementation)

```bash
pip install -e ".[dev]"      # from the repo, with dev deps
pip install schemalock       # once published to PyPI
```

Requires Python 3.9+. Runtime dependencies are just `httpx` and `PyYAML`.

### Rust (single-binary port)

```bash
cd rust
cargo build --release
./target/release/schemalock test --config ../examples/escrow_api.yaml \
  --base-url http://127.0.0.1:8000
```

Builds with rustls TLS, so `https://` targets work with no OpenSSL. See
[`rust/README.md`](rust/README.md).

---

## Quick start with the bundled example

```bash
uvicorn examples.mock_server:app --port 8000 &
schemalock test --config examples/escrow_api.yaml --base-url http://127.0.0.1:8000
```

Set `MOCK_BREAK_CONTRACT=1` before starting the mock server to see SchemaLock
catch a deliberately broken contract (renamed envelope field, wrong status
code, and a leaked-existence 200-instead-of-404 auth bug).

---

## Config reference

| Key | Type | Default | Description |
|---|---|---|---|
| `name` | string | `"SchemaLock contract"` | Human label shown in the report header |
| `base_url` | string | — | Target base URL; `--base-url` overrides it |
| `auth_header` | string | — | Default auth header, e.g. `"Authorization: Bearer xyz"` |
| `error_envelopes.<name>.required_fields` | `string[]` | `[]` | Fields that must be present in the error body |
| `error_envelopes.<name>.field_types` | `map` | `{}` | Field → type (`string`, `number`, `boolean`, `object`, `array`, `null`) |
| `endpoints[]` | list | required | One entry per endpoint under test |

Each endpoint:

| Key | Type | Default | Description |
|---|---|---|---|
| `name` | string | required | Unique label used in reports |
| `method` | `GET`/`POST`/`PUT`/`PATCH`/`DELETE` | required | HTTP method |
| `path` | string | required | Path template; `{placeholders}` are filled from `path_params` |
| `body` | object | — | Optional JSON request body |
| `auth_required` | bool | `false` | Replay without credentials; must return `401`/`403` |
| `path_params` | map | `{}` | Values for `{placeholders}` in `path` |
| `expect.status` | int \| `int[]` | `200` | Expected status code or list of acceptable ones |
| `expect.error_envelope` | string | — | Envelope to validate when the response is `4xx`/`5xx` |

Malformed configs fail fast with a precise field path (e.g.
`endpoints[2].expect.status: missing required field`).

---

## CLI reference

```
schemalock test --config <path> --base-url <url>
                 [--auth-header "Authorization: Bearer <token>"]
                 [--json-report <path>]
                 [--timeout <seconds>]
```

| Flag | Description |
|---|---|
| `--config` | Path to `schemalock.yaml` (required) |
| `--base-url` | Target base URL (overrides `config.base_url`) |
| `--auth-header` | Default auth header for authenticated requests |
| `--json-report` | Write a machine-readable JSON report to this path |
| `--timeout` | Per-request timeout in seconds (default `10.0`) |

---

## CI integration

```yaml
# .github/workflows/schemalock.yml
name: SchemaLock

on:
  pull_request:

jobs:
  contract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Start your backend, e.g. docker compose up -d api

      - name: Install SchemaLock
        run: pip install schemalock

      - name: Lock the API contract
        run: schemalock test --config schemalock.yaml --base-url http://127.0.0.1:8000

      - name: Upload report artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: schemalock-report
          path: report.json
```

The non-zero exit code on failure fails the job; add `--json-report` and
`actions/upload-artifact` (with `if: always()`) to keep a record even when the
gate trips.

---

## Implementations

This repo ships two behaviorally-equivalent implementations, both validated
against the same example fixture (`examples/escrow_api.yaml` +
`examples/mock_server.py`):

- **Python** — the canonical implementation, `httpx` + `PyYAML`.
- **Rust** (`rust/`) — a parallel port for zero-runtime, single-binary CI use.
  Builds with rustls TLS (HTTPS supported). See
  [`rust/README.md`](./rust/README.md).

The equivalence claim is enforced by a CI **parity gate**
([`scripts/parity_check.py`](./scripts/parity_check.py)): it runs both CLIs
against the same mock server — correct contract and broken contract — and
asserts their JSON reports are byte-identical. Any drift between the two
implementations fails CI:

```bash
python3 scripts/parity_check.py --rust-binary rust/target/debug/schemalock
```

---

## Project docs

- [`PRD.md`](./PRD.md) — problem statement, scope, and success criteria.
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — module layout and design rationale.
- [`CHANGELOG.md`](./CHANGELOG.md) — release history.
- [`ROADMAP`](https://github.com/BreachDirect/schemalock/issues) — planned
  phases tracked as issues (OpenAPI checks, auth matrices, drift reporting).

## Wave alignment

Built for **Drips Stellar Wave 8**
([drips.network/wave/stellar](https://www.drips.network/wave/stellar)) as a
standalone, reusable open-source dependency — not tied to any single org's
private codebase — so any Wave-funded backend can adopt it directly or as a CI
step.

---

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest tests/ -v
# Rust port: cd rust && cargo fmt --check && cargo clippy -- -D warnings && cargo test
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor guide,
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards, and
[SECURITY.md](SECURITY.md) for reporting vulnerabilities.

---

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 BreachDirect.
