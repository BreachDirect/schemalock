Thanks for contributing to SchemaLock! Please fill out the template below.

## Summary

<!-- What does this PR change and why? (required) -->

Closes #<!-- issue number, e.g. 12 -->

## Testing performed

<!-- Commands run and their results. CI runs ruff + pytest (Python) and
cargo fmt / clippy / test (Rust), plus the cross-language parity gate. -->

- [ ] Python: `ruff check .`, `ruff format --check .`, `pytest tests/` pass
- [ ] Rust: `cargo fmt --all -- --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test` pass
- [ ] Cross-language parity: `python3 scripts/parity_check.py --rust-binary rust/target/debug/schemalock` passes
- [ ] Tests included for new/changed behaviour
- [ ] Docs updated (README, PRD, ARCHITECTURE, etc. as applicable)
