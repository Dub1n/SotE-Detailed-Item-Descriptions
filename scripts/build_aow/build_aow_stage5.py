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


def read_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return rows, fieldnames


def split_weapons(value: str) -> List[str]:
    parts = []
    for chunk in (value or "").split("|"):
        name = chunk.strip()
        if name:
            parts.append(name)
    return parts


def unique_ordered(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for val in values:
        if val not in seen:
            seen.add(val)
            ordered.append(val)
    return ordered


def format_block(row: Dict[str, str]) -> List[str]:
    follow = (row.get("Follow-up") or "").strip()
    hand = (row.get("Hand") or "").strip()
    part = (row.get("Part") or "").strip()
    subcat = (row.get("subCategorySum") or "").strip()

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
        weapons: List[str] = []
        for r in skill_rows:
            weapons.extend(split_weapons(r.get("Weapon", "")))
        unique_weapons = [w for w in unique_ordered(weapons) if w]

        lines.append(f"### {skill}")
        lines.append("")

        def emit_blocks(block_rows: List[Dict[str, str]]) -> None:
            for idx, row in enumerate(block_rows):
                block_lines = format_block(row)
                for line in block_lines:
                    lines.append(line)
                if idx != len(block_rows) - 1:
                    lines.append("")

        if len(unique_weapons) > 1:
            for w_idx, weapon in enumerate(unique_weapons):
                lines.append(f"#### {weapon}")
                lines.append("")
                weapon_rows = [
                    r for r in skill_rows if weapon in split_weapons(r.get("Weapon", ""))
                ]
                emit_blocks(weapon_rows)
                if w_idx != len(unique_weapons) - 1:
                    lines.append("")
        else:
            emit_blocks(skill_rows)

        lines.append("")
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
