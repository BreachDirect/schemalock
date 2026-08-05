# SchemaLock

**Declarative API contract test harness for Stellar backend services.**

![Python CI](https://github.com/BreachDirect/schemalock/actions/workflows/ci.yml/badge.svg)
![Rust CI](https://github.com/BreachDirect/schemalock/actions/workflows/rust-ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.9+-blue)
![Rust](https://img.shields.io/badge/rust-1.86+-orange)
![License](https://img.shields.io/badge/license-MIT-blue)

Stellar Wave backends (escrow services, marketplaces, trust/reputation APIs)
keep shipping the same two classes of regression: error response shapes
drifting between releases, and auth boundaries that silently stop being
enforced. SchemaLock is a small, fast, CI-friendly tool that locks those
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

3 checks: 3 passed, 0 failed, 0 errored
```

## What it checks (Phase 1)

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

## Install

```bash
pip install -e ".[dev]"
```

## Quick start with the bundled example

```bash
uvicorn examples.mock_server:app --port 8000 &
schemalock test --config examples/escrow_api.yaml --base-url http://127.0.0.1:8000
```

Set `MOCK_BREAK_CONTRACT=1` before starting the mock server to see SchemaLock
catch a deliberately broken contract (renamed envelope field, wrong status
code, and a leaked-existence 200-instead-of-404 auth bug).

## CLI reference

```
schemalock test --config <path> --base-url <url>
                 [--auth-header "Authorization: Bearer <token>"]
                 [--json-report <path>]
                 [--timeout <seconds>]
```

Exit code is `0` if every check passes, `1` otherwise — drop it straight into
a CI step.

## Implementations

This repo ships two behaviorally-equivalent Phase 1 implementations, both
validated against the same example fixture (`examples/escrow_api.yaml` +
`examples/mock_server.py`):

- **Python** (this directory) — the canonical implementation, `httpx` + `PyYAML`.
- **Rust** (`rust/`) — a parallel port for zero-runtime, single-binary CI use.
  Builds with rustls TLS (HTTPS supported). See [`rust/README.md`](./rust/README.md).

## Project docs


- [`PRD.md`](./PRD.md) — problem statement, scope, and success criteria.
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — module layout and design rationale.

## Roadmap

Phase 1 (this release) ships the core CLI and the three checks above. Planned
phases — schema-aware/OpenAPI checks, a reusable GitHub Action, role-based auth
matrices, and historical drift reporting — are tracked as issues in this repo.

## Wave alignment

Built for **Stellar Wave 8** as a standalone, reusable open-source dependency —
not tied to any single org's private codebase — so any Wave-funded backend can
adopt it directly or as a CI step.

## License

MIT
