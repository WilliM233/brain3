\# BRAIN 3.0 — Release Playbook

\### Project Flux Meridian · Release Division · Version 1.0



\---



> This is a living document. Each release cycle may refine it. 

> The version number on this playbook should match the release it guided.

> When in doubt: gates are real, issues are logged, humans sign off.



\---



\## How to Use This Document



This playbook runs the BRAIN 3.0 release cycle from hardening through deployment.

Each phase has a clear owner, a gate condition that must be satisfied before proceeding,

and a set of tasks with checkboxes. Nothing moves forward until the gate is met.



\*\*Roles referenced:\*\*

\- \*\*L\*\* — The human. Product owner and final decision-maker.

\- \*\*Desmond Ops\*\* — DevOps / Implementation. Claude Code session.

\- \*\*Quincy Assurance\*\* — QA Engineer. Fresh Claude Code session, cold context.

\- \*\*Seraphina Lock\*\* — Security Reviewer. Fresh Claude Code session, cold context.

\- \*\*Wilhelmina Prose\*\* — Technical Writer. Fresh Claude Code session.

\- \*\*Apollo Swagger\*\* — API Documentation Specialist. Fresh Claude Code session.

\- \*\*Regina Meridian\*\* — Release Manager. Fresh Claude Code session.



\*\*Fresh context matters.\*\* QA and Security agents must be started in new sessions

with no memory of the implementation. Cold context finds what warm context misses.



\---



\## Phase 0 — Pre-Hardening Gate

\*\*Owner:\*\* L  

\*\*Gate condition:\*\* All feature tickets merged to `develop`, CI passing, Docker stack running clean.



This phase is L's responsibility. Before any specialist agent activates,

the codebase must be in a stable, integrated state.



\### Checklist



\- \[ ] All tickets (01–12) have merged PRs into `develop`

\- \[ ] No open feature branches with unmerged work

\- \[ ] GitHub Actions CI is green on `develop`

\- \[ ] `docker compose -f docker-compose.dev.yml up -d` starts without errors

\- \[ ] `GET /health` returns `{"status": "healthy", "database": "connected"}`

\- \[ ] FastAPI `/docs` loads and shows all expected endpoints

\- \[ ] Alembic migrations run cleanly from scratch: `alembic upgrade head`

\- \[ ] No `.env` credentials committed to the repository



\*\*Gate:\*\* All boxes checked → proceed to Phase 1.  

\*\*If blocked:\*\* Resolve issues before activating any specialist agents.



\---



\## Phase 1 — QA \& Hardening

\*\*Owner:\*\* Quincy Assurance (fresh Claude Code session)  

\*\*Gate condition:\*\* Phase 0 complete.  

\*\*Deliverables:\*\* GitHub issues filed, QA summary report.



\### Briefing Quincy



Start a new Claude Code session in the `brain3/` directory.

Provide Quincy's brief (see `docs/briefs/QA\_BRIEF.md`).

Quincy reviews the integrated codebase cold — no prior context.



\### Quincy's Scope



\- \[ ] Pattern consistency — all routers and schemas follow ticket #4 conventions

\- \[ ] Acceptance criteria — verify each ticket's criteria is actually implemented

\- \[ ] Composable filters — test task filter combinations manually

\- \[ ] Edge cases — overdue filter, standalone tasks, streak logic, range queries

\- \[ ] Error handling — invalid UUIDs return 404, invalid values return 400

\- \[ ] Test coverage — pytest suite exists and passes per CLAUDE.md standards

\- \[ ] Response schemas — actual responses match defined Pydantic schemas

\- \[ ] Cascade behavior — deleting a domain cascades correctly through the hierarchy



\### Issue Filing Rules



Every finding gets a GitHub issue. No exceptions. No inline fixes.  

Quincy uses the standard issue format from `docs/templates/ISSUE\_TEMPLATE.md`.



Severity classification:

\- \*\*Blocker\*\* — release cannot proceed until resolved

\- \*\*Major\*\* — address before release if possible

\- \*\*Minor\*\* — log for next cycle

\- \*\*Cosmetic\*\* — log, address when convenient



\### Deliverable



Quincy produces a QA Summary Report filed as a GitHub issue labeled `qa-report`:



```markdown

\## QA Summary Report — vX.X.X Hardening



\*\*Date:\*\* YYYY-MM-DD

\*\*Tickets reviewed:\*\* 01–12

\*\*Total findings:\*\* X (B: X, Maj: X, Min: X, Cos: X)



\### Blockers

\- Issue #XX — \[title]



\### Majors  

\- Issue #XX — \[title]



\### Minors \& Cosmetics

\- Issue #XX — \[title]



\### Assessment

\[One paragraph: overall code quality, patterns followed, readiness for release pending blockers.]

```



\*\*Gate:\*\* QA Summary Report filed → proceed to Phase 1b.



\---



\## Phase 1b — Security Review

\*\*Owner:\*\* Seraphina Lock (fresh Claude Code session)  

\*\*Gate condition:\*\* Phase 1 complete.  

\*\*Deliverables:\*\* Security report, GitHub issues filed.



\### Briefing Seraphina



Start a new Claude Code session. Provide Seraphina's brief (see `docs/briefs/SECURITY\_BRIEF.md`).



\### Seraphina's Scope



\- \[ ] Input validation on all endpoints — no unvalidated user input reaches the database

\- \[ ] SQL injection surface — ORM usage is correct, no raw query construction from user input

\- \[ ] Environment variables — no secrets in code, `.env.example` is clean

\- \[ ] CORS configuration — permissive for dev, documented restriction path for production

\- \[ ] Docker — PostgreSQL not exposed to host network in production config

\- \[ ] Auth readiness — middleware pattern is in place and ready for Phase 3 addition

\- \[ ] Dependency audit — no known vulnerable packages in `requirements.txt`

\- \[ ] `.gitignore` — `.env` files are ignored, no secrets in git history



\### Note on Phase 1 Auth Deferral



Authentication is intentionally deferred to Phase 3. Seraphina is not expected

to flag the absence of auth as a blocker — it is a known and accepted design decision.

She is expected to flag anything that would make adding auth in Phase 3 harder,

or anything that creates unnecessary exposure in the current firewall-only security model.



\*\*Gate:\*\* Security report filed, no unaddressed blockers → proceed to Phase 2.



\---



\## Phase 2 — Bug Resolution

\*\*Owner:\*\* Desmond Ops (Claude Code session in `brain3/`)  

\*\*Gate condition:\*\* QA and Security reports filed, blockers identified.  

\*\*Deliverables:\*\* Blocker issues resolved, PRs merged to `develop`.



\### Process



Desmond works through GitHub issues in severity order: Blockers first, then Majors.

Each fix gets its own feature branch and PR. No bundling multiple fixes in one PR.



Branch format: `fix/issue-XX-short-description`



\- \[ ] All Blocker issues resolved and merged to `develop`

\- \[ ] Major issues addressed where feasible

\- \[ ] Minor and Cosmetic issues labeled for next cycle — do not attempt to close them all

\- \[ ] CI passes on `develop` after all fixes are merged

\- \[ ] Health check still passes after fixes



\*\*Gate:\*\* No open Blockers, CI green → proceed to Phase 3.



\---



\## Phase 3 — Technical Writing

\*\*Owner:\*\* Wilhelmina Prose (fresh Claude Code session)  

\*\*Gate condition:\*\* No open Blockers, codebase stable.  

\*\*Deliverables:\*\* Updated README, installation guide, GitHub Wiki pages.



\### Briefing Wilhelmina



Start a new Claude Code session. Provide Wilhelmina's brief (see `docs/briefs/WRITING\_BRIEF.md`).

Provide access to: current README, design document, all ticket specs, CLAUDE.md.



\### Wilhelmina's Scope



\- \[ ] README updated — architecture overview, tech stack, quick start, project status

\- \[ ] Installation guide — `docs/dev-setup.md` covers prerequisites, setup, start/stop, reset

\- \[ ] Deployment guide — based on ticket 12 outcomes, covers TrueNAS setup end to end

\- \[ ] Environment variable reference — every variable documented with type and description

\- \[ ] Contributor guide — how to work on the project, based on CLAUDE.md

\- \[ ] GitHub Wiki — at minimum: Home, Architecture, Setup, API Overview, MCP Setup

\- \[ ] All documents versioned and dated



\*\*Gate:\*\* Documentation complete, reviewed by L → proceed to Phase 3b.



\---



\## Phase 3b — API Documentation

\*\*Owner:\*\* Apollo Swagger (fresh Claude Code session)  

\*\*Gate condition:\*\* Phase 3 complete.  

\*\*Deliverables:\*\* API reference document, MCP tool guide.



\### Briefing Apollo



Start a new Claude Code session. Provide Apollo's brief (see `docs/briefs/API\_DOC\_BRIEF.md`).

Provide access to: all routers, all schemas, MCP ticket spec, design document section 6.



\### Apollo's Scope



\- \[ ] Every API endpoint documented: method, path, parameters, request body, response schema, example

\- \[ ] All query filter parameters documented with types and behavior descriptions

\- \[ ] OpenAPI spec verified against actual implementation — flag any mismatches

\- \[ ] MCP tool guide — every tool Claude can call, with parameters, examples, expected responses

\- \[ ] Integration guide — how to connect `brain3-mcp` to a running BRAIN 3.0 instance

\- \[ ] Composable query patterns documented — the "recipes" Claude uses most



\*\*Gate:\*\* API reference and MCP guide complete, reviewed by L → proceed to Phase 4.



\---



\## Phase 4 — Release Preparation

\*\*Owner:\*\* Desmond Ops + Regina Meridian  

\*\*Gate condition:\*\* All documentation complete, CI passing on `develop`.  

\*\*Deliverables:\*\* CI workflow validated, version tag ready, release notes drafted.



\### Desmond's Tasks



\- \[ ] GitHub Actions CI workflow (ticket 13) validated end to end on `develop`

\- \[ ] `scripts/smoke-test.sh` runs successfully against local stack

\- \[ ] `scripts/backup.sh` runs successfully and produces a backup file

\- \[ ] `docker-compose.prod.yml` tested — both containers start, migrations run, health check passes

\- \[ ] Semantic version confirmed: `v1.0.0`



\### Regina's Tasks



\- \[ ] All Blocker and Major issues from QA/Security are closed

\- \[ ] CI is green on `develop`

\- \[ ] Release notes drafted from closed GitHub issues — format:



```markdown

\## BRAIN 3.0 — v1.0.0



\*\*Release date:\*\* YYYY-MM-DD



\### What's included

\[Plain language summary of what Phase 1 delivers]



\### Endpoints delivered

\[List of API endpoint groups]



\### Infrastructure

\[Docker setup, Alembic migrations, CI workflow, backup scripts]



\### Known limitations

\[Anything deferred to Phase 2 or Phase 3 — auth, scheduler, UI]



\### Deployment

See `docs/deployment.md` for full TrueNAS deployment instructions.

```



\*\*Gate:\*\* Desmond and Regina both sign off → proceed to Phase 5.



\---



\## Phase 5 — Human Testing

\*\*Owner:\*\* L  

\*\*Gate condition:\*\* Phase 4 complete, release notes drafted.  

\*\*Deliverables:\*\* Smoke test results, final sign-off.



This is the most important gate. L tests the system as a real user,

not as a developer looking for bugs.



\### Checklist



\- \[ ] Run `scripts/smoke-test.sh` — all steps pass

\- \[ ] Create a real Domain, Goal, Project, and Task through the API

\- \[ ] Complete a Task and verify activity log entry

\- \[ ] Log a State Check-in

\- \[ ] Verify `GET /api/reports/activity-summary` returns meaningful data

\- \[ ] Connect `brain3-mcp` and verify Claude can query tasks through conversation

\- \[ ] Ask Claude "what tasks do I have?" and verify the response is accurate

\- \[ ] Verify backup script runs and produces a file

\- \[ ] Confirm deployment docs are accurate — could a stranger follow them?



\### Sign-off



When L is satisfied:



> "Approved for release. v1.0.0 is ready."



\*\*Gate:\*\* L sign-off received → proceed to Phase 6.



\---



\## Phase 6 — Official Release

\*\*Owner:\*\* Regina Meridian  

\*\*Gate condition:\*\* L sign-off received.  

\*\*Deliverables:\*\* `develop` → `main` merged, `v1.0.0` tag created, GitHub release published.



\### Regina's Release Steps



\- \[ ] Open PR: `develop` → `main`, title: `Release: BRAIN 3.0 v1.0.0`

\- \[ ] PR description includes full release notes

\- \[ ] CI passes on the PR

\- \[ ] L approves the PR (final human gate)

\- \[ ] Merge PR to `main`

\- \[ ] Create git tag: `git tag -a v1.0.0 -m "BRAIN 3.0 Phase 1 — The Core Loop"`

\- \[ ] Push tag: `git push origin v1.0.0`

\- \[ ] Publish GitHub release with release notes attached

\- \[ ] Verify the release appears on the GitHub releases page



\*\*Gate:\*\* GitHub release published → proceed to Phase 7.



\---



\## Phase 7 — TrueNAS Deployment

\*\*Owner:\*\* Desmond Ops + L  

\*\*Gate condition:\*\* v1.0.0 published on GitHub.  

\*\*Deliverables:\*\* BRAIN 3.0 running live on TrueNAS.



\### Deployment Steps



Follow `docs/deployment.md` exactly. If the docs are wrong, fix the docs first,

then proceed. The deployment guide is the source of truth.



\- \[ ] Pull `v1.0.0` release onto TrueNAS

\- \[ ] Create production `.env` from `.env.production.example`

\- \[ ] `docker compose -f docker-compose.prod.yml up -d`

\- \[ ] Verify both containers are healthy: `docker compose ps`

\- \[ ] `GET /health` returns healthy from TrueNAS IP

\- \[ ] Run smoke test against TrueNAS: `scripts/smoke-test.sh http://TRUENAS\_IP:8000`

\- \[ ] Verify MCP connects to TrueNAS instance from client machine

\- \[ ] Confirm backup cron job is scheduled in TrueNAS UI

\- \[ ] Run backup manually and verify file appears in backup path



\### Final Confirmation



> BRAIN 3.0 v1.0.0 is live. The Core Loop is complete.



\---



\## Appendix A — Phase Summary



| Phase | Name | Owner | Gate In | Gate Out |

|-------|------|-------|---------|----------|

| 0 | Pre-Hardening | L | Tickets merged | CI green, stack healthy |

| 1 | QA \& Hardening | Quincy | Phase 0 | QA report filed |

| 1b | Security Review | Seraphina | Phase 1 | Security report filed |

| 2 | Bug Resolution | Desmond | Reports filed | No open blockers |

| 3 | Technical Writing | Wilhelmina | No blockers | Docs complete |

| 3b | API Documentation | Apollo | Phase 3 | API + MCP guide complete |

| 4 | Release Prep | Desmond + Regina | Docs done | Notes drafted, CI green |

| 5 | Human Testing | L | Phase 4 | L sign-off |

| 6 | Official Release | Regina | L sign-off | v1.0.0 published |

| 7 | Deployment | Desmond + L | v1.0.0 tagged | Live on TrueNAS |



\---



\## Appendix B — Quick Reference: When to Involve Which Agent



| Situation | Who |

|-----------|-----|

| Feature ticket implementation | Desmond |

| Bug fix from QA report | Desmond |

| Code review / quality audit | Quincy (fresh session) |

| Security review | Seraphina (fresh session) |

| README / wiki / install guide | Wilhelmina (fresh session) |

| API endpoint documentation | Apollo (fresh session) |

| CI setup / deployment config | Desmond |

| Release gate decisions | Regina |

| Any final decision | L |



\---



\*BRAIN 3.0 Release Playbook · Version 1.0\*  

\*Project Flux Meridian · L Melton · March 2026\*

