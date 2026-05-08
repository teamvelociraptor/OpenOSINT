"""Domain intelligence tools."""

from __future__ import annotations

import socket
import ssl
from datetime import datetime
from typing import Any

import dns.exception
import dns.resolver
import dns.reversename
import requests
import whois

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OpenOSINT/1.0; +https://github.com/openosint/openosint)"
}


def check_domain(domain: str) -> dict[str, Any]:
    """Comprehensive domain intelligence: WHOIS, DNS, HTTP headers, SSL."""
    domain = domain.lower().strip().lstrip("https://").lstrip("http://").split("/")[0]

    result: dict[str, Any] = {
        "status": "ok",
        "domain": domain,
        "registered": False,
        "registrar": None,
        "creation_date": None,
        "expiration_date": None,
        "registrant": None,
        "nameservers": [],
        "dns": {},
        "http_headers": {},
        "ssl": {},
        "ip_addresses": [],
        "notes": [],
    }

    # WHOIS
    try:
        w = whois.whois(domain)
        result["registered"] = bool(w.domain_name)
        result["registrar"] = str(w.registrar) if w.registrar else None

        for date_field in ("creation_date", "expiration_date", "updated_date"):
            val = getattr(w, date_field, None)
            if isinstance(val, list):
                val = val[0]
            if isinstance(val, datetime):
                result[date_field.replace("updated_", "")] = val.isoformat()
            elif val:
                result[date_field] = str(val)

        if w.name:
            result["registrant"] = str(w.name)
        elif w.org:
            result["registrant"] = str(w.org)

        ns = w.name_servers
        if ns:
            result["nameservers"] = sorted({str(s).lower().rstrip(".") for s in ns})
    except Exception as e:
        result["notes"].append(f"WHOIS lookup failed: {type(e).__name__}")

    # DNS records
    for rtype in ("A", "AAAA", "MX", "NS", "TXT"):
        result["dns"][rtype] = _dns_records(domain, rtype)

    # IP addresses
    if result["dns"].get("A"):
        result["ip_addresses"] = result["dns"]["A"]

    # SSL certificate
    result["ssl"] = _ssl_info(domain)

    # HTTP headers
    result["http_headers"] = _http_headers(domain)

    return result


def _dns_records(domain: str, rtype: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, rtype, lifetime=5.0)
        if rtype == "MX":
            return [f"{r.preference} {str(r.exchange).rstrip('.')}" for r in answers]
        return [str(r).rstrip(".") for r in answers]
    except Exception:
        return []


def _ssl_info(domain: str) -> dict[str, Any]:
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(5)
            s.connect((domain, 443))
            cert = s.getpeercert()

        not_before = cert.get("notBefore", "")
        not_after = cert.get("notAfter", "")
        san = []
        for field, value in cert.get("subjectAltName", []):
            if field == "DNS":
                san.append(value)

        issuer = dict(x[0] for x in cert.get("issuer", []))

        return {
            "valid": True,
            "issuer": issuer.get("organizationName", "unknown"),
            "subject": dict(x[0] for x in cert.get("subject", [])).get("commonName", domain),
            "valid_from": not_before,
            "valid_until": not_after,
            "san": san[:10],
        }
    except ssl.SSLError as e:
        return {"valid": False, "error": str(e)}
    except Exception:
        return {"valid": None, "error": "Could not connect on port 443"}


def _http_headers(domain: str) -> dict[str, str]:
    for scheme in ("https", "http"):
        try:
            resp = requests.head(
                f"{scheme}://{domain}",
                headers=HEADERS,
                timeout=6,
                allow_redirects=True,
            )
            interesting = {
                "server", "x-powered-by", "x-frame-options", "strict-transport-security",
                "content-security-policy", "x-content-type-options", "x-generator",
                "via", "x-varnish", "cf-ray", "x-amzn-requestid",
            }
            return {
                k.lower(): v
                for k, v in resp.headers.items()
                if k.lower() in interesting
            }
        except Exception:
            continue
    return {}
