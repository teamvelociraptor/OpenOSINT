"""Data breach checking via HaveIBeenPwned API."""

from __future__ import annotations

import hashlib
from typing import Any

import requests

HIBP_BREACH_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/{}"
HIBP_PASTE_URL = "https://haveibeenpwned.com/api/v3/pasteaccount/{}"
HIBP_PWNED_URL = "https://api.pwnedpasswords.com/range/{}"


def check_breach(email: str, api_key: str | None = None) -> dict[str, Any]:
    """Check if an email has appeared in known data breaches."""
    result: dict[str, Any] = {
        "status": "ok",
        "email": email,
        "breach_count": 0,
        "breaches": [],
        "paste_count": 0,
        "pastes": [],
        "notes": [],
    }

    if not api_key:
        result["status"] = "no_api_key"
        result["notes"].append(
            "HaveIBeenPwned API key not configured. "
            "Get one at https://haveibeenpwned.com/API/Key ($3.50/month)"
        )
        return result

    headers = {
        "hibp-api-key": api_key,
        "User-Agent": "OpenOSINT/1.0",
    }

    # Breach check
    try:
        resp = requests.get(
            HIBP_BREACH_URL.format(requests.utils.quote(email)),
            headers=headers,
            params={"truncateResponse": "false"},
            timeout=10,
        )
        if resp.status_code == 200:
            breaches = resp.json()
            result["breach_count"] = len(breaches)
            result["breaches"] = [
                {
                    "name": b.get("Name"),
                    "title": b.get("Title"),
                    "domain": b.get("Domain"),
                    "breach_date": b.get("BreachDate"),
                    "pwn_count": b.get("PwnCount"),
                    "description": b.get("Description", "")[:200],
                    "data_classes": b.get("DataClasses", []),
                    "verified": b.get("IsVerified"),
                    "sensitive": b.get("IsSensitive"),
                }
                for b in breaches
            ]
        elif resp.status_code == 404:
            result["notes"].append("No breaches found for this email")
        elif resp.status_code == 401:
            result["status"] = "auth_error"
            result["notes"].append("Invalid HIBP API key")
        elif resp.status_code == 429:
            result["status"] = "rate_limited"
            result["notes"].append("HIBP rate limit hit — try again in a moment")
    except Exception as e:
        result["notes"].append(f"Breach check failed: {type(e).__name__}")

    # Paste check
    try:
        resp = requests.get(
            HIBP_PASTE_URL.format(requests.utils.quote(email)),
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            pastes = resp.json()
            result["paste_count"] = len(pastes)
            result["pastes"] = [
                {
                    "source": p.get("Source"),
                    "id": p.get("Id"),
                    "title": p.get("Title"),
                    "date": p.get("Date"),
                    "email_count": p.get("EmailCount"),
                }
                for p in pastes[:10]
            ]
    except Exception:
        pass

    return result


def check_password_pwned(password: str) -> dict[str, Any]:
    """Check if a password hash prefix appears in the PWNED passwords database (k-anonymity)."""
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]

    try:
        resp = requests.get(HIBP_PWNED_URL.format(prefix), timeout=6)
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                line_suffix, count = line.split(":")
                if line_suffix == suffix:
                    return {"pwned": True, "count": int(count)}
            return {"pwned": False, "count": 0}
    except Exception as e:
        return {"status": "error", "error": str(e)}

    return {"pwned": False, "count": 0}
