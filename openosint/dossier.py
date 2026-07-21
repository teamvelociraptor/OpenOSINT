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


# ---------------------------------------------------------------------------
# Deterministic entity extraction — fallback when the synthesis LLM is
# unavailable.  Extracts structured entities from raw tool output using
# pattern matching, maps them to Legios ontology types.
# ---------------------------------------------------------------------------


def _extract_entities_deterministic(
    results: dict[str, str],
    target: str,
    target_type: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    """Parse raw tool outputs for structured entity/link drafts.

    Returns (entities, links, confidence).  Each entity has the shape
    Legios's ingest_from_payload expects: entity_type, display_name,
    ref_id, properties, optional lat/lon/classification.  Links are
    {link_type, src_ref, dst_ref, confidence}.

    This is best-effort and intentionally conservative — if a pattern
    doesn't match, no entity is created.  The LLM synthesis should always
    produce richer results; this is purely a fallback so that the ontology
    gets *something* even when the LLM can't be reached."""
    entities: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    ref_map: dict[str, str] = {}
    ref_counter: list[int] = [0]

    def _ref(label: str) -> str:
        nl = label.lower().replace(" ", "_")[:48]
        if nl not in ref_map:
            ref_map[nl] = f"det{nl}"
        return ref_map[nl]

    def _add(
        etype: str, name: str, props: dict | None = None,
        conf: float = 0.6, lat: float | None = None, lon: float | None = None,
    ) -> str:
        rid = _ref(name)
        ent: dict[str, Any] = {
            "entity_type": etype, "display_name": name,
            "ref_id": rid, "confidence": conf,
        }
        if props:
            ent["properties"] = props
        if lat is not None:
            ent["lat"] = lat
        if lon is not None:
            ent["lon"] = lon
        entities.append(ent)
        return rid

    def _link(lt: str, src: str, dst: str, conf: float = 0.6) -> None:
        links.append({"link_type": lt, "src_ref": src, "dst_ref": dst, "confidence": conf})

    # ── IntelProduct for the report itself ───────────────────────────────
    report_ref = _add("IntelProduct", f"Dossier: {target}", {
        "format": "markdown", "topic": target, "confidence": 0.8},
        conf=0.8)

    # ── WHOIS ────────────────────────────────────────────────────────────
    whois_text = results.get("search_whois", "")
    if whois_text:
        # Registrant organization
        org_m = re.search(r"(?i)(?:Registrant\s+)?(?:Org|Organization|Company)[\s:]+(.+)", whois_text)
        if org_m:
            org_name = org_m.group(1).strip().rstrip(".")
            if org_name and org_name.lower() != target.lower():
                org_ref = _add("Organization", org_name, {
                    "sector": "unknown", "source": "whois"}, conf=0.65)
                _link("sourced_from", org_ref, report_ref)
        # Registrant email
        email_m = re.search(r"(?i)Registrar\s+Abuse\s+Contact\s+Email[\s:]+(.+)", whois_text)
        if not email_m:
            email_m = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", whois_text)
        if email_m:
            email_val = email_m.group(0).strip() if email_m.groups() else email_m.group(0)
            persona_ref = _add("Persona", email_val, {
                "platform": "email", "associated_email": email_val}, conf=0.6)
            _link("sourced_from", persona_ref, report_ref)
        # Name servers
        ns_matches = re.findall(r"(?i)Name\s+Server[\s:]+(\S+)", whois_text)
        for ns in ns_matches[:3]:
            ns_ref = _add("NetworkService", ns.strip("."), {
                "service_type": "dns", "role": "nameserver"}, conf=0.5)
            _link("sourced_from", ns_ref, report_ref)

    # ── DNS ──────────────────────────────────────────────────────────────
    dns_text = results.get("search_dns", "")
    if dns_text:
        a_records = re.findall(r"(?i)\[DNS\]\s*A[\s:]+(\d{1,3}(?:\.\d{1,3}){3})", dns_text)
        for ip_val in a_records[:5]:
            ip_ref = _add("Platform", ip_val, {
                "ip_address": ip_val, "role": "dns_resolved"}, conf=0.7)
            _link("sourced_from", ip_ref, report_ref)
        mx_records = re.findall(r"(?i)\[DNS\]\s*MX[\s:]+\d+\s+(\S+)", dns_text)
        for mx in mx_records[:3]:
            mx_ref = _add("NetworkService", mx.strip("."), {
                "service_type": "mail", "role": "mx"}, conf=0.65)
            _link("sourced_from", mx_ref, report_ref)

    # ── Holehe (email) ──────────────────────────────────────────────────
    email_text = results.get("search_email", "")
    if email_text:
        found_services = re.findall(r"\[\+\]\s+(\S+)", email_text)
        for svc in found_services[:10]:
            svc_name = svc.rstrip(".")
            persona_ref = _add("Persona", f"{target} @ {svc_name}", {
                "platform": svc_name, "associated_email": target}, conf=0.75)
            _link("sourced_from", persona_ref, report_ref)

    # ── Sherlock (username) ─────────────────────────────────────────────
    user_text = results.get("search_username", "")
    if user_text:
        platform_matches = re.findall(
            r"\[\+\]\s+(\S+):\s+(https?://\S+)", user_text)
        for plat, url in platform_matches[:15]:
            persona_ref = _add("Persona", f"{target} @ {plat}", {
                "platform": plat.lower(), "profile_url": url,
                "handle": target}, conf=0.8)
            _link("sourced_from", persona_ref, report_ref)

    # ── IP geolocation ──────────────────────────────────────────────────
    ip_text = results.get("search_ip", "")
    if ip_text:
        org_ip = re.search(r"(?i)\[\+\]\s+Org[\s:]+(.+)", ip_text)
        if org_ip:
            org_val = org_ip.group(1).strip()
            org_ref = _add("Organization", org_val, {
                "sector": "isp", "source": "ipinfo"}, conf=0.6)
            _link("sourced_from", org_ref, report_ref)
        host_ip = re.search(r"(?i)\[\+\]\s+Hostname[\s:]+(\S+)", ip_text)
        if host_ip:
            host_val = host_ip.group(1).strip()
            ns_ref = _add("NetworkService", host_val, {
                "service_type": "hosted", "role": "reverse_dns"}, conf=0.6)
            _link("sourced_from", ns_ref, report_ref)

    # ── Breaches ────────────────────────────────────────────────────────
    breach_text = results.get("search_breach", "")
    if breach_text:
        breach_count = re.search(
            r"(?i)Found\s+in\s+(\d+)\s+breach", breach_text)
        if breach_count:
            count = int(breach_count.group(1))
            ev_ref = _add("Event", f"Breach exposure for {target}", {
                "severity": "high" if count > 3 else "medium",
                "kind": "breach", "breach_count": count}, conf=0.85)
            _link("sourced_from", ev_ref, report_ref)

    # ── Subdomains ──────────────────────────────────────────────────────
    domain_text = results.get("search_domain", "")
    if domain_text:
        subs = re.findall(r"\[\+\]\s+(\S+)", domain_text)
        for sub in subs[:10]:
            sub = sub.strip().rstrip(".")
            if sub and sub != target:
                sub_ref = _add("NetworkService", sub, {
                    "service_type": "subdomain","parent_domain": target}, conf=0.75)
                _link("sourced_from", sub_ref, report_ref)

    # ── IP2Location (VPN/Proxy detection) ──────────────────────────────
    ip2l_text = results.get("search_ip2location", "")
    if ip2l_text:
        if re.search(r"(?i)Proxy|VPN|Tor", ip2l_text):
            sec_ref = _add("Event", f"Anonymization detected for {target}", {
                "kind": "anonymization_service", "source": "ip2location"}, conf=0.7)
            _link("sourced_from", sec_ref, report_ref)

    # ── AbuseIPDB ───────────────────────────────────────────────────────
    abuse_text = results.get("search_abuseipdb", "")
    if abuse_text:
        score_m = re.search(r"(?i)(?:abuse\s+confidence\s+score|score)[\s:]+(\d+)", abuse_text)
        if score_m:
            score = int(score_m.group(1))
            if score > 50:
                abuse_ref = _add("Event", f"Abuse report for {target}", {
                    "kind": "abuse_reports", "abuse_confidence_score": score,
                    "severity": "critical" if score > 80 else "high"}, conf=score / 100.0)
                _link("sourced_from", abuse_ref, report_ref)

    confidence = 0.5
    if entities:
        # Discount non-IntelProduct entities; the target report itself is always present
        meaningful = len([e for e in entities if e["entity_type"] != "IntelProduct"])
        confidence = min(0.8, 0.3 + meaningful * 0.08)

    return entities, links, confidence


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
    """LLM synthesis with deterministic fallback. Returns the structured
    payload dict with entity/link drafts. On LLM failure, falls back to
    deterministic extraction from raw tool output patterns — never returns
    an empty-entities payload unless the tools produced nothing at all."""
    fallback = _det_fallback(target, target_type, results)
    try:
        from openai import AsyncOpenAI
    except Exception as exc:  # openai extra not installed
        logger.warning("openai package unavailable (%s); using deterministic extraction", exc)
        return fallback

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
        logger.warning("dossier LLM synthesis failed (%s); using deterministic extraction", exc)
        return fallback

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


def _det_fallback(target: str, target_type: str, results: dict[str, str]) -> dict[str, Any]:
    """Deterministic fallback: extract entities from raw tool output
    patterns without an LLM.  Used when the synthesis model is unavailable.
    Produces the same Legios-compatible payload shape as LLM synthesis.
    Returns a report-only payload (no entities) if extraction yields
    nothing, which is the cleanest way to signal "tools ran but found
    nothing structured" vs "tools didn't run at all"."""
    entities, links, confidence = _extract_entities_deterministic(results, target, target_type)
    report = _report_only_payload(target, target_type, results)["report"]
    if entities:
        report = report.replace(
            "**Note:** Structured entity synthesis unavailable",
            "**Note:** Entities extracted deterministically (no LLM)."
        )
    payload: dict[str, Any] = {
        "source_platform": "openosint",
        "report": report,
        "confidence": confidence,
        "entities": entities,
        "links": links,
    }
    return payload


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def run_dossier(
    target: str,
    target_type: str | None = None,
    *,
    recursive: bool = False,
    max_pivot_depth: int = 2,
    max_pivot_entities: int = 20,
    max_pivot_calls: int = 40,
) -> dict[str, Any]:
    """Run a compound OSINT operation against ``target`` and return a
    structured, ontology-ready payload (DOCTRINE.md §4.5 ``dossier``).

    ``target_type`` is one of domain/email/username/phone/ip/organization/
    person; inferred from the target string when omitted. The returned dict
    is directly consumable by Legios's ``Ontology.ingest_from_payload``.

    When ``recursive=True``, the investigation uses the BFS pivot engine
    (``pivot.investigate_recursive``) to automatically discover and
    re-investigate new entities at deeper hops, returning richer entity/
    link graphs. Depth/clarity/tool-call budgets control how deep it goes."""
    target = target.strip()
    if not target:
        return {"source_platform": "openosint", "report": "_Empty target._",
                "confidence": 0.0, "entities": [], "links": []}
    ttype = (target_type or _infer_target_type(target)).strip().lower()
    if ttype not in _TOOL_CHAIN:
        ttype = "domain"

    results = await _run_chain(target, ttype)

    # If recursive, run the pivot engine for deeper investigation.
    # The pivot discovers new entities from tool output and re-investigates
    # them at deeper BFS layers. All findings are fed into the LLM synthesis.
    pivot_layers: list[dict[str, Any]] = []
    if recursive and ttype in ("domain", "email", "username", "ip"):
        try:
            from openosint.pivot import investigate_recursive

            layers = await investigate_recursive(
                target,
                max_depth=max_pivot_depth,
                max_entities_to_enqueue=max_pivot_entities,
                max_tool_calls=max_pivot_calls,
                tool_timeout=30,
            )
            pivot_layers = [
                {
                    "depth": l.depth,
                    "seed": l.seed_entity,
                    "discovered": [
                        {"value": e.value, "kind": e.kind.value,
                         "depth": e.depth, "confidence": e.confidence,
                         "source_tool": e.source_tool}
                        for e in l.discovered
                    ],
                }
                for l in layers if l.discovered
            ]
        except Exception as exc:
            logger.warning("dossier: recursive pivot failed (%s); continuing with flat results", exc)

    payload = await _synthesize(target, ttype, results)
    # Merge pivot discoveries into payload as additional entities
    if pivot_layers:
        pivot_entities = []
        pivot_links = []
        pivot_ref_map: dict[str, str] = {}
        ref_counter: list[int] = [len(payload.get("entities", []))]

        def _pivot_ref(val: str) -> str:
            nv = val.lower()
            if nv not in pivot_ref_map:
                pivot_ref_map[nv] = f"pd{ref_counter[0]}"
                ref_counter[0] += 1
            return pivot_ref_map[nv]

        for pl in pivot_layers:
            seed_ref = _pivot_ref(pl["seed"])
            for de in pl["discovered"]:
                ref = _pivot_ref(de["value"])
                pivot_entities.append({
                    "entity_type": "Persona",
                    "display_name": de["value"],
                    "ref_id": ref,
                    "confidence": de["confidence"],
                    "properties": {
                        "kind": de["kind"],
                        "source_tool": de["source_tool"],
                        "pivot_depth": de["depth"],
                    },
                })
                pivot_links.append({
                    "link_type": "sourced_from",
                    "src_ref": ref,
                    "dst_ref": seed_ref,
                    "confidence": de["confidence"],
                })

        payload["entities"] = list(payload.get("entities", [])) + pivot_entities
        payload["links"] = list(payload.get("links", [])) + pivot_links
        payload["pivot_layers"] = pivot_layers

    # Attach the raw tool outputs as provenance; never lose the ground truth.
    payload["raw_tool_output"] = results
    return payload
