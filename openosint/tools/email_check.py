"""Email check tool — public alias for email_tools."""

from .email_tools import check_email, _derive_username_variants

__all__ = ["check_email", "_derive_username_variants"]
