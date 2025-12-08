import argparse
import csv
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Tuple, Any, Mapping, Set


ROOT = Path(__file__).resolve().parents[2]
HELPERS_DIR = ROOT / "scripts"
if str(HELPERS_DIR) not in sys.path:
    sys.path.append(str(HELPERS_DIR))

from helpers.diff import (  # noqa: E402
    load_rows_by_key,
    report_row_deltas,
)
from helpers.force_collapse import (  # noqa: E402
    load_force_collapse_map,
)
from helpers.output import format_path_for_console  # noqa: E402
INPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-1.csv"
OUTPUT_DEFAULT = ROOT / "work/aow_pipeline/AoW-data-2.csv"
FORCE_COLLAPSE_DEFAULT = ROOT / "work/aow_pipeline/force_collapse_pairs.json"

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
STANCE_SUPERARMOR_COL = "AtkSuperArmor"
RENAME_MAP = {
    "Weapon Poise": "Wep Poise Range",
    "Poise Dmg MV": "Stance Dmg",
}

# Columns that indicate whether a row carries any meaningful damage data.
ZERO_MV_ATK_COLUMNS = [
    "Phys MV",
    "Magic MV",
    "Fire MV",
    "Ltng MV",
    "Holy MV",
    "Status MV",
    "Weapon Buff MV",
    "Stance Dmg",  # Source: Poise Dmg MV
    "AtkPhys",
    "AtkMag",
    "AtkFire",
    "AtkLtng",
    "AtkHoly",
]


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


def round_half_up(value: float) -> int:
    quantized = Decimal(str(value)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(quantized)


def summarize_range(raw_value: Any) -> Tuple[str, Tuple[float, float] | None]:
    """
    Collapse a pipe-delimited range like '5.5 | 5' to a min-max string.
    Returns (text, (min, max)) where the bounds are None when no numbers
    are found.
    """
    text = str(raw_value or "").strip()
    if not text:
        return "", None
    values = []
    for part in text.split("|"):
        piece = part.strip()
        if not piece:
            continue
        num = parse_float(piece)
        if num is not None:
            values.append(num)
    if not values:
        return text, None
    mn, mx = min(values), max(values)
    if mn == mx:
        return fmt_number(mn), (mn, mx)
    return f"{fmt_number(mn)}-{fmt_number(mx)}", (mn, mx)


def compute_stance_damage(
    poise_range: Tuple[float, float] | None,
    poise_mv_value: Any,
    super_armor_value: Any,
) -> str:
    if poise_range is None:
        return ""
    poise_mv = parse_float(poise_mv_value)
    if poise_mv is None:
        return ""
    super_val = parse_float(super_armor_value)
    if super_val is None:
        super_val = 0.0
    mn, mx = poise_range
    low = round_half_up(mn * poise_mv / 100 + super_val)
    high = round_half_up(mx * poise_mv / 100 + super_val)
    if low == high:
        return str(low)
    return f"{low}-{high}"


def collapse_rows(
    rows: List[Dict[str, str]],
    fieldnames: List[str],
    *,
    force_groups: Mapping[str, str] | None = None,
    force_overrides: Mapping[str, Dict[str, str]] | None = None,
    force_primary: Mapping[str, str] | None = None,
) -> Tuple[List[Dict[str, str]], List[str], List[str], List[str]]:
    force_groups = force_groups or {}
    force_overrides = force_overrides or {}
    force_primary = force_primary or {}
    if "Phys MV" not in fieldnames:
        raise ValueError("Expected 'Phys MV' column in input.")
    numeric_start = fieldnames.index("Phys MV")
    base_output_columns = [
        col
        for col in fieldnames
        if col not in DROP_COLUMNS and col != STANCE_SUPERARMOR_COL
    ]
    output_columns = [RENAME_MAP.get(col, col) for col in base_output_columns]
    output_source_map = {
        out: src for out, src in zip(output_columns, base_output_columns)
    }
    has_phys_attr = "PhysAtkAttribute" in fieldnames
    # Ensure Bullet sits next to Step in the output order.
    if "Bullet" in output_columns and "Step" in output_columns:
        output_columns.remove("Bullet")
        step_idx = output_columns.index("Step")
        output_columns.insert(step_idx + 1, "Bullet")
    if "Holy MV" in output_columns:
        idx = output_columns.index("Holy MV")
        output_columns[idx + 1: idx + 1] = ["Dmg Type", "Dmg MV"]
    else:
        output_columns.extend(["Dmg Type", "Dmg MV"])
    output_source_map["Dmg Type"] = None
    output_source_map["Dmg MV"] = None
    if "PhysAtkAttribute" in output_columns:
        output_columns.remove("PhysAtkAttribute")
        output_source_map.pop("PhysAtkAttribute", None)
    col_positions = {col: idx for idx, col in enumerate(fieldnames)}
    numeric_columns = [
        col
        for col in output_columns
        if (source := output_source_map.get(col)) in col_positions
        and col_positions.get(source, 0) >= numeric_start
        and source not in {"PhysAtkAttribute", "Wep Status"}
    ]

    grouped: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    warnings: List[str] = []
    forced_seen: Set[str] = set()

    def source_value(row: Mapping[str, str], col: str) -> Any:
        source_col = output_source_map.get(col, col)
        return row.get(source_col, "")

    forced_names = set(force_groups.keys())
    rows_by_name = {
        row.get("Name", ""): row for row in rows if row.get("Name", "")
    }
    canonical_map: Dict[str, Dict[str, str]] = {}
    warn_cols_set = {col for col in output_columns if col not in numeric_columns}
    warn_cols_set.update(
        {
            "Weapon Source",
            "Weapon",
            "Weapon Poise",
            "Disable Gem Attr",
            "PhysAtkAttribute",
            "isAddBaseAtk",
            "Overwrite Scaling",
            "subCategory1",
            "subCategory2",
            "subCategory3",
            "subCategory4",
        }
    )
    warn_cols: List[str] = sorted(warn_cols_set)
    name_derived_cols = {
        "Name",
        "Skill",
        "Follow-up",
        "Hand",
        "Part",
        "FP",
        "Charged",
        "Step",
        "Bullet",
        "Tick",
    }
    for group_id, primary in force_primary.items():
        base_row = rows_by_name.get(primary)
        if base_row is None:
            # Fallback to any row in the group if primary missing.
            base_row = next(
                (
                    rows_by_name.get(name)
                    for name, gid in force_groups.items()
                    if gid == group_id and rows_by_name.get(name)
                ),
                {},
            )
        base_row = base_row or {}
        overrides = force_overrides.get(group_id, {})
        canonical_map[group_id] = {}
        for col in warn_cols:
            canonical_map[group_id][col] = overrides.get(
                col, source_value(base_row, col)
            )

    def parse_super(val: Any) -> float:
        parsed = parse_float(val)
        return parsed if parsed is not None else 0.0

    for row in rows:
        name = row.get("Name", "")
        raw_row = dict(row)
        working_row = dict(row)
        if name in force_groups:
            group_id = force_groups[name]
            key = ("__FORCED__", group_id)
            forced_seen.add(group_id)
            canon = canonical_map.get(group_id, {})
            overrides = force_overrides.get(group_id, {})
            if canon:
                for col in warn_cols:
                    if col in overrides:
                        continue
                    if col in name_derived_cols:
                        continue
                    raw_val = source_value(raw_row, col)
                    canon_val = canon.get(col, "")
                    if str(raw_val) != str(canon_val):
                        warnings.append(
                            f"Disagreement on column '{col}' for key {key}: "
                            f"keeping '{canon_val}', saw '{raw_val}'"
                        )
                for col, val in canon.items():
                    working_row[col] = val
            if overrides:
                for col, val in overrides.items():
                    working_row[col] = val
        else:
            key = tuple(row.get(col, "") for col in GROUP_KEYS)
        if key not in grouped:
            grouped[key] = {
                col: source_value(working_row, col) for col in output_columns
            }
            if has_phys_attr:
                grouped[key]["_phys_attr"] = working_row.get(
                    "PhysAtkAttribute", ""
                )
            grouped[key]["_stance_super"] = parse_super(
                working_row.get(STANCE_SUPERARMOR_COL, "")
            )
            # Normalize numeric seeds to floats when possible.
            for col in numeric_columns:
                num = parse_float(grouped[key].get(col, ""))
                if num is not None:
                    grouped[key][col] = num
            continue

        agg = grouped[key]
        if has_phys_attr and "_phys_attr" not in agg:
            agg["_phys_attr"] = working_row.get("PhysAtkAttribute", "")
        agg["_stance_super"] = agg.get("_stance_super", 0.0) + parse_super(
            working_row.get(STANCE_SUPERARMOR_COL, "")
        )
        for col in output_columns:
            if col in numeric_columns:
                num = parse_float(source_value(working_row, col))
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
                incoming = source_value(working_row, col)
                if existing == "" and incoming != "":
                    agg[col] = incoming
                elif existing != incoming and incoming != "":
                    warnings.append(
                        f"Disagreement on column '{col}' for key {key}: "
                        f"keeping '{existing}', saw '{incoming}'"
                    )

    def zero_for_disabled(agg_row: Dict[str, Any]) -> None:
        try:
            disable_flag = int(
                str(agg_row.get("Disable Gem Attr", "0") or "0")
            )
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

        attr = (
            agg_row.get("_phys_attr") or agg_row.get("PhysAtkAttribute") or ""
        ).strip()
        non_zero = [
            (name, val)
            for (name, _), val in zip(dmg_fields, values)
            if val > 0
        ]
        has_zero = any(val == 0 for val in values)

        if not non_zero:
            dmg_type, dmg_mv = "-", 0.0
        else:
            dmg_mv = sum(val for _, val in non_zero) / len(non_zero) / 100.0

            if has_zero:
                dmg_type = " | ".join(name for name, _ in non_zero)
                if len(non_zero) > 1:
                    max_val = max(val for _, val in non_zero)
                    min_val = min(val for _, val in non_zero)
                    if max_val > 0 and min_val < 0.75 * max_val:
                        dmg_type = f"! | {dmg_type}"
            else:
                mn = min(val for _, val in non_zero)
                mx = max(val for _, val in non_zero)
                if mn > 0 and mx >= 2 * mn:
                    dmg_type = "!"
                elif 1 < len(non_zero) < 5:
                    max_val = max(val for _, val in non_zero)
                    threshold = max_val * 0.75
                    if any(
                        val < threshold for _, val in non_zero if val == val
                    ):  # guard for NaN
                        types = " | ".join(name for name, _ in non_zero)
                        dmg_type = f"! | {types}"
                    else:
                        dmg_type = " | ".join(name for name, _ in non_zero)
                else:
                    dmg_type = "Weapon"

        if attr and attr not in {"252", "253"}:
            dmg_type = attr
        return dmg_type, dmg_mv

    def has_nonzero_damage_data(agg_row: Mapping[str, Any]) -> bool:
        for col in ZERO_MV_ATK_COLUMNS:
            val = parse_float(agg_row.get(col, 0))
            # Keep rows with malformed data to avoid false drops.
            if val is None or val != val:  # NaN check via self-inequality
                return True
            if val != 0:
                return True
        super_val = parse_float(agg_row.get("_stance_super", 0))
        if super_val is None or super_val != super_val:
            return True
        return super_val != 0

    # Finalize output rows with numeric formatting.
    output_rows: List[Dict[str, str]] = []
    for agg in grouped.values():
        dmg_type, dmg_mv = compute_damage_meta(agg)
        if not has_nonzero_damage_data(agg):
            continue
        poise_range_text, poise_range_bounds = summarize_range(
            agg.get("Wep Poise Range", "")
        )
        stance_dmg = compute_stance_damage(
            poise_range_bounds,
            agg.get("Stance Dmg", ""),
            agg.get("_stance_super", 0.0),
        )
        out_row: Dict[str, str] = {}
        for col in output_columns:
            val = agg.get(col, "")
            if col == "Wep Poise Range":
                out_row[col] = poise_range_text
            elif col == "Stance Dmg":
                out_row[col] = stance_dmg
            elif col in numeric_columns:
                out_row[col] = fmt_number(val)
            elif col == "Dmg Type":
                out_row[col] = dmg_type
            elif col == "Dmg MV":
                out_row[col] = fmt_number(dmg_mv)
            else:
                out_row[col] = val
        output_rows.append(out_row)
    return output_rows, output_columns, warnings, sorted(forced_seen)


def read_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return rows, fieldnames


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
        description="Collapse AoW rows and sum numeric columns."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=INPUT_DEFAULT,
        help="Path to AoW-data-1.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DEFAULT,
        help="Path to write AoW-data-2.csv",
    )
    parser.add_argument(
        "--force-collapse",
        type=Path,
        default=FORCE_COLLAPSE_DEFAULT,
        help="Path to JSON list of Name pairs to force-collapse.",
    )
    args = parser.parse_args()

    force_groups, force_overrides, force_primary = load_force_collapse_map(
        args.force_collapse
    )
    before_rows = load_rows_by_key(args.output, GROUP_KEYS)
    rows, fieldnames = read_rows(args.input)
    output_rows, output_columns, warnings, forced_groups = collapse_rows(
        rows,
        fieldnames,
        force_groups=force_groups,
        force_overrides=force_overrides,
        force_primary=force_primary,
    )
    write_csv(output_rows, output_columns, args.output)

    path_text = format_path_for_console(args.output, ROOT)
    print(f"Wrote {len(output_rows)} rows to {path_text}")
    report_row_deltas(
        before_rows=before_rows,
        after_rows=output_rows,
        fieldnames=output_columns,
        key_fields=GROUP_KEYS,
        align_columns=True,
    )
    if forced_groups:
        if len(forced_groups) <= 10:
            print(f"Forced ({len(forced_groups)}) collapse:")
            for label in forced_groups:
                print(f"  - {label}")
        else:
            print(f"Forced ({len(forced_groups)}) collapses")
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        # Show a small sample to avoid noise.
        for msg in warnings[:20]:
            print(f"  - {msg}")
        if len(warnings) > 20:
            print(f"  ... {len(warnings) - 20} more")


if __name__ == "__main__":
    main()
