import subprocess

def search_phone(phone):
    """Run phoneinfoga to gather info on a phone number."""
    try:
        result = subprocess.run(
            ["phoneinfoga", "scan", "-n", phone],
            capture_output=True, text=True
        )
        output = result.stdout or result.stderr
        found = [line.strip() for line in output.splitlines() if line.strip()]
        return "\n".join(found) if found else "No results found for this phone number."
    except Exception as e:
        return f"Error: {str(e)}"
