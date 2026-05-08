import subprocess

def search_username(username):
    """Run sherlock to find social accounts associated with a username."""
    try:
        result = subprocess.run(["sherlock", username], capture_output=True, text=True)
        output = result.stdout or result.stderr
        # Parse only found results
        found = [line.strip() for line in output.splitlines() if "[+]" in line]
        if found:
            return "Accounts found:\n" + "\n".join(found)
        else:
            return "No accounts found for this username."
    except Exception as e:
        return f"Error: {str(e)}"