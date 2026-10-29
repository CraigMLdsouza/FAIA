"""MCP discovery interface for the FAIA catalog and local tool metadata."""

from __future__ import annotations

import argparse
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from auth import BearerTokenMiddleware, validate_auth_configuration
from repository_resolver import FAIARepositoryResolver
from result_formatter import ResultFormatter
from tool_registry import ToolRegistry


def create_server(
    *,
    registry: ToolRegistry | None = None,
    resolver: FAIARepositoryResolver | None = None,
    formatter: ResultFormatter | None = None,
    host: str = "127.0.0.1",
    port: int = 8001,
) -> FastMCP:
    """Create the MCP server with discovery and metadata-only registration tools."""
    registry = registry or ToolRegistry()
    resolver = resolver or FAIARepositoryResolver()
    formatter = formatter or ResultFormatter()
    server = FastMCP(
        "FAIA",
        instructions=(
            "Search FAIA's tool and capability catalog, or register local tool metadata. "
            "Registered tools are descriptions only: FAIA does not execute their code."
        ),
        host=host,
        port=port,
    )

    @server.tool()
    def search_tools(query: str, limit: int = 10) -> dict[str, Any]:
        """Search the built-in catalog and locally registered tool metadata."""
        normalized_query = query.strip() if isinstance(query, str) else ""
        if not normalized_query:
            raise ValueError("Search query must not be blank.")
        if len(normalized_query) > 500:
            raise ValueError("Search query must be at most 500 characters.")
        return {
            "query": normalized_query,
            "catalog": formatter.format_search_response(resolver.resolve(query=normalized_query)),
            "registered_tools": registry.search(normalized_query, limit=limit),
            "execution_supported": False,
        }

    @server.tool()
    def register_tool(
        name: str,
        description: str,
        input_schema: dict[str, Any],
        provider: str = "",
        documentation_url: str = "",
    ) -> dict[str, Any]:
        """Persist a tool's metadata and input schema; this does not enable execution."""
        tool = registry.register(
            name=name,
            description=description,
            input_schema=input_schema,
            provider=provider,
            documentation_url=documentation_url,
        )
        return {
            "status": "registered",
            "tool": tool,
            "execution_supported": False,
            "next_step": "Connect to the tool through its provider; FAIA only stores and discovers metadata.",
        }

    @server.tool()
    def list_registered_tools() -> dict[str, Any]:
        """List locally registered tool metadata."""
        tools = registry.list_tools()
        return {"tools": tools, "count": len(tools), "execution_supported": False}

    @server.tool()
    def remove_registered_tool(name: str) -> dict[str, Any]:
        """Remove a tool's metadata from the local FAIA registry."""
        tool = registry.remove(name)
        return {"status": "removed", "name": tool["name"], "execution_supported": False}

    return server


def create_http_app(server: FastMCP) -> Starlette:
    """Create the authenticated Streamable HTTP app with an unauthenticated health check."""
    validate_auth_configuration()
    app = server.streamable_http_app()

    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "HEALTHY", "service": "FAIA MCP"})

    app.routes.append(Route("/health", health, methods=["GET"]))
    app.add_middleware(BearerTokenMiddleware, exempt_paths={"/health"})
    return app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run FAIA's MCP discovery and local metadata registration server."
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport. stdio is the recommended local-agent default.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("FAIA_MCP_HOST", "127.0.0.1"),
        help="HTTP bind host (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FAIA_MCP_PORT", "8001")),
        help="HTTP bind port (default: 8001).",
    )
    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port)
    if args.transport == "stdio":
        server.run(transport="stdio")
        return

    import uvicorn

    app = create_http_app(server)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
