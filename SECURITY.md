# Security Policy

## Reporting a Vulnerability

SchemaLock is a CI contract checker, so its own codebase must stay reliable — a
bug here can make other Stellar backends ship broken or unauthenticated APIs.
If you find a vulnerability in SchemaLock (a false pass, a crash, a config
parsing flaw, or a security issue in the tool itself), **do not open a public
issue.**

Report it privately via
[GitHub Security Advisories](../../security/advisories).

### What to include

1. **Affected version** — commit hash, Python package version, or crate version
2. **Description** — what the vulnerability is and its impact
3. **Reproduction** — config YAML, target URL, and command that triggers it
4. **Expected vs actual** — including exit codes and output

### Response targets

| Timeframe | Promise |
|---|---|
| Acknowledgement | within **48 hours** |
| Fix for critical issues | within **7 days** |
| Coordinated disclosure | we coordinate with you before any public writeup |

## Security posture

SchemaLock is designed to be safe to run in CI:

- **Deterministic reports** — the Python and Rust implementations are held to
  byte-identical JSON output by the CI parity gate, so a change in check
  semantics cannot hide.
- **Dependency auditing** — CI runs `cargo audit` (Rust) and `pip-audit`
  (Python) on every push/PR; both gates must stay green for merges.
- **Dependency automation** — Dependabot keeps crates and pip packages updated;
  CI enforces `ruff` and `cargo clippy -- -D warnings`, so the tool stays
  lint-clean.
- **Tight dependency surface** — the Python runtime depends only on `httpx` +
  `PyYAML`; the Rust binary uses rustls TLS (no OpenSSL), keeping the audit
  surface small.
- **Fail closed in CI** — non-zero exit code on any failed or errored check
  fails the surrounding CI step.

## Scope

In scope for security reports:

- The Python package (`schemalock/`)
- The Rust crate (`rust/`)
- The config parser and check logic (both languages)
- The parity gate (`scripts/parity_check.py`)
- The CI workflow definitions in `.github/workflows/`

Out of scope: vulnerabilities in the backend APIs that SchemaLock *tests*
(report those to the backend maintainers), and general issues in third-party
dependencies already tracked by `cargo audit` / `pip-audit`.

## Supported Versions

| Version | Supported |
| --- | --- |
| `main` | ✅ |
| Latest tagged release (`vX.Y.Z`) | ✅ |

## Safe Harbor

We will not pursue legal action against researchers who report vulnerabilities
in good faith: you act in good faith, do not access or destroy data beyond
demonstrating the vulnerability, and allow us a reasonable window to respond
before any public disclosure. We thank you for helping keep SchemaLock — and the
Stellar backends that rely on it — safe.
