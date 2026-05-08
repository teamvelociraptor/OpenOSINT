"""Unit tests for OpenOSINT OSINT tools (no API keys required)."""

from openosint.tools.dork_tools import generate_dorks
from openosint.tools.email_tools import _derive_username_variants, check_email
from openosint.tools.ip_tools import check_ip
from openosint.tools.phone_tools import check_phone
from openosint.tools.registry import TOOL_DEFINITIONS, execute_tool

# ─── Email ───────────────────────────────────────────────────────────────────

class TestCheckEmail:
    def test_valid_gmail(self):
        r = check_email("user@gmail.com")
        assert r["format_valid"] is True
        assert r["domain"] == "gmail.com"
        assert r["provider"] == "Google"
        assert r["disposable"] is False

    def test_invalid_format(self):
        r = check_email("notanemail")
        assert r["format_valid"] is False
        assert r["status"] == "invalid_format"

    def test_disposable_email(self):
        r = check_email("test@mailinator.com")
        assert r["disposable"] is True
        assert "Disposable" in r["notes"][0]

    def test_username_extraction(self):
        r = check_email("john.doe@example.com")
        assert r["username"] == "john.doe"
        assert "johndoe" in r["username_variants"]

    def test_username_variants(self):
        variants = _derive_username_variants("john.doe")
        assert "john.doe" in variants
        assert "johndoe" in variants
        assert "john" in variants


# ─── Phone ───────────────────────────────────────────────────────────────────

class TestCheckPhone:
    def test_us_number(self):
        r = check_phone("+1 650 253 0000")
        assert r["valid"] is True
        assert r["country_code"] == 1
        assert r["e164"] == "+16502530000"

    def test_italian_number(self):
        r = check_phone("+39 02 1234 5678")
        assert r["valid"] is True
        assert r["country_code"] == 39

    def test_invalid_number(self):
        r = check_phone("000")
        assert r["valid"] is False or r["status"] == "error"

    def test_format_output(self):
        r = check_phone("+1 555 867 5309")
        assert r["e164"].startswith("+1")
        assert r["international"] is not None
        assert r["national"] is not None


# ─── Dorks ───────────────────────────────────────────────────────────────────

class TestGenerateDorks:
    def test_email_dorks(self):
        r = generate_dorks("user@example.com", "email")
        assert r["status"] == "ok"
        assert len(r["dorks"]) >= 5
        assert any("user@example.com" in d for d in r["dorks"])

    def test_domain_dorks(self):
        r = generate_dorks("example.com", "domain")
        assert any("site:example.com" in d for d in r["dorks"])

    def test_person_dorks(self):
        r = generate_dorks("John Doe", "person")
        assert any('"John Doe"' in d for d in r["dorks"])

    def test_username_dorks(self):
        r = generate_dorks("johndoe", "username")
        assert any("johndoe" in d for d in r["dorks"])

    def test_all_types(self):
        for target_type in ("person", "email", "username", "domain", "company"):
            r = generate_dorks("test", target_type)
            assert r["status"] == "ok"
            assert len(r["dorks"]) > 0


# ─── IP (private / loopback — no network call) ───────────────────────────────

class TestCheckIp:
    def test_private_ip(self):
        r = check_ip("192.168.1.1")
        assert r["private"] is True
        assert "Private" in r["notes"][0]

    def test_loopback(self):
        r = check_ip("127.0.0.1")
        # Python's ipaddress treats loopback as private too
        assert "Loopback" in r["notes"][0]

    def test_invalid_ip(self):
        r = check_ip("not.an.ip")
        assert r["status"] == "error"

    def test_ipv6_loopback(self):
        r = check_ip("::1")
        assert r["type"] == "IPv6"


# ─── Registry ────────────────────────────────────────────────────────────────

class TestRegistry:
    def test_tool_count(self):
        assert len(TOOL_DEFINITIONS) == 10

    def test_all_tools_have_required_fields(self):
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert "required" in tool["input_schema"]

    def test_unknown_tool_returns_error(self):
        class FakeConfig:
            hibp_api_key = None
            abuseipdb_api_key = None

        result = execute_tool("nonexistent_tool", {}, FakeConfig())
        assert result["status"] == "error"
        assert "Unknown tool" in result["error"]
