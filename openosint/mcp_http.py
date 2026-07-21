"""
OpenOSINT MCP Server — Streamable HTTP + JSON-RPC transports.

Exposes all OSINT tools plus the compound ``dossier`` tool over two
transport protocols on one ASGI app:

1. ``/mcp`` — MCP streamable HTTP (FastMCP) — for MCP-native SDK clients.
2. ``/jsonrpc`` — Plain JSON-RPC 2.0 POST — for Legios's ``MCPToolClient``,
   which sends JSON-RPC POST without SSE session setup.

Run:  ``openosint-mcp-http --host 0.0.0.0 --port 8765``
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from openosint.tools.generate_dorks import run_dork_osint
from openosint.tools.search_abuseipdb import run_abuseipdb_osint
from openosint.tools.search_breach import run_breach_osint
from openosint.tools.search_censys import run_censys_osint
from openosint.tools.search_dns import run_dns_osint
from openosint.tools.search_domain import run_domain_osint
from openosint.tools.search_email import run_email_osint
from openosint.tools.search_github import run_github_osint
from openosint.tools.search_ip import run_ip_osint
from openosint.tools.search_ip2location import run_ip2location_osint
from openosint.tools.search_paste import run_paste_osint
from openosint.tools.search_phone import run_phone_osint
from openosint.tools.search_shodan import run_shodan_osint
from openosint.tools.search_username import run_username_osint
from openosint.tools.search_virustotal import run_virustotal_osint
from openosint.tools.search_whois import run_whois_osint

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8765


# ---------------------------------------------------------------------------
# FastMCP streamable HTTP server (MCP SDK clients)
# ---------------------------------------------------------------------------

def _build_fastmcp() -> FastMCP:
    mcp = FastMCP(
        "openosint",
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @mcp.tool()
    async def search_email(email: str) -> str:
        """Enumerate accounts linked to an email using holehe."""
        return await run_email_osint(email, timeout_seconds=120)

    @mcp.tool()
    async def search_username(username: str) -> str:
        """Enumerate platforms where a username is registered using sherlock."""
        return await run_username_osint(username, timeout_seconds=180)

    @mcp.tool()
    async def search_breach(email: str) -> str:
        """Check if an email appears in known data breaches (HaveIBeenPwned)."""
        return await run_breach_osint(email, timeout_seconds=15)

    @mcp.tool()
    async def search_whois(domain: str) -> str:
        """WHOIS lookup for a domain."""
        return await run_whois_osint(domain, timeout_seconds=15)

    @mcp.tool()
    async def search_ip(ip: str) -> str:
        """IP geolocation/ownership lookup."""
        return await run_ip_osint(ip, timeout_seconds=10)

    @mcp.tool()
    async def search_domain(domain: str) -> str:
        """Enumerate subdomains of a domain using sublist3r."""
        return await run_domain_osint(domain, timeout_seconds=120)

    @mcp.tool()
    async def generate_dorks(target: str) -> str:
        """Generate Google dork URLs for a target."""
        return await run_dork_osint(target)

    @mcp.tool()
    async def search_paste(query: str) -> str:
        """Search paste sites for a query."""
        return await run_paste_osint(query, timeout_seconds=15)

    @mcp.tool()
    async def search_phone(phone: str) -> str:
        """Phone number carrier/type lookup."""
        return await run_phone_osint(phone, timeout_seconds=60)

    @mcp.tool()
    async def search_shodan(query: str) -> str:
        """Shodan search for internet-exposed services."""
        return await run_shodan_osint(query, timeout_seconds=30)

    @mcp.tool()
    async def search_virustotal(target: str) -> str:
        """VirusTotal reputation/report for a target."""
        return await run_virustotal_osint(target, timeout_seconds=30)

    @mcp.tool()
    async def search_censys(target: str) -> str:
        """Censys host/service search."""
        return await run_censys_osint(target, timeout_seconds=30)

    @mcp.tool()
    async def search_ip2location(ip: str) -> str:
        """IP2Location geolocation lookup."""
        return await run_ip2location_osint(ip, timeout_seconds=30)

    @mcp.tool()
    async def search_abuseipdb(ip: str) -> str:
        """AbuseIPDB reputation check for an IP."""
        return await run_abuseipdb_osint(ip, timeout_seconds=30)

    @mcp.tool()
    async def search_github(query: str) -> str:
        """GitHub profile/repo/email discovery."""
        return await run_github_osint(query, timeout_seconds=30)

    @mcp.tool()
    async def search_dns(domain: str) -> str:
        """DNS record lookup for a domain."""
        return await run_dns_osint(domain, timeout_seconds=10)

    @mcp.tool()
    async def dossier(target: str, target_type: str = "", recursive: bool = False) -> dict:
        """Compound OSINT operation (DOCTRINE.md §4.5): run the full relevant
        tool chain against one target and return a structured, ontology-ready
        payload — a markdown report plus entity and link drafts (Persona,
        Organization, Installation, IntelProduct, …) that Legios ingests
        directly into its Unified Intelligence Model. target_type selects the
        chain: domain/email/username/phone/ip/organization/person (inferred
        from the target if empty). When recursive=True, automatically pivots
        on discovered entities up to 2 BFS hops (requires more API calls).
        Returns a JSON dict."""
        from openosint.dossier import run_dossier

        payload = await run_dossier(target, target_type or None, recursive=recursive)
        return payload

    logger.info("OpenOSINT FastMCP server built (streamable-http, path /mcp)")
    return mcp


# ---------------------------------------------------------------------------
# Tools registry for JSON-RPC — single source of truth shared by both
# transports so they stay behavior-identical.
# ---------------------------------------------------------------------------

_TOOL_HANDLERS: dict[str, Any] = {
    "search_email":       lambda a: run_email_osint(a["email"], timeout_seconds=120),
    "search_username":    lambda a: run_username_osint(a["username"], timeout_seconds=180),
    "search_breach":      lambda a: run_breach_osint(a["email"], timeout_seconds=15),
    "search_whois":       lambda a: run_whois_osint(a["domain"], timeout_seconds=15),
    "search_ip":          lambda a: run_ip_osint(a["ip"], timeout_seconds=10),
    "search_domain":      lambda a: run_domain_osint(a["domain"], timeout_seconds=120),
    "generate_dorks":     lambda a: run_dork_osint(a["target"]),
    "search_paste":       lambda a: run_paste_osint(a["query"], timeout_seconds=15),
    "search_phone":       lambda a: run_phone_osint(a["phone"], timeout_seconds=60),
    "search_shodan":      lambda a: run_shodan_osint(a["query"], timeout_seconds=30),
    "search_virustotal":  lambda a: run_virustotal_osint(a["target"], timeout_seconds=30),
    "search_censys":      lambda a: run_censys_osint(a["target"], timeout_seconds=30),
    "search_ip2location": lambda a: run_ip2location_osint(a["ip"], timeout_seconds=30),
    "search_abuseipdb":   lambda a: run_abuseipdb_osint(a["ip"], timeout_seconds=30),
    "search_github":      lambda a: run_github_osint(a["query"], timeout_seconds=30),
    "search_dns":         lambda a: run_dns_osint(a["domain"], timeout_seconds=10),
}

# Tool definitions for tools/list response
_TOOL_DEFS: list[dict[str, Any]] = [
    {"name": "search_email",       "description": "Enumerate accounts linked to an email using holehe.",
     "inputSchema": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]}},
    {"name": "search_username",    "description": "Enumerate platforms where a username is registered using sherlock.",
     "inputSchema": {"type": "object", "properties": {"username": {"type": "string"}}, "required": ["username"]}},
    {"name": "search_breach",      "description": "Check if an email appears in known data breaches (HaveIBeenPwned).",
     "inputSchema": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]}},
    {"name": "search_whois",       "description": "WHOIS lookup for a domain.",
     "inputSchema": {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}},
    {"name": "search_ip",          "description": "IP geolocation/ownership lookup.",
     "inputSchema": {"type": "object", "properties": {"ip": {"type": "string"}}, "required": ["ip"]}},
    {"name": "search_domain",      "description": "Enumerate subdomains of a domain using sublist3r.",
     "inputSchema": {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}},
    {"name": "generate_dorks",     "description": "Generate Google dork URLs for a target.",
     "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}},
    {"name": "search_paste",       "description": "Search paste sites for a query.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "search_phone",       "description": "Phone number carrier/type lookup.",
     "inputSchema": {"type": "object", "properties": {"phone": {"type": "string"}}, "required": ["phone"]}},
    {"name": "search_shodan",      "description": "Shodan search for internet-exposed services.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "search_virustotal",  "description": "VirusTotal reputation/report for a target.",
     "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}},
    {"name": "search_censys",      "description": "Censys host/service search.",
     "inputSchema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}},
    {"name": "search_ip2location", "description": "IP2Location geolocation lookup.",
     "inputSchema": {"type": "object", "properties": {"ip": {"type": "string"}}, "required": ["ip"]}},
    {"name": "search_abuseipdb",   "description": "AbuseIPDB reputation check for an IP.",
     "inputSchema": {"type": "object", "properties": {"ip": {"type": "string"}}, "required": ["ip"]}},
    {"name": "search_github",      "description": "GitHub profile/repo/email discovery.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "search_dns",         "description": "DNS record lookup for a domain.",
     "inputSchema": {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}},
    {"name": "dossier",            "description": "Compound OSINT operation: run the full tool chain and return a structured, ontology-ready payload.",
     "inputSchema": {"type": "object",
        "properties": {
            "target": {"type": "string"},
            "target_type": {"type": "string", "enum": ["domain","email","username","phone","ip","organization","person"]},
            "recursive": {"type": "boolean"},
        },
        "required": ["target"]}},
]


# ---------------------------------------------------------------------------
# JSON-RPC handler — plain POST, no SSE session setup needed.
# Legios's MCPToolClient sends JSON-RPC 2.0 POST to this endpoint.
# ---------------------------------------------------------------------------

async def _jsonrpc_handler(request: Request) -> Response:
    """Handle JSON-RPC 2.0 POST with methods: tools/list, tools/call."""
    if request.method == "GET":
        return Response("OpenOSINT MCP (JSON-RPC endpoint — use POST)", media_type="text/plain")

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})

    rpc_id = body.get("id", None)
    method = body.get("method", "")

    if method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0", "id": rpc_id,
            "result": {"tools": _TOOL_DEFS},
        })

    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Special handler for dossier
        if tool_name == "dossier":
            from openosint.dossier import run_dossier

            target = arguments.get("target", "")
            if not target:
                return JSONResponse({"jsonrpc": "2.0", "id": rpc_id,
                    "error": {"code": -32602, "message": "'target' must be a non-empty string"}})
            try:
                payload = await run_dossier(
                    target,
                    arguments.get("target_type"),
                    recursive=bool(arguments.get("recursive", False)),
                )
                return JSONResponse({
                    "jsonrpc": "2.0", "id": rpc_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]},
                })
            except Exception as exc:
                logger.exception("dossier error")
                return JSONResponse({"jsonrpc": "2.0", "id": rpc_id,
                    "error": {"code": -32603, "message": str(exc)}})

        handler = _TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return JSONResponse({"jsonrpc": "2.0", "id": rpc_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}})

        try:
            result = await handler(arguments)
            text = str(result) if result is not None else ""
            return JSONResponse({
                "jsonrpc": "2.0", "id": rpc_id,
                "result": {"content": [{"type": "text", "text": text}], "isError": False},
            })
        except Exception as exc:
            logger.exception("Error in tool '%s'", tool_name)
            return JSONResponse({"jsonrpc": "2.0", "id": rpc_id,
                "result": {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True}})

    return JSONResponse({"jsonrpc": "2.0", "id": rpc_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"}})


# ---------------------------------------------------------------------------
# Unified ASGI app — mounts FastMCP streamable HTTP + JSON-RPC endpoint
# ---------------------------------------------------------------------------

def build_app():
    """Return a Starlette ASGI app with both transports mounted."""
    fastmcp_app = _build_fastmcp().streamable_http_app()

    app = Starlette(
        routes=[
            Mount("/mcp", app=fastmcp_app),
            Route("/jsonrpc", endpoint=_jsonrpc_handler, methods=["GET", "POST"]),
            # Root path — same JSON-RPC handler, for backward compatibility
            # with Legios's MCPToolClient which POSTs to the root URL.
            Route("/", endpoint=_jsonrpc_handler, methods=["GET", "POST"]),
        ],
    )
    logger.info("OpenOSINT MCP server built (paths: / streamable-http, /jsonrpc plain RPC)")
    return app


def serve_http(host: str = _DEFAULT_HOST, port: int = _DEFAULT_PORT) -> None:
    """Run the unified MCP HTTP server with uvicorn."""
    import uvicorn

    uvicorn.run(build_app(), host=host, port=port)
