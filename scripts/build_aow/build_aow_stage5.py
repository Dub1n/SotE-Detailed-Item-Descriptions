import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
HELPERS_DIR = ROOT / "scripts"
if str(HELPERS_DIR) not in sys.path:
    sys.path.append(str(HELPERS_DIR))

from colorize_stats import (  # type: ignore  # noqa: E402
    colourize_text,
    get_merge_rules,
    get_tag_rules,
)
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


def colorize_line(
    text: str,
    enabled: bool,
    tag_rules: Sequence,
    merge_rules: Sequence,
) -> str:
    if not enabled:
        return text
    colored, _ = colourize_text(
        text,
        tag_rules,
        merge_rules,
        fix_only=False,
        capitalized_only=False,
    )
    return colored


def normalize_subcat(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = cleaned.replace(" | ", ", ")
    cleaned = cleaned.replace(" / ", "/")
    return cleaned


def format_block(
    row: Dict[str, str],
    skill_has_followups: bool,
    colorize: bool,
    tag_rules: Sequence,
    merge_rules: Sequence,
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

    text_lines = []
    for col in TEXT_COLS:
        val = (row.get(col, "") or "").strip()
        if val in {"", "-"}:
            continue
        text_lines.append(colorize_line(val, colorize, tag_rules, merge_rules))

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


def write_markdown(
    rows: List[Dict[str, str]],
    output_path: Path,
    colorize: bool = False,
    color_mode: str = "all",
) -> None:
    skills_in_order = unique_ordered([row.get("Skill", "") for row in rows])
    lines: List[str] = []
    tag_rules = get_tag_rules(color_mode) if colorize else ()
    merge_rules = get_merge_rules(color_mode) if colorize else ()

    for skill in skills_in_order:
        skill_rows = [r for r in rows if r.get("Skill", "") == skill]
        weapon_values = unique_ordered([weapon_value(r) for r in skill_rows])
        weapon_values = [w for w in weapon_values if w]

        lines.append(f"### {skill}")
        lines.append("")

        def emit_blocks(block_rows: List[Dict[str, str]]) -> None:
            block_has_followups = has_followups(block_rows)
            blocks = [
                format_block(
                    row,
                    block_has_followups,
                    colorize,
                    tag_rules,
                    merge_rules,
                )
                for row in block_rows
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
    parser.add_argument(
        "--color",
        action="store_true",
        help="Apply colour tags to text lines using scripts/colorize_stats.py rules.",
    )
    parser.add_argument(
        "--color-mode",
        choices=["all", "status"],
        default="all",
        help="Pattern set for colouring (default: all).",
    )
    args = parser.parse_args()

    rows, _ = read_rows(args.input)
    write_markdown(
        rows,
        args.output,
        colorize=args.color,
        color_mode=args.color_mode,
    )
    print(f"Wrote markdown to {args.output}")


if __name__ == "__main__":
    main()
