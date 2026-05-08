"""Email investigation tools."""

from __future__ import annotations

import re
import socket
from typing import Any

import dns.resolver
import dns.exception

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "sharklasers.com", "guerrillamailblock.com", "grr.la", "guerrillamail.info",
    "guerrillamail.biz", "guerrillamail.de", "guerrillamail.net", "guerrillamail.org",
    "spam4.me", "yopmail.com", "dispostable.com", "maildrop.cc", "trashmail.com",
    "trashmail.net", "trashmail.at", "discard.email", "fakeinbox.com",
    "mailnull.com", "spamgourmet.com", "spamgourmet.net", "spamgourmet.org",
    "10minutemail.com", "10minutemail.net", "10minutemail.org", "20minutemail.com",
    "tempr.email", "temp-mail.org", "mohmal.com", "emailondeck.com",
}

MAJOR_PROVIDERS = {
    "gmail.com": "Google",
    "googlemail.com": "Google",
    "yahoo.com": "Yahoo",
    "yahoo.co.uk": "Yahoo",
    "outlook.com": "Microsoft",
    "hotmail.com": "Microsoft",
    "live.com": "Microsoft",
    "msn.com": "Microsoft",
    "icloud.com": "Apple",
    "me.com": "Apple",
    "mac.com": "Apple",
    "protonmail.com": "Proton",
    "proton.me": "Proton",
    "tutanota.com": "Tutanota",
    "fastmail.com": "Fastmail",
    "zoho.com": "Zoho",
    "aol.com": "AOL",
}

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def check_email(email: str) -> dict[str, Any]:
    """Validate an email and gather intelligence about it."""
    result: dict[str, Any] = {
        "email": email,
        "status": "ok",
        "valid": False,
        "format_valid": False,
        "domain": None,
        "username": None,
        "provider": None,
        "disposable": False,
        "mx_records": [],
        "domain_exists": False,
        "notes": [],
    }

    # Format validation
    if not EMAIL_RE.match(email):
        result["status"] = "invalid_format"
        result["notes"].append("Invalid email format")
        return result

    result["format_valid"] = True
    local, domain = email.rsplit("@", 1)
    result["username"] = local
    result["domain"] = domain

    # Provider identification
    domain_lower = domain.lower()
    result["provider"] = MAJOR_PROVIDERS.get(domain_lower, domain_lower)
    result["disposable"] = domain_lower in DISPOSABLE_DOMAINS

    if result["disposable"]:
        result["notes"].append("Disposable/temporary email address")

    # MX record lookup
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5.0)
        mx_records = sorted(
            [(int(r.preference), str(r.exchange).rstrip(".")) for r in answers],
            key=lambda x: x[0],
        )
        result["mx_records"] = [{"priority": p, "host": h} for p, h in mx_records]
        result["domain_exists"] = True
        result["valid"] = True
    except (dns.exception.DNSException, dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        result["notes"].append("No MX records found — domain may not accept email")
    except Exception:
        result["notes"].append("MX lookup failed (timeout or DNS error)")

    # A record fallback
    if not result["domain_exists"]:
        try:
            socket.getaddrinfo(domain, None)
            result["domain_exists"] = True
        except socket.gaierror:
            result["notes"].append("Domain does not resolve")

    # Username patterns to investigate further
    result["username_variants"] = _derive_username_variants(local)

    return result


def _derive_username_variants(local: str) -> list[str]:
    """Derive likely usernames from the email local part."""
    variants: list[str] = [local]
    # Remove dots and underscores
    clean = local.replace(".", "").replace("_", "").replace("-", "")
    if clean != local:
        variants.append(clean)
    # Parts split by separators
    parts = re.split(r"[.\-_]", local)
    if len(parts) >= 2:
        variants.append(parts[0])
        variants.append("".join(parts))
        if len(parts) == 2:
            variants.append(f"{parts[0]}{parts[1][0]}")
    return list(dict.fromkeys(variants))  # deduplicate, preserve order
