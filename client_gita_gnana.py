# client_gita_gnana.py
"""
Client script for interacting with the Gita Gnana MCP server.
It demonstrates connecting via FastMCP's async Client, listing available tools,
and calling the server's RPCs:
- get_pdf_text()
- answer(question)
- update_system_prompt(new_prompt)

Run the server (gita_gnana_server.py) first. The client will automatically
detect the transport (stdio) when pointing at the script path.
"""

import asyncio
import os
import json
from pathlib import Path

# Import the FastMCP client. The package name may differ depending on the
# installation; adjust if necessary.
try:
    from fastmcp import Client  # type: ignore
except ImportError as e:
    raise ImportError(
        "FastMCP client library not found. Install it with 'pip install fastmcp'."
    ) from e

# Path to the server script. Using the same directory ensures the stdio transport
# works out‑of‑the‑box.
SERVER_SCRIPT = Path(__file__).with_name("gita_gnana_server.py")
# Allow overriding transport via environment variable. If MCP_SERVER_URL is set, use it as the endpoint.
SERVER_URL = os.getenv("MCP_SERVER_URL")


async def list_tools(client: Client):
    """Print the list of tools exposed by the server."""
    tools = await client.list_tools()
    print("Available tools:")
    if isinstance(tools, dict):
        for name, meta in tools.items():
            print(f" - {name}: {meta.get('description', '')}")
    else:
        for tool in tools:
            print(f" - {tool.name}: {getattr(tool, 'description', '')}")

async def call_tool(client: Client, name: str, **params):
    """Call a tool and pretty‑print the JSON result."""
    result = await client.call_tool(name, params)
    # The server may return plain strings, but we format everything as JSON for
    # readability.
    print(f"\nResult of {name}({json.dumps(params)}):")
    if isinstance(result, (dict, list)):
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result)

async def main():
    # The client infers the transport (stdio) from the file path.
    # Determine transport: if SERVER_URL is set, connect via HTTP, else use stdio with script.
    if SERVER_URL:
        client = Client(SERVER_URL)
    else:
        client = Client(str(SERVER_SCRIPT))
    async with client:
        # Basic connectivity check
        await client.ping()
        await list_tools(client)

        # 1. Fetch PDF text (truncated for display)
        await call_tool(client, "get_pdf_text")

        # 3. Ask a question
        question = "What is the purpose of the Bhagavad Gita according to the PDF?"
        await call_tool(client, "answer", question=question)

        # 4. Update the system prompt (optional demo)
        new_prompt = (
            "You are a concise assistant. Answer using only the provided sources. "
            "If the answer is not present, reply with 'I don't know.'"
        )
        await call_tool(client, "update_system_prompt", new_prompt=new_prompt)
        # Verify the update by calling answer again
        await call_tool(client, "answer", question="What is your new instruction?")

if __name__ == "__main__":
    asyncio.run(main())
