import requests

HIBP_API_KEY = "YOUR_API_KEY_HERE"  # https://haveibeenpwned.com/API/Key

def search_breach(email):
    """Check if an email appears in known data breaches via HaveIBeenPwned."""
    try:
        headers = {
            "hibp-api-key": HIBP_API_KEY,
            "user-agent": "OpenOSINT"
        }
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false"
        response = requests.get(url, headers=headers)

        if response.status_code == 404:
            return "No breaches found for this email."
        elif response.status_code == 401:
            return "Error: Invalid HIBP API key."
        elif response.status_code != 200:
            return f"Error: HTTP {response.status_code}"

        breaches = response.json()
        lines = [f"[+] Found in {len(breaches)} breach(es):"]
        for b in breaches:
            lines.append(
                f"  - {b['Name']} ({b['BreachDate']}) — "
                f"leaked: {', '.join(b['DataClasses'][:4])}"
            )
        return "\n".join(lines)

    except Exception as e:
        return f"Error: {str(e)}"
