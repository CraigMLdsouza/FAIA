import json

import pytest

from tool_registry import DuplicateToolError, ToolRegistry, ToolRegistryError


def sample_tool(**overrides):
    tool = {
        "name": "lookup_customer",
        "description": "Look up a customer in the CRM.",
        "input_schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
        "provider": "Example CRM",
        "documentation_url": "https://example.com/api",
    }
    tool.update(overrides)
    return tool


def test_registration_persists_and_can_be_loaded_again(tmp_path):
    registry_path = tmp_path / "nested" / "tools.json"
    registry = ToolRegistry(registry_path)

    registered = registry.register(**sample_tool())
    reloaded = ToolRegistry(registry_path)

    assert registered["name"] == "lookup_customer"
    assert reloaded.list_tools() == [registered]
    assert json.loads(registry_path.read_text(encoding="utf-8"))["version"] == 1


def test_returned_schemas_cannot_mutate_registry_state(tmp_path):
    registry = ToolRegistry(tmp_path / "tools.json")
    registered = registry.register(**sample_tool())
    registered["input_schema"]["properties"]["customer_id"]["type"] = "integer"

    listed = registry.list_tools()
    listed[0]["input_schema"]["properties"]["customer_id"]["type"] = "boolean"

    assert registry.list_tools()[0]["input_schema"]["properties"]["customer_id"]["type"] == "string"


def test_duplicate_names_are_case_insensitive(tmp_path):
    registry = ToolRegistry(tmp_path / "tools.json")
    registry.register(**sample_tool())

    with pytest.raises(DuplicateToolError, match="already registered"):
        registry.register(**sample_tool(name="Lookup_Customer"))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"name": "../unsafe"}, "Tool name"),
        ({"description": " "}, "description"),
        (
            {"input_schema": {"type": "object", "properties": {}, "required": ["missing"]}},
            "declared in properties",
        ),
        ({"documentation_url": "file:///private/data"}, "HTTP or HTTPS"),
    ],
)
def test_invalid_registration_is_rejected(tmp_path, overrides, message):
    registry = ToolRegistry(tmp_path / "tools.json")

    with pytest.raises(ToolRegistryError, match=message):
        registry.register(**sample_tool(**overrides))

    assert registry.list_tools() == []


def test_search_ranks_name_matches_and_remove_persists(tmp_path):
    registry_path = tmp_path / "tools.json"
    registry = ToolRegistry(registry_path)
    registry.register(**sample_tool())
    registry.register(
        **sample_tool(
            name="crm_report",
            description="Create a monthly sales report.",
            provider="Example CRM",
        )
    )

    assert [tool["name"] for tool in registry.search("customer lookup")] == [
        "lookup_customer"
    ]
    assert registry.remove("LOOKUP_CUSTOMER")["name"] == "lookup_customer"
    assert [tool["name"] for tool in ToolRegistry(registry_path).list_tools()] == [
        "crm_report"
    ]


def test_malformed_registry_fails_loudly(tmp_path):
    registry_path = tmp_path / "tools.json"
    registry_path.write_text("{", encoding="utf-8")

    with pytest.raises(ToolRegistryError, match="Could not read tool registry"):
        ToolRegistry(registry_path)
