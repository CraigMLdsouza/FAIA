# Contributing

Thanks for helping improve FAIA. Keep changes focused, preserve the existing REST response contract, and add tests for behavior changes.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The REST API can be started with `uvicorn api:app --host 127.0.0.1 --port 8000`. The MCP server can be started with `python mcp_server.py`.

## Updating the built-in catalog

Catalog refreshes fetch public upstream repository data and rewrite checked-in artifacts. Generated ingestion datasets and reports go under `data/`; runtime catalog files go under `catalog_output/`. Run the following from the project directory, review the generated files, and include only intentional updates:

```powershell
python ingestion.py --seed-file data/seed_repositories.json
python capability_catalog.py
python provider_intelligence.py
python repository_index_builder.py
python repository_resolver.py --run-tests
```

`python ingestion.py --offline-demo` is for pipeline testing only. It overwrites the normal ingestion output files under `data/` with demo data.

## Registering tools

The registration contract is metadata-only. A tool needs a unique name, a human-readable description, and an object-shaped JSON Schema input definition. Provider and documentation URL are optional. FAIA stores this information locally and never executes registered code.

When changing registration behavior:

- Keep validation and persistence in `tool_registry.py`.
- Preserve atomic writes so interrupted updates do not corrupt the registry.
- Add or update tests under `tests/`.
- Avoid storing credentials, access tokens, or executable code in registry records.

## Pull requests

- Explain the user-visible change and how you tested it.
- Include tests for new behavior.
- Do not commit `.env` files, local `.faia/` data, logs, caches, or credentials.
