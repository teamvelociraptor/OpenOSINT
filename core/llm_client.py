import sys
import os
import json
import re
import importlib
import ollama

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'modules')))

# ── DYNAMIC IMPORTS ────────────────────────────────────────────────────────────
TOOL_MAP = {}

def try_import(module_name, tool_name, func_name):
    try:
        mod = importlib.import_module(module_name)
        TOOL_MAP[tool_name] = getattr(mod, func_name)
    except Exception as e:
        print(f"--- [WARN] Tool '{tool_name}' unavailable: {e} ---")

try_import('email_check',  'search_email',    'search_email')
try_import('social_check', 'search_username', 'search_username')
try_import('domain_check', 'search_domain',   'search_domain')
try_import('breach_check', 'search_breach',   'search_breach')
try_import('whois_check',  'search_whois',    'search_whois')
try_import('ip_check',     'search_ip',       'search_ip')
try_import('google_dork',  'generate_dorks',  'generate_dorks')
try_import('paste_check',  'search_paste',    'search_paste')
try_import('phone_check',  'search_phone',    'search_phone')

TOOL_DESCRIPTIONS = """
Available tools:
- search_email(email)       → find accounts associated with an email (holehe)
- search_username(username) → find accounts associated with a username (sherlock)
- search_domain(domain)     → find subdomains (sublist3r)
- search_breach(email)      → check if email appears in data breaches (HIBP)
- search_whois(domain)      → WHOIS info for a domain
- search_ip(ip)             → geolocate and get ASN info for an IP
- generate_dorks(target)    → generate Google dork URLs for any target
- search_paste(query)       → search Pastebin dumps for email or username
- search_phone(phone)       → gather info on a phone number
"""

# ── HELPERS ────────────────────────────────────────────────────────────────────
def extract_first_json(text):
    """Extract only the first valid JSON object from a string."""
    depth = 0
    start = None
    for i, char in enumerate(text):
        if char == '{':
            if start is None:
                start = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0 and start is not None:
                candidate = text[start:i+1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    start = None
                    depth = 0
    return None

def run_tool(name, arg):
    if name not in TOOL_MAP:
        return f"Error: tool '{name}' not available."
    print(f"--- [LOG] Calling tool: {name}({arg}) ---")
    return TOOL_MAP[name](arg)

# ── REACT LOOP ─────────────────────────────────────────────────────────────────
def react_loop(prompt, max_steps=8):
    system_prompt = f"""You are an expert OSINT analyst. Investigate a target step by step using tools.

    {TOOL_DESCRIPTIONS}

    At each step return ONLY ONE valid JSON object, then stop. Do not write anything else.

    Run a tool:
    {{"action": "tool", "tool": "<tool_name>", "arg": "<argument>", "reason": "<why>"}}

    Write final report (only after using at least 2 tools):
    {{"action": "report", "content": "<full report text>"}}

    STRICT RULES:
    - Step 1 MUST always be generate_dorks on the target full name.
    - generate_dorks only generates URLs — it does NOT fetch results. Use its output to brainstorm.
    - search_username requires a single username with NO spaces (e.g. "tommaso.bertocchi", "TommasoBertocchi", "tombertocchi").
    - search_email requires a valid email address — do NOT pass a full name to it.
    - search_breach requires a valid email address — do NOT pass a full name to it.
    - search_paste accepts names, emails, or usernames.
    - For a full name target, try multiple username variations: FirstnamLastname, firstname.lastname, flastname, firstnamel.
    - Run each variation as a separate search_username call.
    - If results return profiles that could belong to different people, flag ambiguity in the report.
    - Run at least 2 tools before writing the report.
    - Never invent emails or usernames — only use what tools actually return.
    - Report must include: ambiguity check, subject summary, online presence, conclusion."""

    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user',   'content': f"Investigate: {prompt}. Your first action must be generate_dorks."}
    ]

    findings   = []
    used_tools = set()

    for step in range(max_steps):
        response = ollama.chat(model='qwen2.5', messages=messages)
        raw = response.message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        # Block hallucinated assumptions
        if "assuming" in raw.lower() or "placeholder" in raw.lower():
            messages.append({'role': 'assistant', 'content': raw})
            messages.append({'role': 'user', 'content': (
                "Do not simulate or assume results. "
                "Return ONE JSON action and wait for the real tool output."
            )})
            continue

        decision = extract_first_json(raw)
        if not decision:
            messages.append({'role': 'assistant', 'content': raw})
            messages.append({'role': 'user', 'content': (
                "Invalid JSON. Return a single valid JSON object only. "
                "Do not add any text before or after it."
            )})
            continue

        action = decision.get("action")

        # Block report if no tools used yet
        if action == "report" and len(used_tools) < 2:
            messages.append({'role': 'assistant', 'content': raw})
            messages.append({'role': 'user', 'content': (
                f"You have only used {len(used_tools)} tool(s). "
                "Run at least 2 tools before writing the report. "
                "Use generate_dorks first."
            )})
            continue

        if action == "report":
            return decision.get("content", "Error: empty report.")

        elif action == "tool":
            tool_name = decision.get("tool", "").strip()
            arg       = decision.get("arg", "").strip()
            reason    = decision.get("reason", "")

            tool_key = f"{tool_name}:{arg}"
            if tool_key in used_tools:
                messages.append({'role': 'assistant', 'content': raw})
                messages.append({'role': 'user', 'content': (
                    f"Already ran {tool_name}({arg}). Pick a different tool or write the report."
                )})
                continue
            used_tools.add(tool_key)

            print(f"--- [REASON] {reason} ---")
            result = run_tool(tool_name, arg)
            findings.append(f"[{tool_name}({arg})]\n{result}")

            messages.append({'role': 'assistant', 'content': raw})
            messages.append({'role': 'user', 'content': (
                f"Tool result:\n{result}\n\n"
                f"All findings so far:\n" + "\n\n".join(findings) + "\n\n"
                f"Tools used: {len(used_tools)}. "
                "Return ONE JSON for the next action. Stop after the closing brace."
            )})

        else:
            messages.append({'role': 'assistant', 'content': raw})
            messages.append({'role': 'user', 'content': 'Invalid action. Use "tool" or "report".'})

    # Fallback if max steps reached
    messages.append({'role': 'user', 'content': (
        "Max steps reached. Write the final OSINT report now based only on actual findings. "
        "No placeholder values."
    )})
    final = ollama.chat(model='qwen2.5', messages=messages)
    return final.message.content


# ── MAIN ENTRY POINT ───────────────────────────────────────────────────────────
def generate_response(prompt, history=None):
    if history is None:
        history = []

    intent_check = ollama.chat(
        model='qwen2.5',
        messages=[
            {'role': 'system', 'content': (
                "Reply with only 'OSINT' if the user wants to investigate/search/find info about "
                "a person, email, username, domain, IP, or phone number. "
                "Reply with only 'CHAT' for everything else."
            )},
            {'role': 'user', 'content': prompt}
        ]
    )

    intent = intent_check.message.content.strip().upper()

    if "OSINT" not in intent:
        messages = [
            {'role': 'system', 'content': "You are a helpful OSINT assistant."}
        ] + history + [{'role': 'user', 'content': prompt}]
        response = ollama.chat(model='qwen2.5', messages=messages)
        return response.message.content

    print("--- [LOG] OSINT query detected, starting ReAct loop... ---")
    return react_loop(prompt)