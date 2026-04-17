"""KoLMafia MCP server — stdio transport."""

import json

import httpx
from mcp.server.fastmcp import FastMCP

from kolmafia_mcp import relay

mcp = FastMCP("KoLMafia")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def submit_gcli(command: str) -> str:
    """
    Submit a gCLI command to KoLMafia and return its output.

    Examples: 'status', 'buy 1 meat paste', 'use 1 milk of magnesium',
              'equip seal-clubbing club', 'adventure 5 Haunted Pantry'
    """
    try:
        return await relay.submit_gcli(command)
    except httpx.ConnectError:
        return "Error: could not connect to KoLMafia relay (is KoLMafia running?)"
    except httpx.HTTPStatusError as e:
        return f"Error: relay returned HTTP {e.response.status_code}"


@mcp.tool()
async def get_status() -> str:
    """
    Return current player status: HP, MP, level, class, meat, adventures
    remaining, current location, and familiar.
    """
    try:
        data = await relay.get_status()
        return json.dumps(data, indent=2)
    except httpx.ConnectError:
        return "Error: could not connect to KoLMafia relay (is KoLMafia running?)"
    except Exception as e:
        return f"Error fetching status: {e}"


@mcp.tool()
async def get_effects() -> str:
    """
    Return all currently active effects and their remaining turns.
    """
    try:
        data = await relay.get_effects()
        if not data:
            return "No active effects."
        lines = [f"{name}: {turns} turns" for name, turns in sorted(data.items())]
        return "\n".join(lines)
    except httpx.ConnectError:
        return "Error: could not connect to KoLMafia relay (is KoLMafia running?)"
    except Exception as e:
        return f"Error fetching effects: {e}"


@mcp.tool()
async def search_inventory(query: str) -> str:
    """
    Search inventory for items whose names contain the query string
    (case-insensitive). Returns matching items with their quantities.
    """
    try:
        data = await relay.get_inventory()
    except httpx.ConnectError:
        return "Error: could not connect to KoLMafia relay (is KoLMafia running?)"
    except Exception as e:
        return f"Error fetching inventory: {e}"

    q = query.lower()
    matches = {k: v for k, v in data.items() if q in str(k).lower()}

    if not matches:
        return f"No inventory items matching '{query}'."
    lines = [f"{name}: {qty}" for name, qty in sorted(matches.items())]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("kolmafia://inventory")
async def inventory_resource() -> str:
    """
    Full inventory listing, sorted alphabetically and formatted as
    'item name: quantity' per line. Use the search_inventory tool
    when you only need a specific item.
    """
    try:
        data = await relay.get_inventory()
    except httpx.ConnectError:
        return "Error: could not connect to KoLMafia relay (is KoLMafia running?)"
    except Exception as e:
        return f"Error fetching inventory: {e}"

    if not data:
        return "Inventory is empty."

    lines = [f"{name}: {qty}" for name, qty in sorted(data.items())]
    header = f"Inventory ({len(data)} unique items)\n" + "-" * 40
    return header + "\n" + "\n".join(lines)


@mcp.resource("kolmafia://equipment")
async def equipment_resource() -> str:
    """Currently equipped items by slot."""
    try:
        data = await relay.get_equipment()
    except httpx.ConnectError:
        return "Error: could not connect to KoLMafia relay (is KoLMafia running?)"
    except Exception as e:
        return f"Error fetching equipment: {e}"

    if not data:
        return "Nothing equipped."
    lines = [f"{slot}: {item}" for slot, item in sorted(data.items())]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
