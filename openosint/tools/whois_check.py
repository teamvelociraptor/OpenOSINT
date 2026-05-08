"""WHOIS check tool — public alias for dns_tools.whois_lookup."""

from .dns_tools import whois_lookup

__all__ = ["whois_lookup"]


def check_whois(target: str) -> dict:
    """Perform a WHOIS lookup on a domain or IP address."""
    return whois_lookup(target)
