# Changelog

All notable changes to SchemaLock are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repo hygiene: `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, Dependabot config,
  `CODEOWNERS`, and a release workflow for tagged builds.
- README: install instructions, config reference, CI integration example,
  accurate example output, and a CLI flags table.

## [0.1.0] - 2026-08-09

Phase 1 of the declarative API contract harness for Stellar Wave 7/8.

### Added

- Python package `schemalock` (`httpx` + `PyYAML`) with `schemalock test` CLI.
- Three checks: status code contract, error envelope stability, and auth
  boundary enforcement.
- Declarative `schemalock.yaml` config with precise validation error paths.
- Console and `--json-report` output; CI-friendly exit codes.
- Parallel Rust implementation in `rust/` with rustls TLS support.
- Cross-language parity gate (`scripts/parity_check.py`) enforcing
  byte-identical JSON reports.
- Bundled example mock server + escrow config for smoke/e2e tests.
- CI: ruff + pytest (Python), fmt/clippy/test/audit (Rust), and both smoke tests.

[Unreleased]: https://github.com/BreachDirect/schemalock/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/BreachDirect/schemalock/releases/tag/v0.1.0
