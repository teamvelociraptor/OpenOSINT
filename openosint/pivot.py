"""
Recursive pivot engine for the dossier compound tool (DOCTRINE.md §4.5).

``investigate_recursive()`` runs a budget-bounded BFS starting from a seed
value, detects the seed's entity type, routes it to the relevant OSINT tools,
parses the raw text output for *new* identifiers (emails, usernames, domains,
IPs), and enqueues high-confidence discoveries for further investigation at
the next BFS depth — until depth, entity-count, or tool-call budgets are
exhausted.

Designed to feed into ``dossier.run_dossier()``: each depth layer produces a
set of entity discoveries with confidence scores.  The deepest layers (furthest
from the seed) have lower confidence, so the final LLM synthesis can weigh them
accordingly.

Budget caps are non-negotiable to prevent runaway cost / latency.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entity type detection from raw values
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")
_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{2,30}$")
_PHONE_RE = re.compile(r"\+?\d{7,15}")


class Kind(str, Enum):
    """Entity kinds that the pivot engine can detect and re-investigate."""
    EMAIL = "email"
    USERNAME = "username"
    DOMAIN = "domain"
    IP = "ip"
    PHONE = "phone"
    UNKNOWN = "unknown"


def detect_kind(value: str) -> Kind:
    v = value.strip()
    if _EMAIL_RE.fullmatch(v):
        return Kind.EMAIL
    if _IP_RE.fullmatch(v):
        return Kind.IP
    if _PHONE_RE.fullmatch(v) and len(v) >= 7:
        return Kind.PHONE
    if _DOMAIN_RE.fullmatch(v) and not v.startswith(".") and v.count(".") >= 1:
        return Kind.DOMAIN
    if _USERNAME_RE.match(v):
        return Kind.USERNAME
    return Kind.UNKNOWN


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PivotEntity:
    """A discovered entity at a given BFS depth with confidence."""
    value: str
    kind: Kind
    depth: int
    confidence: float  # decays with depth
    source_tool: str   # which tool produced this entity
    source_target: str # the input that produced this entity


@dataclass
class LayerResult:
    """Results from one BFS depth layer."""
    depth: int
    seed_entity: str
    tool_results: dict[str, str]  # tool_name → raw output
    discovered: list[PivotEntity]  # entities found in this layer


# ---------------------------------------------------------------------------
# Entity extraction from tool output
# ---------------------------------------------------------------------------

# Which entity kinds each tool tends to reveal
_TOOL_EXTRACTS: dict[str, list[Kind]] = {
    "search_email":     [Kind.USERNAME, Kind.DOMAIN, Kind.EMAIL],
    "search_breach":    [Kind.EMAIL, Kind.USERNAME],
    "search_username":  [Kind.EMAIL, Kind.DOMAIN],
    "search_whois":     [Kind.EMAIL, Kind.DOMAIN],
    "search_dns":       [Kind.IP, Kind.DOMAIN],
    "search_domain":    [Kind.IP, Kind.DOMAIN],
    "search_ip":        [Kind.DOMAIN, Kind.IP],
    "search_github":    [Kind.EMAIL, Kind.USERNAME],
    "search_paste":     [Kind.EMAIL, Kind.USERNAME, Kind.DOMAIN],
    "search_shodan":    [Kind.IP, Kind.DOMAIN],
    "search_virustotal":[Kind.DOMAIN, Kind.IP],
    "search_phone":     [Kind.USERNAME, Kind.EMAIL],
    "search_abuseipdb": [Kind.DOMAIN, Kind.IP],
    "generate_dorks":   [],
    "search_ip2location":[Kind.DOMAIN, Kind.IP],
}

# ── Tool → arg key name mapping (same as dossier._TOOL_CHAIN) ──────────────

_TOOL_ARG_KEY: dict[str, str] = {
    "search_email": "email",
    "search_breach": "email",
    "search_username": "username",
    "search_whois": "domain",
    "search_dns": "domain",
    "search_domain": "domain",
    "search_ip": "ip",
    "search_github": "query",
    "search_paste": "query",
    "search_shodan": "query",
    "search_virustotal": "target",
    "search_phone": "phone",
    "search_censys": "target",
    "search_abuseipdb": "ip",
    "search_ip2location": "ip",
    "generate_dorks": "target",
}

# ── Tool routing for each entity kind ──────────────────────────────────────

_KIND_TO_TOOLS: dict[Kind, list[str]] = {
    Kind.EMAIL:    ["search_email", "search_breach", "search_paste"],
    Kind.USERNAME: ["search_username", "search_github", "search_paste"],
    Kind.DOMAIN:   ["search_dns", "search_whois", "search_domain"],
    Kind.IP:       ["search_ip", "search_shodan", "search_abuseipdb"],
    Kind.PHONE:    ["search_phone"],
    Kind.UNKNOWN:  ["generate_dorks"],
}

# ── Confidence constants ──────────────────────────────────────────────────

_BASE_CONFIDENCE: dict[Kind, float] = {
    Kind.EMAIL: 0.90,
    Kind.USERNAME: 0.85,
    Kind.DOMAIN: 0.85,
    Kind.IP: 0.80,
    Kind.PHONE: 0.75,
    Kind.UNKNOWN: 0.50,
}

_CONFIDENCE_DECAY_PER_DEPTH: float = 0.20   # each BFS hop reduces confidence by 20%
_MIN_CONFIDENCE_TO_ENQUEUE: float = 0.35     # don't recurse on low-confidence finds


def _confidence(kind: Kind, depth: int) -> float:
    base = _BASE_CONFIDENCE.get(kind, 0.5)
    return max(0.10, base - depth * _CONFIDENCE_DECAY_PER_DEPTH)


# ---------------------------------------------------------------------------
# Raw text parsing — extract identifiers from tool output
# ---------------------------------------------------------------------------

def _extract_emails(text: str) -> set[str]:
    return set(_EMAIL_RE.findall(text))


def _extract_ips(text: str) -> set[str]:
    """Return valid IPv4 addresses.  Filters out common non-routable ranges
    that are likely noise (0.x, 127.x, 10.x, 172.16-31.x, 192.168.x)."""
    from ipaddress import ip_address, IPv4Address

    raw = _IP_RE.findall(text)
    valid: set[str] = set()
    for r in raw:
        try:
            addr = ip_address(r)
            if isinstance(addr, IPv4Address) and not (
                addr.is_private or addr.is_loopback or addr.is_unspecified
            ):
                valid.add(r)
        except ValueError:
            continue
    return valid


def _extract_domains(text: str) -> set[str]:
    """Extract likely domain names.  Filters out email addresses (those
    get their own handler) and common noise like time formats or version
    strings."""
    candidates = _DOMAIN_RE.findall(text.lower())
    # Reject email addresses (handled by _extract_emails) and common noise
    skip = {"example.com", "localhost", "local"}
    result: set[str] = set()
    for c in candidates:
        if c in skip:
            continue
        if _EMAIL_RE.fullmatch(c):
            continue
        result.add(c)
    return result


def _extract_usernames(text: str) -> set[str]:
    """Extract likely usernames from tool output.  Tries to find patterns
    like '[+] platform: https://site.com/user' (sherlock format) or
    'Username: value' lines."""
    # Sherlock-style: [+] PlatformName: https://site.com/username
    sherlock = re.findall(r"\[\+\]\s+\S+:\s+https?://\S+/([a-zA-Z][a-zA-Z0-9_.-]+)", text)
    # Holehe-style: [+] platform.com  (but also has [-] lines)
    # Generic: look for "Username:" / "User:" / "username:" patterns
    labeled = re.findall(
        r"(?:user(?:name)?|account|handle)[:\s]+([a-zA-Z][a-zA-Z0-9_.-]{2,30})",
        text,
        re.IGNORECASE,
    )
    return set(sherlock) | set(labeled)


def _extract_for_kind(text: str, kind: Kind) -> set[str]:
    mapping = {
        Kind.EMAIL: _extract_emails,
        Kind.IP: _extract_ips,
        Kind.DOMAIN: _extract_domains,
        Kind.USERNAME: _extract_usernames,
    }
    extractor = mapping.get(kind)
    if extractor is None:
        return set()
    return extractor(text)


# ---------------------------------------------------------------------------
# BFS recursive investigation
# ---------------------------------------------------------------------------


async def investigate_recursive(
    seed: str,
    *,
    max_depth: int = 2,
    max_entities_to_enqueue: int = 20,
    max_tool_calls: int = 40,
    tool_timeout: int = 30,
) -> list[LayerResult]:
    """Run a budget-bounded BFS investigation from ``seed``.

    Parameters
    ----------
    seed:
        Starting value (email, domain, IP, username, phone).
    max_depth:
        Maximum BFS hops from the seed (default 2).
    max_entities_to_enqueue:
        Maximum total entities to enqueue for further investigation
        across all depth layers (default 20).
    max_tool_calls:
        Hard cap on total tool invocations across the entire run (default 40).
    tool_timeout:
        Per-tool-call timeout in seconds (default 30).

    Returns
    -------
    list[LayerResult]
        One ``LayerResult`` per depth layer investigated.  Never raises —
        returns partial results on errors.  The first entry (depth=0) is
        always present and covers the seed itself.
    """
    from openosint.dossier import _HANDLERS, _chain_for, _infer_target_type

    layers: list[LayerResult] = []
    investigated: set[tuple[Kind, str]] = set()  # already visited
    queue: list[tuple[str, Kind, int]] = []       # (value, kind, depth)
    enqueued: set[tuple[Kind, str]] = set()       # in queue (dedup)
    call_count = 0

    seed_kind = detect_kind(seed)
    if seed_kind == Kind.UNKNOWN:
        seed_kind = Kind.DOMAIN  # fallback
    queue.append((seed, seed_kind, 0))
    enqueued.add((seed_kind, seed.lower()))

    while queue and call_count < max_tool_calls:
        value, kind, depth = queue.pop(0)
        key = (kind, value.lower())
        if key in investigated:
            continue
        investigated.add(key)

        if depth > 0:
            logger.debug("pivot: depth=%d investigating %s (%s)", depth, value, kind.value)

        # Map kind to the right tool chain
        if kind in (Kind.EMAIL, Kind.USERNAME, Kind.PHONE, Kind.IP, Kind.DOMAIN):
            # Use dossier's tool chain for known types
            ttype = {
                Kind.EMAIL: "email",
                Kind.USERNAME: "username",
                Kind.PHONE: "phone",
                Kind.IP: "ip",
                Kind.DOMAIN: "domain",
            }[kind]
            chain = _chain_for(ttype)
        else:
            chain = [("generate_dorks", "target")]

        # Limit chain by remaining budget
        remaining = max_tool_calls - call_count
        chain = chain[:remaining]
        call_count += len(chain)

        # Run tools concurrently
        async def _run_one(tool_name: str, arg_key: str) -> tuple[str, str]:
            if tool_name not in _HANDLERS:
                return tool_name, f"[{tool_name} not available]"
            handler, _ = _HANDLERS[tool_name]
            try:
                text = await asyncio.wait_for(
                    handler({arg_key: value}),
                    timeout=float(tool_timeout),
                )
                return tool_name, str(text) if text else ""
            except asyncio.TimeoutError:
                return tool_name, f"[{tool_name} timed out]"
            except Exception as exc:
                return tool_name, f"[{tool_name} error: {exc}]"

        results_list = await asyncio.gather(
            *(_run_one(name, key) for name, key in chain)
        )
        results: dict[str, str] = dict(results_list)

        # Extract new entities from tool outputs
        discovered: list[PivotEntity] = []
        for tool_name, output in results_list:
            if not output or output.startswith("["):
                continue
            # Try each extractable kind for this tool
            extractable_kinds = _TOOL_EXTRACTS.get(tool_name, [])
            extractable_kinds = [k for k in extractable_kinds if k != kind]  # skip same kind
            for ek in extractable_kinds:
                found = _extract_for_kind(output, ek)
                for val in found:
                    if val.lower() == value.lower():
                        continue  # same value, skip
                    conf = _confidence(ek, depth + 1)
                    de = PivotEntity(
                        value=val,
                        kind=ek,
                        depth=depth + 1,
                        confidence=conf,
                        source_tool=tool_name,
                        source_target=value,
                    )
                    discovered.append(de)
                    # Enqueue for further investigation if confidence is high enough
                    ekey = (ek, val.lower())
                    if (
                        conf >= _MIN_CONFIDENCE_TO_ENQUEUE
                        and ekey not in investigated
                        and ekey not in enqueued
                        and depth + 1 < max_depth
                        and len(queued := len([q for q in queue if q not in investigated])) < max_entities_to_enqueue
                    ):
                        enqueued.add(ekey)
                        queue.append((val, ek, depth + 1))

        layers.append(LayerResult(
            depth=depth,
            seed_entity=value,
            tool_results=results,
            discovered=discovered,
        ))

    logger.debug(
        "pivot: done — %d layers, %d tool calls, %d total discovered entities",
        len(layers), call_count,
        sum(len(l.discoved) for l in layers),
    )
    return layers


# ---------------------------------------------------------------------------
# Aggregate pivot findings into a dossier-compatible payload
# ---------------------------------------------------------------------------


def _report_from_layers(layers: list[LayerResult]) -> str:
    """Build a markdown report from pivot layer results."""
    lines = ["# Recursive OSINT Investigation", ""]
    for layer in layers:
        lines.append(f"## Depth {layer.depth}: {layer.seed_entity}")
        lines.append("")
        if layer.discovered:
            for de in layer.discovered:
                lines.append(
                    f"- **{de.value}** ({de.kind.value}) — conf {de.confidence:.0%}, "
                    f"from {de.source_tool} → {de.source_target}"
                )
            lines.append("")
        for tool, output in layer.tool_results.items():
            if output:
                lines.append(f"### {tool}")
                lines.append("")
                lines.append(f"```\n{output}\n```")
                lines.append("")
    return "\n".join(lines)


async def pivot_to_dossier_payload(
    seed: str,
    *,
    max_depth: int = 2,
    max_entities: int = 20,
    max_tool_calls: int = 40,
    tool_timeout: int = 30,
) -> dict[str, Any]:
    """Run recursive investigation and produce a dossier-compatible payload.

    This is an alternative to ``dossier.run_dossier()`` for deep/unknown
    targets: instead of a flat tool chain + LLM synthesis, it runs a BFS
    pivot and returns findings as entities with links back to their source.
    LLM synthesis is *not* used here — entities are derived deterministically
    from tool output patterns.

    The returned dict has the same shape as ``dossier.run_dossier()``:
    {source_platform, report, confidence, entities, links}
    so Legios's single write door handles it identically.
    """
    layers = await investigate_recursive(
        seed,
        max_depth=max_depth,
        max_entities_to_enqueue=max_entities,
        max_tool_calls=max_tool_calls,
        tool_timeout=tool_timeout,
    )

    entities: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    entity_ref_map: dict[str, str] = {}  # value → ref_id
    ref_counter: list[int] = [0]

    def _ref_id() -> str:
        ref_counter[0] += 1
        return f"pv{ref_counter[0]}"

    for layer in layers:
        seed_ref = _entity_map_get_or_create(
            layer.seed_entity, entities, entity_ref_map, _ref_id
        )

        for de in layer.discovered:
            ref = _entity_map_get_or_create(de.value, entities, entity_ref_map, _ref_id, de.kind, de.confidence)
            links.append({
                "link_type": "sourced_from",
                "src_ref": ref,
                "src_label": de.value,
                "dst_ref": seed_ref,
                "confidence": de.confidence * 0.9,
            })
            # If same email and username, link them
            # (handled by the kind-based mapping)

    # Compute overall confidence as average of all discoveries, weighted by depth
    all_conf = [de.confidence for layer in layers for de in layer.discovered]
    avg_conf = sum(all_conf) / len(all_conf) if all_conf else 0.0

    report = _report_from_layers(layers)
    return {
        "source_platform": "openosint",
        "report": report,
        "confidence": round(avg_conf, 2),
        "entities": entities,
        "links": links,
        "pivot_layers": len(layers),
        "pivot_depth": max_depth if layers else 0,
    }


def _entity_map_get_or_create(
    value: str,
    entities: list[dict[str, Any]],
    ref_map: dict[str, str],
    ref_id_fn,
    kind: Kind | None = None,
    confidence: float = 0.5,
) -> str:
    """Get or create the ref_id for a value in the entity list."""
    nv = value.lower()
    if nv in ref_map:
        return ref_map[nv]
    rid = ref_id_fn()
    ref_map[nv] = rid

    k = kind or detect_kind(value)
    entity_type = {
        Kind.EMAIL: "Persona",
        Kind.USERNAME: "Persona",
        Kind.DOMAIN: "Organization",
        Kind.IP: "Platform",
        Kind.PHONE: "Sensor",
        Kind.UNKNOWN: "IntelProduct",
    }.get(k, "IntelProduct")

    props: dict[str, Any] = {}
    if k == Kind.EMAIL:
        props["platform"] = "email"
        props["associated_email"] = value
    elif k == Kind.USERNAME:
        props["platform"] = "social_media"
        props["handle"] = value
    elif k == Kind.DOMAIN:
        props["domain"] = value
    elif k == Kind.IP:
        props["ip_address"] = value

    entities.append({
        "entity_type": entity_type,
        "display_name": value,
        "ref_id": rid,
        "confidence": confidence,
        "properties": props,
    })
    return rid
