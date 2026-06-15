"""
Bright Data referral link constants.

Single source of truth for all affiliate URLs. Two tiers:
  PRODUCT — CLI / MCP / web in-product placements (missing-key messages, UI hints)
  CONTENT — README / docs / changelog static content

To swap in PartnerStack custom links, replace the _PRODUCT_BASE and/or
_CONTENT_BASE strings below. UTM params are appended on top of either base.
"""

from __future__ import annotations

_MAIN = "https://get.brightdata.com/984ni58s2oad"

# Replace with PartnerStack custom links when available:
_PRODUCT_BASE: str = _MAIN   # CLI / MCP / web placements
_CONTENT_BASE: str = _MAIN   # README / docs / changelog placements


def _link(base: str, medium: str) -> str:
    return f"{base}?utm_source=github&utm_medium={medium}"


# In-product placements (missing-key / missing-zone setup messages)
BRIGHTDATA_LINK_CLI = _link(_PRODUCT_BASE, "cli")
BRIGHTDATA_LINK_MCP = _link(_PRODUCT_BASE, "mcp")
BRIGHTDATA_LINK_WEB = _link(_PRODUCT_BASE, "web")

# Content placements (static files — duplicated inline in README/docs/changelog
# so they stay importable from Python too, for reference and future tooling)
BRIGHTDATA_LINK_README = _link(_CONTENT_BASE, "readme")
BRIGHTDATA_LINK_DOCS = _link(_CONTENT_BASE, "docs")
BRIGHTDATA_LINK_CHANGELOG = _link(_CONTENT_BASE, "changelog")
