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
    ("AtkHoly", "Text Bullet"),
    ("Overwrite Scaling", "Text Scaling"),
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
    row.setdefault("Text Bullet", "")
    row.setdefault("Text Scaling", "")
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

    part_raw = (row.get("Part") or "").strip()
    part_suffix = part_raw if part_raw and part_raw != "-" else ""

    def append_x(text: str) -> str:
        # Add 'x' after each numeric token or numeric range.
        def repl(match: re.Match[str]) -> str:
            token = match.group(0)
            return f"{token}x"

        return re.sub(r"-?\d+(?:\.\d+)?(?:-?\d+(?:\.\d+)?)?", repl, text)

    dmg_type = (row.get("Dmg Type") or "").strip()
    dmg_mv_raw = (row.get("Dmg MV") or "").strip()
    if dmg_mv_raw in {"", "-"}:
        row["Text Wep Dmg"] = "-"
    elif dmg_type == "-":
        row["Text Wep Dmg"] = "!"
    else:
        row["Text Wep Dmg"] = f"({dmg_type} Damage){part_suffix}: {append_x(dmg_mv_raw)}"

    status_raw = (row.get("Status MV") or "").strip()
    status_val = parse_float(status_raw if status_raw not in {"", "-"} else "")
    wep_status_raw = (row.get("Wep Status") or "").strip()
    if not status_raw or status_raw == "-" or status_val is None:
        row["Text Wep Status"] = "-"
    elif wep_status_raw.strip() == "None" or zeros_only(status_raw):
        row["Text Wep Status"] = "-"
    else:
        buildup = format_multiplier(status_val * 0.01)
        label = "Weapon" if not wep_status_raw or wep_status_raw == "-" else wep_status_raw
        row["Text Wep Status"] = f"({label} Buildup){part_suffix}: {buildup}"

    stance_raw = (row.get("Stance Dmg") or "").strip()
    if stance_raw in {"", "-"}:
        row["Text Stance"] = "-"
    else:
        row["Text Stance"] = f"(Stance Damage){part_suffix}: {stance_raw}"

    base_cols = {
        "Text Phys": ("Base Physical Damage", row.get("AtkPhys", "")),
        "Text Mag": ("Base Magic Damage", row.get("AtkMag", "")),
        "Text Fire": ("Base Fire Damage", row.get("AtkFire", "")),
        "Text Ltng": ("Base Lightning Damage", row.get("AtkLtng", "")),
        "Text Holy": ("Base Holy Damage", row.get("AtkHoly", "")),
    }
    for col, (label, value) in base_cols.items():
        val_clean = (value or "").strip()
        if not val_clean or val_clean == "-":
            row[col] = "-"
        else:
            row[col] = f"({label}){part_suffix}: {val_clean}"
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
