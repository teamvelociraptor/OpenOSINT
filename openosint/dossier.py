# openosint/dossier.py
"""
Dossier — compound OSINT operation producing a structured, ontology-ready
payload for the Legios Unified Intelligence Model (DOCTRINE.md §4.5).

Unlike the existing single-target tools (which return CLI display text) and
unlike ``investigate_multi`` (which returns a markdown report), ``dossier``
runs the relevant tool chain for one target and synthesizes the raw outputs
into a structured payload in the exact shape Legios's
``Ontology.ingest_from_payload`` consumes:

    {
      "source_platform": "openosint",
      "report": str,                 # markdown report
      "confidence": float,
      "entities": [ {entity_type, display_name, ref_id?, ...}, ... ],
      "links":    [ {link_type, src_ref, dst_ref, confidence?}, ... ]
    }

The entity/link drafts use the doctrine's extended entity catalog
(Persona, Organization, Installation, IntelProduct, Person, Sensor, Network,
NetworkService, Vulnerability, Credential, ExploitSession). ``src_ref``/
``dst_ref`` resolve to a draft's ``ref_id`` (or a real id) — the same
placeholder scheme Legios's ingest door resolves server-side.

Synthesis is AI-driven (DOCTRINE.md §7.2 maps the dossier to tier-research /
Gemma): the raw OSINT text outputs are fed to an LLM with a strict JSON
schema prompt, so entity typing and link assertion are a model judgment call
against real tool output — never a fragile regex parse. Falls back to a
report-only payload (no entities) if the LLM is unavailable, rather than
fabricating structure.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Which tools to run for a given target_type. Each entry is (tool_name,
# arg_key, arg_value_fn) where arg_value_fn(target) -> str|None (None skips).
# ---------------------------------------------------------------------------
_TOOL_CHAIN: dict[str, list[tuple[str, str]]] = {
    "domain": [
        ("search_domain", "domain"),
        ("search_whois", "domain"),
        ("search_dns", "domain"),
        ("generate_dorks", "target"),
    ],
    "email": [
        ("search_email", "email"),
        ("search_breach", "email"),
        ("generate_dorks", "target"),
    ],
    "username": [
        ("search_username", "username"),
        ("generate_dorks", "target"),
    ],
    "phone": [
        ("search_phone", "phone"),
    ],
    "ip": [
        ("search_ip", "ip"),
        ("search_ip2location", "ip"),
        ("search_abuseipdb", "ip"),
    ],
    "organization": [
        ("search_domain", "domain"),
        ("search_whois", "domain"),
        ("search_github", "query"),
        ("generate_dorks", "target"),
    ],
    "person": [
        ("search_username", "username"),
        ("search_email", "email"),
        ("search_breach", "email"),
        ("generate_dorks", "target"),
    ],
}

# Infer target_type from the target string when the caller omits it.
def _infer_target_type(target: str) -> str:
    t = target.strip().lower()
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", t):
        return "ip"
    if "@" in t and " " not in t:
        return "email"
    if t.startswith("+") or re.match(r"^\d{6,}$", t):
        return "phone"
    if " " not in t and "." in t and not t.endswith(".com") is False:
        pass  # fallthrough: treat as domain/organization
    if " " in t:
        return "person"
    return "domain"


def _chain_for(target_type: str) -> list[tuple[str, str]]:
    return _TOOL_CHAIN.get(target_type, _TOOL_CHAIN["domain"])


# ---------------------------------------------------------------------------
# Run the tool chain — reuse the same handler registry the MCP server uses
# so the dossier exercises the real tool functions, not a parallel path.
# ---------------------------------------------------------------------------
async def _run_chain(target: str, target_type: str) -> dict[str, str]:
    """Return {tool_name: result_text} for the chain. Failures become a short
    error string per tool — one tool's missing binary must not abort the rest."""
    from openosint.mcp_server import _HANDLERS  # real handler registry

    chain = _chain_for(target_type)
    results: dict[str, str] = {}

    async def _one(tool_name: str, arg_key: str) -> None:
        if tool_name not in _HANDLERS:
            results[tool_name] = f"[{tool_name} not available]"
            return
        handler, _ = _HANDLERS[tool_name]
        try:
            text = await handler({arg_key: target})
            results[tool_name] = text if isinstance(text, str) else str(text)
        except Exception as exc:  # tools return error strings, but be safe
            results[tool_name] = f"[{tool_name} error: {exc}]"

    await asyncio.gather(*(_one(name, key) for name, key in chain))
    return results


# ---------------------------------------------------------------------------
# LLM synthesis into the ingest_from_payload shape.
# ---------------------------------------------------------------------------
_ENTITY_TYPES = (
    "Person", "Persona", "Organization", "Installation", "Sensor", "Platform",
    "Event", "Network", "NetworkService", "Vulnerability", "Credential",
    "ExploitSession", "IntelProduct",
)
_LINK_TYPES = (
    "sourced_from", "same_as", "member_of", "operates", "targets",
    "located_at", "controls", "contains", "connected_to", "hosts",
    "has_vulnerability", "exploits", "unlocks", "compromised_by",
    "observed_by", "co_located_with", "correlates_with",
)

_SYNTHESIS_PROMPT = """You are an intelligence analyst synthesizing raw OSINT tool output into a structured ontology payload for the Legios command platform.

Given a target and the raw text output of several OSINT tools, produce a JSON object with:
- "report": a concise markdown intelligence report (factual, sourced to the tool outputs, no speculation beyond what the data supports)
- "confidence": a float 0.0-1.0 reflecting overall confidence in the findings
- "entities": a list of entity drafts. Each entity has: "entity_type" (one of: {entity_types}), "display_name", "ref_id" (a short stable local id you invent, e.g. "org_targetcorp"), optional "external_id", optional "lat"/"lon" (numbers, only if a real geolocation is evident), optional "classification" (one of: unclassified, velociraptor_internal, velociraptor_sensitive, velociraptor_restricted), and "properties" (a dict of type-specific fields).
- "links": a list of link drafts. Each link has: "link_type" (one of: {link_types}), "src_ref", "dst_ref" (each a ref_id from above or a placeholder), optional "confidence" (float).

Rules:
- Only create entities for things actually evidenced in the tool output. Do not invent people, organizations, or locations.
- Always include an IntelProduct entity for the report itself, and link discovered entities to it via "sourced_from".
- Use "Persona" for online identities/aliases discovered (with platform, profile_url), "Organization" for companies/orgs, "Installation" for physical sites with a real location, "Person" for a real individual, "Network" for subnets/IP ranges, "NetworkService" for exposed hosts/services.
- Use "same_as" to link a Persona to a Person when they represent the same individual.
- Keep properties minimal and factual. Never put passwords or secret material anywhere.
- Output ONLY the JSON object, no prose before or after."""


def _build_synth_prompt(target: str, target_type: str, results: dict[str, str]) -> str:
    body = "\n\n".join(f"### {name}\n{txt}" for name, txt in results.items())
    return _SYNTHESIS_PROMPT.format(
        entity_types=", ".join(_ENTITY_TYPES),
        link_types=", ".join(_LINK_TYPES),
    ) + f"\n\nTarget: {target}\nTarget type: {target_type}\n\nRaw OSINT output:\n{body}"


def _llm_config() -> dict[str, str]:
    """Resolve an OpenAI-compatible endpoint. Honors the existing OpenOSINT
    OPENAI_* env vars, defaulting to the homelab LiteLLM tier-research model."""
    return {
        "base_url": os.environ.get("OPENOSINT_LITELLM_BASE_URL",
                                    os.environ.get("OPENAI_BASE_URL", "http://10.0.5.130:4000/v1")),
        "api_key": os.environ.get("OPENOSINT_LITELLM_API_KEY",
                                  os.environ.get("OPENAI_API_KEY", "sk-placeholder")),
        "model": os.environ.get("OPENOSINT_DOSSIER_MODEL",
                                os.environ.get("OPENAI_MODEL", "tier-research")),
    }


async def _synthesize(target: str, target_type: str, results: dict[str, str]) -> dict[str, Any]:
    """LLM synthesis. Returns the structured payload dict. On any failure,
    returns a report-only payload (no entities) so the caller always gets
    something usable — never fabricated structure."""
    report_only = _report_only_payload(target, target_type, results)
    try:
        from openai import AsyncOpenAI
    except Exception as exc:  # openai extra not installed
        logger.warning("openai package unavailable (%s); dossier returning report-only", exc)
        return report_only

    cfg = _llm_config()
    client = AsyncOpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])
    prompt = _build_synth_prompt(target, target_type, results)
    try:
        resp = await client.chat.completions.create(
            model=cfg["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
            timeout=120,
        )
    except Exception as exc:
        logger.warning("dossier LLM synthesis failed (%s); returning report-only", exc)
        return report_only

    text = (resp.choices[0].message.content or "").strip()
    text = _strip_json_fences(text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("dossier LLM returned non-JSON (%s); returning report-only", exc)
        return report_only

    # Validate + normalize against the doctrine's vocabularies so a model
    # hallucination of a bogus entity/link type never reaches the ontology.
    payload = _validate_payload(payload)
    payload.setdefault("source_platform", "openosint")
    if "report" not in payload:
        payload["report"] = report_only["report"]
    return payload


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _validate_payload(payload: Any) -> dict[str, Any]:
    """Drop entities/links whose type isn't in the doctrine catalog. Keeps
    the rest intact so a model that gets one field wrong doesn't lose the
    whole payload."""
    if not isinstance(payload, dict):
        return {"entities": [], "links": [], "confidence": 0.0}
    ents = [e for e in payload.get("entities", []) if isinstance(e, dict)
            and e.get("entity_type") in _ENTITY_TYPES and e.get("display_name")]
    for e in ents:
        e.setdefault("ref_id", e["display_name"].replace(" ", "_").lower()[:48])
        if "confidence" not in e:
            e["confidence"] = float(payload.get("confidence", 0.7))
    links = [lk for lk in payload.get("links", []) if isinstance(lk, dict)
             and lk.get("link_type") in _LINK_TYPES and lk.get("src_ref") and lk.get("dst_ref")]
    return {
        "entities": ents,
        "links": links,
        "confidence": float(payload.get("confidence", 0.7) or 0.7),
    }


def _report_only_payload(target: str, target_type: str, results: dict[str, str]) -> dict[str, Any]:
    body = "\n\n".join(f"### {name}\n{txt}" for name, txt in results.items()) or "_No tool output._"
    report = (
        f"# OSINT Dossier: {target}\n\n"
        f"**Target type:** {target_type}\n\n"
        f"**Note:** Structured entity synthesis unavailable; raw tool output below.\n\n"
        f"{body}"
    )
    return {
        "source_platform": "openosint",
        "report": report,
        "confidence": 0.4,
        "entities": [],
        "links": [],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def run_dossier(target: str, target_type: str | None = None) -> dict[str, Any]:
    """Run a compound OSINT operation against ``target`` and return a
    structured, ontology-ready payload (DOCTRINE.md §4.5 ``dossier``).

    ``target_type`` is one of domain/email/username/phone/ip/organization/
    person; inferred from the target string when omitted. The returned dict
    is directly consumable by Legios's ``Ontology.ingest_from_payload``."""
    target = target.strip()
    if not target:
        return {"source_platform": "openosint", "report": "_Empty target._",
                "confidence": 0.0, "entities": [], "links": []}
    ttype = (target_type or _infer_target_type(target)).strip().lower()
    if ttype not in _TOOL_CHAIN:
        ttype = "domain"
    results = await _run_chain(target, ttype)
    payload = await _synthesize(target, ttype, results)
    # Attach the raw tool outputs as provenance; never lose the ground truth.
    payload["raw_tool_output"] = results
    return payload
