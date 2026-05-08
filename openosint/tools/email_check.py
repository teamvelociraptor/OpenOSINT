"""Email check tool — public alias for email_tools."""

from .email_tools import _derive_username_variants, check_email

__all__ = ["check_email", "_derive_username_variants"]
