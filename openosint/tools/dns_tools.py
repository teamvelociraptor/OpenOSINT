"""DNS and WHOIS lookup tools."""

from __future__ import annotations

from typing import Any

import dns.resolver
import dns.reversename
import dns.exception
import whois


VALID_RECORD_TYPES = {"A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "PTR"}


def dns_lookup(domain: str, record_type: str) -> dict[str, Any]:
    """Perform a DNS lookup for a specific record type."""
    record_type = record_type.upper()
    if record_type not in VALID_RECORD_TYPES:
        return {
            "status": "error",
            "error": f"Invalid record type '{record_type}'. Valid: {', '.join(sorted(VALID_RECORD_TYPES))}",
        }

    result: dict[str, Any] = {
        "status": "ok",
        "domain": domain,
        "record_type": record_type,
        "records": [],
        "ttl": None,
    }

    try:
        if record_type == "PTR":
            rev = dns.reversename.from_address(domain)
            answers = dns.resolver.resolve(rev, "PTR", lifetime=5.0)
        else:
            answers = dns.resolver.resolve(domain, record_type, lifetime=5.0)

        result["ttl"] = answers.rrset.ttl if answers.rrset else None

        if record_type == "MX":
            result["records"] = sorted(
                [f"{r.preference} {str(r.exchange).rstrip('.')}" for r in answers],
                key=lambda x: int(x.split()[0]),
            )
        elif record_type == "SOA":
            r = answers[0]
            result["records"] = [
                {
                    "mname": str(r.mname).rstrip("."),
                    "rname": str(r.rname).rstrip("."),
                    "serial": r.serial,
                    "refresh": r.refresh,
                    "retry": r.retry,
                    "expire": r.expire,
                    "minimum": r.minimum,
                }
            ]
        else:
            result["records"] = [str(r).rstrip('"').lstrip('"').rstrip(".") for r in answers]

    except dns.resolver.NXDOMAIN:
        result["status"] = "nxdomain"
        result["records"] = []
    except dns.resolver.NoAnswer:
        result["status"] = "no_answer"
        result["records"] = []
    except dns.exception.Timeout:
        result["status"] = "timeout"
        result["error"] = "DNS query timed out"
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"{type(e).__name__}: {e}"

    return result


def whois_lookup(target: str) -> dict[str, Any]:
    """Perform a WHOIS lookup on a domain or IP."""
    result: dict[str, Any] = {
        "status": "ok",
        "target": target,
        "domain_name": None,
        "registrar": None,
        "creation_date": None,
        "expiration_date": None,
        "updated_date": None,
        "name_servers": [],
        "registrant_name": None,
        "registrant_org": None,
        "registrant_country": None,
        "admin_email": None,
        "tech_email": None,
        "status_flags": [],
        "dnssec": None,
        "raw": None,
    }

    try:
        w = whois.whois(target)

        def _first(val):
            if isinstance(val, list):
                return val[0] if val else None
            return val

        def _date_str(val):
            from datetime import datetime
            val = _first(val)
            if isinstance(val, datetime):
                return val.isoformat()
            return str(val) if val else None

        result["domain_name"] = str(_first(w.domain_name) or "").lower() or None
        result["registrar"] = str(w.registrar) if w.registrar else None
        result["creation_date"] = _date_str(w.creation_date)
        result["expiration_date"] = _date_str(w.expiration_date)
        result["updated_date"] = _date_str(w.updated_date)

        ns = w.name_servers
        if ns:
            result["name_servers"] = sorted({str(s).lower().rstrip(".") for s in ns})

        result["registrant_name"] = str(w.name) if w.name else None
        result["registrant_org"] = str(w.org) if w.org else None
        result["registrant_country"] = str(w.country) if w.country else None
        result["admin_email"] = str(w.emails[0]) if isinstance(w.emails, list) and w.emails else str(w.emails) if w.emails else None

        if hasattr(w, "status"):
            status = w.status
            if isinstance(status, list):
                result["status_flags"] = [str(s).split(" ")[0] for s in status]
            elif status:
                result["status_flags"] = [str(status).split(" ")[0]]

        result["dnssec"] = str(w.dnssec) if hasattr(w, "dnssec") and w.dnssec else None

    except Exception as e:
        result["status"] = "error"
        result["error"] = f"{type(e).__name__}: {e}"

    return result
