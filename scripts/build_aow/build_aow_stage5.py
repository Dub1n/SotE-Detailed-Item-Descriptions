import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
INPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-4.csv"
OUTPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-5.md"


TEXT_COLS = [
    "Text Wep Dmg",
    "Text Wep Status",
    "Text Stance",
    "Text Phys",
    "Text Mag",
    "Text Fire",
    "Text Ltng",
    "Text Holy",
]

FOLLOW_DISPLAY = {
    "Heavy": "Heavy Follow-up",
    "Light": "Light Follow-up",
}


def read_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return rows, fieldnames


def weapon_value(row: Dict[str, str]) -> str:
    val = (row.get("Weapon") or "-").strip()
    return val if val else "-"


def unique_ordered(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for val in values:
        if val not in seen:
            seen.add(val)
            ordered.append(val)
    return ordered


def merge_blocks(blocks: List[List[str]]) -> List[List[str]]:
    merged: List[List[str]] = []
    index_by_key: Dict[str, int] = {}
    for block in blocks:
        if not block:
            continue
        key = block[0]
        if key not in index_by_key:
            index_by_key[key] = len(merged)
            merged.append(list(block))
        else:
            merged[index_by_key[key]].extend(block[1:])
    return merged


def has_followups(rows: List[Dict[str, str]]) -> bool:
    return any((row.get("Follow-up") or "").strip() not in {"", "-"} for row in rows)


def normalize_subcat(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = cleaned.replace(" | ", ", ")
    cleaned = cleaned.replace(" / ", "/")
    return cleaned


def format_block(
    row: Dict[str, str],
    skill_has_followups: bool,
) -> List[str]:
    follow_raw = (row.get("Follow-up") or "").strip()
    follow = FOLLOW_DISPLAY.get(follow_raw, follow_raw)
    if skill_has_followups and follow in {"", "-"}:
        follow = "Skill"
    hand = (row.get("Hand") or "").strip()
    part = (row.get("Part") or "").strip()
    subcat = normalize_subcat(row.get("subCategorySum") or "")

    subcat_line = f"({subcat})" if subcat else ""
    subcat_suffix = f" ({subcat})" if subcat else ""

    text_lines = [
        row.get(col, "").strip()
        for col in TEXT_COLS
        if (row.get(col, "") or "").strip() not in {"", "-"}
    ]

    blocks: List[str] = []
    if follow == "-" and hand == "-":
        if part == "-":
            if subcat_line:
                blocks.append(subcat_line)
            blocks.extend(text_lines)
        else:
            header = f"{part}{subcat_suffix}"
            blocks.append(header)
            blocks.extend([f"    {line}" for line in text_lines])
    else:
        label_parts = []
        if follow != "-":
            label_parts.append(follow)
        if hand != "-":
            label_parts.append(hand)
        label = " ".join(label_parts).strip() or "-"
        if part == "-":
            heading = f"{label}{subcat_suffix}".strip()
            blocks.append(heading)
            blocks.extend([f"    {line}" for line in text_lines])
        else:
            blocks.append(label)
            blocks.append(f"    {part}{subcat_suffix}")
            blocks.extend([f"        {line}" for line in text_lines])

    return blocks


def write_markdown(rows: List[Dict[str, str]], output_path: Path) -> None:
    skills_in_order = unique_ordered([row.get("Skill", "") for row in rows])
    lines: List[str] = []

    for skill in skills_in_order:
        skill_rows = [r for r in rows if r.get("Skill", "") == skill]
        weapon_values = unique_ordered([weapon_value(r) for r in skill_rows])
        weapon_values = [w for w in weapon_values if w]

        lines.append(f"### {skill}")
        lines.append("")

        def emit_blocks(block_rows: List[Dict[str, str]]) -> None:
            block_has_followups = has_followups(block_rows)
            blocks = [
                format_block(row, block_has_followups) for row in block_rows
            ]
            merged_blocks = merge_blocks(blocks)
            for block_lines in merged_blocks:
                for line in block_lines:
                    lines.append(line)

        if len(weapon_values) > 1:
            for w_idx, weapon in enumerate(weapon_values):
                lines.append(f"#### {weapon}")
                lines.append("")
                weapon_rows = [
                    r for r in skill_rows if weapon_value(r) == weapon
                ]
                emit_blocks(weapon_rows)
                if w_idx != len(weapon_values) - 1:
                    lines.append("")
        else:
            emit_blocks(skill_rows)

        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 5: render AoW-data-4.csv into markdown helper text."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_DEFAULT,
        help="Path to AoW-data-4.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DEFAULT,
        help="Path to write AoW-data-5.md",
    )
    args = parser.parse_args()

    rows, _ = read_rows(args.input)
    write_markdown(rows, args.output)
    print(f"Wrote markdown to {args.output}")


if __name__ == "__main__":
    main()
