import whois

def search_whois(domain):
    """Run WHOIS lookup on a domain."""
    try:
        w = whois.whois(domain)
        lines = ["[+] WHOIS Results:"]
        fields = {
            "Domain":      w.domain_name,
            "Registrar":   w.registrar,
            "Created":     w.creation_date,
            "Expires":     w.expiration_date,
            "Updated":     w.updated_date,
            "Name Servers": w.name_servers,
            "Emails":      w.emails,
            "Org":         w.org,
            "Country":     w.country,
        }
        for key, val in fields.items():
            if val:
                if isinstance(val, list):
                    val = val[0] if len(val) == 1 else ", ".join(str(v) for v in val[:3])
                lines.append(f"  {key}: {val}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"
