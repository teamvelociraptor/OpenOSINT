import subprocess

def search_domain(domain):
    """Run sublist3r to find subdomains for a domain."""
    try:
        result = subprocess.run(["sublist3r", "-d", domain], capture_output=True, text=True)
        output = result.stdout or result.stderr
        found = [line.strip() for line in output.splitlines() if line.strip() and not line.startswith("[")]
        if found:
            return "Subdomains found:\n" + "\n".join(found)
        else:
            return "No subdomains found for this domain."
    except Exception as e:
        return f"Error: {str(e)}"