"""Load item ID → name mapping from KoLMafia's bundled data/items.txt."""

import glob
import os
import zipfile
from functools import lru_cache

_JAR_SEARCH_PATHS = [
    "/Applications/KoLmafia.app/Contents/app/",
    os.path.expanduser("~/Desktop/KolMafia/"),
    os.path.expanduser("~/Downloads/"),
]


def _find_kolmafia_jar() -> str | None:
    for directory in _JAR_SEARCH_PATHS:
        jars = sorted(
            glob.glob(os.path.join(directory, "KoLmafia*.jar")),
            key=os.path.getmtime,
            reverse=True,
        )
        if jars:
            return jars[0]
    return None


@lru_cache(maxsize=1)
def load() -> dict[str, str]:
    """
    Returns {str(item_id): item_name} for all items in KoLMafia's database.
    Result is cached for the process lifetime.
    """
    jar_path = _find_kolmafia_jar()
    if not jar_path:
        return {}

    result: dict[str, str] = {}
    try:
        with zipfile.ZipFile(jar_path) as zf:
            with zf.open("data/items.txt") as f:
                for raw_line in f:
                    line = raw_line.decode("utf-8").strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) < 2:
                        continue
                    try:
                        item_id = str(int(parts[0]))
                        result[item_id] = parts[1]
                    except ValueError:
                        pass
    except Exception:
        pass

    return result


def name_for(item_id: int | str) -> str:
    """Return item name for the given ID, or 'item#<id>' if unknown."""
    return load().get(str(item_id), f"item#{item_id}")
