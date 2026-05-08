import requests

def search_paste(query):
    """Search Pastebin dumps via psbdmp.ws for an email or username."""
    try:
        response = requests.get(
            f"https://psbdmp.ws/api/search/{query}",
            timeout=10
        )
        if response.status_code != 200:
            return f"Error: HTTP {response.status_code}"

        data = response.json()
        if not data or not data.get("data"):
            return "No pastes found."

        lines = [f"[+] Found in {len(data['data'])} paste(s):"]
        for paste in data["data"][:10]:  # limit to 10
            lines.append(f"  - https://pastebin.com/{paste['id']} ({paste.get('time', 'unknown date')})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"
