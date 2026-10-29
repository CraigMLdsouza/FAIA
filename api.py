#!/usr/bin/env python3
"""
FAIA Network Routing Layer - Version v1.0.2
[PRODUCTION INTEGRATION BASELINE - HARDENED GOLD MASTER FROZEN]
Exposes decoupled semantic discovery and entity formatting pipelines over an async FastAPI microservices gateway.
Applies patches: API-GM-001 through API-GM-005. Fully Certified.
"""

import sys
import json
from contextlib import asynccontextmanager
import os
from typing import Any, Dict, List, Optional

# Production Application Core Dependency Wrappers
try:
    from fastapi import FastAPI, HTTPException, status, Path
    from pydantic import BaseModel, ConfigDict, Field
    from fastapi.middleware.cors import CORSMiddleware
    from auth import BearerTokenMiddleware, validate_auth_configuration
except ImportError:
    raise ImportError(
        "[CRITICAL INITIALIZATION FAILURE] fastapi and pydantic are mandatory production runtime dependencies. "
        "Run: pip install fastapi pydantic uvicorn"
    )

# Internal Frozen Component Import Interceptors
try:
    from repository_resolver import FAIARepositoryResolver
    from result_formatter import ResultFormatter, PRODUCT_RESPONSE_SCHEMA  # API-GM-001: Core Authority Retained Here
except ImportError:
    raise ImportError(
        "[MANDATORY COMPONENT MISMATCH] api.py requires frozen discovery elements within its execution path. "
        "Ensure repository_resolver.py and result_formatter.py are local."
    )

# Setup Structured Production Loggers
sys.stderr.write(f"FAIA Core Engine Network Gateway Online - Freeze Control Enabled\n")


# =====================================================================
# Pydantic Structural Request & Response Data Models
# =====================================================================

class SearchRequest(BaseModel):
    """Request model enforcing strict payload boundary input constraints."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"query": "workflow automation"}
        }
    )

    query: str = Field(
        ...,
        description="Natural language expression string or structural entity mapping target identifier.",
        json_schema_extra={"example": "workflow automation"}
    )


class SearchResponse(BaseModel):
    """Presentation response envelope mapping directly onto PRODUCT_RESPONSE_SCHEMA constraints."""
    status: str = Field(..., description="Execution status return marker.")
    query: str = Field(..., description="Raw normalized text query string.")
    result_type: str = Field(..., description="Surfaced resolution intent class target.")
    data: Dict[str, Any] = Field(..., description="Fully serialized product response dataset.")
    summary: Dict[str, Any] = Field(..., description="Human-readable outcome metrics tracking blocks.")
    meta: Dict[str, Any] = Field(..., description="Retrieval metadata, version metrics, and trace performance latency.")
    related_matches: Optional[List[Dict[str, Any]]] = Field(None, description="Additional ranked related matches.")


class HealthResponse(BaseModel):
    """Health schema metric payload format signatures."""
    status: str = Field("HEALTHY", json_schema_extra={"example": "HEALTHY"})
    service: str = Field("FAIA", json_schema_extra={"example": "FAIA"})
    version: str = Field("1.0.0", json_schema_extra={"example": "1.0.0"})
    resolver_status: str = Field(..., json_schema_extra={"example": "VALIDATED"})
    health_metrics: Dict[str, Any] = Field(..., description="Internal index sizes and verification tracking bounds.")


class ErrorResponse(BaseModel):
    """Structured error tracking schema models for total data compliance."""
    status: str = Field("ERROR", json_schema_extra={"example": "ERROR"})
    error_code: str = Field(..., json_schema_extra={"example": "INVALID_QUERY"})
    message: str = Field(..., description="Human-readable error description narrative tracer.")


# =====================================================================
# Microservice Shared State Singleton Factories
# =====================================================================

class ServiceStateContainer:
    """Provides safe shared runtime interface containers across active network threads."""
    resolver: Optional[FAIARepositoryResolver] = None
    formatter: Optional[ResultFormatter] = None

state = ServiceStateContainer()


@asynccontextmanager
async def faia_platform_lifespan(app: FastAPI):
    """
    System Bootstrap Validation Layer
    Safely builds core internal engine lookups before exposing routing contexts.
    Fails fast if dependencies contain data drift out of matching constraints.
    """
    sys.stderr.write(" -> Initializing internal catalog mappings during application server bootstrap loops...\n")
    try:
        validate_auth_configuration()
        state.resolver = FAIARepositoryResolver()
        state.formatter = ResultFormatter()
        
        health_payload = state.resolver.health()
        resolver_status = health_payload.get("validation_status", "FAILED")
        
        if resolver_status != "VALIDATED":
            raise RuntimeError(f"Resolver catalog matrix state failed validation protocols: {json.dumps(health_payload)}")
            
        sys.stderr.write(f" -> Core Subsystems Bootstrap Status Code: {resolver_status} [OK]\n")
        
    except Exception as exc:
        sys.stderr.write(f"[FATAL PLATFORM ERROR] Aborting startup sequences. Cause: {exc}\n")
        raise RuntimeError(f"FAIA Core Engine layer failed initialization steps. Cause: {str(exc)}")
        
    yield
    sys.stderr.write(" -> Decommissioning engine network port routing matrices...\n")


# =====================================================================
# Core Application App Layer Declarations
# =====================================================================

app = FastAPI(
    title="FAIA REST API",
    description=(
        "Search the built-in FAIA catalog and retrieve repository or provider metadata. "
        "For MCP discovery and local tool metadata registration, run mcp_server.py."
    ),
    version="1.0.0",
    lifespan=faia_platform_lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "FAIA_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows POST, OPTIONS, GET, etc.
    allow_headers=["*"],  # Allows Content-Type, Authorization, etc.
)
app.add_middleware(BearerTokenMiddleware, exempt_paths={"/health"})

# =====================================================================
# HTTP Service Routes Implementations
# =====================================================================

@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health Metric Tracking Endpoint"
)
async def get_system_health():
    """Surfaces structural component index status indicators cleanly."""
    if not state.resolver:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error_code="ENGINE_UNAVAILABLE",
                message="The internal repository resolver subsystem is currently uninitialized."
            ).model_dump()
        )
        
    health_metrics = state.resolver.health()
    return {
        "status": "HEALTHY",
        "service": "FAIA",
        "version": "1.0.0",
        "resolver_status": health_metrics.get("validation_status", "FAILED"),
        "health_metrics": health_metrics
    }


@app.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Primary FAIA Discovery Pipeline Endpoint"
)
async def execute_semantic_intent_resolution(payload: SearchRequest):
    """Primary service entrance lane. Passes queries to resolver and outputs serialized schemas."""
    raw_query = payload.query
    if not raw_query or not raw_query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error_code="INVALID_QUERY",
                message="Search input expression text parameter cannot be blank strings."
            ).model_dump()
        )
        
    trimmed_query = raw_query.strip()
    if len(trimmed_query) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error_code="QUERY_TOO_LONG",
                message="Inbound search expression string limits exceeded max threshold bounds of 500 characters."
            ).model_dump()
        )

    try:
        resolver_response = state.resolver.resolve(query=trimmed_query)
        product_payload = state.formatter.format_search_response(resolver_response)
        return product_payload
        
    except Exception as inner_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code="RESOLUTION_PIPELINE_FAULT",
                message=f"Internal data translation failure tracking collection arrays: {str(inner_err)}"
            ).model_dump()
        )


@app.get(
    "/repository/{repository_id}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve Exact Repository Catalog Records"
)
async def get_repository_catalog_profile(repository_id: str = Path(..., description="Canonical internal repository query mapping dictionary key string tracker.")):
    """API-GM-002 Hardened: Returns clean repository metadata profile details from catalog store layers."""
    clean_id = repository_id.strip()
    repo_payload = state.resolver.repository(repository_id=clean_id)
    
    if not repo_payload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error_code="REPOSITORY_NOT_FOUND",
                message=f"Target repository profile string ID tracking key '{clean_id}' could not be located."
            ).model_dump()
        )
        
    return {
        "repository_id": repo_payload.get("repository_id"),
        "repository_name": repo_payload.get("repository_name") or clean_id,
        "provider_id": repo_payload.get("provider_id"),
        "repository_url": repo_payload.get("repository_url"),
        "tool_count": repo_payload.get("tool_count", 0),
        "capability_count": repo_payload.get("capability_count", 0),
        "domains": repo_payload.get("domains", [])
    }


@app.get(
    "/provider/{provider_id}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve Exact Provider Catalog Records"
)
async def get_provider_catalog_profile(provider_id: str = Path(..., description="Canonical vendor space string profile lookup identifier details key index value.")):
    """API-GM-003 Hardened: Returns clean hosting vendor statistics profiles from table stores preserves encapsulation bounds."""
    clean_p_id = provider_id.strip().lower()
    profile_meta = state.resolver.provider_profiles.get(clean_p_id)
    
    if not profile_meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error_code="PROVIDER_NOT_FOUND",
                message=f"Target hosting provider profile entry key value '{clean_p_id}' could not be verified within indices."
            ).model_dump()
        )
        
    return {
        "provider_id": profile_meta.get("provider_id"),
        "provider_rank": profile_meta.get("provider_rank", 99),
        "capability_count": profile_meta.get("capability_count", 0),
        "repository_count": profile_meta.get("repository_count", 0),
        "domains": profile_meta.get("covered_domains", []),
        "search_tokens": profile_meta.get("search_tokens", [])
    }


@app.get(
    "/schema",
    status_code=status.HTTP_200_OK,
    summary="Expose Product Response Serialization Contract Specifications"
)
async def get_product_presentation_schema():
    """Exposes schema versions parameters and response shape definitions from the authority module layer."""
    return {
        "schema_version": "1.0.2",
        "schema": PRODUCT_RESPONSE_SCHEMA
    }


@app.get(
    "/version",
    status_code=status.HTTP_200_OK,
    summary="Surfaces Operational Component Artifact Version Signatures"
)
async def get_application_platform_versions():
    """Surfaces specific frozen code assembly identifier tags."""
    return {
        "service": "FAIA",
        "api_version": "1.0.0",
        "resolver_version": "2.2.1",
        "formatter_version": "1.0.2"
    }


# =====================================================================
# Standalone Local Verification Mock Loop Setup Blocks
# =====================================================================

if __name__ == "__main__":
    import uvicorn
    sys.stderr.write(" -> Triggering internal loop uvicorn network engine runtime layer hooks...\n")
    uvicorn.run("api.py:app" if "api.py" in sys.argv[0] else app, host="127.0.0.1", port=8000, reload=False)