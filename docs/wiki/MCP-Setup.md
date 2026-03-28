# MCP Setup

BRAIN 3.0's primary interface is Claude, connected through the **Model Context Protocol (MCP)**. The MCP gives Claude full read/write access to the BRAIN 3.0 API — every CRUD operation, every filter, every report. This is where the partner relationship lives.

---

## How It Works

The MCP server is a separate application ([brain3-mcp](https://github.com/WilliM233/brain3-mcp)) that runs as a Claude subprocess on your local machine. It translates Claude's tool calls into HTTP requests against the BRAIN 3.0 API.

```
Claude Desktop  →  brain3-mcp (local subprocess)  →  BRAIN 3.0 API (localhost or TrueNAS)
```

The MCP server does not store data — it's a translation layer. All state lives in the BRAIN 3.0 database, accessed through the API.

## What Claude Can Do

With the MCP connected, Claude has access to:

- **Full CRUD** on all seven pillar entities — create, read, update, delete domains, goals, projects, tasks, routines, check-ins, and activity log entries
- **Filtered queries** — find tasks by energy level, cognitive type, context, due date, and more
- **Tag management** — create tags, attach/detach them from tasks, query tasks by tag
- **Routine management** — complete routines, manage schedules, track streaks
- **Reporting** — activity summaries, domain balance, routine adherence, friction analysis
- **Health check** — verify the API and database are connected

This gives Claude enough context to act as a partner: reasoning about priorities, noticing neglected areas, matching tasks to current capacity, and surfacing patterns from the activity log.

---

## Setup

### Prerequisites

- BRAIN 3.0 API running and accessible (see [Deployment Guide](../deployment.md) or [Dev Setup](../dev-setup.md))
- Python 3.12+ on your local machine
- Claude Desktop (or Claude Code)

### 1. Clone the MCP server

```bash
git clone https://github.com/WilliM233/brain3-mcp.git
cd brain3-mcp
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Claude Desktop

Add the MCP server to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "brain3": {
      "command": "python",
      "args": ["/path/to/brain3-mcp/mcp/server.py"],
      "env": {
        "BRAIN3_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

If your API is running on TrueNAS or another server, replace `localhost:8000` with the server's IP and port:

```json
"BRAIN3_API_URL": "http://192.168.1.100:8000"
```

### 4. Verify

Restart Claude Desktop, then ask Claude to run the `health_check` tool. If it reports healthy, the connection is working.

---

## Troubleshooting

**Claude doesn't see the BRAIN 3.0 tools:**
- Is the MCP server configured in Claude Desktop's settings? Check the config file path.
- Did you restart Claude Desktop after adding the configuration?

**Health check fails:**
- Is the BRAIN 3.0 API running? `curl http://localhost:8000/health`
- Is `BRAIN3_API_URL` set correctly? It must include the protocol (`http://`) and port.
- If the API is on another machine, is port 8000 open and reachable from your local network?

**MCP server crashes on startup:**
- Check that Python 3.12+ is installed and the dependencies are installed.
- Check the path to `server.py` in your configuration.

---

For full MCP server documentation, see the [brain3-mcp repository](https://github.com/WilliM233/brain3-mcp).
