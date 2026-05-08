"""Rich terminal display for OpenOSINT."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.status import Status
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

THEME = Theme(
    {
        "primary": "bold bright_cyan",
        "secondary": "dim cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "muted": "dim white",
        "tool.name": "bold magenta",
        "tool.input": "dim white",
        "tool.result": "white",
        "target": "bold bright_white",
        "header": "bold bright_white",
        "accent": "bright_cyan",
    }
)

LOGO = """\
 ██████╗ ██████╗ ███████╗███╗   ██╗ ██████╗ ███████╗██╗███╗   ██╗████████╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝
██║   ██║██████╔╝█████╗  ██╔██╗ ██║██║   ██║███████╗██║██╔██╗ ██║   ██║
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██║   ██║╚════██║██║██║╚██╗██║   ██║
╚██████╔╝██║     ███████╗██║ ╚████║╚██████╔╝███████║██║██║ ╚████║   ██║
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝  """

TOOL_ICONS: dict[str, str] = {
    "check_email": "✉",
    "check_username": "◈",
    "check_domain": "◎",
    "check_ip": "⊕",
    "check_phone": "☏",
    "check_breach": "⚠",
    "check_metadata": "◉",
    "generate_dorks": "⌕",
    "dns_lookup": "⊞",
    "whois_lookup": "⊟",
}


class Display:
    def __init__(self, quiet: bool = False) -> None:
        self.quiet = quiet
        self.console = Console(theme=THEME, highlight=False)

    def banner(self, version: str = "1.0.0") -> None:
        logo_text = Text(LOGO, style="bright_cyan")
        tagline = Text()
        tagline.append("  AI-Powered Open Source Intelligence Agent", style="dim white")
        tagline.append("  ·  ", style="dim")
        tagline.append(f"v{version}", style="dim cyan")
        tagline.append("  ·  ", style="dim")
        tagline.append("github.com/openosint/openosint", style="dim cyan")

        content = Text()
        content.append_text(logo_text)
        content.append("\n")
        content.append_text(tagline)

        self.console.print(
            Panel(content, border_style="bright_cyan", padding=(0, 2), box=box.HEAVY)
        )
        self.console.print()

    def show_disclaimer_banner(self) -> bool:
        """Display the legal disclaimer and prompt for acceptance. Returns True if accepted."""
        lines = [
            "[bold yellow]OpenOSINT is for LEGAL and AUTHORIZED use only.[/]",
            "",
            "You are responsible for complying with all applicable laws.",
            "Misuse of this tool may violate privacy laws and regulations.",
            "",
            "[dim]By continuing, you accept the terms in DISCLAIMER.md[/]",
            "[dim]Type [bold]yes[/] to accept and continue, or [bold]Ctrl-C[/] to exit.[/]",
        ]
        content = "\n".join(lines)
        self.console.print()
        self.console.print(
            Panel(
                content,
                title="[bold yellow]  LEGAL DISCLAIMER  [/]",
                border_style="yellow",
                padding=(1, 2),
                box=box.HEAVY,
            )
        )
        self.console.print()
        try:
            self.console.print("[dim]  Accept? [/]", end="")
            answer = input().strip().lower()
        except (KeyboardInterrupt, EOFError):
            self.console.print()
            return False
        return answer == "yes"

    def rule(self, title: str = "") -> None:
        self.console.print(Rule(title, style="dim cyan"))

    def investigation_start(self, target: str) -> None:
        t = Text()
        t.append("  Target  ", style="bold black on bright_cyan")
        t.append("  ")
        t.append(target, style="bold bright_white")
        self.console.print()
        self.console.print(t)
        self.console.print()

    @contextmanager
    def thinking(self, message: str = "Thinking...") -> Generator[Status, None, None]:
        with self.console.status(
            f"[dim cyan]{message}[/]", spinner="dots", spinner_style="bright_cyan"
        ) as status:
            yield status

    def tool_call(self, name: str, inputs: dict[str, Any]) -> None:
        icon = TOOL_ICONS.get(name, "◆")
        header = Text()
        header.append(f" {icon} ", style="bright_cyan")
        header.append(name, style="tool.name")

        params = "  ".join(f"[dim]{k}[/] [white]{v}[/]" for k, v in inputs.items())
        self.console.print(f"  [bright_cyan]›[/] [tool.name]{name}[/]  [dim]{params}[/]")

    def tool_result_brief(self, name: str, result: dict[str, Any]) -> None:
        status = result.get("status", "")
        icon = "[green]✓[/]" if status not in ("error", "not_found") else "[red]✗[/]"
        summary = _summarize_result(name, result)
        self.console.print(f"    {icon} {summary}")

    def agent_text(self, text: str) -> None:
        """Print text the agent outputs (non-report)."""
        self.console.print(f"  [dim]{text}[/]")

    def final_report(self, markdown_text: str, target: str) -> None:
        self.console.print()
        self.console.print(
            Rule("[bold bright_cyan]  INTELLIGENCE REPORT  [/]", style="bright_cyan")
        )
        self.console.print()
        self.console.print(Markdown(markdown_text))
        self.console.print()
        self.console.print(Rule(style="dim cyan"))

    def error(self, message: str) -> None:
        self.console.print(f"  [error]✗  {message}[/]")

    def warn(self, message: str) -> None:
        self.console.print(f"  [warning]!  {message}[/]")

    def success(self, message: str) -> None:
        self.console.print(f"  [success]✓  {message}[/]")

    def info(self, message: str) -> None:
        self.console.print(f"  [muted]{message}[/]")

    def config_table(self, config_data: dict[str, Any]) -> None:
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Key", style="dim cyan", min_width=20)
        table.add_column("Value", style="white")
        for key, value in config_data.items():
            if "key" in key.lower() and value:
                display_val = "***"
            elif value:
                display_val = str(value)
            else:
                display_val = "[dim]not set[/]"
            table.add_row(key, display_val)
        self.console.print(Panel(table, title="[bold]Configuration[/]", border_style="dim cyan"))

    def prompt(self, text: str = "") -> str:
        prompt_text = Text()
        prompt_text.append("openosint", style="bold bright_cyan")
        prompt_text.append(" ❯ ", style="bright_cyan")
        if text:
            prompt_text.append(text, style="dim")
        self.console.print(prompt_text, end="")
        return input()

    def print(self, *args: Any, **kwargs: Any) -> None:
        self.console.print(*args, **kwargs)


def _summarize_result(tool_name: str, result: dict[str, Any]) -> str:
    """Return a one-line human summary for a tool result."""
    if result.get("status") == "error":
        return f"[red]{result.get('error', 'error')}[/]"

    summaries: dict[str, str] = {
        "check_email": (
            f"[white]{result.get('email', '')}[/] — "
            f"valid=[cyan]{result.get('valid', '?')}[/] "
            f"provider=[cyan]{result.get('provider', '?')}[/]"
        ),
        "check_username": f"found on [cyan]{result.get('found_count', 0)}[/] platforms",
        "check_domain": (
            f"registered=[cyan]{result.get('registered', '?')}[/] "
            f"registrar=[cyan]{result.get('registrar', 'unknown')}[/]"
        ),
        "check_ip": f"[cyan]{result.get('country', '?')}[/] / [cyan]{result.get('org', '?')}[/]",
        "check_phone": (
            f"valid=[cyan]{result.get('valid', '?')}[/] "
            f"country=[cyan]{result.get('country', '?')}[/]"
        ),
        "check_breach": f"breaches=[cyan]{result.get('breach_count', 0)}[/]",
        "check_metadata": f"fields found=[cyan]{len(result.get('metadata', {}))}[/]",
        "generate_dorks": f"generated [cyan]{len(result.get('dorks', []))}[/] dork queries",
        "dns_lookup": f"[cyan]{len(result.get('records', []))}[/] records",
        "whois_lookup": f"registrar=[cyan]{result.get('registrar', 'unknown')}[/]",
    }
    return summaries.get(tool_name, str(result)[:80])
