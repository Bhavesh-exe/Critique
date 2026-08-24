# GEMINI.md — Critique Workspace Rules & Workflow Directives

> **Scope**: Applied automatically to all Antigravity agent interactions in this repository.

---

## 🔁 Mandatory Workflow Protocols

### 1. Task Initialization Protocol (Before Starting Work)
- **Always read `wid.md` and `flow.md`** at the start of any new task, plan, or investigation.
  - Check `wid.md` to understand what features and milestones have already been built and verified.
  - Check `flow.md` to align with the existing architecture, data flow, formulas, and platform contracts.
- Do not make assumptions or reinvent components that are already documented in `wid.md` and `flow.md`.

---

### 2. Task Completion Protocol (Before Finishing Work)
- **Always update `wid.md` and `flow.md`** before concluding any task:
  - **`wid.md`**: Add any new features, bug fixes, refactorings, or modifications made during the turn.
  - **`flow.md`**: Update if any component flow, API lifecycle, mathematical calculation, or UI state interaction was modified or added.
- Keep both files accurate, cleanly formatted, and up to date at all times.

---

## 🔒 Core Development Guidelines

1. **Git Isolation**:
   - The user's home directory contains an unrelated git repository. **NEVER** run git commands from the parent directory.
   - Any git operations must strictly remain inside the `critique/` project root.

2. **Clean & Minimal Code**:
   - Adhere to the single `TasteProfile` contract in `critique/models.py`.
   - New platforms must only implement a `BaseFetcher` in `critique/fetchers/` and register in `__init__.py`.
   - Avoid unnecessary dependencies or overcomplicating simple features.

3. **Verification**:
   - Verify code using Python syntax compilation (`compileall` / `py_compile`) and test scripts before concluding tasks.
