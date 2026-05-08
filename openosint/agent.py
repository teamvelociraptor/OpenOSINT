"""OpenOSINT AI agent — Anthropic native tool use loop."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic

from .config import Config
from .display import Display
from .tools.registry import TOOL_DEFINITIONS, execute_tool

SYSTEM_PROMPT = """You are OpenOSINT, an elite AI-powered Open Source Intelligence agent built for
security researchers, journalists, and investigators.

Your mission: conduct thorough, methodical OSINT investigations using only publicly available
information.

## Investigation Protocol

When given a target, follow this sequence:

1. **Identify** — Determine what type of target this is (email, username, domain, IP, phone,
   person name, or compound).
2. **Pivot** — Start with the most specific tool for the target type, then pivot on findings:
   - An email → check_email → extract domain → check_domain → check username variants
     → check_username
   - A domain → check_domain + dns_lookup (TXT for SPF/DMARC) + whois_lookup → check IPs found
   - A username → check_username → note platforms found → check email patterns → generate_dorks
   - An IP → check_ip → reverse DNS → check that domain
   - A phone → check_phone → generate_dorks
3. **Cross-reference** — Use results from one tool to inform calls to other tools.
4. **Dorks** — Always generate_dorks as part of every investigation.
5. **Breach check** — Always attempt check_breach for any email found (even if no HIBP key,
   the model will note it).
6. **Report** — After exhausting relevant tools, compile the final intelligence report.

## Final Report Format

Always end with a structured report using this exact markdown structure:

---

## Target Overview
Brief description of the target and investigation scope.

## Digital Footprint
Summary of online presence found.

## Account Discovery
List of confirmed accounts/profiles with URLs.

## Breach Exposure
Breach and paste findings.

## Technical Infrastructure
Domain, DNS, IP, SSL findings (if applicable).

## OSINT Assessment
Confidence levels, data quality, and key findings summary.

## Recommended Next Steps
3–5 specific, actionable next investigation steps.

---

## Principles
- Note confidence (HIGH / MEDIUM / LOW) for key findings.
- Distinguish confirmed vs inferred data.
- Flag sensitive findings (GPS coordinates, PII) appropriately.
- Be concise but complete — this report may be read by lawyers, editors, or executives.
- You operate within legal and ethical bounds: public data only, no deception.
"""


class OpenOSINTAgent:
    def __init__(self, config: Config, display: Display) -> None:
        self.config = config
        self.display = display
        self._setup_client()
        self.messages: list[dict[str, Any]] = []
        self.investigation_log: list[dict[str, Any]] = []

    def _setup_client(self) -> None:
        if self.config.provider == "anthropic":
            self.client: Any = anthropic.Anthropic(api_key=self.config.anthropic_api_key)
        elif self.config.provider == "openai":
            import openai as _openai
            self.client = _openai.OpenAI(api_key=self.config.openai_api_key)
        elif self.config.provider == "ollama":
            import openai as _openai
            self.client = _openai.OpenAI(
                base_url=f"{self.config.ollama_base_url}/v1",
                api_key="ollama",
            )
        else:
            raise ValueError(f"Unknown provider: {self.config.provider!r}")

    def investigate(self, target: str) -> str:
        """Run a full OSINT investigation on the target. Returns the final report."""
        self.messages = [
            {
                "role": "user",
                "content": (
                    f"Investigate this target: {target}\n\n"
                    "Conduct a thorough OSINT investigation using all relevant tools. "
                    "Follow the investigation protocol, cross-reference findings, and "
                    "compile a complete intelligence report."
                ),
            }
        ]
        self.investigation_log = []
        return self._run_loop()

    def chat(self, user_message: str) -> str:
        """Send a message in an ongoing investigation session."""
        self.messages.append({"role": "user", "content": user_message})
        return self._run_loop()

    def reset(self) -> None:
        self.messages = []
        self.investigation_log = []

    def _run_loop(self) -> str:
        for iteration in range(self.config.max_iterations):
            try:
                with self.display.thinking(
                    f"[dim]Iteration {iteration + 1} — thinking...[/]"
                    if iteration > 0
                    else "Analyzing target..."
                ):
                    response = self._call_api()
            except Exception as e:
                err = str(e)
                if "401" in err or "authentication" in err.lower() or "api_key" in err.lower():
                    raise RuntimeError(f"Authentication failed — check your API key.\n{e}") from e
                if "429" in err or "rate_limit" in err.lower():
                    raise RuntimeError(f"Rate limit hit — wait a moment and retry.\n{e}") from e
                raise

            if self.config.provider == "anthropic":
                return self._handle_anthropic_response(response)
            else:
                return self._handle_openai_response(response)

        return "Investigation complete (maximum iterations reached)."

    def _call_api(self) -> Any:
        if self.config.provider == "anthropic":
            return self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=self.messages,
            )
        else:
            # OpenAI / Ollama compatible path
            tools_openai = _convert_tools_for_openai(TOOL_DEFINITIONS)
            return self.client.chat.completions.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.messages,
                tools=tools_openai,
                tool_choice="auto",
            )

    def _handle_anthropic_response(self, response: Any) -> str:
        """Handle Anthropic API response in the tool-use loop."""
        self.messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        if response.stop_reason == "tool_use":
            tool_results: list[dict[str, Any]] = []

            for block in response.content:
                if block.type == "tool_use":
                    self.display.tool_call(block.name, block.input)

                    with self.display.thinking(f"Running {block.name}..."):
                        result = execute_tool(block.name, block.input, self.config)

                    self.display.tool_result_brief(block.name, result)

                    self.investigation_log.append(
                        {"tool": block.name, "input": block.input, "result": result}
                    )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str),
                        }
                    )

            self.messages.append({"role": "user", "content": tool_results})
            return self._run_loop()

        # Unexpected stop reason — return whatever text we have
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    def _handle_openai_response(self, response: Any) -> str:
        """Handle OpenAI-compatible API response in the tool-use loop."""
        msg = response.choices[0].message
        self.messages.append(
            {"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls}
        )

        if not msg.tool_calls:
            return msg.content or ""

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)

            self.display.tool_call(fn_name, fn_args)

            with self.display.thinking(f"Running {fn_name}..."):
                result = execute_tool(fn_name, fn_args, self.config)

            self.display.tool_result_brief(fn_name, result)
            self.investigation_log.append({"tool": fn_name, "input": fn_args, "result": result})

            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                }
            )

        return self._run_loop()

    def save_report(self, report_text: str, target: str) -> Path:
        """Save the investigation report to a file."""
        reports_dir = Path(self.config.reports_dir)
        reports_dir.mkdir(exist_ok=True)

        safe_target = "".join(c if c.isalnum() or c in "-_." else "_" for c in target)[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = reports_dir / f"report_{safe_target}_{timestamp}.md"

        header = (
            f"# OpenOSINT Investigation Report\n\n"
            f"**Target:** `{target}`  \n"
            f"**Date:** {datetime.now().isoformat()}  \n"
            f"**Model:** {self.config.model}  \n\n---\n\n"
        )
        path.write_text(header + report_text, encoding="utf-8")
        return path


def _convert_tools_for_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]
