# SchemaLock — Product Requirements Document

**Status:** Phase 1 (MVP) — implemented
**Owner:** BreachDirect
**Target program:** Stellar Wave 8 — Contributor Track

## 1. Problem

Stellar-ecosystem backends (escrow services, marketplace APIs, trust/reputation
services) repeatedly need the same class of fix: **API contract regressions**.
Concretely, across Wave issue trackers this shows up as:

- Error response shapes drifting between releases, breaking client error handling
  (confirmed pattern: Wave issue #159, `Talenttrust/Talenttrust-Backend` — "Add API
  contract tests to lock error envelope stability and key error codes").
- Wrong status codes shipped for known states — e.g. a delete-on-non-pending
  resource returning `400` instead of `409` (observed in
  `stellarmarket-labs/stellar-market` PR #833, which had to retrofit six status-code
  tests: 401/403/404/409/204 after the fact).
- Auth boundaries not being asserted at all (routes that should 401/403 silently
  falling through to 200, or vice versa).
- No shared, reusable way to assert this — every team hand-rolls a handful of
  `assert resp.status_code == ...` tests inside their own framework, if they write
  them at all.

**ShieldScan** (a related project) solves a different problem — full DAST /
vulnerability scanning of a running web app. That's too heavy a tool to reach for
when what a backend team actually needs is a **fast, declarative, CI-friendly
contract checker** that runs in seconds against `localhost:8000` and fails the
build the moment an error envelope or status code contract breaks.

## 2. Goal

Give any Stellar Wave backend team a way to:

1. Declare their API's expected contract (endpoints, status codes, error envelope
   shape, auth requirements) in one YAML file.
2. Run `schemalock test` locally or in CI and get a pass/fail + JSON report in
   seconds, with no dependency on a full browser or a running scanner stack.
3. Catch the two most common backend regressions before merge: **error envelope
   drift** and **auth-boundary regressions**.

## 3. Non-goals (Phase 1)

- Not a fuzzer, not a DAST tool, not a vulnerability scanner (that's ShieldScan's job).
- Not a full OpenAPI/JSON-Schema validator (Phase 2+).
- Not a load-testing or performance tool.
- Not GraphQL-schema-aware yet — Phase 1 treats GraphQL endpoints as POST/JSON
  contract targets (status code + envelope only); real GraphQL error-shape
  validation is Phase 2.

## 4. Users

- **Backend maintainers** on Wave-funded repos (Rust/Node/Python APIs) who need a
  drop-in CI check.
- **Wave contributors** picking up "add contract tests" style issues, who want a
  tool instead of hand-rolling assertions per repo.

## 5. Phase 1 requirements (this release)

| # | Requirement | Status |
|---|---|---|
| R1 | YAML config format (`schemalock.yaml`) defining base URL, endpoints, expected status, auth requirement, error envelope shape | ✅ |
| R2 | CLI: `schemalock test --config schemalock.yaml --base-url <url>` | ✅ |
| R3 | Built-in check: error envelope stability (required fields + types present on error responses) | ✅ |
| R4 | Built-in check: auth-required routes (401/403 enforced when no/invalid credentials sent) | ✅ |
| R5 | Built-in check: status code pattern matching (404/422/503/etc. per endpoint) | ✅ |
| R6 | Pytest-style assertion failures with clear diffs, non-zero exit code on failure | ✅ |
| R7 | JSON report output (`--json-report report.json`) for CI artifact upload | ✅ |
| R8 | Example config against a mock escrow/GraphQL-style backend, runnable standalone | ✅ |
| R9 | CI pipeline (GitHub Actions) that installs, lints, and runs SchemaLock against its own mock server | ✅ |

## 6. Success criteria (Phase 1)

- `pip install -e .` + `schemalock test --config examples/escrow_api.yaml --base-url http://127.0.0.1:8000`
  runs against the bundled mock server and produces a correct pass/fail report.
- A deliberately broken mock response (wrong status, missing envelope field,
  missing auth check) is caught and reported with a specific, actionable message.
- CI is green on a clean checkout.

## 7. Roadmap (future phases — tracked as GitHub issues)

- **Phase 2 — Schema-aware checks:** OpenAPI/JSON-Schema validation of full response
  bodies (not just envelope), GraphQL error-shape validation, response header
  contracts.
- **Phase 3 — CI/CD packaging:** Reusable GitHub Action, PR status checks, Slack/
  webhook failure notifications, badge generation.
- **Phase 4 — Auth matrix testing:** Role-based access matrices (multiple roles ×
  multiple routes), JWT expiry/replay/tampering checks.
- **Phase 5 — Drift detection & reporting:** Store historical run results, diff
  contract behavior across deploys/releases, HTML trend dashboard.

## 8. Wave alignment note

This project targets **Stellar Wave 8**. It is scoped as a standalone, reusable
open-source tool (not tied to any single Wave org's private codebase) so any
Wave-funded backend can adopt it as a dependency or CI step.
