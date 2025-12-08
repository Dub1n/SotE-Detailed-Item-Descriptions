import argparse
import csv
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
    "FP",
    "Charged",
    "Step",
    "Bullet",
    "Weapon",
    "isAddBaseAtk",
    "Overwrite Scaling",
]

ANCHOR_INSERTIONS: Tuple[Tuple[str, str], ...] = (
    ("Skill", "Text Name"),
    ("Dmg MV", "Text Wep Dmg"),
    ("Wep Status", "Text Wep Status"),
    ("Stance Dmg", "Text Stance"),
    ("AtkHoly", "Text Bullet"),
    ("Overwrite Scaling", "Text Scaling"),
    ("subCategory4", "Text Category"),
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

    dmg_type = (row.get("Dmg Type") or "").strip()
    dmg_mv_raw = (row.get("Dmg MV") or "").strip()
    dmg_mv_val = parse_float(dmg_mv_raw)
    is_zero_mv = (
        False
        if dmg_mv_val is None and dmg_mv_raw == ""
        else (dmg_mv_val == 0 if dmg_mv_val is not None else dmg_mv_raw == "0")
    )
    if is_zero_mv:
        row["Text Wep Dmg"] = "-"
    elif dmg_type == "-":
        row["Text Wep Dmg"] = "!"
    else:
        mv_text = (
            dmg_mv_raw
            if dmg_mv_raw != ""
            else (format_multiplier(dmg_mv_val) if dmg_mv_val is not None else "")
        )
        label = f"{dmg_type} Damage" if dmg_type else "Damage"
        row["Text Wep Dmg"] = (
            f"{label}: {mv_text}x" if mv_text else ""
        )

    status_raw = (row.get("Status MV") or "").strip()
    status_val = parse_float(status_raw)
    wep_status_raw = (row.get("Wep Status") or "").strip()
    if status_val is None:
        row["Text Wep Status"] = ""
    else:
        is_zero_status = status_val == 0
        if wep_status_raw.strip() == "None" or is_zero_status:
            row["Text Wep Status"] = "-"
        else:
            buildup = format_multiplier(status_val * 0.01)
            if not wep_status_raw:
                label = "Weapon"
            elif wep_status_raw == "-":
                label = "Weapon"
            else:
                label = wep_status_raw
            row["Text Wep Status"] = f"{label} Buildup: {buildup}x"
    return row


def transform_rows(
    rows: List[Dict[str, str]], fieldnames: List[str]
) -> Tuple[List[Dict[str, str]], List[str]]:
    transformed: List[Dict[str, str]] = []
    base_fields = [col for col in fieldnames if col not in DROP_COLUMNS]
    output_fields = ensure_output_fields(base_fields)

    for row in rows:
        base_row = {k: v for k, v in row.items() if k not in DROP_COLUMNS}
        new_row = apply_row_operations(dict(base_row))
        for col, val in base_row.items():
            new_row.setdefault(col, val)
        for col in new_row:
            if col not in output_fields:
                output_fields.append(col)
        transformed.append(new_row)

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
