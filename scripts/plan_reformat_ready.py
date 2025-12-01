import json
from pathlib import Path
from typing import List, Dict

CHUNK_SIZE = 5
READY_DIR = Path("work/responses/ready")
TARGET_FILES = [
    "consumable_Incantation.json",
    "consumable_Sorcery.json",
    "consumable_Physick_Tear.json",
    "consumable_Key_Item.json",
    "skill.json",
    "talisman.json",
]
PROMPT_DIR = Path("work/prompts/reformat_ready")
STYLE_GUIDE = Path("docs/category_formats.md")


def build_prompt(filename: str, batch: List[Dict], batch_idx: int) -> str:
    header = [
        "You are reformatting existing item entries to match the Detailed Item Descriptions mod style.",
        f"Follow the style guide here: {STYLE_GUIDE}",
        "Edit the source file in place (see path below) for only the 5 items provided; keep id/name/category the same.",
        "Retain lore verbatim, move mechanics into info per the guide, and apply the colour/structural rules.",
        "Do not change numbers or add new mechanics; only reformat to the mod style.",
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


def main():
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    for fname in TARGET_FILES:
        path = READY_DIR / fname
        if not path.exists():
            print(f"[skip] missing {path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        batch_num = 0
        for batch in chunk_items(data, CHUNK_SIZE):
            batch_num += 1
            prompt = build_prompt(fname, batch, batch_num)
            out_path = PROMPT_DIR / f"{path.stem}_batch_{batch_num:03d}.txt"
            out_path.write_text(prompt, encoding="utf-8")
            print(f"[write] {out_path}")


if __name__ == "__main__":
    main()
