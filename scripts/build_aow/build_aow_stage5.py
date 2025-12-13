import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple
import re

ROOT = Path(__file__).resolve().parents[2]
INPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-4.csv"
OUTPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-5.md"


TEXT_COLS = [
    "Text Wep Dmg",
    "Text Wep Status",
    "Text Phys",
    "Text Mag",
    "Text Fire",
    "Text Ltng",
    "Text Holy",
    "Text Stance",
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


def indent_lines(lines: List[str], spaces: int) -> List[str]:
    prefix = " " * spaces
    return [f"{prefix}{line}" if line else "" for line in lines]


def merge_blocks(blocks: List[List[str]]) -> List[List[str]]:
    """
    Merge blocks that share the same header and part/subheader line.
    This collapses duplicate parts so their text lines combine under one heading.
    """
    merged: List[List[str]] = []
    index_by_key: Dict[Tuple[str, str | None], int] = {}

    for block in blocks:
        if not block:
            continue
        header = block[0]
        subheader: str | None = None
        start_idx = 1

        if len(block) >= 2 and block[1].startswith("    "):
            subheader = block[1].strip()
            start_idx = 2

        key = (header, subheader)
        if key not in index_by_key:
            index_by_key[key] = len(merged)
            merged.append(list(block))
        else:
            target = merged[index_by_key[key]]
            target.extend(block[start_idx:])

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


def parse_existing(output_path: Path) -> Tuple[List[str], Dict[str, List[str]], Dict[str, str]]:
    """
    Return preamble lines, existing sections keyed by skill, and heading markers.
    Preserves `[x]` markers unless overridden; recognizes `[<]` and `[ ]`.
    """
    if not output_path.exists():
        return [], {}, {}

    heading_re = re.compile(r"^###\s*(\[[xX< ]\])?\s*(.+)$")
    preamble: List[str] = []
    sections: Dict[str, List[str]] = {}
    markers: Dict[str, str] = {}

    current_skill: str | None = None
    current_lines: List[str] = []

    for line in output_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("###"):
            if current_skill is not None:
                sections[current_skill] = current_lines
            match = heading_re.match(line)
            if not match:
                current_skill = None
                current_lines = []
                continue
            marker_raw, skill = match.groups()
            skill = skill.strip()
            if not skill:
                current_skill = None
                current_lines = []
                continue
            marker = "[ ]"
            if marker_raw:
                tag = marker_raw.lower()
                if tag == "[x]":
                    marker = "[x]"
                elif tag == "[<]":
                    marker = "[<]"
            markers[skill] = marker
            current_skill = skill
            current_lines = [line]
        else:
            if current_skill is None:
                preamble.append(line)
            else:
                current_lines.append(line)

    if current_skill is not None:
        sections[current_skill] = current_lines

    return preamble, sections, markers


def write_markdown(
    rows: List[Dict[str, str]],
    output_path: Path,
    existing_preamble: List[str],
    existing_sections: Dict[str, List[str]],
    existing_markers: Dict[str, str],
    force: bool,
) -> None:
    skills_in_order = unique_ordered([row.get("Skill", "") for row in rows])
    lines: List[str] = []

    if existing_preamble:
        lines.extend(existing_preamble)
        if existing_preamble[-1] != "":
            lines.append("")

    for skill in skills_in_order:
        skill_rows = [r for r in rows if r.get("Skill", "") == skill]
        weapon_values = unique_ordered([weapon_value(r) for r in skill_rows])
        weapon_values = [w for w in weapon_values if w]

        existing_marker = existing_markers.get(skill, "[ ]")
        existing_section = existing_sections.get(skill)

        if existing_marker == "[x]" and existing_section and not force:
            # Preserve user-marked sections verbatim unless force is specified.
            lines.extend(existing_section)
            if existing_section[-1] != "":
                lines.append("")
            continue

        marker = existing_marker
        if force and marker == "[x]":
            marker = "[<]"
        heading_parts = ["###"]
        if marker:
            heading_parts.append(marker)
        heading_parts.append(skill)
        lines.append(" ".join(heading_parts))
        lines.append("")

        def emit_blocks(
            block_rows: List[Dict[str, str]], weapon_label: str | None = None
        ) -> None:
            block_has_followups = has_followups(block_rows)
            blocks = [
                format_block(row, block_has_followups) for row in block_rows
            ]
            merged_blocks = merge_blocks(blocks)
            if weapon_label:
                if not merged_blocks:
                    lines.append(weapon_label)
                    return
                if (
                    len(merged_blocks) == 1
                    and merged_blocks[0]
                    and merged_blocks[0][0].startswith("(")
                ):
                    lines.append(f"{weapon_label} {merged_blocks[0][0]}")
                    lines.extend(indent_lines(merged_blocks[0][1:], 4))
                else:
                    lines.append(weapon_label)
                    for block_lines in merged_blocks:
                        lines.extend(indent_lines(block_lines, 4))
                return

            for block_lines in merged_blocks:
                lines.extend(block_lines)

        if len(weapon_values) > 1:
            for weapon in weapon_values:
                weapon_rows = [
                    r for r in skill_rows if weapon_value(r) == weapon
                ]
                emit_blocks(weapon_rows, weapon)
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
        "--force",
        action="store_true",
        help="Force overwrite checked sections, replacing [x] with [<]",
    )
    args = parser.parse_args()

    rows, _ = read_rows(args.input)
    preamble, sections, markers = parse_existing(args.output)
    if preamble and sections:
        # Avoid carrying over corrupted or unexpected leading content.
        preamble = []
    write_markdown(rows, args.output, preamble, sections, markers, args.force)
    print(f"Wrote markdown to {args.output}")


if __name__ == "__main__":
    main()
