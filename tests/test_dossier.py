# tests/test_dossier.py
"""Tests for the compound dossier tool (DOCTRINE.md §4.5).

These exercise the structural/contract guarantees that matter for the Legios
integration without making real external OSINT calls: target-type inference,
payload validation (the doctrine-vocabulary gate that stops a hallucinated
entity/link type from reaching the ontology), and the report-only fallback
when the synthesis LLM is unavailable. The live LLM-synthesis path is
covered by the WP3 live exit-check, not by a mocked unit test (per the repo's
"prefer live verification over trusting mocks" convention).
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from openosint import dossier as d


class TestInferTargetType:
    def test_ip(self):
        assert d._infer_target_type("8.8.8.8") == "ip"

    def test_email(self):
        assert d._infer_target_type("a@b.com") == "email"

    def test_phone(self):
        assert d._infer_target_type("+15551234567") == "phone"

    def test_person_has_space(self):
        assert d._infer_target_type("John Smith") == "person"

    def test_domain_fallback(self):
        assert d._infer_target_type("example.com") == "domain"


class TestValidatePayload:
    def test_drops_bogus_entity_and_link_types(self):
        """A hallucinated entity_type / link_type must never reach the ontology —
        only doctrine-catalog values survive (the whole point of the gate)."""
        p = d._validate_payload({
            "confidence": 0.8,
            "entities": [
                {"entity_type": "BogusType", "display_name": "x"},
                {"entity_type": "Organization", "display_name": "Acme Corp"},
            ],
            "links": [
                {"link_type": "nope", "src_ref": "a", "dst_ref": "b"},
                {"link_type": "sourced_from", "src_ref": "a", "dst_ref": "b"},
            ],
        })
        assert len(p["entities"]) == 1
        assert p["entities"][0]["entity_type"] == "Organization"
        assert p["entities"][0]["ref_id"]  # backfilled, never empty
        assert len(p["links"]) == 1
        assert p["links"][0]["link_type"] == "sourced_from"

    def test_drops_entity_without_display_name(self):
        p = d._validate_payload({"entities": [{"entity_type": "Organization"}]})
        assert p["entities"] == []

    def test_non_dict_returns_empty(self):
        p = d._validate_payload("not a dict")
        assert p == {"entities": [], "links": [], "confidence": 0.0}


class TestReportOnlyFallback:
    async def test_synth_falls_back_to_deterministic_when_llm_unavailable(self):
        """If the synthesis LLM can't be reached, dossier now falls back to
        deterministic entity extraction — entities are derived from tool output
        patterns (subdomains → NetworkService, etc.) rather than returning
        an empty-entities report."""
        import os

        os.environ["OPENOSINT_LITELLM_BASE_URL"] = "http://127.0.0.1:9/v1"
        fake_results = {"search_domain": "Subdomains found for example.com:\n[+] a.example.com"}
        payload = await d._synthesize("example.com", "domain", fake_results)
        assert payload["source_platform"] == "openosint"
        # Entities are now extracted deterministically — not empty.
        assert len(payload["entities"]) > 0
        assert any(e["entity_type"] == "NetworkService" and "a.example.com" in e["display_name"]
                   for e in payload["entities"])
        # Links connect the discovered entities via sourced_from.
        assert len(payload["links"]) > 0
        assert "example.com" in payload["report"]

    async def test_run_dossier_empty_target(self):
        payload = await d.run_dossier("")
        assert payload["entities"] == []
        assert payload["confidence"] == 0.0


class TestRunChain:
    async def test_run_chain_skips_missing_handler(self):
        """A tool whose binary is absent returns an error string; the rest of
        the chain must still run and be represented in the result."""
        with patch("openosint.dossier._HANDLERS", {  # type: ignore[attr-defined]
            "search_domain": (AsyncMock(side_effect=Exception("boom")), lambda a: a["domain"]),
            "generate_dorks": (AsyncMock(return_value="dork output"), lambda a: a["target"]),
        }, create=True):
            # _run_chain imports _HANDLERS from openosint.mcp_server at call time;
            # patch it there too.
            with patch("openosint.mcp_server._HANDLERS", {
                "search_domain": (AsyncMock(side_effect=Exception("boom")), lambda a: a["domain"]),
                "generate_dorks": (AsyncMock(return_value="dork output"), lambda a: a["target"]),
            }):
                results = await d._run_chain("example.com", "domain")
        assert "search_domain" in results and "boom" in results["search_domain"]
        assert results["generate_dorks"] == "dork output"
