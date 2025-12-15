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

TEXT_LABEL_ORDER: Tuple[str, ...] = (
    "Standard",
    "Strike",
    "Slash",
    "Pierce",
    "Magic",
    "Fire",
    "Lightning",
    "Holy",
    "Poison",
    "Deadly Poison",
    "Scarlet Rot",
    "Blood Loss",
    "Frostbite",
    "Sleep",
    "Eternal Sleep",
    "Madness",
    "Death Blight",
    "Status (%)",
    "Stance",
)

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
    Merge blocks by header, collapsing duplicate part/subheader lines under one header.
    Ensures a single header per group while combining repeated parts.
    """
    merged: List[List[str]] = []
    header_order: List[str] = []
    subheader_order: Dict[str, List[str | None]] = {}
    grouped: Dict[str, Dict[str | None, List[str]]] = {}

    def ensure_header(header: str) -> None:
        if header not in grouped:
            grouped[header] = {}
            header_order.append(header)
            subheader_order[header] = []

    def ensure_sub(header: str, sub: str | None) -> None:
        subs = subheader_order[header]
        if sub not in subs:
            subs.append(sub)
        grouped[header].setdefault(sub, [])

    for block in blocks:
        if not block:
            continue
        header = block[0]
        subheader: str | None = None
        start_idx = 1

        if len(block) >= 2 and block[1].startswith("    "):
            subheader = block[1].strip()
            start_idx = 2

        ensure_header(header)
        ensure_sub(header, subheader)
        grouped[header][subheader].extend(block[start_idx:])

    for header in header_order:
        block_lines: List[str] = [header]
        for sub in subheader_order[header]:
            if sub is not None:
                block_lines.append(f"    {sub}")
            block_lines.extend(grouped[header][sub])
        merged.append(block_lines)

    return merged


def has_followups(rows: List[Dict[str, str]]) -> bool:
    return any((row.get("Follow-up") or "").strip() not in {"", "-"} for row in rows)


def normalize_subcat(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = cleaned.replace(" | ", ", ")
    cleaned = cleaned.replace(" / ", "/")
    return cleaned


def sort_text_lines(lines: List[str]) -> List[str]:
    order = {label: idx for idx, label in enumerate(TEXT_LABEL_ORDER)}

    def sort_key(entry: Tuple[int, str]) -> Tuple[int, int]:
        idx, line = entry
        label = line.split(":", 1)[0].strip()
        priority = order.get(label, len(order))
        return priority, idx

    return [line for _, line in sorted(enumerate(lines), key=sort_key)]


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
    text_lines = sort_text_lines(text_lines)

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
        apply_subcat_to_label = skill_has_followups and bool(subcat_suffix)
        label_suffix = subcat_suffix if apply_subcat_to_label else ""
        part_suffix = "" if apply_subcat_to_label else subcat_suffix

        if part == "-":
            heading = f"{label}{label_suffix}".strip()
            blocks.append(heading)
            blocks.extend([f"    {line}" for line in text_lines])
        else:
            blocks.append(f"{label}{label_suffix}".strip())
            blocks.append(f"    {part}{part_suffix}")
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


def build_markdown(
    rows: List[Dict[str, str]],
    output_path: Path,
    existing_preamble: List[str],
    existing_sections: Dict[str, List[str]],
    existing_markers: Dict[str, str],
    force: bool,
) -> Tuple[List[str], Dict[str, List[str]]]:
    skills_in_order = unique_ordered([row.get("Skill", "") for row in rows])
    lines: List[str] = []
    new_sections: Dict[str, List[str]] = {}

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
            new_sections[skill] = list(existing_section)
            continue

        section_lines: List[str] = []
        marker = existing_marker
        if force and marker == "[x]":
            marker = "[<]"
        heading_parts = ["###"]
        if marker:
            heading_parts.append(marker)
        heading_parts.append(skill)
        section_lines.append(" ".join(heading_parts))
        section_lines.append("")

        multi_weapon_labels = [w for w in weapon_values if "|" in w]
        alias_labels: Dict[str, str] = {}
        if len(multi_weapon_labels) == 1:
            alias_labels[multi_weapon_labels[0]] = "All Weapons"

        def emit_blocks(
            block_rows: List[Dict[str, str]], weapon_label: str | None = None
        ) -> None:
            block_has_followups = has_followups(block_rows)
            blocks = [
                format_block(row, block_has_followups) for row in block_rows
            ]
            merged_blocks = merge_blocks(blocks)
            if weapon_label:
                display_label = alias_labels.get(weapon_label, weapon_label)
                if not merged_blocks:
                    section_lines.append(display_label)
                    return
                if (
                    len(merged_blocks) == 1
                    and merged_blocks[0]
                    and merged_blocks[0][0].startswith("(")
                ):
                    section_lines.append(
                        f"{display_label} {merged_blocks[0][0]}"
                    )
                    section_lines.extend(
                        indent_lines(merged_blocks[0][1:], 4)
                    )
                else:
                    section_lines.append(display_label)
                    for block_lines in merged_blocks:
                        section_lines.extend(indent_lines(block_lines, 4))
                return

            for block_lines in merged_blocks:
                section_lines.extend(block_lines)

        if len(weapon_values) > 1:
            for weapon in weapon_values:
                weapon_rows = [
                    r for r in skill_rows if weapon_value(r) == weapon
                ]
                emit_blocks(weapon_rows, weapon)
        else:
            emit_blocks(skill_rows)

        section_lines.append("")
        lines.extend(section_lines)
        new_sections[skill] = section_lines

    return lines, new_sections


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
    old_sections = {k: v for k, v in sections.items()}

    lines, new_sections = build_markdown(
        rows, args.output, preamble, sections, markers, args.force
    )

    # Ensure consistent EOF: trailing blank line + marker for stable diffs.
    if lines and lines[-1] != "":
        lines.append("")
    lines.append("---")
    lines.append("")

    output_text = "\n".join(lines)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_text, encoding="utf-8")

    def normalize_block(block: List[str] | None) -> List[str]:
        if not block:
            return []
        trimmed = list(block)
        while trimmed and trimmed[-1] == "":
            trimmed.pop()
        return trimmed

    changed_skills = []
    for skill, new_block in new_sections.items():
        before = normalize_block(old_sections.get(skill))
        after = normalize_block(new_block)
        if before != after:
            changed_skills.append(skill)
    removed_skills = [s for s in old_sections if s not in new_sections]
    total_changes = len(set(changed_skills) | set(removed_skills))

    if total_changes == 0:
        print(f"No markdown changes. Wrote {args.output}")
        return

    print(f"Wrote markdown to {args.output} ({total_changes} section changes)")
    if total_changes <= 5:
        details = changed_skills + [s for s in removed_skills if s not in changed_skills]
        for skill in details[:5]:
            before = "\n".join(old_sections.get(skill, ["<missing>"]))
            after = "\n".join(new_sections.get(skill, ["<missing>"]))
            print(f"\n--- {skill} (before) ---\n{before}")
            print(f"+++ {skill} (after)  ---\n{after}")


if __name__ == "__main__":
    main()
