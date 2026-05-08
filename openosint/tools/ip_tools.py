"""IP address intelligence tools."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any

import requests

IPAPI_URL = "http://ip-api.com/json/{}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,proxy,hosting,query"
ABUSEIPDB_URL = "https://api.abuseipdb.com/api/v2/check"


def check_ip(ip: str, abuseipdb_key: str | None = None) -> dict[str, Any]:
    """Investigate an IP address: geolocation, ISP, reverse DNS, abuse check."""
    result: dict[str, Any] = {
        "status": "ok",
        "ip": ip,
        "type": None,
        "private": False,
        "country": None,
        "country_code": None,
        "region": None,
        "city": None,
        "zip": None,
        "lat": None,
        "lon": None,
        "timezone": None,
        "isp": None,
        "org": None,
        "asn": None,
        "as_name": None,
        "proxy": None,
        "hosting": None,
        "reverse_dns": None,
        "abuse": None,
        "notes": [],
    }

    # Validate and classify IP
    try:
        addr = ipaddress.ip_address(ip)
        result["type"] = "IPv6" if isinstance(addr, ipaddress.IPv6Address) else "IPv4"
        result["private"] = addr.is_private
        if addr.is_loopback:
            result["private"] = True
            result["notes"].append("Loopback address")
            return result
        if addr.is_private:
            result["notes"].append("Private/reserved IP address")
            return result
    except ValueError:
        result["status"] = "error"
        result["error"] = f"Invalid IP address: {ip}"
        return result

    # Geolocation via ip-api.com (free, no key needed)
    try:
        resp = requests.get(IPAPI_URL.format(ip), timeout=6)
        data = resp.json()
        if data.get("status") == "success":
            result.update(
                {
                    "country": data.get("country"),
                    "country_code": data.get("countryCode"),
                    "region": data.get("regionName"),
                    "city": data.get("city"),
                    "zip": data.get("zip"),
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "timezone": data.get("timezone"),
                    "isp": data.get("isp"),
                    "org": data.get("org"),
                    "asn": data.get("as"),
                    "as_name": data.get("asname"),
                    "proxy": data.get("proxy"),
                    "hosting": data.get("hosting"),
                }
            )
        else:
            result["notes"].append(f"ip-api: {data.get('message', 'no data')}")
    except Exception as e:
        result["notes"].append(f"Geolocation lookup failed: {type(e).__name__}")

    # Reverse DNS
    try:
        result["reverse_dns"] = socket.gethostbyaddr(ip)[0]
    except socket.herror:
        result["reverse_dns"] = None
    except Exception:
        pass

    # AbuseIPDB (optional, requires API key)
    if abuseipdb_key:
        try:
            resp = requests.get(
                ABUSEIPDB_URL,
                headers={"Key": abuseipdb_key, "Accept": "application/json"},
                params={"ipAddress": ip, "maxAgeInDays": 90},
                timeout=6,
            )
            abuse_data = resp.json().get("data", {})
            result["abuse"] = {
                "confidence_score": abuse_data.get("abuseConfidenceScore"),
                "total_reports": abuse_data.get("totalReports"),
                "last_reported": abuse_data.get("lastReportedAt"),
                "usage_type": abuse_data.get("usageType"),
            }
        except Exception as e:
            result["notes"].append(f"AbuseIPDB lookup failed: {type(e).__name__}")
    else:
        result["notes"].append("AbuseIPDB check skipped — no API key configured")

    return result
