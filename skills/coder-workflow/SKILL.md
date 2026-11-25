---
name: coder-workflow
description: Follow the approved Advent Calendar plan and use test-driven development when implementing or fixing project behavior.
---

# Coder workflow

1. Read the user’s requirements, approved plan, and relevant code before editing. For new features or material design changes, discuss the concept, capture the decision and its rationale in one short plan, and get the user’s approval before writing application code.
2. Keep shipped code under `src/`, organized by responsibility. Keep tests and fixtures under `tests/`. Import Python packages by package name. Use `uv` for Python dependencies and commands, commit `uv.lock`, and run tests with `uv run --locked pytest`.
3. Work in red, green, refactor cycles. Write a focused pytest first and confirm it fails for the intended reason. Add the smallest implementation that passes, then refactor and rerun the tests. Exercise observable behavior at the normal entry points. Use fixed clocks, temporary directories, and dummy data to keep tests isolated.
4. Before delivery, run the full suite and verify the relevant user flow. Keep setup and deployment instructions in the repo, and record what passed and what still needs verification. Keep credentials and real gift content out of Git.
