## Summary

Set up a GitHub Actions CI workflow that automatically runs tests and linting on every pull request to `develop`. This gives the code reviewer (you) an automated green/red signal before reviewing Claude Code's PRs.

## Context

- **Scope:** GitHub Actions workflow file only. No new application code. Runs against the existing pytest setup from ticket #2.
- **Trigger:** Ticket #2 (FastAPI scaffolding) is complete, so there are testable endpoints and a pytest configuration to validate against.
- **Purpose:** Every future PR from Claude Code gets automatic test and lint validation. You see a green checkmark or red X on the PR before you review.

## Deliverables

- `.github/workflows/ci.yml` — GitHub Actions workflow file

## Workflow Design

### Trigger
- Runs on every pull request targeting `develop`
- Runs on every push to `develop` (catches anything that slips through)

### Jobs

**1. Test**
- Spin up a PostgreSQL 16 service container (GitHub Actions supports this natively)
- Install Python 3.12
- Install dependencies from `requirements.txt`
- Run Alembic migrations against the test database
- Run `pytest -v` and report results

**2. Lint**
- Install Python 3.12
- Install Ruff (fast Python linter, modern replacement for Pylint + flake8)
- Run `ruff check .` against the codebase
- Fail the workflow if lint errors are found

### Environment
- PostgreSQL service container uses test credentials (not the dev `.env` — hardcoded test values in the workflow)
- Test database is ephemeral — created fresh for each workflow run, destroyed after

## Acceptance Criteria

- [ ] `.github/workflows/ci.yml` exists and is valid
- [ ] Workflow triggers on PRs to `develop` and pushes to `develop`
- [ ] Test job spins up PostgreSQL 16 service container
- [ ] Test job installs Python 3.12 and project dependencies
- [ ] Test job runs `pytest -v` and reports pass/fail
- [ ] Lint job runs Ruff and reports pass/fail
- [ ] Both jobs must pass for the workflow to show green
- [ ] Workflow runs successfully on the current codebase (all existing tests pass, no lint errors)
- [ ] Ruff configuration added (either `pyproject.toml` section or `ruff.toml`) with line length set to 100 to match project standards

## Technical Notes

- Use Ruff over Pylint — it's faster, configured in a single file, and covers both linting and formatting checks
- The PostgreSQL service container in GitHub Actions is straightforward: define it under `services` in the job, set environment variables, and it's available at `localhost:5432`
- Consider caching pip dependencies to speed up workflow runs (`actions/cache` or `setup-python` built-in caching)
- The workflow should be fast — under 2 minutes ideally. Slow CI discourages frequent PRs.
- Add `ruff` to `requirements.txt` or a separate `requirements-dev.txt` for development dependencies

## Dependencies

- Ticket #2 (FastAPI scaffolding with health endpoint and pytest configuration)
