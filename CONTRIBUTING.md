# Contributing to SchemaLock

Thank you for your interest in SchemaLock! We build a declarative API contract
test harness for Stellar backend services and welcome contributors of **all
skill levels** — from first-time open-source contributors to seasoned Rust or
Python engineers.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style & Standards](#code-style--standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Commit Message Conventions](#commit-message-conventions)
- [Issue Reporting](#issue-reporting)
- [Good First Contributions](#good-first-contributions)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating you agree to uphold a welcoming, respectful environment for everyone.

---

## Getting Started

### Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.9+ | Canonical implementation |
| Rust | 1.86+ | Parallel `rust/` port (via [rustup](https://rustup.rs)) |

### 1. Fork & Clone

```bash
git clone https://github.com/<your-username>/schemalock.git
cd schemalock
```

### 2. Python — Install & Test

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### 3. Rust — Build & Test

```bash
cd rust
cargo build
cargo test
cd ..
```

### 4. Run the Example

```bash
uvicorn examples.mock_server:app --port 8000 &
schemalock test --config examples/escrow_api.yaml --base-url http://127.0.0.1:8000
```

Set `MOCK_BREAK_CONTRACT=1` before starting the server to see SchemaLock fail
against a deliberately broken contract.

---

## Development Workflow

### Branching Strategy

| Branch | Purpose |
| --- | --- |
| `main` | Stable, always passing CI |
| `feature/<topic>` | New features or enhancements |
| `fix/<topic>` | Bug fixes |
| `docs/<topic>` | Documentation-only changes |
| `chore/<topic>` | Tooling, CI, dependency updates |

**Always branch off `main`:**

```bash
git checkout main
git pull origin main
git checkout -b feature/my-feature
```

Prefer rebasing over merging to keep a clean history:

```bash
git fetch origin
git rebase origin/main
```

---

## Code Style & Standards

CI enforces formatting, linting, and tests. Run these before every commit:

**Python:**

```bash
ruff check .
pytest tests/ -q
```

**Rust:**

```bash
cd rust
cargo fmt --all -- --check
cargo clippy --all-targets -- -D warnings
cargo test
cargo audit           # dependency vulnerability scan
```

Guidelines:

- Follow [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/) for
  public Rust APIs.
- Avoid `unwrap()` in production paths — use `?` or explicit error handling.
- Keep the Rust and Python implementations **behaviorally equivalent** — both
  must pass against the same `examples/escrow_api.yaml` fixture.

---

## Testing Requirements

Every code contribution **must** include appropriate tests.

| Change type | Required tests |
| --- | --- |
| New check | Unit test (Python + Rust) + fixture case in `examples/` |
| Bug fix | Regression test that would have caught the bug |
| New utility / helper | Unit tests covering happy path and edge cases |
| Refactor | Existing tests must continue to pass (both languages) |

The mock server in `examples/mock_server.py` is the shared source of truth for
e2e tests in both languages — keep it in sync when adding fixtures.

---

## Pull Request Process

### Before Opening a PR

- [ ] Your branch is rebased on the latest `main`
- [ ] Python: `ruff check .` and `pytest tests/` pass
- [ ] Rust: `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test` pass
- [ ] New or updated tests are included
- [ ] No `todo!()` / `unimplemented!()` / debug `println!` / `print()` left in production paths

### Opening the PR

1. Push your branch to your fork.
2. Open a PR against `BreachDirect/schemalock:main`.
3. Fill in the PR template (summary, motivation / linked issue, testing performed).
4. Request a review — maintainers aim to respond within **48 hours**.

### Review Checklist (for reviewers)

- [ ] Code is correct and handles errors gracefully
- [ ] Tests are meaningful and cover edge cases
- [ ] Public APIs are documented
- [ ] Python + Rust parity maintained
- [ ] CI is green

---

## Commit Message Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer: "Closes #<issue>"]
```

### Types

| Type | When to use |
| --- | --- |
| `feat` | New feature or check |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code restructuring, no behaviour change |
| `test` | Adding or fixing tests |
| `chore` | Tooling, CI, dependency bumps |

### Scope (optional)

Use the area affected: `py`, `rust`, `config`, `checks`, `cli`, `docs`, `ci`.

---

## Issue Reporting

### Bug Reports

Please include:

1. **Language & version**: Python (`python --version`) or Rust (`rustc --version`)
2. **Steps to reproduce** (config YAML + target)
3. **Expected vs actual behaviour** (including exit code)
4. **Relevant output** (console or `--json-report`)

Use the **Bug Report** issue template on GitHub.

### Feature Requests

- Describe the problem you're solving, not just the solution.
- Link to any related issues or discussions.
- Check [PRD.md](PRD.md) and the roadmap first — your feature may already be planned.

### Security Vulnerabilities

**Do not open a public issue.** Contact the maintainers privately via GitHub's
[Security Advisories](../../security/advisories) feature — see
[SECURITY.md](SECURITY.md).

---

## Good First Contributions

Not sure where to start?

- Issues tagged [`good-first-issue`](../../issues?q=label%3Agood-first-issue)
- Add fixture coverage for a new error-envelope shape in `examples/`
- Harden config parsing error messages (Python and/or Rust)
- Expand docs with real-world contract examples

**New to Rust or Python?** Start with a documentation or testing issue.
Maintainers are happy to review code and suggest idiomatic improvements.

---

**Thank you for contributing to SchemaLock!** Every PR helps Stellar backends
ship stable, contract-safe APIs. 🚀
