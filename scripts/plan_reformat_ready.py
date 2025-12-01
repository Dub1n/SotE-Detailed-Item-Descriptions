import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

CHUNK_SIZE = 5
READY_DIR = Path("work/responses/ready")
PROMPT_DIR = Path("work/prompts/reformat_ready")
STYLE_GUIDE = Path("docs/category_formats.md")
DEFINITIONS_DOC = Path("docs/definitions.md")
TARGET_CONFIG = Path("scripts/reformat_ready_targets.json")


def build_prompt(filename: str, batch: List[Dict], batch_idx: int) -> str:
    header = [
        "You are reformatting existing item entries to match the Detailed Item Descriptions mod style.",
        f"Follow the style guide here: {STYLE_GUIDE}",
        f"Use the rules in {DEFINITIONS_DOC} for buildup/resistance wording, ordering, Base handling, and per-tick formatting.",
        "Edit the source file in place (see path below) for only the 5 items provided; keep id/name/category the same.",
        "Retain lore verbatim, move mechanics into info per the guide, and apply the colour/structural rules.",
        "Every damage, buildup, and scaling value must be supported by source data: prefer work/fex_cache_filtered, fallback to work/fex_cache, or derive from the PARAM CSVs in ./PARAM/.",
        "Only adjust numbers or scaling when they differ from those sources—do not invent values or add new mechanics.",
        "Hand-edit each entry; do not run or rely on any automated scripts to adjust the text.",
        "Preserve JSON structure/ordering/indentation for untouched items; only modify the targeted entries.",
        "Do not paste the JSON in your reply—save the file instead and briefly confirm completion.",
        f"Source file path: {READY_DIR / filename}",
    ]
    lines: List[str] = header[:]
    for idx, item in enumerate(batch, 1):
        lines.append(f"\nItem {idx}: id={item.get('id')} name={item.get('name')}")
        if "category" in item:
            lines.append(f"category: {item['category']}")
        lines.append("current caption:\n" + (item.get("caption") or ""))
        lines.append("current info:\n" + (item.get("info") or ""))
    return "\n\n".join(lines)


def chunk_items(items: List[Dict], chunk_size: int):
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


def load_ready_data() -> Dict[str, List[Dict]]:
    ready_data: Dict[str, List[Dict]] = {}
    for path in READY_DIR.glob("*.json"):
        ready_data[path.name] = json.loads(path.read_text(encoding="utf-8"))
    return ready_data


def load_target_config() -> Dict:
    if not TARGET_CONFIG.exists():
        raise FileNotFoundError(f"Missing target config: {TARGET_CONFIG}")
    return json.loads(TARGET_CONFIG.read_text(encoding="utf-8"))


def resolve_target_ids(config: Dict, ready_data: Dict[str, List[Dict]]) -> Set[int]:
    include_files = config.get("include_files") or []
    target_ids: Set[int] = {int(i) for i in config.get("include_ids") or []}

    missing_files = [fname for fname in include_files if fname not in ready_data]
    if missing_files:
        raise FileNotFoundError(f"Missing ready files: {', '.join(missing_files)}")

    for fname in include_files:
        for item in ready_data[fname]:
            if isinstance(item, dict) and "id" in item:
                target_ids.add(int(item["id"]))
    return target_ids


def collect_items_by_file(target_ids: Set[int], ready_data: Dict[str, List[Dict]], include_files: List[str]) -> Dict[str, List[Dict]]:
    items_by_file: Dict[str, List[Dict]] = defaultdict(list)
    seen_ids: Set[int] = set()

    def add_from_file(fname: str):
        items = ready_data.get(fname, [])
        for item in items:
            if not isinstance(item, dict) or "id" not in item:
                continue
            item_id = int(item["id"])
            if item_id in target_ids and item_id not in seen_ids:
                seen_ids.add(item_id)
                items_by_file[fname].append(item)

    for fname in include_files:
        add_from_file(fname)

    for fname in sorted(ready_data):
        if fname in include_files:
            continue
        add_from_file(fname)

    missing = target_ids - seen_ids
    if missing:
        missing_str = ", ".join(str(m) for m in sorted(missing))
        raise ValueError(f"Targets missing from ready data: {missing_str}")

    return items_by_file


def main():
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)

    ready_data = load_ready_data()
    config = load_target_config()
    include_files = config.get("include_files") or []
    target_ids = resolve_target_ids(config, ready_data)
    items_by_file = collect_items_by_file(target_ids, ready_data, include_files)

    include_order = include_files
    file_order = include_order + [f for f in sorted(items_by_file) if f not in include_order]

    for fname in file_order:
        if fname not in items_by_file:
            continue
        data = items_by_file[fname]
        batch_num = 0
        for batch in chunk_items(data, CHUNK_SIZE):
            batch_num += 1
            prompt = build_prompt(fname, batch, batch_num)
            out_path = PROMPT_DIR / f"{Path(fname).stem}_batch_{batch_num:03d}.txt"
            out_path.write_text(prompt, encoding="utf-8")
            print(f"[write] {out_path}")


if __name__ == "__main__":
    main()
