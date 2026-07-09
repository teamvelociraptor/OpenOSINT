# openosint/mcp_http.py
"""
OpenOSINT MCP Server — Streamable HTTP transport (DOCTRINE.md §5.2).

The stdio server (``openosint.mcp_server``) is the unchanged upstream
interface. This module exposes the same OSINT tool capabilities — plus the
compound ``dossier`` tool — over MCP streamable HTTP via FastMCP, so a
remote agent like Legios's ``MCPToolClient`` can connect over the network
without a stdio shim. Mirrors Legios's own ``legios/mcp_server.py``: a
FastMCP instance with ``@mcp.tool()`` wrappers delegating to the existing
``run_*_osint`` coroutines, mounted via ``streamable_http_app()``.

Run:  ``openosint-mcp http --host 0.0.0.0 --port 8765``
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

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


def build_http_server() -> FastMCP:
    """FastMCP instance exposing the full OSINT tool set + dossier over
    streamable HTTP. Each ``@mcp.tool()`` wrapper is a thin delegate to the
    existing tool coroutine — the actual tool implementations are shared, so
    HTTP and stdio stay behavior-identical. DNS-rebinding protection is
    disabled (tailnet-bound, same rationale as Legios's own MCP server)."""
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
    async def dossier(target: str, target_type: str = "") -> dict:
        """Compound OSINT operation (DOCTRINE.md §4.5): run the full relevant
        tool chain against one target and return a structured, ontology-ready
        payload — a markdown report plus entity and link drafts (Persona,
        Organization, Installation, IntelProduct, …) that Legios ingests
        directly into its Unified Intelligence Model. target_type selects the
        chain: domain/email/username/phone/ip/organization/person (inferred
        from the target if empty). Returns a JSON dict."""
        from openosint.dossier import run_dossier

        payload = await run_dossier(target, target_type or None)
        return payload

    logger.info("OpenOSINT HTTP MCP server built (streamable-http, path /mcp)")
    return mcp


def build_http_app():
    """Return the ASGI app for embedding/mounting (e.g. behind an existing
    FastAPI). For a standalone server use ``serve_http`` instead."""
    return build_http_server().streamable_http_app()


def serve_http(host: str = _DEFAULT_HOST, port: int = _DEFAULT_PORT) -> None:
    """Run the streamable-HTTP MCP server with uvicorn."""
    import uvicorn

    uvicorn.run(build_http_app(), host=host, port=port)
