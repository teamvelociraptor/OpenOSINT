"""Metadata extraction from images and documents."""

from __future__ import annotations

import io
from typing import Any

import requests
from PIL import ExifTags, Image

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OpenOSINT/1.0)"
}

GPS_TAGS = {
    "GPSLatitude", "GPSLongitude", "GPSAltitude",
    "GPSLatitudeRef", "GPSLongitudeRef", "GPSAltitudeRef",
    "GPSTimeStamp", "GPSDateStamp",
}


def check_metadata(url: str) -> dict[str, Any]:
    """Download a resource and extract metadata from it."""
    result: dict[str, Any] = {
        "status": "ok",
        "url": url,
        "content_type": None,
        "file_size": None,
        "metadata": {},
        "gps": None,
        "notes": [],
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, stream=True)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        result["status"] = "error"
        result["error"] = str(e)
        return result

    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
    result["content_type"] = content_type

    content = resp.content
    result["file_size"] = len(content)

    if content_type.startswith("image/"):
        result.update(_extract_image_metadata(content))
    else:
        result["notes"].append(
            f"Content type '{content_type}' not directly supported for metadata extraction"
        )

    # HTTP response metadata is always interesting
    http_meta: dict[str, str] = {}
    for header in ("last-modified", "date", "server", "x-powered-by", "etag"):
        if val := resp.headers.get(header):
            http_meta[header] = val
    if http_meta:
        result["http_metadata"] = http_meta

    return result


def _extract_image_metadata(content: bytes) -> dict[str, Any]:
    out: dict[str, Any] = {"metadata": {}, "gps": None}

    try:
        img = Image.open(io.BytesIO(content))
        out["metadata"]["format"] = img.format
        out["metadata"]["mode"] = img.mode
        out["metadata"]["size"] = f"{img.width}x{img.height}"

        exif_data = img._getexif()  # type: ignore[attr-defined]
        if not exif_data:
            return out

        decoded: dict[str, Any] = {}
        for tag_id, value in exif_data.items():
            tag = ExifTags.TAGS.get(tag_id, str(tag_id))
            if tag in ("MakerNote", "UserComment", "PrintImageMatching"):
                continue  # skip binary blobs
            if isinstance(value, bytes):
                try:
                    decoded[tag] = value.decode("utf-8", errors="replace").strip()
                except Exception:
                    continue
            else:
                decoded[tag] = str(value) if not isinstance(value, (str, int, float)) else value

        out["metadata"].update(decoded)

        # Parse GPS
        gps_info = exif_data.get(34853)  # GPSInfo tag id
        if gps_info:
            out["gps"] = _parse_gps(gps_info)

    except Exception as e:
        out["notes"] = [f"EXIF extraction failed: {type(e).__name__}: {e}"]

    return out


def _parse_gps(gps_info: dict) -> dict[str, Any] | None:
    try:
        gps_tags = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_info.items()}

        def _to_decimal(dms, ref):
            d, m, s = dms
            decimal = float(d) + float(m) / 60 + float(s) / 3600
            if ref in ("S", "W"):
                decimal = -decimal
            return round(decimal, 6)

        lat = _to_decimal(gps_tags["GPSLatitude"], gps_tags.get("GPSLatitudeRef", "N"))
        lon = _to_decimal(gps_tags["GPSLongitude"], gps_tags.get("GPSLongitudeRef", "E"))

        return {
            "latitude": lat,
            "longitude": lon,
            "maps_url": f"https://www.google.com/maps?q={lat},{lon}",
            "altitude": str(gps_tags.get("GPSAltitude", "")) or None,
        }
    except (KeyError, TypeError, ZeroDivisionError):
        return None
