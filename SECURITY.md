# Security Policy

## Reporting a Vulnerability

SchemaLock is a CI contract checker, and its own codebase must stay reliable —
a bug here can make other Stellar backends ship broken or unauthenticated APIs.
If you find a vulnerability in SchemaLock (a false pass, a crash, a config
parsing flaw, or a security issue in the tool itself), **do not open a public
issue.**

Report it privately via [GitHub Security Advisories](../../security/advisories).

### What to include

1. **Affected version** — commit hash, Python package version, or crate version
2. **Description** — what the vulnerability is and its impact
3. **Reproduction** — config YAML, target URL, and command that triggers it
4. **Expected vs actual** — including exit codes and output

We aim to acknowledge reports within **48 hours** and ship a fix within
**7 days** for critical issues.

## Scope

- The Python package (`schemalock/`)
- The Rust crate (`rust/`)
- The config parser and check logic
- The CI workflow definitions in `.github/workflows/`

## Supported Versions

| Version | Supported |
| --- | --- |
| main | ✅ |

## Safe Harbor

We will not pursue legal action against researchers who report vulnerabilities
in good faith, act in good faith, and do not access or destroy data beyond
demonstrating the vulnerability.
