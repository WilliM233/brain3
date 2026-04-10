# Development Guide

A summary of how development works on BRAIN 3.0. This page covers the workflow, conventions, and key references. For the full developer setup (from clone to running API), see [docs/dev-setup.md](../dev-setup.md). For the authoritative coding standards and project structure, see [CLAUDE.md](../../CLAUDE.md).

---

## Git Workflow

### Branching Strategy

```
main          ← production deploys only
  └── develop ← integration branch, all features merge here
        └── feature/TICKET-XX-short-description
```

- Never commit directly to `main` or `develop`
- One branch per ticket, branched from `develop`
- PRs target `develop`
- `main` is updated from `develop` only for deployment milestones

### Branch Naming

- Features: `feature/TICKET-XX-short-description`
- Documentation: `docs/short-description`

### Commit Messages

[Conventional Commits](https://www.conventionalcommits.org/) with ticket reference:

```
type(scope): description (#XX)
```

**Types:** `feat`, `fix`, `docs`, `test`, `chore`, `refactor`

**Examples:**
```
feat(api): add domain CRUD endpoints (#4)
fix(db): correct cascade delete on projects (#5)
docs: rewrite README with architecture overview
test(api): add composable filter tests for tasks (#5)
```

Commits should be atomic — one logical change per commit.

---

## Pull Request Process

1. Ensure all tests pass (`pytest -v`) and lint is clean (`ruff check .`)
2. Push your feature branch and open a PR targeting `develop`
3. Title format: `TICKET-XX: Short description`
4. Fill out **every section** of the PR template:

| Section | What Goes There |
|---------|----------------|
| **Summary** | What was built, in plain language |
| **Changes** | Files created/modified and why |
| **How to Verify** | Step-by-step verification instructions |
| **Deviations** | Anything that differs from the ticket spec (or "None") |
| **Test Results** | Confirmation that tests pass, with output |
| **Acceptance Checklist** | Criteria from the ticket, checked off |

The **Deviations** section matters. If you deviated from the spec — even for good reasons — document it. Undocumented deviations create confusion during review.

---

## Ticket Workflow

Work is organized through GitHub issues with detailed ticket specs in `docs/tickets/`.

1. Read the ticket spec before starting work
2. Create a feature branch from `develop`
3. If anything in the ticket is ambiguous, ask — don't guess
4. If you find a bug or issue outside the current ticket's scope, **file a GitHub issue** rather than fixing it inline
5. Open a PR when complete, linking to the issue with `Closes #XX`

---

## Testing

Tests use an in-memory SQLite database — no external dependencies needed.

```bash
pytest -v              # Full suite
pytest tests/test_tasks.py -v   # Single file
ruff check .           # Lint
```

**CI runs both** on every push and PR to `develop`. Both must pass.

### Testing Standards

- Every API endpoint gets: happy path, validation, not found (404), and filter tests
- Tests must be independent — each creates its own data
- Use the helper fixtures in `tests/conftest.py` (`make_domain`, `make_goal`, `make_task`, `make_artifact`, `make_protocol`, `make_directive`, `make_skill`, etc.)

---

## Code Standards

| Standard | Rule |
|----------|------|
| Style | PEP 8 |
| Type hints | Required on all function signatures |
| Line length | 100 characters max |
| Strings | f-strings over `.format()` or `%` |
| Paths | `pathlib` over `os.path` |
| ORM style | SQLAlchemy 2.0 (`DeclarativeBase`, `Mapped`, `mapped_column`) |
| Schemas | Pydantic 2.x with `model_config = {"from_attributes": True}` |

---

## Key References

| Resource | What It Covers |
|----------|---------------|
| [CLAUDE.md](../../CLAUDE.md) | Full developer guide — project structure, conventions, design decisions |
| [docs/dev-setup.md](../dev-setup.md) | Prerequisites, clone, configure, start, test, troubleshoot |
| [docs/deployment.md](../deployment.md) | Production deployment on TrueNAS |
| [docs/environment-variables.md](../environment-variables.md) | Every env var documented |
| [System Design Document](../BRAIN_3_0_Design_Document.md) | Architecture, data model, schema, design philosophy |
