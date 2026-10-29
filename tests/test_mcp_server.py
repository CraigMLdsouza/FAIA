import asyncio

from mcp_server import create_server
from tool_registry import ToolRegistry


class StubResolver:
    def resolve(self, *, query):
        return {"query": query, "retrieval_status": "NO_MATCHES_FOUND"}


class StubFormatter:
    def format_search_response(self, payload):
        return {"status": "SUCCESS", "data": payload}


def test_mcp_server_exposes_discovery_and_registration_tools(tmp_path):
    server = create_server(
        registry=ToolRegistry(tmp_path / "tools.json"),
        resolver=StubResolver(),
        formatter=StubFormatter(),
    )

    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == {
        "search_tools",
        "register_tool",
        "list_registered_tools",
        "remove_registered_tool",
    }


def test_mcp_registration_is_discoverable_but_not_executable(tmp_path):
    server = create_server(
        registry=ToolRegistry(tmp_path / "tools.json"),
        resolver=StubResolver(),
        formatter=StubFormatter(),
    )

    _, result = asyncio.run(
        server.call_tool(
            "register_tool",
            {
                "name": "lookup_customer",
                "description": "Look up a customer.",
                "input_schema": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                },
            },
        )
    )

    assert result["status"] == "registered"
    assert result["execution_supported"] is False

    _, search_result = asyncio.run(
        server.call_tool("search_tools", {"query": "customer lookup"})
    )
    assert [tool["name"] for tool in search_result["registered_tools"]] == [
        "lookup_customer"
    ]
    assert search_result["catalog"]["data"]["query"] == "customer lookup"
