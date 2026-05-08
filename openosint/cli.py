"""OpenOSINT CLI entry point."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from . import __version__
from .agent import OpenOSINTAgent
from .config import CONFIG_FILE, PROVIDER_MODELS, Config
from .display import Display

HELP_TEXT = """
[bold bright_cyan]Commands available in interactive mode:[/]

  [cyan]investigate[/] <target>   Run an investigation (or just type the target)
  [cyan]clear[/]                  Clear conversation history
  [cyan]save[/]                   Save the last report to file
  [cyan]help[/]                   Show this help
  [cyan]quit[/] / [cyan]exit[/]            Exit OpenOSINT

[bold bright_cyan]Examples:[/]

  [dim]openosint ❯[/] john.doe@gmail.com
  [dim]openosint ❯[/] investigate @johndoe
  [dim]openosint ❯[/] 8.8.8.8
  [dim]openosint ❯[/] example.com
  [dim]openosint ❯[/] +1 555 867 5309
"""


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="OpenOSINT")
@click.option("--quiet", "-q", is_flag=True, help="Suppress banner")
@click.pass_context
def cli(ctx: click.Context, quiet: bool) -> None:
    """OpenOSINT — AI-powered Open Source Intelligence agent."""
    ctx.ensure_object(dict)
    ctx.obj["quiet"] = quiet

    if ctx.invoked_subcommand is None:
        _interactive_mode(quiet=quiet)


@cli.command()
@click.argument("target")
@click.option("--save", "-s", is_flag=True, help="Save report to file")
@click.option("--output", "-o", type=click.Path(), help="Output file path (implies --save)")
@click.option("--quiet", "-q", is_flag=True, help="Suppress banner")
def investigate(target: str, save: bool, output: Optional[str], quiet: bool) -> None:
    """Investigate a target and produce an intelligence report.

    TARGET can be an email, username, domain, IP address, or phone number.

    \b
    Examples:
      openosint investigate john@example.com
      openosint investigate example.com --save
      openosint investigate 8.8.8.8
    """
    display = Display(quiet=quiet)
    if not quiet:
        display.banner(__version__)

    config = Config.load()
    errors = config.validate()
    if errors:
        for err in errors:
            display.error(err)
        display.info("Run [bright_cyan]openosint config[/] to set up your API keys.")
        sys.exit(1)

    agent = OpenOSINTAgent(config, display)
    display.investigation_start(target)

    try:
        report = agent.investigate(target)
    except RuntimeError as e:
        display.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        display.print()
        display.info("Investigation interrupted.")
        sys.exit(0)

    display.final_report(report, target)

    if save or output:
        if output:
            path = Path(output)
            header = f"# OpenOSINT Investigation Report\n\n**Target:** `{target}`\n\n---\n\n"
            path.write_text(header + report, encoding="utf-8")
            display.success(f"Report saved to [cyan]{path}[/]")
        else:
            path = agent.save_report(report, target)
            display.success(f"Report saved to [cyan]{path}[/]")


@cli.command()
@click.option(
    "--provider",
    type=click.Choice(["anthropic", "openai", "ollama"]),
    help="AI provider",
)
@click.option("--model", help="Model name override")
@click.option("--show", is_flag=True, help="Show current configuration")
def config(provider: Optional[str], model: Optional[str], show: bool) -> None:
    """Configure OpenOSINT: provider, model, and API keys.

    API keys are read from environment variables or .env file:

    \b
      ANTHROPIC_API_KEY   — for Anthropic (default provider)
      OPENAI_API_KEY      — for OpenAI
      HIBP_API_KEY        — for HaveIBeenPwned breach checks
      ABUSEIPDB_API_KEY   — for IP reputation checks
    """
    display = Display()
    cfg = Config.load()

    if show or (not provider and not model):
        display.config_table(
            {
                "provider": cfg.provider,
                "model": cfg.model,
                "anthropic_api_key": cfg.anthropic_api_key,
                "openai_api_key": cfg.openai_api_key,
                "hibp_api_key": cfg.hibp_api_key,
                "abuseipdb_api_key": cfg.abuseipdb_api_key,
                "config_file": str(CONFIG_FILE),
                "max_tokens": cfg.max_tokens,
                "max_iterations": cfg.max_iterations,
                "save_reports": cfg.save_reports,
                "reports_dir": cfg.reports_dir,
            }
        )
        display.info("Set API keys via environment variables or [cyan].env[/] file.")
        return

    if provider:
        cfg.provider = provider  # type: ignore[assignment]
        if not model:
            cfg.model = PROVIDER_MODELS.get(provider, cfg.model)
        display.success(f"Provider set to [cyan]{provider}[/]")

    if model:
        cfg.model = model
        display.success(f"Model set to [cyan]{model}[/]")

    cfg.save()
    display.success(f"Configuration saved to [cyan]{CONFIG_FILE}[/]")


@cli.command()
def version() -> None:
    """Print version information."""
    display = Display()
    display.print(f"[bold bright_cyan]OpenOSINT[/] [dim]v{__version__}[/]")


def _interactive_mode(quiet: bool = False) -> None:
    """Interactive chat-style investigation session."""
    display = Display(quiet=quiet)
    if not quiet:
        display.banner(__version__)

    config = Config.load()
    errors = config.validate()
    if errors:
        for err in errors:
            display.error(err)
        display.warn("Set [cyan]ANTHROPIC_API_KEY[/] in your environment or [cyan].env[/] file.")
        display.warn("Run [cyan]openosint config --show[/] for current settings.")
        sys.exit(1)

    display.info(f"Provider: [cyan]{config.provider}[/]  Model: [cyan]{config.model}[/]")
    display.info(
        "Type a target to investigate, or [cyan]help[/] for commands. "
        "[cyan]Ctrl-C[/] or [cyan]quit[/] to exit."
    )
    display.print()

    agent = OpenOSINTAgent(config, display)
    last_report: Optional[str] = None

    while True:
        try:
            user_input = display.prompt()
        except (KeyboardInterrupt, EOFError):
            display.print()
            display.info("Goodbye.")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in ("quit", "exit", "q", ":q"):
            display.info("Goodbye.")
            break

        elif cmd == "help":
            display.print(HELP_TEXT)

        elif cmd == "clear":
            agent.reset()
            display.success("Conversation cleared.")

        elif cmd == "save":
            if last_report and agent.messages:
                target = _extract_target_from_messages(agent.messages)
                path = agent.save_report(last_report, target or "investigation")
                display.success(f"Saved to [cyan]{path}[/]")
            else:
                display.warn("Nothing to save yet.")

        else:
            # Strip "investigate " prefix if present
            target = user_input.removeprefix("investigate ").strip()

            try:
                if not agent.messages:
                    display.investigation_start(target)
                    report = agent.investigate(target)
                else:
                    report = agent.chat(user_input)
            except RuntimeError as e:
                display.error(str(e))
                continue
            except KeyboardInterrupt:
                display.print()
                display.info("Investigation interrupted. Continue or type [cyan]quit[/].")
                continue

            display.final_report(report, target)
            last_report = report

            if config.save_reports:
                path = agent.save_report(report, target)
                display.info(f"Auto-saved to [cyan]{path}[/]")


def _extract_target_from_messages(messages: list) -> Optional[str]:
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str) and "Investigate this target:" in content:
                lines = content.split("\n")
                for line in lines:
                    if line.startswith("Investigate this target:"):
                        return line.replace("Investigate this target:", "").strip()
    return None
