import requests

def search_ip(ip):
    """Geolocate and gather ASN info for an IP via ipinfo.io (free tier)."""
    try:
        response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=10)
        if response.status_code != 200:
            return f"Error: HTTP {response.status_code}"

        data = response.json()
        lines = ["[+] IP Info:"]
        fields = ["ip", "hostname", "org", "city", "region", "country", "loc", "timezone"]
        for f in fields:
            if f in data:
                lines.append(f"  {f.capitalize()}: {data[f]}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"
