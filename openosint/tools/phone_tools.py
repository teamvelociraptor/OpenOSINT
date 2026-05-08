"""Phone number validation and intelligence."""

from __future__ import annotations

from typing import Any

import phonenumbers
from phonenumbers import geocoder, carrier, timezone as pn_timezone


def check_phone(phone: str) -> dict[str, Any]:
    """Parse, validate, and gather intelligence on a phone number."""
    result: dict[str, Any] = {
        "status": "ok",
        "input": phone,
        "valid": False,
        "possible": False,
        "e164": None,
        "national": None,
        "international": None,
        "country": None,
        "country_code": None,
        "region": None,
        "carrier": None,
        "line_type": None,
        "timezones": [],
        "notes": [],
    }

    # Try parsing with and without a country hint
    parsed = None
    for default_region in (None, "US", "GB"):
        try:
            parsed = phonenumbers.parse(phone, default_region)
            break
        except phonenumbers.NumberParseException:
            continue

    if parsed is None:
        result["status"] = "error"
        result["error"] = "Could not parse phone number — try including country code (e.g. +1)"
        return result

    result["valid"] = phonenumbers.is_valid_number(parsed)
    result["possible"] = phonenumbers.is_possible_number(parsed)

    if not result["possible"]:
        result["notes"].append("Phone number appears invalid or impossible")

    result["e164"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    result["national"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
    result["international"] = phonenumbers.format_number(
        parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
    )

    result["country_code"] = parsed.country_code

    # Country / region
    region = phonenumbers.region_code_for_number(parsed)
    result["region"] = region
    result["country"] = geocoder.description_for_number(parsed, "en") or region

    # Carrier
    carrier_name = carrier.name_for_number(parsed, "en")
    result["carrier"] = carrier_name if carrier_name else None

    # Line type
    line_type_map = {
        phonenumbers.PhoneNumberType.MOBILE: "mobile",
        phonenumbers.PhoneNumberType.FIXED_LINE: "fixed_line",
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed_or_mobile",
        phonenumbers.PhoneNumberType.TOLL_FREE: "toll_free",
        phonenumbers.PhoneNumberType.PREMIUM_RATE: "premium_rate",
        phonenumbers.PhoneNumberType.SHARED_COST: "shared_cost",
        phonenumbers.PhoneNumberType.VOIP: "voip",
        phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "personal",
        phonenumbers.PhoneNumberType.PAGER: "pager",
        phonenumbers.PhoneNumberType.UAN: "uan",
        phonenumbers.PhoneNumberType.VOICEMAIL: "voicemail",
        phonenumbers.PhoneNumberType.UNKNOWN: "unknown",
    }
    number_type = phonenumbers.number_type(parsed)
    result["line_type"] = line_type_map.get(number_type, "unknown")

    # Timezones
    try:
        result["timezones"] = list(pn_timezone.time_zones_for_number(parsed))
    except Exception:
        pass

    return result
