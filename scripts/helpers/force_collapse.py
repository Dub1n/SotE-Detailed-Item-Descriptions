import json
from pathlib import Path
from typing import Dict


def load_force_collapse_map(path: Path) -> Dict[str, str]:
    """
    Load a mapping of Name -> forced group label from a JSON list of pairs.
    Each entry should be a list of at least two Name strings to collapse
    together. Example:
      [
        ["Name A", "Name B"],
        ["Another", "Pair"]
      ]
    """
    mapping: Dict[str, str] = {}
    if not path.exists():
        return mapping
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(
            f"force-collapsed file must be a list, got {type(data).__name__}"
        )
    for entry in data:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        names = [name for name in entry if isinstance(name, str) and name]
        if len(names) < 2:
            continue
        group_id = " | ".join(sorted(names))
        for name in names:
            mapping[name] = group_id
    return mapping
