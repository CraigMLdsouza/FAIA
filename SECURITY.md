# Security Policy

## Supported versions

Security fixes are applied to the latest version on the default branch.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's security
advisory reporting feature for this repository. Do not include credentials,
personal data, or exploit details in a public issue.

FAIA stores registered tool metadata and helps agents discover tools; it does
not execute registered code or manage provider credentials. Please still report
issues that could affect the API, MCP server, registry, or ingestion pipeline.

For hosted deployments, enable `FAIA_REQUIRE_AUTH` and set a strong
`FAIA_AUTH_TOKEN` of at least 32 characters on both services. The public
`/health` endpoints are intentionally unauthenticated for hosting-platform
probes; other HTTP routes require the bearer token. A shared bearer token is
not user-level authorization, so use an OAuth-capable gateway for deployments
with independent users.
