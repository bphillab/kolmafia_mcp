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


async def _gcli_capture(command: str) -> str:
    """Submit a gCLI command and return the stripped text output."""
    pwd = await _get_pwd_hash()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{RELAY_BASE}/KoLmafia/submitCommand",
            data={"cmd": command, "pwd": pwd},
            headers={"Referer": f"{RELAY_BASE}/"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
    return _strip_html(resp.text)


async def submit_gcli(command: str) -> str:
    return await _gcli_capture(command)


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



async def get_skills() -> str:
    """
    Scrapes charsheet.php and extracts skill names grouped by section.
    Skills link to desc_skill.php?whichskill=N via href or onClick.
    Section headers appear as <b>... Skills</b>.
    """
    import re
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{RELAY_BASE}/charsheet.php", timeout=TIMEOUT)
        resp.raise_for_status()
    raw = resp.text
    if not raw:
        return "charsheet.php returned an empty response."

    # Split on section headers like <b>Combat Skills</b> or <b>Seal Clubber Skills</b>
    parts = re.split(r'<b>([^<]*[Ss]kills?[^<]*)</b>', raw)

    if len(parts) < 3:
        names = re.findall(r'<a[^>]+desc_skill\.php[^>]*>([^<]+)</a>', raw)
        return "\n".join(sorted(set(names))) if names else "No skills found in charsheet."

    lines: list[str] = []
    # parts = [pre, header1, body1, header2, body2, ...]
    for i in range(1, len(parts) - 1, 2):
        header = parts[i].strip()
        body = parts[i + 1]
        names = re.findall(r'<a[^>]+desc_skill\.php[^>]*>([^<]+)</a>', body)
        if names:
            lines.append(header)
            lines.extend(f"  {n}" for n in names)
    return "\n".join(lines) if lines else "No skills found in charsheet."


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
