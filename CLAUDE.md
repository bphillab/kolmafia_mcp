# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A [FastMCP](https://github.com/jlowin/fastmcp) server that exposes KoLMafia's relay API as MCP tools and resources, letting Claude interact with the Kingdom of Loathing game client.

## Commands

```bash
# Install (editable)
pip install -e .

# Run the MCP server
kolmafia-mcp
# or
python -m kolmafia_mcp.server
```

No test suite or linter is configured.

## Architecture

Three modules with a simple linear dependency:

**`server.py`** — FastMCP app. Defines all MCP tools (`submit_gcli`, `get_status`, `get_effects`, `search_inventory`) and resources (`kolmafia://inventory`, `kolmafia://equipment`). Each tool/resource delegates entirely to `relay.py`.

**`relay.py`** — Async HTTP client (httpx) that talks to KoLMafia's relay server at `localhost:60080`. Calls `api.php?what={status,effects,inventory}` for game state and `KoLmafia/submitCommand` for gCLI commands. Fetches and caches a `pwd_hash` from `charpane.php` on first use — this hash is required for all mutating requests.

**`items.py`** — Resolves numeric item IDs (returned by the relay API) to human-readable names. Reads KoLMafia's `data/items.txt` from inside the KoLMafia JAR. Searches for the JAR in `/Applications/KoLmafia.app/Contents/app/`, `~/Desktop/KolMafia/`, and `~/Downloads/`. Result is cached for the process lifetime via `@lru_cache`.

**Data flow:** MCP client → `server.py` tool handler → `relay.py` HTTP call → KoLMafia relay (localhost:60080) → JSON parsed, item IDs resolved via `items.py` → result returned to client.
