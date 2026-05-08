"""Tool definitions for the Anthropic tool use API + dispatcher."""

from __future__ import annotations

from typing import Any

from .email_tools import check_email
from .username_tools import check_username
from .domain_tools import check_domain
from .ip_tools import check_ip
from .phone_tools import check_phone
from .breach_tools import check_breach
from .metadata_tools import check_metadata
from .dork_tools import generate_dorks
from .dns_tools import dns_lookup, whois_lookup

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "check_email",
        "description": (
            "Validate an email address and gather intelligence about it: format validity, "
            "MX records, DNS existence, provider identification (Google, Microsoft, Proton, etc.), "
            "disposable address detection, and derived username variants for further investigation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "The email address to investigate (e.g. user@example.com)",
                }
            },
            "required": ["email"],
        },
    },
    {
        "name": "check_username",
        "description": (
            "Search for a username across 17 major social media platforms and developer sites "
            "(GitHub, Reddit, Twitter/X, Instagram, TikTok, YouTube, Twitch, Pinterest, "
            "Keybase, Medium, Dev.to, HackerNews, Telegram, Mastodon, GitLab, npm, PyPI). "
            "Returns confirmed found profiles with direct URLs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "The username to search for across platforms",
                }
            },
            "required": ["username"],
        },
    },
    {
        "name": "check_domain",
        "description": (
            "Perform comprehensive domain intelligence: WHOIS registration data, DNS records "
            "(A, AAAA, MX, NS, TXT), SSL certificate details (issuer, expiry, SANs), "
            "and interesting HTTP response headers (server stack fingerprinting)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "The domain name to investigate (e.g. example.com — no http:// prefix needed)",
                }
            },
            "required": ["domain"],
        },
    },
    {
        "name": "check_ip",
        "description": (
            "Investigate an IP address: geolocation (country, city, ISP), ASN info, "
            "reverse DNS hostname, proxy/VPN/hosting detection, and optionally AbuseIPDB "
            "reputation score if an API key is configured."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ip": {
                    "type": "string",
                    "description": "IPv4 or IPv6 address to investigate",
                }
            },
            "required": ["ip"],
        },
    },
    {
        "name": "check_phone",
        "description": (
            "Validate and analyze a phone number: parse any format, identify country and region, "
            "detect line type (mobile, fixed, VoIP, toll-free), and identify carrier if available. "
            "Include the country code prefix for best results (e.g. +1-555-555-5555)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "phone": {
                    "type": "string",
                    "description": "Phone number in any format (e.g. +1 555 555 5555, +393331234567)",
                }
            },
            "required": ["phone"],
        },
    },
    {
        "name": "check_breach",
        "description": (
            "Check if an email address appears in known data breaches and paste sites "
            "using the HaveIBeenPwned v3 API. Returns breach names, dates, affected data types, "
            "and paste sources. Requires HIBP_API_KEY to be configured."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Email address to check for data breaches",
                }
            },
            "required": ["email"],
        },
    },
    {
        "name": "check_metadata",
        "description": (
            "Download an image from a URL and extract EXIF metadata: camera model, "
            "GPS coordinates (with Google Maps link if present), software, timestamps, "
            "and other embedded metadata. Highly valuable for photo forensics."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Direct URL to the image file (JPEG, PNG, TIFF, etc.)",
                }
            },
            "required": ["url"],
        },
    },
    {
        "name": "generate_dorks",
        "description": (
            "Generate a targeted set of Google/Bing dork queries to find indexed information "
            "about a target. Useful for discovering hidden pages, leaked credentials, "
            "documents, profiles, and more. Always generate dorks as part of the investigation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "The target string (full name, email, username, or domain)",
                },
                "target_type": {
                    "type": "string",
                    "enum": ["person", "email", "username", "domain", "company"],
                    "description": "Type of target",
                },
            },
            "required": ["target", "target_type"],
        },
    },
    {
        "name": "dns_lookup",
        "description": (
            "Query specific DNS record types for a domain. Use this for targeted DNS "
            "reconnaissance: SPF/DKIM/DMARC (TXT), mail servers (MX), zone authority (SOA), "
            "or pointer records for IPs (PTR)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain name or IP address (for PTR lookups)",
                },
                "record_type": {
                    "type": "string",
                    "enum": ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "PTR"],
                    "description": "DNS record type to query",
                },
            },
            "required": ["domain", "record_type"],
        },
    },
    {
        "name": "whois_lookup",
        "description": (
            "Perform a WHOIS lookup for a domain or IP to get registration data: "
            "registrar, creation/expiration dates, nameservers, registrant info, "
            "and domain status flags."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Domain name or IP address to look up",
                }
            },
            "required": ["target"],
        },
    },
]


def execute_tool(name: str, inputs: dict[str, Any], config: Any) -> dict[str, Any]:
    """Dispatch a tool call to its implementation."""
    try:
        if name == "check_email":
            return check_email(inputs["email"])
        elif name == "check_username":
            return check_username(inputs["username"])
        elif name == "check_domain":
            return check_domain(inputs["domain"])
        elif name == "check_ip":
            return check_ip(inputs["ip"], abuseipdb_key=config.abuseipdb_api_key)
        elif name == "check_phone":
            return check_phone(inputs["phone"])
        elif name == "check_breach":
            return check_breach(inputs["email"], api_key=config.hibp_api_key)
        elif name == "check_metadata":
            return check_metadata(inputs["url"])
        elif name == "generate_dorks":
            return generate_dorks(inputs["target"], inputs["target_type"])
        elif name == "dns_lookup":
            return dns_lookup(inputs["domain"], inputs["record_type"])
        elif name == "whois_lookup":
            return whois_lookup(inputs["target"])
        else:
            return {"status": "error", "error": f"Unknown tool: {name}"}
    except KeyError as e:
        return {"status": "error", "error": f"Missing required parameter: {e}"}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}
