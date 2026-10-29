# FAIA

FAIA is an agent-first discovery service for finding tools, MCP servers, providers, and capabilities. Agents connect to FAIA over MCP to search the catalog and register local tool metadata. FAIA describes tools; it does **not** run registered code or proxy tool calls.

## What FAIA does

- **Built-in discovery:** Search a curated catalog of tool repositories, providers, and capabilities.
- **Agent connection:** Expose discovery through the Model Context Protocol (MCP), using standard input/output by default or Streamable HTTP when needed.
- **Local registration:** Save tool names, descriptions, input schemas, providers, and documentation links in a local registry.
- **Existing REST API:** Keep using the HTTP API for search, repository/provider details, health, and schema information.

Registered tools are metadata, not executable MCP tools. Agents use FAIA to discover a tool, then connect to that tool through its own provider. FAIA does not validate provider behavior or grant access to provider credentials.

## Quick start

Requires Python 3.10 or later.

```powershell
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS/Linux: use `source .venv/bin/activate` instead
python -m pip install -r requirements.txt
```

### Connect an MCP-compatible agent

The MCP host starts FAIA as a child process using the config below; you normally do not start a separate stdio server yourself. To check the command manually, run:

```powershell
python mcp_server.py
```

The server exposes four MCP tools:

| MCP tool | Purpose |
| --- | --- |
| `search_tools` | Search the built-in catalog and local registrations |
| `register_tool` | Store a tool's metadata and JSON Schema input definition |
| `list_registered_tools` | List locally registered metadata |
| `remove_registered_tool` | Remove a local registration |

For an MCP client that accepts a `mcpServers` configuration, point it at the Python interpreter and this repository's `mcp_server.py`:

```json
{
  "mcpServers": {
    "faia": {
      "command": "C:\\path\\to\\FAIA\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\FAIA\\mcp_server.py"],
      "env": {
        "FAIA_TOOL_REGISTRY": "C:\\path\\to\\FAIA\\.faia\\registered_tools.json"
      }
    }
  }
}
```

The registry is stored at `.faia/registered_tools.json` in the project by default. Set `FAIA_TOOL_REGISTRY` to use another path. The file is created the first time a tool is registered.

Example registration input:

```json
{
  "name": "lookup_customer",
  "description": "Look up a customer in the team's CRM.",
  "provider": "Example CRM",
  "documentation_url": "https://example.com/api",
  "input_schema": {
    "type": "object",
    "properties": {
      "customer_id": {
        "type": "string",
        "description": "Customer identifier"
      }
    },
    "required": ["customer_id"]
  }
}
```

Call the MCP `register_tool` tool with the object above. Registration is local to this FAIA installation. Names must be unique (case-insensitive); remove an existing entry before registering a replacement. Input schemas must be JSON Schema objects and are limited to 64 KiB. No executable code, credentials, or provider calls are stored.

### Use the REST API

In another terminal:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the interactive API reference. Useful routes include:

- `POST /search` with `{"query": "workflow automation"}`
- `GET /repository/{repository_id}`
- `GET /provider/{provider_id}`
- `GET /health` and `GET /version`

### Run MCP over HTTP

```powershell
python mcp_server.py --transport streamable-http --host 127.0.0.1 --port 8001
```

The MCP endpoint is `http://127.0.0.1:8001/mcp`. Both servers bind to loopback by default. Do not expose either service directly to an untrusted network; place it behind appropriate authentication and network controls before allowing remote access.

## Host on Render

`render.yaml` defines separate REST API and MCP web services. The MCP service
uses a persistent disk for its local metadata registry. Deploy the Blueprint
from the repository in Render after pushing the project to GitHub.

Both services require `FAIA_AUTH_TOKEN` when deployed. Set the **same random
secret** on both services in Render's environment settings. Generate one locally:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep the value private; do not commit it. The API and MCP services require
`Authorization: Bearer <token>` on requests, except their minimal `/health`
checks, which Render needs to access without credentials. REST API routes such
as `/docs` are also protected. Configure `FAIA_CORS_ORIGINS` on the API service
as a comma-separated list if a browser frontend needs cross-origin access.

After deployment, the endpoints are:

- REST API: `https://<faia-api-service>.onrender.com`
- MCP: `https://<faia-mcp-service>.onrender.com/mcp`

Configure remote MCP clients to send the same bearer token in the HTTP
`Authorization` header. This shared-token setup is suitable for a trusted
initial deployment; for multiple independent users, put the services behind an
OAuth-capable identity gateway before sharing them broadly. Anyone holding the
shared token can search and modify the MCP metadata registry.

Render hosting and its persistent disk may incur charges. The deployment
configuration does not create a Render account or deploy services; complete the
Blueprint setup and set the secret in the Render dashboard.

## Refreshing the built-in catalog

The checked-in `catalog_output/` files are the runtime index. To rebuild them from upstream MCP/tool repositories, run these steps from the FAIA directory:

```powershell
python ingestion.py --seed-file data/seed_repositories.json
python capability_catalog.py
python provider_intelligence.py
python repository_index_builder.py
python repository_resolver.py --run-tests
```

Ingestion fetches public repository metadata and candidate files over the network; it can be slow or rate-limited. It writes generated datasets and reports under `data/`, including `data/validated_tools.json`. The remaining steps overwrite generated files under `catalog_output/`. Review the generated diff and reports before committing a catalog refresh. To test the ingestion pipeline without network access, use `python ingestion.py --offline-demo`; this overwrites the same ingestion output files with demo data, so do not run it over data you need to keep.

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

To run the existing resolver regression suite:

```powershell
python repository_resolver.py --run-tests
```

Manual API and resolver diagnostics live in `scripts/` and are intentionally not
collected as automated tests. Run them from the repository root with, for example,
`python -m scripts.discovery_smoke` (start the REST API first for API smoke checks).

For contribution guidance, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Project layout

- `api.py` — existing REST API
- `mcp_server.py` — MCP discovery and registration interface
- `tool_registry.py` — validated, atomic local metadata persistence
- `repository_resolver.py`, `search_engine.py`, `engine.py` — built-in discovery pipeline
- `ingestion.py`, `capability_catalog.py`, `provider_intelligence.py`, `repository_index_builder.py` — catalog refresh pipeline
- `catalog_output/` — generated catalog artifacts required by the runtime
- `data/` — ingestion seed data, generated datasets, and reports used to rebuild the catalog
- `scripts/` — manual certification and diagnostic utilities
- `reports/` — archived local certification logs; not required at runtime
- `registry/pack.v1.json` — versioned capability and vocabulary definitions

Catalog records describe third-party tools and repositories. Their code, names, trademarks, and licenses remain with their respective owners; check each upstream project before using or redistributing it. The FAIA license applies to this project's own source and documentation.

## License

FAIA is licensed under the [Apache License 2.0](LICENSE).
