import argparse
import asyncio
import sys
import logging

# Import the core OSINT tools
from openosint.tools.search_email import run_email_osint
from openosint.tools.search_username import run_username_osint # <-- AGGIUNTA

# ---------------------------------------------------------------------------
# CLI Configuration & Parsing
# ---------------------------------------------------------------------------
def setup_cli_logging(verbose: bool) -> None:
    """
    Configures logging based on the verbosity flag.
    Hides internal debug messages unless explicitly requested by the user.
    """
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")

def create_parser() -> argparse.ArgumentParser:
    """
    Constructs the command-line argument parser using sub-commands
    for easy scalability when new OSINT tools are added.
    """
    parser = argparse.ArgumentParser(
        prog="openosint",
        description="OpenOSINT - Command Line Interface for direct tool execution.",
        epilog="Example: python cli.py email target@example.com"
    )
    
    # Global arguments
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Enable verbose output for debugging"
    )
    
    # Subparsers for different OSINT modules
    subparsers = parser.add_subparsers(
        dest="command", 
        required=True, 
        help="Available OSINT commands"
    )
    
    # Module 1: Email OSINT
    email_parser = subparsers.add_parser(
        "email", 
        help="Run an OSINT scan on a specific email address"
    )
    email_parser.add_argument(
        "target", 
        type=str, 
        help="The target email address (e.g., target@example.com)"
    )
    email_parser.add_argument(
        "-t", "--timeout", 
        type=int, 
        default=120, 
        help="Maximum execution time in seconds (default: 120)"
    )
    
    # Module 2: Username OSINT
    username_parser = subparsers.add_parser(
        "username", 
        help="Run an OSINT scan on a specific username across multiple platforms"
    )
    username_parser.add_argument(
        "target", 
        type=str, 
        help="The target username (e.g., johndoe99)"
    )
    username_parser.add_argument(
        "-t", "--timeout", 
        type=int, 
        default=180, 
        help="Maximum execution time in seconds (default: 180)"
    )
    
    # Module 2: Placeholder for future tools (e.g., username, domain)
    # username_parser = subparsers.add_parser("username", help="...")
    
    return parser

# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------
async def execute_email_scan(target: str, timeout: int) -> None:
    """
    Handles the UI/UX wrapper around the core email OSINT logic.
    """
    print(f"[*] Initializing OSINT scan for: {target}")
    print(f"[*] Timeout set to: {timeout} seconds. Please wait...\n")
    
    try:
        # Call the core business logic
        result = await run_email_osint(email=target, timeout_seconds=timeout)
        
        # Present the output cleanly to the human user
        print("=" * 60)
        print(" [+] SCAN RESULTS ".center(60, "="))
        print("=" * 60)
        print(result)
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[!] CRITICAL ERROR: Could not complete the scan.\nDetails: {e}", file=sys.stderr)
        sys.exit(1)
        
        
async def execute_username_scan(target: str, timeout: int) -> None:
    print(f"[*] Initializing OSINT scan for username: {target}")
    print(f"[*] Timeout set to: {timeout} seconds. Please wait...\n")
    try:
        result = await run_username_osint(username=target, timeout_seconds=timeout)
        print("=" * 60)
        print(" [+] SCAN RESULTS ".center(60, "="))
        print("=" * 60)
        print(result)
        print("=" * 60)
    except Exception as e:
        print(f"\n[!] CRITICAL ERROR: {e}", file=sys.stderr)
        sys.exit(1)

# ---------------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------------
async def async_main() -> None:
    """Main asynchronous flow orchestrator."""
    parser = create_parser()
    args = parser.parse_args()
    
    setup_cli_logging(args.verbose)
    
    # Route to the correct handler based on user command
    if args.command == "email":
        await execute_email_scan(args.target, args.timeout)
    else:
        # Fallback (argparse 'required=True' usually catches this first)
        parser.print_help()
        sys.exit(1)

def main() -> None:
    """
    Synchronous wrapper to handle the asyncio event loop and 
    global OS interrupts (like Ctrl+C).
    """
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C instead of a massive Python traceback
        print("\n\n[!] Operation cancelled by the user. Exiting...", file=sys.stderr)
        sys.exit(130)

if __name__ == "__main__":
    main()