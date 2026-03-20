## Summary

Build the MCP (Model Context Protocol) server that gives Claude full access to BRAIN 3.0. This is the interface that turns the database and API into a conversational partner. The MCP exposes every API endpoint as a tool Claude can call, using a thin 1:1 mapping. Claude's intelligence handles the reasoning — the MCP just provides access.

## Context

- **Scope:** Python MCP server using the Anthropic MCP SDK. One tool per API endpoint. No higher-level "smart" tools in Phase 1 — those can be added later based on real usage patterns.
- **Transport:** stdio — the MCP runs as a subprocess of the Claude client (Claude Desktop or similar). No network port exposed.
- **Reference:** [System Design Document](docs/BRAIN_3.0_Design_Document.docx) — Section 6 (MCP Tool Contract)

## Deliverables

- `mcp/` directory at project root
- `mcp/server.py` — MCP server implementation
- `mcp/requirements.txt` — MCP-specific Python dependencies
- `mcp/README.md` — Setup and configuration instructions for connecting to Claude
- Claude Desktop configuration snippet (JSON) for connecting to the MCP

## MCP Tool Mapping

Each API endpoint becomes one MCP tool. Tool names follow a `verb_entity` convention for clarity.

### Domain Tools
| Tool Name | Maps To | Description |
|-----------|---------|-------------|
| `create_domain` | `POST /api/domains` | Create a life domain |
| `list_domains` | `GET /api/domains` | List all domains |
| `get_domain` | `GET /api/domains/{id}` | Get domain with its goals |
| `update_domain` | `PATCH /api/domains/{id}` | Update a domain |
| `delete_domain` | `DELETE /api/domains/{id}` | Delete a domain |

### Goal Tools
| Tool Name | Maps To | Description |
|-----------|---------|-------------|
| `create_goal` | `POST /api/goals` | Create a goal under a domain |
| `list_goals` | `GET /api/goals` | List goals (filterable by domain, status) |
| `get_goal` | `GET /api/goals/{id}` | Get goal with its projects |
| `update_goal` | `PATCH /api/goals/{id}` | Update a goal |
| `delete_goal` | `DELETE /api/goals/{id}` | Delete a goal |

### Project Tools
| Tool Name | Maps To | Description |
|-----------|---------|-------------|
| `create_project` | `POST /api/projects` | Create a project under a goal |
| `list_projects` | `GET /api/projects` | List projects (filterable by goal, status, deadline) |
| `get_project` | `GET /api/projects/{id}` | Get project with its tasks |
| `update_project` | `PATCH /api/projects/{id}` | Update a project |
| `delete_project` | `DELETE /api/projects/{id}` | Delete a project |

### Task Tools
| Tool Name | Maps To | Description |
|-----------|---------|-------------|
| `create_task` | `POST /api/tasks` | Create a task (standalone or under a project) |
| `list_tasks` | `GET /api/tasks` | List tasks with composable filters (energy, friction, cognitive type, context, status, due date, overdue) |
| `get_task` | `GET /api/tasks/{id}` | Get task with its tags |
| `update_task` | `PATCH /api/tasks/{id}` | Update a task |
| `delete_task` | `DELETE /api/tasks/{id}` | Delete a task |

### Tag Tools
| Tool Name | Maps To | Description |
|-----------|---------|-------------|
| `create_tag` | `POST /api/tags` | Create a tag (or return existing if name matches) |
| `list_tags` | `GET /api/tags` | List all tags (searchable by name) |
| `get_tag` | `GET /api/tags/{id}` | Get a tag |
| `update_tag` | `PATCH /api/tags/{id}` | Update a tag |
| `delete_tag` | `DELETE /api/tags/{id}` | Delete a tag |
| `tag_task` | `POST /api/tasks/{id}/tags/{tag_id}` | Attach a tag to a task |
| `untag_task` | `DELETE /api/tasks/{id}/tags/{tag_id}` | Remove a tag from a task |
| `list_task_tags` | `GET /api/tasks/{id}/tags` | List tags on a task |
| `list_tagged_tasks` | `GET /api/tags/{id}/tasks` | List all tasks with a tag |

### Routine Tools
| Tool Name | Maps To | Description |
|-----------|---------|-------------|
| `create_routine` | `POST /api/routines` | Create a routine |
| `list_routines` | `GET /api/routines` | List routines (filterable by domain, status, frequency, streak_broken) |
| `get_routine` | `GET /api/routines/{id}` | Get routine with its schedules |
| `update_routine` | `PATCH /api/routines/{id}` | Update a routine |
| `delete_routine` | `DELETE /api/routines/{id}` | Delete a routine |
| `complete_routine` | `POST /api/routines/{id}/complete` | Record a routine completion with streak evaluation |
| `add_routine_schedule` | `POST /api/routines/{id}/schedules` | Add a schedule entry |
| `list_routine_schedules` | `GET /api/routines/{id}/schedules` | List schedule entries |
| `delete_routine_schedule` | `DELETE /api/routines/{id}/schedules/{schedule_id}` | Remove a schedule entry |

### Check-in Tools
| Tool Name | Maps To | Description |
|-----------|---------|-------------|
| `create_checkin` | `POST /api/checkins` | Log a state check-in |
| `list_checkins` | `GET /api/checkins` | List check-ins (filterable by type, context, date range) |
| `get_checkin` | `GET /api/checkins/{id}` | Get a check-in |
| `update_checkin` | `PATCH /api/checkins/{id}` | Update a check-in |
| `delete_checkin` | `DELETE /api/checkins/{id}` | Delete a check-in |

### Activity Log Tools
| Tool Name | Maps To | Description |
|-----------|---------|-------------|
| `log_activity` | `POST /api/activity` | Create an activity log entry |
| `list_activity` | `GET /api/activity` | List activity entries (filterable by action type, task, routine, date range) |
| `get_activity` | `GET /api/activity/{id}` | Get activity entry with resolved references |
| `update_activity` | `PATCH /api/activity/{id}` | Update an activity entry |
| `delete_activity` | `DELETE /api/activity/{id}` | Delete an activity entry |

### Reporting Tools
| Tool Name | Maps To | Description |
|-----------|---------|-------------|
| `get_activity_summary` | `GET /api/reports/activity-summary` | Aggregated activity stats for a date range |
| `get_domain_balance` | `GET /api/reports/domain-balance` | Per-domain item counts and recency |
| `get_routine_adherence` | `GET /api/reports/routine-adherence` | Per-routine completion rates and streak health |
| `get_friction_analysis` | `GET /api/reports/friction-analysis` | Predicted vs actual friction by cognitive type |

## Tool Schema Design

Each tool should include:
- **Clear description** — written for Claude, explaining when and why to use this tool. E.g. `list_tasks` description: "List tasks with composable filters. Use to find tasks matching the user's current energy, context, or cognitive capacity. All filter parameters are optional and combine with AND logic."
- **Typed parameters** — matching the API's Pydantic schemas. Required vs optional should match the API.
- **Return type** — JSON matching the API response schemas.

Tool descriptions matter because they're what Claude reads to decide which tool to use. Write them as guidance for a partner, not as dry API docs.

## Acceptance Criteria

- [ ] MCP server starts and connects via stdio transport
- [ ] All API endpoints are exposed as MCP tools (see mapping table above)
- [ ] Tool parameters match the API's Pydantic schemas (types, required/optional)
- [ ] Tool descriptions are clear and guide Claude on when to use each tool
- [ ] MCP correctly forwards requests to the FastAPI API and returns responses
- [ ] MCP handles API errors gracefully (returns meaningful error messages, doesn't crash)
- [ ] MCP handles API being unreachable (clear error message)
- [ ] `mcp/README.md` documents: how to install dependencies, how to start the server, how to configure Claude Desktop
- [ ] Claude Desktop configuration snippet provided and tested
- [ ] Verified end-to-end: Claude can create a domain, add a goal, create a task, complete it, and log activity — all through conversation
- [ ] Health check tool works (`GET /health`) confirming API connectivity

## Technical Notes

- Use the Anthropic Python MCP SDK (`mcp` package)
- The MCP server communicates with the FastAPI API over localhost HTTP. The API URL should be configurable (default `http://localhost:8000`)
- stdio transport means the MCP runs as a subprocess — no ports to manage, no network exposure
- Tool parameter schemas can be derived from the FastAPI OpenAPI spec, but manual definition is fine for Phase 1 — keeps it explicit and allows better descriptions
- Consider a simple `config.json` or environment variable for the API base URL
- Error handling should distinguish between: API returned an error (pass through the message), API unreachable (connection error), and invalid tool parameters (validation error)
- The MCP server should be stateless — all state lives in the API/database

## Security Notes

- stdio transport: no network port exposed, only the local Claude client can connect
- Phase 1: API runs without auth behind the firewall. MCP connects directly.
- Phase 3: when auth is added to the API, the MCP will need to send an API key with requests. Design the HTTP client layer so adding an `Authorization` header is a one-line change.

## Dependencies

- Ticket #2 (FastAPI running with health endpoint)
- Tickets #4-10 (all API endpoints the MCP needs to expose)
