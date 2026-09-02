# Changelog

All notable changes to SchemaLock are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Rust port: `--max-response-bytes` response body cap (default 10 MiB),
  closing the parity gap with the Python implementation — oversized
  responses now produce the same `response exceeded size limit` error
  detail and exit code in both implementations (issue #14).
- Stellar Wave Program application materials: `DRIPS_WAVE.md` application &
  appeal guide, `drips_wave_task` issue template, and complexity labels
  (`trivial`/`medium`/`high`) applied across the bounty queue.

## [0.2.0] - 2026-08-11

### Added

- **SchemaLock Recorder** browser extension (Chrome/Edge, Manifest V3) —
  records live requests, replays auth probes, and exports captures.
- **`schemalock scaffold`** — generates a ready-to-run `schemalock.yaml` from a
  recorder capture: endpoint inference, status-set inference, error-envelope
  clustering, and `auth_required` detection.
- **Security hardening** — redirects never followed, response bodies bounded
  (`--max-response-bytes`, default 10 MiB), secret redaction in scaffold
  output, `SCHEMALOCK_AUTH_HEADER` env-var auth, safe `yaml.safe_load` config
  parsing.
- Full threat model + hardening table in `SECURITY.md`; revamped
  README/CONTRIBUTING with CI integration guide.

### Changed

- `--auth-header` resolution order: flag > `SCHEMALOCK_AUTH_HEADER` env var > config.

## [0.1.0] - 2026-08-09

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

[Unreleased]: https://github.com/BreachDirect/schemalock/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/BreachDirect/schemalock/releases/tag/v0.2.0
[0.1.0]: https://github.com/BreachDirect/schemalock/releases/tag/v0.1.0
