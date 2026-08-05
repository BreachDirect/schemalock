# SchemaLock (Rust)

A parallel implementation of Phase 1, ported from the canonical Python
implementation at the repo root. Same YAML contract format, same three
built-in checks (status code, error envelope stability, auth-required
enforcement), same CLI shape, validated against the **same** example fixture
(`../examples/escrow_api.yaml` + `../examples/mock_server.py`) so both
implementations are provably behaviorally equivalent, not just similar.

## Why a Rust port

The Python CLI needs a Python install + two `pip` dependencies. The Rust
binary compiles to a single static-ish executable with no runtime — a Wave
backend in any language (Rust, Node, Go, whatever) can drop the binary into
CI with no interpreter setup at all. See the root `PRD.md`/`ARCHITECTURE.md`
for the full rationale; this file covers only what's Rust-specific.

## Build & run

```bash
cargo build --release
./target/release/schemalock test \
  --config ../examples/escrow_api.yaml \
  --base-url http://127.0.0.1:8000 \
  --auth-header "Authorization: Bearer valid-token"
```

## Test

```bash
cargo test
```

Unit tests (`tests/config_tests.rs`, `tests/checks_tests.rs`) test config
parsing and check logic directly, no network needed. `tests/e2e_tests.rs`
boots the shared Python mock server (requires `python3` + the root project's
`pip install -e ".[dev]"` to be available) and runs the compiled binary
against it — the same regressions (leaked-404-as-200, renamed envelope field)
that the Python e2e test catches, this test catches too.

## HTTPS support

The Rust binary builds with a rustls TLS backend (the `tls` feature on `ureq`),
so `https://` targets work out of the box — no OpenSSL required. The original
sandbox that produced this port only had an old `apt` Rust (1.75), which forced
temporary exact pins on `ureq` and dropped TLS; those pins are gone and TLS is
now enabled by default.

## What's ported vs. what isn't (yet)

| Python | Rust | Status |
|---|---|---|
| `config.py` | `src/config.rs` | ✅ same validation rules, same error message shapes |
| `checks/status_patterns.py` | `src/checks/status.rs` | ✅ |
| `checks/error_envelope.py` | `src/checks/envelope.rs` | ✅ |
| `checks/auth.py` | `src/checks/auth.rs` | ✅ |
| `runner.py` | `src/runner.rs` | ✅ |
| `report.py` | `src/report.rs` | ✅ (console + JSON, same shape) |
| `cli.py` | `src/main.rs` | ✅ same `test` subcommand and flags |
| HTTPS support | — | ✅ rustls (`ureq` feature `tls`) |
| pytest plugin / GitHub Action | — | Not yet ported either language (Phase 2/3) |
