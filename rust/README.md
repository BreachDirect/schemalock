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

## Known limitation: HTTP only, no TLS (for now)

This crate currently builds **without** a TLS backend — `https://` targets
will fail. This is a toolchain artifact, not a design choice: the sandbox this
was built in only has `apt`'s Rust 1.75 available (no `rustup` access), and
recent `native-tls`/`rustls` releases require Rust 1.80+. Several transitive
dependencies are pinned to older versions in `Cargo.toml` specifically to stay
buildable on 1.75.

**On a normal machine or in GitHub Actions with a current stable Rust
toolchain (1.80+), this is trivial to lift**: relax the exact-pinned
dependency versions back to normal ranges and add back
`features = ["json", "native-tls"]` (or `"tls"` for rustls) to the `ureq`
dependency in `Cargo.toml`. No application code changes are needed — the
limitation is entirely in the dependency graph, not in `runner.rs`/`auth.rs`.

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
| HTTPS support | — | ⚠️ pending a modern toolchain, see above |
| pytest plugin / GitHub Action | — | Not yet ported either language (Phase 2/3) |
