"""OpenOSINT entry point — delegates to cli.py."""

from .cli import cli

__all__ = ["cli"]


if __name__ == "__main__":
    cli()
