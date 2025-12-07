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
    "Bullet",
    "Weapon",
    "PhysAtkAttribute",
    "isAddBaseAtk",
    "Overwrite Scaling",
]

DROP_COLUMNS = {"Name", "Tick", "AtkId"}


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
    rounded = round(num, 1)
    if rounded.is_integer():
        return str(int(rounded))
    text = f"{rounded:.1f}"
    return text.rstrip("0").rstrip(".")


def collapse_rows(rows: List[Dict[str, str]], fieldnames: List[str]) -> Tuple[List[Dict[str, str]], List[str], List[str]]:
    if "Phys MV" not in fieldnames:
        raise ValueError("Expected 'Phys MV' column in input.")
    numeric_start = fieldnames.index("Phys MV")
    output_columns = [col for col in fieldnames if col not in DROP_COLUMNS]
    # Ensure Bullet sits next to Step in the output order.
    if "Bullet" in output_columns and "Step" in output_columns:
        output_columns.remove("Bullet")
        step_idx = output_columns.index("Step")
        output_columns.insert(step_idx + 1, "Bullet")
    if "Holy MV" in output_columns:
        idx = output_columns.index("Holy MV")
        output_columns[idx + 1 : idx + 1] = ["Dmg Type", "Dmg MV"]
    else:
        output_columns.extend(["Dmg Type", "Dmg MV"])

    col_positions = {col: idx for idx, col in enumerate(fieldnames)}
    numeric_columns = [
        col
        for col in output_columns
        if col in col_positions
        and col_positions.get(col, 0) >= numeric_start
        and col != "PhysAtkAttribute"
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

    def zero_for_disabled(agg_row: Dict[str, Any]) -> None:
        try:
            disable_flag = int(str(agg_row.get("Disable Gem Attr", "0") or "0"))
        except ValueError:
            disable_flag = 0
        if disable_flag != 1:
            return
        wep_fields = {
            "phys": "Wep Phys",
            "magic": "Wep Magic",
            "fire": "Wep Fire",
            "ltng": "Wep Ltng",
            "holy": "Wep Holy",
        }
        mv_fields = {
            "phys": "Phys MV",
            "magic": "Magic MV",
            "fire": "Fire MV",
            "ltng": "Ltng MV",
            "holy": "Holy MV",
        }
        for key, wep_col in wep_fields.items():
            mv_col = mv_fields[key]
            wep_val = parse_float(agg_row.get(wep_col, 0))
            if wep_val is not None and wep_val == 0:
                agg_row[mv_col] = 0

    def compute_damage_meta(agg_row: Dict[str, Any]) -> Tuple[str, float]:
        zero_for_disabled(agg_row)
        dmg_fields = [
            ("Phys", "Phys MV"),
            ("Magic", "Magic MV"),
            ("Fire", "Fire MV"),
            ("Ltng", "Ltng MV"),
            ("Holy", "Holy MV"),
        ]
        values = []
        for _, col in dmg_fields:
            val = parse_float(agg_row.get(col, 0))
            values.append(val if val is not None else 0.0)

        non_zero = [(name, val) for (name, _), val in zip(dmg_fields, values) if val > 0]
        has_zero = any(val == 0 for val in values)

        if not non_zero:
            return "-", 0.0

        dmg_mv = sum(val for _, val in non_zero) / len(non_zero) / 100.0

        if has_zero:
            dmg_type = " | ".join(name for name, _ in non_zero)
            if len(non_zero) > 1:
                max_val = max(val for _, val in non_zero)
                min_val = min(val for _, val in non_zero)
                if max_val > 0 and min_val < 0.75 * max_val:
                    return f"! | {dmg_type}", dmg_mv
            return dmg_type or "-", dmg_mv

        mn = min(val for _, val in non_zero)
        mx = max(val for _, val in non_zero)
        if mn > 0 and mx >= 2 * mn:
            return "!", dmg_mv

        if 1 < len(non_zero) < 5:
            max_val = max(val for _, val in non_zero)
            threshold = max_val * 0.75
            if any(val < threshold for _, val in non_zero if val == val):  # guard for NaN
                types = " | ".join(name for name, _ in non_zero)
                return f"! | {types}", dmg_mv
            return " | ".join(name for name, _ in non_zero), dmg_mv

        return "Weapon", dmg_mv

    # Finalize output rows with numeric formatting.
    output_rows: List[Dict[str, str]] = []
    for agg in grouped.values():
        dmg_type, dmg_mv = compute_damage_meta(agg)
        out_row: Dict[str, str] = {}
        for col in output_columns:
            val = agg.get(col, "")
            if col in numeric_columns:
                out_row[col] = fmt_number(val)
            elif col == "Dmg Type":
                out_row[col] = dmg_type
            elif col == "Dmg MV":
                out_row[col] = fmt_number(dmg_mv)
            else:
                out_row[col] = val
        output_rows.append(out_row)
    return output_rows, output_columns, warnings


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
    output_rows, output_columns, warnings = collapse_rows(rows, fieldnames)
    write_csv(output_rows, output_columns, args.output)

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
