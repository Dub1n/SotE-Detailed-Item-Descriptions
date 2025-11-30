import json
import re
from pathlib import Path

ITEMS_INDEX = Path("work/items_index.json")
READY_DIR = Path("work/responses/ready")
OUTPUT = Path("work/responses/ready/ashes_generated.json")


def load_items_index():
    return json.loads(ITEMS_INDEX.read_text(encoding="utf-8"))


def normalize(name: str) -> str:
    """Lowercase and strip non-alphanumerics for loose matching."""
    return re.sub(r"[^a-z0-9]+", "", name.lower()) if name else ""


def dedupe(seq):
    seen = set()
    for item in seq:
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        yield item


def load_skill_info_map():
    """
    Map skill name -> info, plus a normalized lookup for aliases.

    We only read from the ready skill JSONs because the base bundle
    may be absent; mod/real_dlc hold the data currently on disk.
    """
    skill_data = {}
    normalized = {}
    for path in sorted(READY_DIR.glob("*skill*merged_sorted*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for obj in data:
            if not isinstance(obj, dict):
                continue
            if obj.get("category") != "skill":
                continue
            name = (obj.get("name") or "").strip()
            info = obj.get("info")
            caption = obj.get("caption")
            if not name or not info:
                continue
            skill_data[name] = {"info": info, "caption": caption}
            norm = normalize(name)
            if norm:
                normalized.setdefault(norm, []).append((name, info, caption))
    # pick the longest info string per normalized key to break ties
    normalized_best = {}
    for key, entries in normalized.items():
        name, info, caption = max(entries, key=lambda entry: len(entry[1]))
        normalized_best[key] = (name, {"info": info, "caption": caption})
    return skill_data, normalized_best


def extract_boilerplate(vanilla_caption: str) -> tuple[str, str]:
    """
    Split vanilla caption into:
      boilerplate (affinity / lead-in)
      usable_on (if present)
    Strip out the quoted skill block when present.
    """
    usable_on = ""
    usable_match = re.search(r"(Usable on[\s\S]*)", vanilla_caption, re.IGNORECASE)
    if usable_match:
        usable_on = usable_match.group(1).strip()
        vanilla_caption = vanilla_caption[: usable_match.start()].rstrip()

    # Remove quoted skill description block if present.
    quoted_block = re.search(r"[\"“”][\s\S]*?[\"”]", vanilla_caption)
    if quoted_block:
        vanilla_caption = (
            vanilla_caption[: quoted_block.start()] + vanilla_caption[quoted_block.end() :]
        ).strip()

    parts = [p.strip() for p in re.split(r"\n\s*\n", vanilla_caption) if p.strip()]
    return "\n\n".join(parts), usable_on


def extract_skill_candidates(vanilla_caption: str, item_name: str) -> list[str]:
    """
    Gather possible skill names from the caption and item name.
    Handles quoted names as well as bare `Skill: <name>` patterns.
    """
    candidates: list[str] = []

    quoted = re.search(r'[\"“”]([^\"“”:]+?):', vanilla_caption)
    if quoted:
        candidates.append(quoted.group(1).strip())

    for match in re.finditer(r"Skill:\s*([^\n\r.\"”]+)", vanilla_caption, re.IGNORECASE):
        candidates.append(match.group(1).strip())

    if ":" in item_name:
        candidates.append(item_name.split(":", 1)[1].strip())
    else:
        candidates.append(item_name.strip())

    return list(dedupe(candidates))


def extract_short_caption(vanilla_caption: str, skill_name: str, fallback: str | None) -> str:
    """
    Pull the quoted block from the vanilla caption and strip the leading
    '<skill name>:' portion. If not found, fall back to the provided text.
    """
    quoted = re.search(r'[\"“]([\s\S]*?)[\"”]', vanilla_caption)
    if quoted:
        body = quoted.group(1).strip()
        # Remove "<skill name>: ..." prefix if present.
        if skill_name:
            pattern = rf"^{re.escape(skill_name)}\s*[:：]\s*"
            body = re.sub(pattern, "", body, flags=re.IGNORECASE).strip()
        if body:
            return body
    return (fallback or "").strip()


def main():
    items = load_items_index()
    skill_data_map, skill_norm_map = load_skill_info_map()
    ashes = [i for i in items if i.get("category") == "ash"]
    out = []
    skipped = []
    seen_ids = set()
    for ash in ashes:
        vanilla_cap = ash.get("vanilla_caption") or ""
        if not vanilla_cap.strip():
            skipped.append((ash["id"], ash["name"], "no vanilla caption"))
            continue
        boiler, usable = extract_boilerplate(vanilla_cap)
        candidates = extract_skill_candidates(vanilla_cap, ash.get("name", ""))
        skill_name = None
        skill_data = None

        for cand in candidates:
            if cand in skill_data_map:
                skill_name = cand
                skill_data = skill_data_map[cand]
                break

        if skill_data is None:
            for cand in candidates:
                norm = normalize(cand)
                if norm in skill_norm_map:
                    skill_name, skill_data = skill_norm_map[norm]
                    break

        if not skill_data:
            skipped.append(
                (
                    ash["id"],
                    ash["name"],
                    f"no skill info for candidates {candidates}",
                )
            )
            continue

        skill_info = skill_data["info"]
        skill_caption = skill_data.get("caption")
        short_caption = extract_short_caption(vanilla_cap, skill_name or "", skill_caption)
        if usable:
            short_caption = short_caption or usable

        if ash["id"] in seen_ids:
            skipped.append((ash["id"], ash["name"], "duplicate id (kept first)"))
            continue
        seen_ids.add(ash["id"])
        out.append(
            {
                "id": ash["id"],
                "name": ash["name"],
                "category": "ash",
                "caption": short_caption,
                "info": skill_info,
            }
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(out)} ashes entries -> {OUTPUT}")
    if skipped:
        print(f"Skipped {len(skipped)} ashes (missing data):")
        for sid, name, reason in skipped[:50]:
            print(f"  - {sid} {name}: {reason}")
        if len(skipped) > 50:
            print(f"  ...and {len(skipped)-50} more")


if __name__ == "__main__":
    main()
