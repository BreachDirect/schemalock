# SchemaLock

**Lock your API contract down before your backend drifts out of it.**

[![Python CI](https://github.com/BreachDirect/schemalock/actions/workflows/ci.yml/badge.svg)](https://github.com/BreachDirect/schemalock/actions/workflows/ci.yml)
[![Rust CI](https://github.com/BreachDirect/schemalock/actions/workflows/rust-ci.yml/badge.svg)](https://github.com/BreachDirect/schemalock/actions/workflows/rust-ci.yml)
[![Python](https://img.shields.io/badge/python-3.9+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/rust-1.86+-orange?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![License](https://img.shields.io/badge/license-MIT-blue)](#license)

SchemaLock is a small, fast, CI-friendly **API contract test harness** for
Stellar backend services. It reads one declarative YAML file, fires requests at
your running backend, and fails the build the moment a contract drifts —
without a DAST scanner, a browser, or bespoke per-repo test boilerplate.

It was built for the two regressions Stellar Wave backends keep shipping:

- **Error response shapes drifting** between releases, breaking client error handling.
- **Auth boundaries silently stopping being enforced** — routes that should
  401/403 falling through to 200, or leaking resource existence via 404.

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

## Contents

- [Features](#features)
- [Install](#install)
- [Quick start](#quick-start)
- [Bootstrap a contract from real traffic](#bootstrap-a-contract-from-real-traffic)
- [What it checks](#what-it-checks)
- [Config reference](#config-reference)
- [CLI reference](#cli-reference)
- [CI integration](#ci-integration)
- [Security](#security)
- [Implementations](#implementations)
- [Roadmap](#roadmap)

## Features

| | |
| --- | --- |
| 🚦 **Status code contracts** | expected status (or a set of acceptable ones) per endpoint |
| 📦 **Error envelope stability** | required fields + types asserted; additive fields allowed |
| 🔐 **Auth boundary checks** | unauthenticated replay must get 401/403 — never 200, never 404 |
| 🎬 **Bootstrap from live traffic** | Chrome extension records real requests → `schemalock scaffold` writes the YAML for you |
| 🪶 **CI-first** | seconds-fast, pytest-style output, JSON report artifact, non-zero exit on failure |
| 🧬 **Dual-language** | Python and Rust implementations with a byte-identical-report parity gate |
| 🛡️ **Security-minded** | no redirects, bounded response reads, secret redaction, env-var auth |

Every check is independent: an endpoint failing one check doesn't block the
others, so all findings surface in a single run.

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

## Quick start

```bash
uvicorn examples.mock_server:app --port 8000 &
schemalock test --config examples/escrow_api.yaml --base-url http://127.0.0.1:8000
```

Want to watch it *fail*? Start the mock with a deliberately broken contract
(renamed envelope field, wrong status code, leaked-existence 200-instead-of-404
auth bug):

```bash
MOCK_BREAK_CONTRACT=1 uvicorn examples.mock_server:app --port 8001 &
schemalock test --config examples/escrow_api.yaml --base-url http://127.0.0.1:8001
# exit code 1 — every regression is caught and explained
```

## Bootstrap a contract from real traffic

Don't want to hand-write the YAML? Install the **SchemaLock Recorder** browser
extension ([Chrome/Edge, Manifest V3](./browser-extension/README.md)), drive
your app while it records, and let the tool write the contract:

```bash
schemalock scaffold schemalock-capture.json --output schemalock.yaml
schemalock test --config schemalock.yaml --base-url http://127.0.0.1:8000 \
    --auth-header "Authorization: Bearer valid-token"
```

What gets inferred from the recording:

- **Endpoints** — method + path pattern; variable segments are normalized to
  `{placeholders}` and sample `path_params` are kept, so the config runs as-is.
- **Expected statuses** — the set of statuses observed per endpoint.
- **Error envelopes** — 4xx/5xx bodies clustered by shape into `standard` /
  `error_vN` envelopes.
- **`auth_required`** — from observed 401/403s, plus **auth probes**: the
  extension replays requests without credentials to prove the boundary is real.

Try it against the bundled mock — a demo frontend is served at
`http://127.0.0.1:8000/demo`:

```bash
uvicorn examples.mock_server:app --port 8000 &
# open http://127.0.0.1:8000/demo, record with the extension, export, scaffold
```

## What it checks

- **Status code contract** — each endpoint expects a specific status (or one of
  several), so a `400`-instead-of-`409` regression fails CI immediately.
- **Error envelope stability** — required fields and field types on error
  responses are asserted. *Additive* fields are allowed (contracts should permit
  growth); *missing* fields or *type drift* fail the check.
- **Auth boundary enforcement** — endpoints marked `auth_required: true` are
  replayed with no credentials and must return `401`/`403` — never a silent
  `200` (auth bypass) or a `404` (resource-existence leak to unauthenticated
  callers).

## Config reference

```yaml
name: string                        # human label, shown in report header
base_url: string                    # optional; --base-url overrides this
auth_header: string                 # optional default, e.g. "Authorization: Bearer xyz"

error_envelopes:                    # optional
  <envelope_name>:
    required_fields: [string]
    field_types: { field_name: "string"|"number"|"boolean"|"object"|"array"|"null" }

endpoints:                          # non-empty list
  - name: string                    #   unique label, used in reports
    method: GET|POST|PUT|PATCH|DELETE
    path: string                    #   supports {placeholders} for path params
    path_params: { name: value }    #   optional sample values for {placeholders}
    body: object                    #   optional request JSON body
    auth_required: bool             #   default false
    expect:
      status: int | [int, ...]      #   single status or list of acceptable statuses
      error_envelope: <envelope_name>   # checked when response is 4xx/5xx
```

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

## CLI reference

```
schemalock test --config <path> --base-url <url>
                 [--auth-header "Authorization: Bearer <token>"]
                 [--json-report <path>]
                 [--timeout <seconds>]
                 [--max-response-bytes <bytes>]

schemalock scaffold <capture.json> [--name <name>] [--base-url <url>]
                                    [--output schemalock.yaml]
```

| Flag | Description |
|---|---|
| `--config` | Path to `schemalock.yaml` (required) |
| `--base-url` | Target base URL (overrides `config.base_url`) |
| `--auth-header` | Default auth header for authenticated requests |
| `--json-report` | Write a machine-readable JSON report to this path |
| `--timeout` | Per-request timeout in seconds (default `10.0`) |
| `--max-response-bytes` | Abort a request whose response body exceeds this many bytes (default 10 MiB) |

Notes:

- Exit code `0` = every check passes, `1` = a check failed or errored.
- **Auth header resolution** — `--auth-header` flag, then the
  `SCHEMALOCK_AUTH_HEADER` env var, then `config.auth_header`. Prefer the env
  var: argv is visible in process listings and shell history.
- **`--max-response-bytes`** caps response body reads (default 10 MiB); an
  oversized response is reported as `ERROR` instead of exhausting CI memory.

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

## Security

SchemaLock runs against targets it doesn't fully trust and handles credentials,
so it ships security-minded defaults:

- **No redirects** — an authenticated check never forwards a token to a
  different origin via a 3xx response.
- **Bounded response reads** — capped at 10 MiB by default.
- **Secrets stay out of argv** — use the `SCHEMALOCK_AUTH_HEADER` env var.
- **Redaction on scaffold** — captured request bodies are scrubbed of values
  under sensitive keys (`token`, `password`, `api_key`, `authorization`, …)
  before YAML is emitted.
- **Safe parsing** — YAML configs use `safe_load`; no arbitrary code paths.
- **Recorder never stores token values** — only a boolean "was authenticated"
  flag; bodies are capped (256 KB) and the total capture budget is bounded.

See [SECURITY.md](./SECURITY.md) for the full threat model and reporting policy.

## Implementations

This repo ships two behaviorally-equivalent implementations, both validated
against the same example fixture (`examples/escrow_api.yaml` +
`examples/mock_server.py`):

- **Python** — the canonical implementation, `httpx` + `PyYAML`.
- **Rust** (`rust/`) — a parallel port for zero-runtime, single-binary CI use,
  built on `ureq` + rustls. See [`rust/README.md`](./rust/README.md).

Equivalence is enforced by a CI **parity gate**
([`scripts/parity_check.py`](./scripts/parity_check.py)): both CLIs run against
the same mock server — correct and broken contract — and their JSON reports
must be byte-identical. Any drift between the implementations fails CI:

```bash
python3 scripts/parity_check.py --rust-binary rust/target/debug/schemalock
```

## Project docs

- [`PRD.md`](./PRD.md) — problem statement, scope, and success criteria.
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — module layout and design rationale.
- [`CHANGELOG.md`](./CHANGELOG.md) — release history.
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — how to contribute.
- [`SECURITY.md`](./SECURITY.md) — security policy.
- [`ROADMAP`](https://github.com/BreachDirect/schemalock/issues) — planned
  phases tracked as issues (OpenAPI checks, auth matrices, drift reporting).

## Wave alignment

Built for **Drips Stellar Wave 8**
([drips.network/wave/stellar](https://www.drips.network/wave/stellar)) as a
standalone, reusable open-source dependency — not tied to any single org's
private codebase — so any Wave-funded backend can adopt it directly or as a CI
step.

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

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 BreachDirect.
