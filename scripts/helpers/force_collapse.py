import json
from pathlib import Path
from typing import Dict, Tuple


def load_force_collapse_map(path: Path) -> Tuple[Dict[str, str], Dict[str, Dict[str, str]]]:
    """
    Load force-collapse rules from JSON. Supports two formats:
      - List of Name strings (length >= 2)
      - Object with {"names": [...], "overrides": {"Col": "Value"}}
    Returns (name_to_group, group_overrides).
    """
    name_to_group: Dict[str, str] = {}
    group_overrides: Dict[str, Dict[str, str]] = {}
    if not path.exists():
        return name_to_group, group_overrides
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(
            f"force-collapsed file must be a list, got {type(data).__name__}"
        )
    for entry in data:
        if isinstance(entry, list):
            names = [name for name in entry if isinstance(name, str) and name]
            overrides: Dict[str, str] = {}
        elif isinstance(entry, dict):
            names = [
                name
                for name in entry.get("names", [])
                if isinstance(name, str) and name
            ]
            overrides = {
                k: v
                for k, v in (entry.get("overrides") or {}).items()
                if isinstance(k, str) and isinstance(v, str)
            }
        else:
            continue

        if len(names) < 2:
            continue
        group_id = " | ".join(sorted(names))
        for name in names:
            name_to_group[name] = group_id
        if overrides:
            group_overrides[group_id] = overrides
    return name_to_group, group_overrides
