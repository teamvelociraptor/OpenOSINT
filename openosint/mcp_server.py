# openosint/mcp_server.py

import asyncio
import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, CallToolResult

# Import the core business logic
from openosint.tools.search_email import run_email_osint
from openosint.tools.search_username import run_username_osint

# ---------------------------------------------------------------------------
# Configuration & Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format='[MCP Server] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server Initialization
# ---------------------------------------------------------------------------
app = Server("openosint")

# ---------------------------------------------------------------------------
# Tool Discovery (Exposed to the LLM)
# ---------------------------------------------------------------------------
@app.list_tools()
async def list_tools() -> List[Tool]:
    """
    Registers and exposes available OSINT tools to the connected AI agent.
    The 'description' field is critical as it acts as the system prompt for the LLM.
    """
    return [
        Tool(
            name="search_email",
            description=(
                "Search for accounts, forums, and services associated with an email address. "
                "Use this tool to map a target's online presence."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "The target email address (e.g., target@example.com)"
                    }
                },
                "required": ["email"]
            }
        ),
        Tool(
            name="search_username",
            description=(
                "Search for a specific username across hundreds of social networks, "
                "forums, and web services. Useful for tracking an alias."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "The target username or alias (e.g., darkhacker99)"
                    }
                },
                "required": ["username"]
            }
        )
        # Future tools (e.g., search_username) will be appended here.
    ]

# ---------------------------------------------------------------------------
# Tool Execution & Routing
# ---------------------------------------------------------------------------
@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """
    Acts as the main router for incoming tool execution requests from the LLM.
    Validates arguments and delegates to specific private handler functions.
    """
    logger.info(f"Received execution request for tool: '{name}'")
    
    try:
        # Route: search_email
        if name == "search_email":
            return await _handle_search_email(arguments)
        elif name == "search_username":
            return await _handle_search_username(arguments)
            
        # Fallback for unknown tools
        logger.warning(f"Unknown tool requested by AI: {name}")
        raise ValueError(f"Tool '{name}' is not supported by this server.")

    except ValueError as ve:
        # Handled validation errors (e.g., missing params by the LLM)
        logger.error(f"Validation Error: {ve}")
        return _create_tool_response(f"Validation Error: {str(ve)}", is_error=True)
        
    except Exception as e:
        # Unhandled execution errors
        logger.exception(f"Unexpected system error while executing {name}.")
        return _create_tool_response(f"Internal System Error: {str(e)}", is_error=True)

# ---------------------------------------------------------------------------
# Specific Tool Handlers (Private functions)
# ---------------------------------------------------------------------------
async def _handle_search_email(arguments: Dict[str, Any]) -> CallToolResult:
    """
    Specific execution handler for the 'search_email' tool.
    Extracts parameters, enforces business rules, and calls the core OSINT logic.
    """
    email = arguments.get("email")
    
    # Fail fast: Validate required parameters from the LLM payload
    if not email:
        raise ValueError("The 'email' parameter is strictly required.")

    logger.info(f"Delegating to core logic for target: {email}")
    
    # Execute the OSINT scan (Timeout handled safely by the core logic)
    result_text = await run_email_osint(email, timeout_seconds=120)
    
    return _create_tool_response(result_text)

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------
def _create_tool_response(text: str, is_error: bool = False) -> CallToolResult:
    """
    Helper function to wrap raw string outputs into the strict MCP CallToolResult schema.
    
    Args:
        text (str): The payload (result or error message).
        is_error (bool): Set to True if the LLM should treat this as a tool failure.
    """
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        isError=is_error
    )
    
async def _handle_search_username(arguments: Dict[str, Any]) -> CallToolResult:
    username = arguments.get("username")
    if not username:
        raise ValueError("The 'username' parameter is strictly required.")
    
    logger.info(f"Delegating to core logic for username: {username}")
    result_text = await run_username_osint(username, timeout_seconds=180)
    return _create_tool_response(result_text)

# ---------------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------------
async def main() -> None:
    """
    Initializes and runs the MCP server over Standard I/O.
    This is the standard communication protocol for local AI clients (e.g., Claude Code).
    """
    logger.info("Starting OpenOSINT MCP Server via stdio...")
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, 
            write_stream, 
            app.create_initialization_options()
        )

if __name__ == "__main__":
    # The server is started asynchronously
    asyncio.run(main())