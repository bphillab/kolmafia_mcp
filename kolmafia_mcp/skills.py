"""Load skill and effect data from KoLMafia's bundled data files."""

import glob
import html
import os
import re
import zipfile
from dataclasses import dataclass
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


@dataclass(frozen=True)
class CastableBuff:
    skill_name: str
    effect_name: str
    mp_cost: int
    duration: int   # turns; 0 = unknown/variable
    tags: frozenset


@lru_cache(maxsize=1)
def _load_skill_data() -> dict[str, tuple[int, int, frozenset]]:
    """Return {skill_name: (mp_cost, duration, tags)} from classskills.txt."""
    jar_path = _find_kolmafia_jar()
    if not jar_path:
        return {}
    result: dict[str, tuple[int, int, frozenset]] = {}
    try:
        with zipfile.ZipFile(jar_path) as zf:
            with zf.open("data/classskills.txt") as f:
                for raw_line in f:
                    line = raw_line.decode("utf-8").strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) < 5:
                        continue
                    try:
                        name = html.unescape(parts[1])
                        tags = frozenset(t.strip() for t in parts[3].split(","))
                        mp_cost = int(parts[4])
                        duration = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0
                        result[name] = (mp_cost, duration, tags)
                    except (ValueError, IndexError):
                        pass
    except Exception:
        pass
    return result


@lru_cache(maxsize=1)
def _load_cast_effect_map() -> dict[str, str]:
    """Return {skill_name: effect_name} from statuseffects.txt default actions."""
    jar_path = _find_kolmafia_jar()
    if not jar_path:
        return {}
    result: dict[str, str] = {}
    try:
        with zipfile.ZipFile(jar_path) as zf:
            with zf.open("data/statuseffects.txt") as f:
                for raw_line in f:
                    line = raw_line.decode("utf-8").strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) < 7:
                        continue
                    effect_name = html.unescape(parts[1])
                    # default_action may be pipe-delimited; grab first cast action
                    for action in parts[6].split("|"):
                        action = action.strip()
                        # "cast 1 SkillName" or "cast 1 SkillName ^ AltName"
                        m = re.match(r"^cast \d+ (.+?)(?:\s*\^.*)?$", action)
                        if m:
                            skill_name = html.unescape(m.group(1).strip())
                            result[skill_name] = effect_name
                            break
    except Exception:
        pass
    return result


@lru_cache(maxsize=1)
def all_castable_buffs() -> dict[str, CastableBuff]:
    """Return {skill_name: CastableBuff} for every skill that grants a buff via casting."""
    skill_data = _load_skill_data()
    cast_map = _load_cast_effect_map()

    result: dict[str, CastableBuff] = {}
    for skill_name, effect_name in cast_map.items():
        mp_cost, duration, tags = skill_data.get(skill_name, (0, 0, frozenset()))
        result[skill_name] = CastableBuff(
            skill_name=skill_name,
            effect_name=effect_name,
            mp_cost=mp_cost,
            duration=duration,
            tags=tags,
        )
    return result
