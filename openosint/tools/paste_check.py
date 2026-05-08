"""Paste site check — searches public paste aggregators for a target string."""

from __future__ import annotations

from typing import Any

import requests

PSBDMP_SEARCH = "https://psbdmp.ws/api/search/{}"


def check_pastes(query: str) -> dict[str, Any]:
    """Search public paste aggregators for occurrences of a target string.

    Uses the free psbdmp.ws API which indexes Pastebin dumps. Returns
    matching paste IDs and snippets. No API key required.
    """
    result: dict[str, Any] = {
        "status": "ok",
        "query": query,
        "paste_count": 0,
        "pastes": [],
        "notes": [],
    }

    try:
        resp = requests.get(
            PSBDMP_SEARCH.format(requests.utils.quote(query)),
            timeout=10,
            headers={"User-Agent": "OpenOSINT/1.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            pastes = data if isinstance(data, list) else data.get("data", [])
            result["paste_count"] = len(pastes)
            result["pastes"] = [
                {
                    "id": p.get("id"),
                    "tags": p.get("tags", ""),
                    "text_snippet": (p.get("text") or "")[:200],
                }
                for p in pastes[:20]
            ]
        elif resp.status_code == 404:
            result["notes"].append("No pastes found for this query")
        elif resp.status_code == 429:
            result["status"] = "rate_limited"
            result["notes"].append("Rate limited by paste search API")
        else:
            result["notes"].append(f"Paste search returned HTTP {resp.status_code}")
    except requests.exceptions.Timeout:
        result["status"] = "error"
        result["error"] = "Request timed out"
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"{type(e).__name__}: {e}"

    return result
