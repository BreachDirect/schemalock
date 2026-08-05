name: Pull Request
description: Changes to SchemaLock
title: "[feat]: "
labels: []
body:
  - type: markdown
    attributes:
      value: |
        Thanks for contributing to SchemaLock! Please complete the checklist below.
  - type: textarea
    id: summary
    attributes:
      label: Summary
      description: What does this PR change and why?
    validations:
      required: true
  - type: input
    id: issue
    attributes:
      label: Linked issue
      description: e.g. `Closes #12`
  - type: textarea
    id: testing
    attributes:
      label: Testing performed
      description: |
        Commands run and results. CI runs ruff + pytest (Python) and
        cargo fmt / clippy / test (Rust).
    validations:
      required: true
  - type: checkboxes
    id: checklist
    attributes:
      label: PR checklist
      options:
        - label: Python: `ruff check .` and `pytest tests/` pass
        - label: Rust: `cargo fmt --all -- --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test` pass
        - label: Tests included for new/changed behaviour
        - label: Docs updated (README, PRD, etc. as applicable)
        - label: Python + Rust parity maintained (both pass the shared fixture)
