"""GET /dashboard — session-gated web dashboard landing page.

Plain HTMLResponse strings, no template engine — not worth adding Jinja2 for
a handful of small pages. The HTML returned here is fully static; no
user-controlled data (email, provider, plan URLs) is ever interpolated into
it server-side. All personalization happens client-side via fetch() against
the existing JSON API (/v1/me, /v1/checkout) and is rendered with
textContent / href assignment rather than innerHTML, so provider-supplied
fields like email — which are attacker-influenceable — never become HTML.

/v1/checkout's contract is untouched (it's used publicly today per
CLOUD.md); the ?reference_id={user.id} param is appended here instead,
client-side, using the id this page already has from /v1/me.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from cloud.session_auth import get_current_user

router = APIRouter()

_PLANS = ["payg", "starter", "pro"]

_DASHBOARD_HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>OpenOSINT Cloud — Dashboard</title></head>
<body>
<h1>Dashboard</h1>
<p id="account">Loading account…</p>
<h2>Upgrade / buy credits</h2>
<ul id="checkout-links"></ul>
<script>
const PLANS = """ + json.dumps(_PLANS) + """;

async function loadAccount() {
  const resp = await fetch("/v1/me");
  if (!resp.ok) {
    document.getElementById("account").textContent = "Not logged in.";
    return null;
  }
  return resp.json();
}

async function renderCheckoutLinks(userId) {
  const list = document.getElementById("checkout-links");
  for (const plan of PLANS) {
    const resp = await fetch("/v1/checkout?plan=" + encodeURIComponent(plan));
    if (!resp.ok) continue;
    const data = await resp.json();
    const sep = data.url.includes("?") ? "&" : "?";
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = data.url + sep + "reference_id=" + encodeURIComponent(userId);
    a.textContent = plan + " (" + data.credits + " credits)";
    li.appendChild(a);
    list.appendChild(li);
  }
}

(async () => {
  const me = await loadAccount();
  if (!me) return;
  const account = document.getElementById("account");
  account.textContent = "Logged in as " + (me.email || me.provider) +
    " — " + (me.linked ? "billing linked" : "billing not linked");
  await renderCheckoutLinks(me.id);
})();
</script>
</body>
</html>"""


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(user=Depends(get_current_user)) -> HTMLResponse:
    return HTMLResponse(_DASHBOARD_HTML)
