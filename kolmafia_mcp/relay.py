"""HTTP client for the KoLMafia relay server (localhost:60080)."""

import re
from html.parser import HTMLParser
from typing import Any

import httpx

from kolmafia_mcp import items as item_db

RELAY_BASE = "http://localhost:60080"
TIMEOUT = 30.0

# Cached per process lifetime — valid as long as the KoLMafia session is open.
_pwd_hash: str | None = None


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def _strip_html(text: str) -> str:
    if "<" not in text:
        return text.strip()
    stripper = _HTMLStripper()
    stripper.feed(text)
    return stripper.get_text()


async def _api_get(what: str) -> Any:
    """Call api.php — returns parsed JSON. Does not require pwd."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{RELAY_BASE}/api.php",
            params={"what": what, "for": "KoLMafia-MCP"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()


async def _get_pwd_hash() -> str:
    """
    Fetch and cache the session password hash from charpane.php.
    KoLMafia embeds it as: var pwdhash = "<hash>";
    """
    global _pwd_hash
    if _pwd_hash:
        return _pwd_hash
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{RELAY_BASE}/charpane.php", timeout=TIMEOUT)
        resp.raise_for_status()
    match = re.search(r'var pwdhash\s*=\s*"([a-f0-9]+)"', resp.text)
    if not match:
        raise RuntimeError(
            "Could not find pwdhash in charpane.php — is a character logged in to KoLMafia?"
        )
    _pwd_hash = match.group(1)
    return _pwd_hash


async def submit_gcli(command: str) -> str:
    """
    Submit a gCLI command to KoLMafia.
    Output appears in KoLMafia's CLI window; it cannot be captured via HTTP.
    Returns a confirmation string.
    """
    pwd = await _get_pwd_hash()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{RELAY_BASE}/KoLmafia/submitCommand",
            data={"cmd": command, "pwd": pwd},
            headers={"Referer": f"{RELAY_BASE}/"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    return f"Command submitted: {command!r}  (output visible in KoLMafia's CLI window)"


async def get_status() -> dict:
    return await _api_get("status")


async def get_effects() -> dict:
    """
    Returns a flat {effect_name: turns_remaining} dict.
    Effects are embedded in the status response under the "effects" key.
    Each value is an array: [name, turns, type, source, id].
    """
    status = await _api_get("status")
    raw: dict = status.get("effects", {})
    return {v[0]: v[1] for v in raw.values()}


async def get_inventory() -> dict[str, int]:
    """
    Returns {item_name: quantity}.
    Uses api.php?what=inventory for IDs, then resolves names from the JAR.
    """
    raw = await _api_get("inventory")
    return {item_db.name_for(item_id): int(qty) for item_id, qty in raw.items()}


_SKILL_TYPES = {
    0: "Passive",
    1: "Noncombat",
    2: "Buff",
    3: "Combat",
    4: "Summon",
    5: "Other",
    6: "Song",
    7: "Combat Passive",
    8: "Expression",
    9: "Walk",
}


async def get_skills() -> list[dict]:
    """
    Returns a list of known skills, each with name, type, mp_cost, and
    duration (turns; 0 for non-buffs). Sourced from api.php?what=skills.
    Each raw value is an array: [name, type_id, mp_cost, duration, ...].
    """
    raw: dict = await _api_get("skills")
    skills = []
    for v in raw.values():
        skills.append({
            "name": v[0],
            "type": _SKILL_TYPES.get(v[1], f"type_{v[1]}"),
            "mp_cost": v[2],
            "duration": v[3],
        })
    return sorted(skills, key=lambda s: s["name"])


async def get_equipment() -> dict[str, str]:
    """
    Returns {slot: item_name}.
    Equipment slot→item_id is embedded in the status response.
    """
    status = await _api_get("status")
    equipment: dict = status.get("equipment", {})
    result: dict[str, str] = {}
    for slot, item_id in equipment.items():
        # "fakehands" is an integer count, not an item ID — skip it.
        if slot == "fakehands":
            continue
        if item_id and str(item_id) != "0":
            result[slot] = item_db.name_for(item_id)
    return result
