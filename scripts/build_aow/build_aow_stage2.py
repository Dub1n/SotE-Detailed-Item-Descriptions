import argparse
import csv
import json
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
VALUE_BLACKLIST_DEFAULT = ROOT / "work/aow_pipeline/value_blacklist.json"
COPY_ROWS_DEFAULT = ROOT / "work/aow_pipeline/copy_rows.json"

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

SUBCATEGORY_RENAMES = {
    "Charged Weapon Skill": "Charged Skill",
    "Charged R2": "Charged Attack",
    "Roar Attack": "Roar",
}

DAMAGE_ELEMENTS: List[Tuple[str, str, str]] = [
    ("Phys", "Phys MV", "Wep Phys"),
    ("Magic", "Magic MV", "Wep Magic"),
    ("Fire", "Fire MV", "Wep Fire"),
    ("Ltng", "Ltng MV", "Wep Ltng"),
    ("Holy", "Holy MV", "Wep Holy"),
]
MAX_DAMAGE_TYPES = 5
NEAR_EQUAL_THRESHOLD = 0.75


def load_value_blacklist(path: Path) -> Dict[str, Dict[str, List[str]]]:
    if not path.exists():
        return {}
    with path.open() as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse value blacklist at {path}: {exc}") from exc
    norm: Dict[str, Dict[str, List[str]]] = {}
    for stage, cols in data.items():
        stage_key = str(stage)
        if not isinstance(cols, dict):
            continue
        norm[stage_key] = {}
        for col, values in cols.items():
            if not isinstance(values, list):
                continue
            norm[stage_key][col] = [str(v) for v in values]
    return norm


def apply_value_blacklist(
    rows: List[Dict[str, str]],
    blacklist: Mapping[str, Mapping[str, List[str]]],
    *,
    stage_key: str,
) -> None:
    stage_rules = blacklist.get(stage_key, {})
    if not stage_rules:
        return
    for row in rows:
        for col, banned in stage_rules.items():
            val = row.get(col)
            if val is None:
                continue
            if val.strip() in banned:
                row[col] = ""


def load_copy_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse copy rows at {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(
            f"copy rows file must be a list, got {type(data).__name__}"
        )
    entries: List[Dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or entry.get("Name")
        copies_raw = entry.get("copies") or entry.get("Copies") or []
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(copies_raw, list):
            continue
        norm_copies: List[Dict[str, str]] = []
        for copy_entry in copies_raw:
            if not isinstance(copy_entry, dict):
                continue
            overrides = copy_entry.get("overrides")
            overrides = overrides if isinstance(overrides, dict) else copy_entry
            norm_copies.append(
                {str(k): str(v) for k, v in overrides.items()}
            )
        if norm_copies:
            entries.append({"name": name, "copies": norm_copies})
    return entries


def apply_row_copies(
    rows: List[Dict[str, str]],
    fieldnames: List[str],
    copies: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, str]], List[str], List[str]]:
    if not copies:
        return rows, [], []
    added: List[Dict[str, str]] = []
    notes: List[str] = []
    warnings: List[str] = []
    unknown_warned: Set[Tuple[str, str]] = set()
    by_name: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        by_name.setdefault(row.get("Name", ""), []).append(row)

    for entry in copies:
        name = entry.get("name")
        copy_list = entry.get("copies") or []
        base_rows = by_name.get(name, [])
        if not base_rows:
            warnings.append(f"No rows found to copy for Name '{name}'")
            continue
        added_count = 0
        for overrides in copy_list:
            for base_row in base_rows:
                new_row = dict(base_row)
                for col, val in overrides.items():
                    if col not in fieldnames:
                        warn_key = (name, col)
                        if warn_key not in unknown_warned:
                            warnings.append(
                                f"Unknown column '{col}' in copy for Name '{name}'"
                            )
                            unknown_warned.add(warn_key)
                    new_row[col] = str(val)
                added.append(new_row)
                added_count += 1
        notes.append(f"{name}: added {added_count} copied row(s)")
    return rows + added, notes, warnings


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


def normalize_subcategory_value(value: str) -> str:
    if value is None:
        return value
    text = str(value).strip()
    return SUBCATEGORY_RENAMES.get(text, text)


def normalize_subcategory_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    for idx in range(1, 5):
        col = f"subCategory{idx}"
        if col in normalized:
            normalized[col] = normalize_subcategory_value(normalized[col])
    return normalized


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
    if "PhysAtkAttribute" in output_columns:
        output_columns.remove("PhysAtkAttribute")
        output_source_map.pop("PhysAtkAttribute", None)
    col_positions = {col: idx for idx, col in enumerate(fieldnames)}
    non_numeric_trail_cols = {
        "PhysAtkAttribute",
        "Wep Status",
        "isAddBaseAtk",
        "Overwrite Scaling",
        "subCategory1",
        "subCategory2",
        "subCategory3",
        "subCategory4",
    }
    numeric_columns = [
        col
        for col in output_columns
        if (source := output_source_map.get(col)) in col_positions
        and col_positions.get(source, 0) >= numeric_start
        and source not in non_numeric_trail_cols
    ]

    grouped: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    warnings: List[str] = []
    forced_seen: Set[str] = set()

    # Normalize subcategory labels before any grouping or force overrides.
    rows = [normalize_subcategory_row(row) for row in rows]

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
        # Normalize Dmg Type to "-" when Dmg MV is 0 before grouping.
        dmg_mv_val = parse_float(working_row.get("Dmg MV"))
        if dmg_mv_val == 0:
            working_row["Dmg Type"] = "-"
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
                    skip_warn = False
                    if col == "Dmg Type" and (
                        existing == "-" or incoming == "-"
                    ):
                        skip_warn = True
                    if col == "Overwrite Scaling" and (
                        existing == "null" or incoming == "null"
                    ):
                        skip_warn = True
                    if not skip_warn:
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

    def compute_damage_entries(agg_row: Dict[str, Any]) -> List[Tuple[str, float]]:
        zero_for_disabled(agg_row)
        attr_raw = (
            agg_row.get("_phys_attr") or agg_row.get("PhysAtkAttribute") or ""
        )
        attr_text = str(attr_raw).strip()
        attr_lower = attr_text.lower()
        attr_is_weapon = attr_lower in {"252", "253", "weapon"}

        entries_raw: List[Tuple[str, float, float | None]] = []
        for key, mv_col, wep_col in DAMAGE_ELEMENTS:
            mv_val = parse_float(agg_row.get(mv_col, 0))
            if mv_val is None or mv_val <= 0:
                continue
            wep_val = parse_float(agg_row.get(wep_col, 0))
            entries_raw.append((key, mv_val, wep_val))

        if not entries_raw:
            return []

        wep_non_zero = [
            wep for _, _, wep in entries_raw if wep is not None and wep > 0
        ]
        avg_wep = (
            sum(wep_non_zero) / len(wep_non_zero) if wep_non_zero else None
        )

        def scaled_mv(mv: float, wep: float | None) -> float:
            if avg_wep and wep is not None and len(entries_raw) > 1:
                return mv * (wep / avg_wep)
            return mv

        def phys_label(count: int) -> str:
            if 2 <= count <= 4:
                return attr_text if attr_text and not attr_is_weapon else "Weapon"
            if near_equal:
                if attr_is_weapon or not attr_text:
                    return "Weapon"
                return f"Weapon ({attr_text} Physical)"
            if attr_is_weapon or not attr_text:
                return "Weapon"
            return attr_text

        type_labels = {
            "Magic": "Magic",
            "Fire": "Fire",
            "Ltng": "Lightning",
            "Holy": "Holy",
        }

        # Special-case: when multiple elemental MVs share the same value,
        # collapse to a single "Damage" entry (optionally with phys suffix).
        distinct_mv_values = {mv for _, mv, _ in entries_raw}
        if len(entries_raw) >= 2 and len(distinct_mv_values) == 1:
            phys_mv_present = any(key == "Phys" for key, _, _ in entries_raw)
            base_label = "Damage"
            if phys_mv_present and not attr_is_weapon and attr_text:
                base_label = f"{base_label} ({attr_text} Physical)"
            first_mv = entries_raw[0][1]
            return [(base_label, first_mv)]

        mv_values = [mv for _, mv, _ in entries_raw]
        min_mv, max_mv = min(mv_values), max(mv_values)
        near_equal = (
            len(entries_raw) >= 2
            and max_mv > 0
            and min_mv >= NEAR_EQUAL_THRESHOLD * max_mv
        )

        # Special-case: all five elemental MVs are present -> single Weapon average.
        if len(entries_raw) == 5:
            scaled = [scaled_mv(mv, wep) for _, mv, wep in entries_raw]
            avg_val = sum(scaled) / len(scaled) if scaled else 0.0
            return [("Weapon", avg_val)]

        entries: List[Tuple[str, float]] = []
        for key, mv_val, wep_val in entries_raw:
            if key == "Phys":
                label = phys_label(len(entries_raw))
            else:
                label = type_labels.get(key, key)
            entries.append((label, scaled_mv(mv_val, wep_val)))

        return entries[:MAX_DAMAGE_TYPES]

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
    pending_rows: List[Tuple[Dict[str, Any], List[Tuple[str, float]]]] = []
    max_damage_slots = 0
    for agg in grouped.values():
        entries = compute_damage_entries(agg)
        if not has_nonzero_damage_data(agg):
            continue
        if not entries:
            entries = [("", "")]
        max_damage_slots = max(max_damage_slots, len(entries))

        if parse_float(agg.get("Weapon Buff MV", 0)) == 0 and all(
            parse_float(agg.get(col, 0)) == 0
            for col in ["AtkPhys", "AtkMag", "AtkFire", "AtkLtng", "AtkHoly"]
        ):
            agg["Overwrite Scaling"] = "null"

        poise_range_text, poise_range_bounds = summarize_range(
            agg.get("Wep Poise Range", "")
        )
        stance_dmg = compute_stance_damage(
            poise_range_bounds,
            agg.get("Stance Dmg", ""),
            agg.get("_stance_super", 0.0),
        )
        base_row: Dict[str, Any] = {}
        for col in output_columns:
            val = agg.get(col, "")
            if col == "Wep Poise Range":
                base_row[col] = poise_range_text
            elif col == "Stance Dmg":
                base_row[col] = stance_dmg
            else:
                base_row[col] = val
        pending_rows.append((base_row, entries))

    # Ensure we always emit at least one Dmg Type/MV column.
    pair_count = max(1, min(max_damage_slots or 1, MAX_DAMAGE_TYPES))
    mv_indices = [
        output_columns.index(col)
        for col in ["Holy MV", "Ltng MV", "Fire MV", "Magic MV", "Phys MV"]
        if col in output_columns
    ]
    insert_idx = max(mv_indices) if mv_indices else len(output_columns) - 1
    dmg_pair_columns: List[str] = []
    for idx in range(1, pair_count + 1):
        dmg_pair_columns.extend([f"Dmg Type {idx}", f"Dmg MV {idx}"])
    final_output_columns = list(output_columns)
    final_output_columns[insert_idx + 1: insert_idx + 1] = dmg_pair_columns

    numeric_set = set(numeric_columns)
    output_rows: List[Dict[str, str]] = []
    for base_row, entries in pending_rows:
        out_row: Dict[str, str] = {}
        for col in final_output_columns:
            if col.startswith("Dmg Type "):
                idx = int(col.split()[-1]) - 1
                out_row[col] = entries[idx][0] if idx < len(entries) else ""
                continue
            if col.startswith("Dmg MV "):
                idx = int(col.split()[-1]) - 1
                mv_val = entries[idx][1] if idx < len(entries) else ""
                out_row[col] = fmt_number(mv_val) if mv_val != "" else ""
                continue
            val = base_row.get(col, "")
            if col == "Wep Poise Range" or col == "Stance Dmg":
                out_row[col] = val
            elif col in numeric_set:
                out_row[col] = fmt_number(val)
            else:
                out_row[col] = val
        output_rows.append(out_row)

    return output_rows, final_output_columns, warnings, sorted(forced_seen)


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
    parser.add_argument(
        "--value-blacklist",
        type=Path,
        default=VALUE_BLACKLIST_DEFAULT,
        help="Path to value_blacklist.json",
    )
    parser.add_argument(
        "--copy-rows",
        type=Path,
        default=COPY_ROWS_DEFAULT,
        help="Path to copy_rows.json",
    )
    args = parser.parse_args()

    copy_rows = load_copy_rows(args.copy_rows)
    value_blacklist = load_value_blacklist(args.value_blacklist)
    force_groups, force_overrides, force_primary = load_force_collapse_map(
        args.force_collapse
    )
    before_rows = load_rows_by_key(args.output, GROUP_KEYS)
    rows, fieldnames = read_rows(args.input)
    rows, copy_notes, copy_warnings = apply_row_copies(
        rows, fieldnames, copy_rows
    )
    apply_value_blacklist(rows, value_blacklist, stage_key="2")
    output_rows, output_columns, warnings, forced_groups = collapse_rows(
        rows,
        fieldnames,
        force_groups=force_groups,
        force_overrides=force_overrides,
        force_primary=force_primary,
    )
    warnings = copy_warnings + warnings
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
    if copy_notes:
        print(f"Copied rows ({len(copy_notes)}):")
        for note in copy_notes:
            print(f"  - {note}")
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
