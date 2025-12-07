import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Any


ROOT = Path(__file__).resolve().parents[2]
INPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-1.csv"
OUTPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-2.csv"

GROUP_KEYS = [
    "Skill",
    "Follow-up",
    "Hand",
    "Part",
    "FP",
    "Charged",
    "Step",
    "Weapon",
    "PhysAtkAttribute",
    "isAddBaseAtk",
    "Overwrite Scaling",
]

DROP_COLUMNS = {"Name", "Bullet", "Tick", "AtkId"}


def parse_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return 0.0
        return float(text)
    except (TypeError, ValueError):
        return None


def fmt_number(value: Any) -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value) if value is not None else ""
    if num.is_integer():
        return str(int(num))
    return f"{num}".rstrip("0").rstrip(".")


def collapse_rows(rows: List[Dict[str, str]], fieldnames: List[str]) -> Tuple[List[Dict[str, str]], List[str]]:
    if "Phys MV" not in fieldnames:
        raise ValueError("Expected 'Phys MV' column in input.")
    numeric_start = fieldnames.index("Phys MV")
    output_columns = [col for col in fieldnames if col not in DROP_COLUMNS]
    col_positions = {col: idx for idx, col in enumerate(fieldnames)}
    numeric_columns = [
        col
        for col in output_columns
        if col_positions.get(col, 0) >= numeric_start and col != "PhysAtkAttribute"
    ]

    grouped: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    warnings: List[str] = []
    for row in rows:
        key = tuple(row.get(col, "") for col in GROUP_KEYS)
        if key not in grouped:
            grouped[key] = {col: row.get(col, "") for col in output_columns}
            # Normalize numeric seeds to floats when possible.
            for col in numeric_columns:
                num = parse_float(grouped[key].get(col, ""))
                if num is not None:
                    grouped[key][col] = num
            continue

        agg = grouped[key]
        for col in output_columns:
            if col in numeric_columns:
                num = parse_float(row.get(col, ""))
                if num is None:
                    continue
                current = parse_float(agg.get(col, 0))
                if current is None:
                    agg[col] = num
                else:
                    agg[col] = current + num
            else:
                # Keep the first value; record disagreement for visibility.
                existing = agg.get(col, "")
                incoming = row.get(col, "")
                if existing == "" and incoming != "":
                    agg[col] = incoming
                elif existing != incoming and incoming != "":
                    warnings.append(f"Disagreement on column '{col}' for key {key}: keeping '{existing}', saw '{incoming}'")

    # Finalize output rows with numeric formatting.
    output_rows: List[Dict[str, str]] = []
    for agg in grouped.values():
        out_row: Dict[str, str] = {}
        for col in output_columns:
            val = agg.get(col, "")
            if col in numeric_columns:
                out_row[col] = fmt_number(val)
            else:
                out_row[col] = val
        output_rows.append(out_row)
    return output_rows, warnings


def read_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return rows, fieldnames


def write_csv(rows: List[Dict[str, str]], fieldnames: List[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collapse AoW rows and sum numeric columns.")
    parser.add_argument("--input", type=Path, default=INPUT_DEFAULT, help="Path to AoW-data-1.csv")
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT, help="Path to write AoW-data-2.csv")
    args = parser.parse_args()

    rows, fieldnames = read_rows(args.input)
    output_rows, warnings = collapse_rows(rows, fieldnames)
    write_csv(output_rows, [col for col in fieldnames if col not in DROP_COLUMNS], args.output)

    print(f"Wrote {len(output_rows)} rows to {args.output}")
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        # Show a small sample to avoid noise.
        for msg in warnings[:20]:
            print(f"  - {msg}")
        if len(warnings) > 20:
            print(f"  ... {len(warnings) - 20} more")


if __name__ == "__main__":
    main()
