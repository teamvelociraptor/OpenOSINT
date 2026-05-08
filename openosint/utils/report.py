"""Report utilities: saving and formatting investigation reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def format_report_header(target: str, model: str) -> str:
    """Return a Markdown header block for an investigation report."""
    return (
        f"# OpenOSINT Investigation Report\n\n"
        f"**Target:** `{target}`  \n"
        f"**Date:** {datetime.now().isoformat()}  \n"
        f"**Model:** {model}  \n\n"
        "---\n\n"
    )


def save_report(
    report_text: str,
    target: str,
    model: str = "unknown",
    reports_dir: str | Path = "reports",
) -> Path:
    """Save a report to disk, creating the reports directory if needed.

    Returns the path of the saved file.
    """
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)

    safe_target = "".join(c if c.isalnum() or c in "-_." else "_" for c in target)[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = reports_path / f"report_{safe_target}_{timestamp}.md"

    header = format_report_header(target, model)
    path.write_text(header + report_text, encoding="utf-8")
    return path
