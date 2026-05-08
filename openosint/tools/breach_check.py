"""Breach check tool — public alias for breach_tools."""

from .breach_tools import check_breach, check_password_pwned

__all__ = ["check_breach", "check_password_pwned"]
