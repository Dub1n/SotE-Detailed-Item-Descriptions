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

INPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-2.csv"
OUTPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-3.csv"

KEY_FIELDS = [
    "Skill",
    "Follow-up",
    "Hand",
    "Part",
    "Weapon",
    "Dmg Type",
    "Wep Status",
]

DROP_COLUMNS = {
    "Wep Poise Range",
    "Disable Gem Attr",
    "Wep Phys",
    "Wep Magic",
    "Wep Fire",
    "Wep Ltng",
    "Wep Holy",
}


def read_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return rows, fieldnames


def unique_join(values: List[str], sep: str = " | ") -> str:
    seen = set()
    ordered: List[str] = []
    for val in values:
        if not val or val == "-":
            continue
        if val not in seen:
            ordered.append(val)
            seen.add(val)
    return sep.join(ordered)


def aggregate_steps(
    rows: List[Dict[str, str]],
    col: str,
) -> str:
    """
    Build a zero-padded FP/Charged/Step string for the given column.
    Only include FP/Charged groups that exist in the input rows; pad Steps
    within each present group up to the max step in the set.
    Format (when present):
      fp1_uncharged[ | fp1_charged][ [fp0_uncharged[ | fp0_charged]]]
    """
    combos: Dict[tuple[int, int, int], str] = {}
    max_step = 1
    steps_by_group: Dict[tuple[int, int], int] = {}
    for row in rows:
        try:
            step = int(str(row.get("Step", "") or "1"))
        except ValueError:
            step = 1
        fp_val = 1 if str(row.get("FP", "")).strip() != "0" else 0
        charged_val = 1 if str(row.get("Charged", "")).strip() == "1" else 0
        max_step = max(max_step, step)
        steps_by_group[(fp_val, charged_val)] = max(
            steps_by_group.get((fp_val, charged_val), 1), step
        )
        combos[(fp_val, charged_val, step)] = str(row.get(col, "") or "0")

    def series(fp: int, charged: int) -> str | None:
        if (fp, charged) not in steps_by_group:
            return None
        values: List[str] = []
        for step in range(1, max_step + 1):
            values.append(combos.get((fp, charged, step), "0"))
        try:
            if all(float(v) == 0 for v in values):
                return None
        except ValueError:
            pass
        return ", ".join(values)

    fp1_uncharged = series(1, 0)
    fp1_charged = series(1, 1)
    fp0_uncharged = series(0, 0)
    fp0_charged = series(0, 1)
    fp1_parts = [p for p in (fp1_uncharged, fp1_charged) if p is not None]
    fp0_parts = [p for p in (fp0_uncharged, fp0_charged) if p is not None]

    fp1_text = " | ".join(fp1_parts)
    fp0_text = " | ".join(fp0_parts)

    if fp1_text and fp0_text:
        return f"{fp1_text} [{fp0_text}]"
    if fp1_text:
        return fp1_text
    if fp0_text:
        return f"[{fp0_text}]"
    return "-"


def fmt_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text


def collapse_weapons(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Second-pass collapse: merge rows that differ only by Weapon but share
    identical non-Weapon columns and numeric arrangement. Weapons are
    concatenated, and numeric positions become ranges when values differ.
    """
    fixed_cols = [
        "Skill",
        "Follow-up",
        "Hand",
        "Part",
        "Weapon Source",
        "Dmg Type",
        "Wep Status",
        "Overwrite Scaling",
        "subCategorySum",
    ]
    agg_cols = [
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

    def tokenize(text: str) -> List[tuple[str, str]]:
        parts = re.split(r"(-?\d+(?:\.\d+)?)", text)
        tokens: List[tuple[str, str]] = []
        for idx, part in enumerate(parts):
            if part == "":
                continue
            if idx % 2 == 1:
                tokens.append(("num", part))
            else:
                tokens.append(("sep", part))
        return tokens

    def pattern(text: str) -> Tuple[tuple[str, ...], int]:
        tokens = tokenize(text)
        shape: List[str] = []
        num_count = 0
        for kind, val in tokens:
            if kind == "num":
                shape.append("{n}")
                num_count += 1
            else:
                shape.append(val)
        return tuple(shape), num_count

    groups: Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], List[Dict[str, str]]] = {}
    shape_cache: Dict[str, Tuple[tuple[str, ...], int]] = {}
    for row in rows:
        patterns: List[str] = []
        num_counts: List[int] = []
        for col in agg_cols:
            val = row.get(col, "") or ""
            shape, count = shape_cache.setdefault(val, pattern(val))
            patterns.append("|".join(shape))
            num_counts.append(count)
        key = (
            tuple(row.get(col, "") for col in fixed_cols),
            tuple(patterns),
            tuple(num_counts),
        )
        groups.setdefault(key, []).append(row)

    merged: List[Dict[str, str]] = []
    for key, rows_in_group in groups.items():
        if len(rows_in_group) == 1:
            merged.append(rows_in_group[0])
            continue
        base_tokens: Dict[str, List[tuple[str, str]]] = {}
        for col in agg_cols:
            base_tokens[col] = tokenize(rows_in_group[0].get(col, "") or "")
        # Validate identical token shapes across rows.
        compatible = True
        for row in rows_in_group[1:]:
            for col in agg_cols:
                if tokenize(row.get(col, "") or "") != base_tokens[col]:
                    compatible = False
                    break
            if not compatible:
                break
        if not compatible:
            merged.extend(rows_in_group)
            continue

        out = dict(rows_in_group[0])
        # Merge weapons in seen order, deduped.
        weapons: List[str] = []
        for row in rows_in_group:
            for part in (row.get("Weapon", "") or "").split("|"):
                name = part.strip()
                if name and name not in weapons:
                    weapons.append(name)
        out["Weapon"] = " | ".join(weapons)

        # Merge numeric positions into ranges.
        for col in agg_cols:
            nums_by_idx: List[List[float]] = []
            tokens = base_tokens[col]
            # Collect numeric positions consistently across rows.
            tokenized_rows = [tokenize(row.get(col, "") or "") for row in rows_in_group]
            num_positions = [i for i, (k, _) in enumerate(tokens) if k == "num"]
            for pos_idx, token_idx in enumerate(num_positions):
                nums: List[float] = []
                for trow in tokenized_rows:
                    try:
                        num = float(trow[token_idx][1])
                    except (IndexError, ValueError):
                        num = 0.0
                    nums.append(num)
                nums_by_idx.append(nums)

            ranges: List[str] = []
            for vals in nums_by_idx:
                mn, mx = min(vals), max(vals)
                ranges.append(fmt_number(mn) if mn == mx else f"{fmt_number(mn)}-{fmt_number(mx)}")

            # Rebuild string.
            rebuilt_parts: List[str] = []
            range_idx = 0
            for kind, val in tokens:
                if kind == "num":
                    rebuilt_parts.append(ranges[range_idx])
                    range_idx += 1
                else:
                    rebuilt_parts.append(val)
            out[col] = "".join(rebuilt_parts)

        merged.append(out)

    return merged


def collapse_rows(
    rows: List[Dict[str, str]]
) -> Tuple[List[Dict[str, str]], List[str]]:
    grouped: Dict[Tuple[str, ...], List[Dict[str, str]]] = {}
    for row in rows:
        key = tuple(
            row.get(col, "")
            for col in [
                "Skill",
                "Follow-up",
                "Hand",
                "Part",
                "Weapon",
                "Dmg Type",
                "Wep Status",
            ]
        )
        grouped.setdefault(key, []).append(row)

    output_rows: List[Dict[str, str]] = []
    for rowset in grouped.values():
        base = rowset[0]
        out: Dict[str, str] = {
            "Skill": base.get("Skill", ""),
            "Follow-up": base.get("Follow-up", ""),
            "Hand": base.get("Hand", ""),
            "Part": base.get("Part", ""),
            "Weapon Source": base.get("Weapon Source", ""),
            "Weapon": base.get("Weapon", ""),
            "Dmg Type": base.get("Dmg Type", ""),
            "Wep Status": base.get("Wep Status", ""),
        }
        subcats: List[str] = []
        overwrite_vals: List[str] = []
        for row in rowset:
            for col in ("subCategory1", "subCategory2", "subCategory3", "subCategory4"):
                val = (row.get(col) or "").strip()
                if val and val not in subcats:
                    subcats.append(val)
            ov = (row.get("Overwrite Scaling") or "").strip()
            if ov and ov != "-" and ov not in overwrite_vals:
                overwrite_vals.append(ov)

        out["subCategorySum"] = " | ".join(subcats)
        out["Overwrite Scaling"] = ", ".join(overwrite_vals)

        agg_cols = [
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
        for col in agg_cols:
            out[col] = aggregate_steps(rowset, col)

        output_rows.append(out)

    merged_rows = collapse_weapons(output_rows)

    output_fields = [
        "Skill",
        "Follow-up",
        "Hand",
        "Part",
        "Weapon Source",
        "Weapon",
        "Dmg Type",
        "Dmg MV",
        "Status MV",
        "Wep Status",
        "Weapon Buff MV",
        "Stance Dmg",
        "AtkPhys",
        "AtkMag",
        "AtkFire",
        "AtkLtng",
        "AtkHoly",
        "Overwrite Scaling",
        "subCategorySum",
    ]
    return merged_rows, output_fields


def transform_rows(
    rows: List[Dict[str, str]], fieldnames: List[str]
) -> Tuple[List[Dict[str, str]], List[str]]:
    filtered_rows: List[Dict[str, str]] = []
    for row in rows:
        filtered_rows.append(
            {k: v for k, v in row.items() if k not in DROP_COLUMNS}
        )
    collapsed, output_fields = collapse_rows(filtered_rows)
    return collapsed, output_fields


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
        description="Stage 3 placeholder: pass AoW-data-2.csv through."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_DEFAULT,
        help="Path to AoW-data-2.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DEFAULT,
        help="Path to write AoW-data-3.csv",
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
