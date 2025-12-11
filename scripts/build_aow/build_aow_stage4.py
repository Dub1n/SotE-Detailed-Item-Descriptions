import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
HELPERS_DIR = ROOT / "scripts"
if str(HELPERS_DIR) not in sys.path:
    sys.path.append(str(HELPERS_DIR))

from helpers.diff import (  # noqa: E402
    load_rows_by_key,
    report_row_deltas,
)
from helpers.output import format_path_for_console  # noqa: E402

INPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-3.csv"
OUTPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-4.csv"

PHYSICAL_COLOR = "#F395C4"
MAGIC_COLOR = "#57DBCE"
FIRE_COLOR = "#F48C25"
LIGHTNING_COLOR = "#FFE033"
HOLY_COLOR = "#F5EB89"
HEADER_COLOR = "#C0B194"
POISON_COLOR = "#40BF40"
ROT_COLOR = "#EF7676"
BLEED_COLOR = "#C84343"
FROST_COLOR = "#9DD7FB"
MADNESS_COLOR = "#EEAA2B"
SLEEP_COLOR = "#A698F4"
DEATH_COLOR = "#A17945"

KEY_FIELDS = [
    "Skill",
    "Follow-up",
    "Hand",
    "Part",
    "Weapon",
    "Dmg Type",
    "Wep Status",
]

ANCHOR_INSERTIONS: Tuple[Tuple[str, str], ...] = (
    ("Skill", "Text Name"),
    ("Weapon", "Text Wep Dmg"),
    ("Text Wep Dmg", "Text Wep Status"),
    ("Weapon Buff MV", "Text Stance"),
    ("Text Stance", "Text Phys"),
    ("Text Phys", "Text Mag"),
    ("Text Mag", "Text Fire"),
    ("Text Fire", "Text Ltng"),
    ("Text Ltng", "Text Holy"),
    ("subCategorySum", "Text Category"),
)

DROP_COLUMNS = {
    "Wep Poise Range",
    "Disable Gem Attr",
    "Wep Phys",
    "Wep Magic",
    "Wep Fire",
    "Wep Ltng",
    "Wep Holy",
    "Phys MV",
    "Magic MV",
    "Fire MV",
    "Ltng MV",
    "Holy MV",
    "Dmg MV",
    "Status MV",
    "Wep Status",
    "Stance Dmg",
    "AtkPhys",
    "AtkMag",
    "AtkFire",
    "AtkLtng",
    "AtkHoly",
    "Weapon Source",
    "Dmg Type",
    "Overwrite Scaling",
}


def parse_float(value: str) -> float | None:
    try:
        text = str(value).strip()
        if text == "":
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def format_multiplier(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text else "0"


def zeros_only(text: str) -> bool:
    nums = re.findall(r"-?\d+(?:\.\d+)?", text or "")
    if not nums:
        return False
    return all(float(n) == 0 for n in nums)


def wrap_label(label: str, color: str | None) -> str:
    return f'<font color="{color}">{label}</font>' if color else label


def wrap_segment(text: str, color: str) -> str:
    return f'<font color="{color}">{text}</font>' if text else text


def color_for_damage_type(label: str) -> str | None:
    l = label.lower()
    if l in {"standard", "physical", "phys", "pierce", "slash", "strike", "blunt"}:
        return PHYSICAL_COLOR
    if l == "magic":
        return MAGIC_COLOR
    if l == "fire":
        return FIRE_COLOR
    if l in {"lightning", "ltng"}:
        return LIGHTNING_COLOR
    if l == "holy":
        return HOLY_COLOR
    return None


def color_for_status(label: str) -> str | None:
    l = label.lower()
    if l in {"blood loss", "hemorrhage"}:
        return BLEED_COLOR
    if l in {"poison", "deadly poison"}:
        return POISON_COLOR
    if l in {"scarlet rot", "rot"}:
        return ROT_COLOR
    if l in {"frost", "frostbite"}:
        return FROST_COLOR
    if l in {"madness"}:
        return MADNESS_COLOR
    if l in {"sleep", "eternal sleep"}:
        return SLEEP_COLOR
    if l in {"death blight"}:
        return DEATH_COLOR
    return None


CHARGED_COLOR = "#ffd59aff"
FP_COLOR = "#b9bec3ff"
FP_CHARGED_COLOR = "#dabd9dff"
DIVIDER_COLOR = "#e0ded9ff"
FP_DIVIDER_COLOR = "#d9e0e0ff"


def colorize_fp_block(block: str) -> str:
    # block includes brackets
    content = block[1:-1]
    parts = content.split("|", 1)
    left = wrap_segment(parts[0], FP_COLOR)
    divider = ""
    right = ""
    if len(parts) == 2:
        divider = wrap_segment("|", FP_DIVIDER_COLOR)
        right = wrap_segment(parts[1], FP_CHARGED_COLOR)
    return f'{wrap_segment("[", FP_COLOR)}{left}{divider}{right}{wrap_segment("]", FP_COLOR)}'


def colorize_main_part(part: str) -> str:
    if "|" not in part:
        return part
    left, right = part.split("|", 1)
    divider = wrap_segment("|", DIVIDER_COLOR)
    right_colored = wrap_segment(right, CHARGED_COLOR)
    return f"{left}{divider}{right_colored}"


def colorize_numeric_payload(payload: str) -> str:
    if not payload:
        return payload
    tokens = re.split(r"(\[[^\]]*\])", payload)
    pieces: List[str] = []
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("[") and tok.endswith("]") and re.search(r"\d", tok):
            pieces.append(colorize_fp_block(tok))
        else:
            pieces.append(colorize_main_part(tok))
    return "".join(pieces)


def read_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return rows, fieldnames


def ensure_output_fields(fieldnames: List[str]) -> List[str]:
    fields = list(fieldnames)
    for anchor, new_col in ANCHOR_INSERTIONS:
        if new_col in fields:
            continue
        if anchor in fields:
            fields.insert(fields.index(anchor) + 1, new_col)
        else:
            fields.append(new_col)
    return fields


def apply_row_operations(row: Dict[str, str]) -> Dict[str, str]:
    """
    Hook for future Stage 3 transforms.
    Modify or add columns based on existing row values here.
    """
    row.setdefault("Text Name", "")
    row.setdefault("Text Stance", "")
    row.setdefault("Text Category", "")

    # Clean subCategorySum of "-" and empties.
    subcat_raw = row.get("subCategorySum", "")
    if subcat_raw:
        parts = [
            p.strip()
            for p in subcat_raw.split("|")
            if p.strip() and p.strip() != "-"
        ]
        deduped: List[str] = []
        seen = set()
        for p in parts:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        row["subCategorySum"] = " | ".join(deduped)

    # Zero-only normalization.
    zero_cols = [
        "Dmg MV",
        "Status MV",
        "Weapon Buff MV",
        "Stance Dmg",
        "AtkPhys",
        "AtkMag",
        "AtkFire",
        "AtkLtng",
        "AtkHoly",
    ]
    for col in zero_cols:
        val = (row.get(col) or "").strip()
        if val and zeros_only(val):
            row[col] = "-"

    dmg_type = (row.get("Dmg Type") or "").strip()
    dmg_mv_raw = (row.get("Dmg MV") or "").strip()
    if dmg_mv_raw in {"", "-"}:
        row["Text Wep Dmg"] = "-"
    elif dmg_type == "-":
        row["Text Wep Dmg"] = "!"
    else:
        label = "Damage" if dmg_type == "Weapon" else dmg_type
        label_color = color_for_damage_type(label)
        label_text = wrap_label(f"{label}:", label_color)
        row["Text Wep Dmg"] = f"{label_text} {colorize_numeric_payload(dmg_mv_raw)} [AR]"

    status_raw = (row.get("Status MV") or "").strip()
    wep_status_raw = (row.get("Wep Status") or "").strip()
    if (
        not status_raw
        or status_raw == "-"
        or wep_status_raw.strip() == "None"
        or zeros_only(status_raw)
    ):
        row["Text Wep Status"] = "-"
    else:
        label = "Status" if not wep_status_raw or wep_status_raw == "-" else wep_status_raw
        num_match = re.search(r"-?\d+(?:\.\d+)?", status_raw)
        label_color = color_for_status(label)
        label_text = wrap_label(f"{label}:", label_color)
        if num_match:
            mv_value = format_multiplier(float(num_match.group(0)))
            row["Text Wep Status"] = f"{label_text} {colorize_numeric_payload(mv_value + '%')}"
        else:
            row["Text Wep Status"] = f"{label_text} {colorize_numeric_payload(status_raw)}"

    stance_raw = (row.get("Stance Dmg") or "").strip()
    if stance_raw in {"", "-"}:
        row["Text Stance"] = "-"
    else:
        row["Text Stance"] = f"{wrap_label('Stance:', HEADER_COLOR)} {colorize_numeric_payload(stance_raw)}"

    overwrite_raw = (row.get("Overwrite Scaling") or "").strip()
    scaling_label = overwrite_raw if overwrite_raw not in {"", "-"} else "Weapon Scaling"

    base_cols = {
        "Text Phys": ("Standard", row.get("AtkPhys", "")),
        "Text Mag": ("Magic", row.get("AtkMag", "")),
        "Text Fire": ("Fire", row.get("AtkFire", "")),
        "Text Ltng": ("Lightning", row.get("AtkLtng", "")),
        "Text Holy": ("Holy", row.get("AtkHoly", "")),
    }
    for col, (label, value) in base_cols.items():
        val_clean = (value or "").strip()
        if not val_clean or val_clean == "-":
            row[col] = "-"
        else:
            label_color = color_for_damage_type(label)
            label_text = wrap_label(f"{label}:", label_color)
            row[col] = f"{label_text} {colorize_numeric_payload(val_clean)} [{scaling_label}]"
    return row


def transform_rows(
    rows: List[Dict[str, str]], fieldnames: List[str]
) -> Tuple[List[Dict[str, str]], List[str]]:
    transformed: List[Dict[str, str]] = []
    base_fields = [col for col in fieldnames if col not in DROP_COLUMNS]
    output_fields = ensure_output_fields(base_fields)

    for row in rows:
        new_row = apply_row_operations(dict(row))
        cleaned_row = {k: v for k, v in new_row.items() if k not in DROP_COLUMNS}
        for col in cleaned_row:
            if col not in output_fields:
                output_fields.append(col)
        transformed.append(cleaned_row)

    normalized: List[Dict[str, str]] = []
    for row in transformed:
        normalized.append({col: row.get(col, "") for col in output_fields})
    return normalized, output_fields


def write_csv(
    rows: List[Dict[str, str]], fieldnames: List[str], output_path: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 4: add text helper columns for downstream use."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_DEFAULT,
        help="Path to AoW-data-3.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DEFAULT,
        help="Path to write AoW-data-4.csv",
    )
    args = parser.parse_args()

    rows, fieldnames = read_rows(args.input)
    output_rows, output_columns = transform_rows(rows, fieldnames)
    key_fields = [field for field in KEY_FIELDS if field in output_columns]
    before_rows = load_rows_by_key(args.output, key_fields)
    write_csv(output_rows, output_columns, args.output)

    path_text = format_path_for_console(args.output, ROOT)
    print(f"Wrote {len(output_rows)} rows to {path_text}")
    if key_fields:
        report_row_deltas(
            before_rows=before_rows,
            after_rows=output_rows,
            fieldnames=output_columns,
            key_fields=key_fields,
            align_columns=True,
        )


if __name__ == "__main__":
    main()
