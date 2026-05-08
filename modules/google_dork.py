import urllib.parse

def generate_dorks(target):
    """Generate Google dork URLs for a given target (name, email, username, domain)."""
    dorks = [
        f'"{target}"',
        f'"{target}" site:linkedin.com',
        f'"{target}" site:facebook.com',
        f'"{target}" site:twitter.com',
        f'"{target}" site:instagram.com',
        f'"{target}" filetype:pdf',
        f'"{target}" inurl:profile',
        f'"{target}" leaked OR breach OR dump',
        f'"{target}" resume OR cv',
        f'intitle:"{target}"',
    ]
    base = "https://www.google.com/search?q="
    lines = ["[+] Google Dork URLs:"]
    for dork in dorks:
        encoded = urllib.parse.quote(dork)
        lines.append(f"  {dork}\n    → {base}{encoded}")
    return "\n".join(lines)
