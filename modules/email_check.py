import subprocess
import re

def search_email(email):
    """Run holehe and return only confirmed hits."""
    try:
        result = subprocess.run(["holehe", email], capture_output=True, text=True)
        output = result.stdout or result.stderr

        # Parse only lines with [+] (found) from holehe output
        found = [line.strip() for line in output.splitlines() if line.strip().startswith("[+]")]

        if found:
            return "Accounts found:\n" + "\n".join(found)
        else:
            return "No accounts found for this email."

    except Exception as e:
        return f"Error: {str(e)}"