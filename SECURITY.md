# Security Policy

SchemaLock is a CI contract checker. A bug here can make other Stellar
backends ship broken or unauthenticated APIs, and the tool itself handles
credentials and replays traffic against live targets — so the project's own
security posture matters.

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

- The Python package (`schemalock/`) — including the HTTP layer (`http.py`)
  and the `scaffold` generator
- The Rust crate (`rust/`)
- The browser extension recorder (`browser-extension/`)
- The config parser and check logic (both languages)
- The parity gate (`scripts/parity_check.py`)
- The CI workflow definitions in `.github/workflows/`

Out of scope: vulnerabilities in the backend APIs that SchemaLock *tests*
(report those to the backend maintainers), and general issues in third-party
dependencies already tracked by `cargo audit` / `pip-audit`.

## Threat model & hardening

SchemaLock runs contract checks against a **target it does not fully trust**
(a live backend, possibly with a hostile load balancer or compromised
upstream). It also handles credentials on the command line and in configs.

| Concern | Mitigation |
| --- | --- |
| **Credentials leaked via redirects** | Redirects are never followed (Python: `follow_redirects=False`; Rust: `ureq` `redirects(0)`). An authenticated check cannot forward a token to a different origin via a 3xx response. |
| **Memory exhaustion from huge responses** | Response bodies are read incrementally and capped at 10 MiB by default (`--max-response-bytes`). Exceeding the cap is reported as `ERROR`, not a crash. |
| **Tokens in process listings / shell history** | `--auth-header` on argv is discouraged; pass `SCHEMALOCK_AUTH_HEADER` env var instead (flag > env > config precedence). |
| **Secrets committed from captured traffic** | `schemalock scaffold` redacts values under sensitive keys (`token`, `password`, `api_key`, `authorization`, …) in emitted YAML. |
| **Arbitrary code execution via config** | Config and capture files are parsed with `yaml.safe_load` / `json.load` — no YAML tags, no dynamic imports. |
| **Recorder leaking token values** | The extension stores only a boolean "was this request authenticated?" flag — never header values. Response bodies capped at 256 KB, total capture budget 32 MB (oldest entries evicted). |
| **Compromised CI token** | GitHub Actions workflows run with `permissions: contents: read` (least privilege). |
| **TLS** | Python uses `httpx` with certificate verification; Rust builds with rustls. |

### Known limitations

- The Rust port reads response bodies into memory without a size cap (Python
  only). A hostile target could consume unbounded RAM on a Rust-based CI run;
  a bounded reader is planned to mirror Python.
- The recorder extension requests broad `host_permissions` (`http(s)://*/*`)
  so its auth probes can replay against any recorded target. Only install it on
  developer machines; do not ship it to end users.

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
