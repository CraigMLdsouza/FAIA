"""Local, persistent metadata registry for tools discovered through FAIA."""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_REGISTRY_VERSION = 1
_MAX_SCHEMA_BYTES = 64 * 1024


class ToolRegistryError(ValueError):
    """Raised when a tool registration is invalid or cannot be found."""


class DuplicateToolError(ToolRegistryError):
    """Raised when a tool name is already registered."""


class ToolRegistry:
    """Stores tool descriptions and input schemas; it never executes tools."""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        configured_path = path or os.environ.get("FAIA_TOOL_REGISTRY")
        self.path = Path(configured_path).expanduser() if configured_path else (
            Path(__file__).resolve().parent / ".faia" / "registered_tools.json"
        )
        self.path = self.path.resolve()
        self._lock = threading.RLock()
        self._tools = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}

        try:
            with self.path.open("r", encoding="utf-8") as registry_file:
                payload = json.load(registry_file)
        except (OSError, json.JSONDecodeError) as exc:
            raise ToolRegistryError(f"Could not read tool registry '{self.path}': {exc}") from exc

        if not isinstance(payload, dict) or payload.get("version") != _REGISTRY_VERSION:
            raise ToolRegistryError(
                f"Tool registry '{self.path}' has an unsupported or invalid format."
            )
        records = payload.get("tools")
        if not isinstance(records, list):
            raise ToolRegistryError(f"Tool registry '{self.path}' must contain a tools list.")

        tools: dict[str, dict[str, Any]] = {}
        for record in records:
            validated = self._validate_record(record)
            key = validated["name"].casefold()
            if key in tools:
                raise ToolRegistryError(
                    f"Tool registry '{self.path}' contains duplicate name '{validated['name']}'."
                )
            tools[key] = validated
        return tools

    @staticmethod
    def _validate_record(record: Any) -> dict[str, Any]:
        if not isinstance(record, dict):
            raise ToolRegistryError("Each registered tool must be a JSON object.")

        name = record.get("name")
        description = record.get("description")
        input_schema = record.get("input_schema")
        provider = record.get("provider", "")
        documentation_url = record.get("documentation_url", "")

        if not isinstance(name, str) or not _NAME_PATTERN.fullmatch(name):
            raise ToolRegistryError(
                "Tool name must be 1-128 characters: letters, numbers, '.', '_' or '-'."
            )
        if not isinstance(description, str) or not description.strip():
            raise ToolRegistryError("Tool description must not be blank.")
        if len(description) > 4000:
            raise ToolRegistryError("Tool description must be at most 4000 characters.")
        if not isinstance(provider, str) or len(provider) > 200:
            raise ToolRegistryError("Provider must be a string of at most 200 characters.")
        if not isinstance(documentation_url, str) or len(documentation_url) > 2048:
            raise ToolRegistryError("Documentation URL must be a string of at most 2048 characters.")
        if documentation_url:
            parsed_url = urlparse(documentation_url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                raise ToolRegistryError("Documentation URL must be an absolute HTTP or HTTPS URL.")

        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            raise ToolRegistryError("Input schema must be a JSON Schema object with type 'object'.")
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        if not isinstance(properties, dict) or not all(
            isinstance(key, str) and isinstance(value, dict)
            for key, value in properties.items()
        ):
            raise ToolRegistryError("Input schema properties must map names to JSON Schema objects.")
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise ToolRegistryError("Input schema required must be a list of property names.")
        if not set(required).issubset(properties):
            raise ToolRegistryError("Every required input must be declared in properties.")
        try:
            schema_size = len(json.dumps(input_schema, allow_nan=False).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ToolRegistryError(f"Input schema must contain valid JSON values: {exc}") from exc
        if schema_size > _MAX_SCHEMA_BYTES:
            raise ToolRegistryError("Input schema must be at most 64 KiB.")

        return {
            "name": name,
            "description": description.strip(),
            "input_schema": input_schema,
            "provider": provider.strip(),
            "documentation_url": documentation_url.strip(),
        }

    def _save(self, tools: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _REGISTRY_VERSION,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "tools": sorted(tools.values(), key=lambda item: item["name"].casefold()),
        }
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = temporary_file.name
                json.dump(payload, temporary_file, indent=2, ensure_ascii=False, allow_nan=False)
                temporary_file.write("\n")
            os.replace(temporary_path, self.path)
        except (OSError, TypeError, ValueError) as exc:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
            raise ToolRegistryError(f"Could not save tool registry '{self.path}': {exc}") from exc

    def register(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        provider: str = "",
        documentation_url: str = "",
    ) -> dict[str, Any]:
        record = self._validate_record(
            {
                "name": name,
                "description": description,
                "input_schema": input_schema,
                "provider": provider,
                "documentation_url": documentation_url,
            }
        )
        key = record["name"].casefold()
        with self._lock:
            if key in self._tools:
                raise DuplicateToolError(f"Tool '{record['name']}' is already registered.")
            record = copy.deepcopy(record)
            updated_tools = {**self._tools, key: record}
            self._save(updated_tools)
            self._tools = updated_tools
            return copy.deepcopy(record)

    def list_tools(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                copy.deepcopy(tool)
                for tool in sorted(self._tools.values(), key=lambda item: item["name"].casefold())
            ]

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise ToolRegistryError("Search query must not be blank.")
        if len(query) > 500:
            raise ToolRegistryError("Search query must be at most 500 characters.")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ToolRegistryError("Search limit must be between 1 and 50.")

        query_tokens = set(_TOKEN_PATTERN.findall(query.casefold()))
        ranked: list[tuple[int, str, dict[str, Any]]] = []
        with self._lock:
            tools = list(self._tools.values())

        for tool in tools:
            name_tokens = set(_TOKEN_PATTERN.findall(tool["name"].casefold()))
            provider_tokens = set(_TOKEN_PATTERN.findall(tool["provider"].casefold()))
            description_tokens = set(_TOKEN_PATTERN.findall(tool["description"].casefold()))
            score = (
                4 * len(query_tokens & name_tokens)
                + 2 * len(query_tokens & provider_tokens)
                + len(query_tokens & description_tokens)
            )
            if score:
                ranked.append((score, tool["name"].casefold(), tool))

        ranked.sort(key=lambda result: (-result[0], result[1]))
        return [copy.deepcopy(tool) for _, _, tool in ranked[:limit]]

    def remove(self, name: str) -> dict[str, Any]:
        if not isinstance(name, str) or not name.strip():
            raise ToolRegistryError("Tool name must not be blank.")
        key = name.strip().casefold()
        with self._lock:
            if key not in self._tools:
                raise ToolRegistryError(f"Tool '{name}' is not registered.")
            removed = self._tools[key]
            updated_tools = {tool_key: tool for tool_key, tool in self._tools.items() if tool_key != key}
            self._save(updated_tools)
            self._tools = updated_tools
            return copy.deepcopy(removed)
