# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

This is a freshly-scaffolded `uv` Python project. It currently contains only the stub entrypoint `main.py` (prints a hello message), an empty `README.md`, and no declared dependencies or source package. There is no application architecture yet — treat early work here as greenfield.

## Tooling

- Package/environment manager: **`uv`** (do not use `pip`/`venv` directly; the `.venv/` is uv-managed).
- Python: **3.14+** (pinned by `.python-version`; enforced by `requires-python` in `pyproject.toml`).

## Commands

```bash
uv sync                 # create/update .venv from pyproject.toml + uv.lock
uv run main.py          # run the entrypoint
uv add <pkg>            # add a runtime dependency (updates pyproject.toml + uv.lock)
uv add --dev <pkg>      # add a dev-only dependency
uv run python -c "..."  # run arbitrary Python inside the project env
```

No test, lint, or build tooling is configured yet. When adding tests, install and run via `uv` (e.g. `uv add --dev pytest` then `uv run pytest`, single test: `uv run pytest path::test_name`).

## ArmorClaude policy enforcement

This repo runs under **ArmorClaude intent enforcement** (a SessionStart/UserPromptSubmit hook). Before making any tool call, you must register an intent plan via `register_intent_plan` (already allow-listed in `.claude/settings.local.json`). If the plan changes materially mid-task, re-anchor it with `trust_reanchor`. Tool calls without a registered plan are blocked.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/001-eol-trait-query/plan.md` (EOL Trait Query Service). Supporting design
artifacts: `research.md`, `data-model.md`, `contracts/`, and `quickstart.md` in the
same feature directory; project principles in `.specify/memory/constitution.md`.
<!-- SPECKIT END -->
