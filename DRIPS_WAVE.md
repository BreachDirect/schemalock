# SchemaLock — Drips Stellar Wave: Repo Application & Appeal Guide

This repository is applying to the **Stellar Wave Program**
([drips.network/wave/stellar](https://www.drips.network/wave/stellar)). This
file documents (1) the application checklist, (2) the **substantive changes that
have landed since the previous application was reviewed**, and (3) the issue
queue we are putting up for the program.

## 1. Application checklist

### Already in the repository (code/docs done)

- [x] **GitHub Organization host** — repo lives under `BreachDirect` (not a personal account).
- [x] **Open-source license** — `LICENSE` (MIT).
- [x] **README with ecosystem utility** — top of `README.md` states the Stellar
      problem it solves and links the Wave program; 5-minute quick start included.
- [x] **`CONTRIBUTING.md`** — PR standards, code style, testing requirements,
      commit conventions, DCO, good-first-issue pointers.
- [x] **Repo hygiene files** — `SECURITY.md` (full threat model + hardening table),
      `CODE_OF_CONDUCT.md`, `CHANGELOG.md` (Keep a Changelog), `PRD.md`,
      `ARCHITECTURE.md`.
- [x] **Green CI quality gates** — GitHub Actions for Python and Rust:
      `ruff`, `pytest`, `cargo fmt --check`, `cargo clippy -- -D warnings`,
      `cargo test`, plus `pip-audit` / `cargo audit` dependency scanning and
      Dependabot. All must stay green for merges.
- [x] **Python/Rust parity gate** — `scripts/parity_check.py` asserts the two
      implementations produce **byte-identical** JSON reports on shared fixtures.
- [x] **Two tagged, artifact-bearing releases** — `v0.1.0` (Phase 1) and
      `v0.2.0` (Recorder + scaffold + security hardening), both built and
      published by the `Release` workflow with Python wheels, sdist, Rust
      binary, and checksums.
- [x] **Bounty issue template** — `.github/ISSUE_TEMPLATE/drips_wave_task.md`.
- [x] **Bounty queue** — 5 scoped issues with acceptance criteria (see §3),
      each labeled with a complexity (`trivial`/`medium`/`high`) + `drips-wave`.
- [x] **Complexity labels created** — `trivial` (100 pts), `medium` (150 pts),
      `high` (200 pts).

### Human steps only you can do (cannot be committed)

- [ ] **Repo is Public** — confirm in GitHub repo Settings.
- [ ] **Set the maintainer Ethereum address in `FUNDING.json`** — create
      `FUNDING.json` at the repo root on `main`:
      ```json
      { "drips": { "ethereum": { "ownedBy": "0x…your address…" } } }
      ```
      (not committed yet — maintainer must supply the address).
- [ ] **Claim the project on Drips** — Drips app → Projects → Claim (verifies `FUNDING.json`).
- [ ] **Install the Drips Wave GitHub App** on the `BreachDirect` org
      (read/write on issues, labels, PRs).
- [ ] **Apply the repo to the Stellar Wave Program** in the Drips app and wait
      for approval.
- [ ] **Complete KYC / identity verification** on Drips (required before distributing rewards).

## 2. Substantive changes since the previous application (appeal basis)

The previous application was declined. Since then the following **meaningful,
reviewable work** has landed on `main`. If the concern was **low activity**,
that concern is addressed directly: the project went from a single Phase 1
commit to an actively-shipped tool in six weeks — **12 commits, 2 tagged
releases (`v0.1.0`, `v0.2.0`), and a documented feature roadmap**, every
commit CI-green.

**Momentum at a glance** (all dates 2026):

- Jul 7 — Phase 1 MVP shipped
- Jul 18 — parallel Rust implementation
- Aug 5–8 — CI quality gates, security audits, parity gate, Wave 8 branding
- Aug 11 — SchemaLock Recorder + scaffold, repo hygiene revamp, **v0.2.0 released today**

| Date | Change | Relevance |
|---|---|---|
| 2026-07-07 | **Phase 1 MVP shipped** — CLI (`schemalock test`), YAML config, status/envelope/auth checks, mock escrow example, test suite, CI (`98c02d0`) | Deliverable, not a stub |
| 2026-07-18 | **Parallel Rust implementation** of the full Phase 1 (`ff5a71d`) | Dual-language, single-binary CI use |
| 2026-08-05 | **HTTPS via rustls**, dependency pins lifted, CI quality gates + contributor docs (`6245925`) | Repo maturity |
| 2026-08-05 | **Python/Rust parity gate** — byte-identical JSON reports on shared fixtures (`3e539f8`, `c2bf832`) | Reproducibility guarantee |
| 2026-08-05 | **Security audit gates** — `cargo audit` + `pip-audit` + Dependabot in CI (`58c3cdb`, `195d840`) | Supply-chain hygiene |
| 2026-08-08 | **Drips Wave 8 branding**, lint/format gates, security hardening (`e017b04`) | Program alignment |
| 2026-08-11 | **SchemaLock Recorder browser extension + `schemalock scaffold`** — record real traffic and auto-generate the contract YAML (`c4ac84d`) | Onboarding, the missing feature for adoption |
| 2026-08-11 | **Repo hygiene revamp** — README/CONTRIBUTING/SECURITY/CODE_OF_CONDUCT/CHANGELOG, issue templates, CODEOWNERS (`8160205`, `bb380fc`) | Application-readiness |
| 2026-08-11 | **Security hardening** — no redirects, bounded response reads, secret redaction, env-var auth, full threat model documented | Trust |

Evidence of sustained activity: **10+ commits across Aug 5–11**, all on `main`,
all CI-green, in a coherent direction tracked in `PRD.md` (§7 roadmap → GitHub
issues), and **two tagged releases with CI-built artifacts** — `v0.1.0` (Phase 1)
and `v0.2.0` (Recorder + scaffold), proving a repeatable release process rather
than a one-off dump.

## 3. Issue queue (ready to add to the program)

| # | Title | Complexity | Points |
|---|---|---|---|
| 12 | Phase 1.5: GraphQL example contract + mock fixture | `trivial` | 100 |
| 2 | Phase 3: CI/CD packaging — reusable GitHub Action + notifications | `medium` | 150 |
| 1 | Phase 2: Schema-aware checks (OpenAPI/JSON-Schema + GraphQL error shape) | `high` | 200 |
| 3 | Phase 4: Auth matrix testing — RBAC roles + JWT expiry/replay checks | `high` | 200 |
| 4 | Phase 5: Drift detection & historical reporting dashboard | `high` | 200 |

Every issue has a Goal, bounded Scope, Why, and verifiable acceptance criteria,
and the whole queue is documented against the `PRD.md` roadmap.

## 4. How to appeal (do this in the Drips app)

1. Open **Maintainers → Orgs and Repos** in the [Drips Wave app](https://www.drips.network/wave).
2. Find the rejected `schemalock` repo and click **Appeal**.
3. Use §2 as your summary of work since rejection — list the dated, concrete
   changes (commit hashes included) rather than a generic "we improved things".
4. Wait for the mandatory **two-week** gap after the original rejection before
   appealing (if less time has passed, the appeal button won't accept it).
5. Appeals are capped at three per repo, with a one-month cooldown between
   declined appeals — so submit only after the substantive changes are all merged.
