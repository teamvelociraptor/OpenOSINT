import subprocess
import os

def search_metadata(filepath):
    """Extract metadata from a file using exiftool."""
    if not os.path.exists(filepath):
        return f"Error: File not found — {filepath}"
    try:
        result = subprocess.run(
            ["exiftool", filepath],
            capture_output=True, text=True
        )
        output = result.stdout or result.stderr
        lines = [f"[+] Metadata for {os.path.basename(filepath)}:"]
        for line in output.splitlines():
            if line.strip():
                lines.append(f"  {line.strip()}")
        return "\n".join(lines) if len(lines) > 1 else "No metadata found."
    except Exception as e:
        return f"Error: {str(e)}"
