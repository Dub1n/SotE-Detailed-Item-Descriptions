import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, NamedTuple


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

AGG_COLS = [
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


class StepLayout(NamedTuple):
    max_step: int
    has_fp1: bool
    has_fp0: bool
    has_charged: bool


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


def zeros_only(text: str) -> bool:
    nums = re.findall(r"-?\d+(?:\.\d+)?", text or "")
    if not nums:
        return False
    return all(float(n) == 0 for n in nums)


def aggregate_steps(
    rows: List[Dict[str, str]],
    col: str,
    layout: StepLayout,
) -> str:
    """
    Build a zero-padded FP/Charged/Step string for the given column using the
    provided layout so every numeric column in the collapsed row shares the
    same arrangement.
    Format (when present):
      fp1_uncharged[ | fp1_charged][ [fp0_uncharged[ | fp0_charged]]]
    """
    value_map: Dict[tuple[int, int, int], str] = {}
    for row in rows:
        try:
            step = int(str(row.get("Step", "") or "1"))
        except ValueError:
            step = 1
        fp_val = 0 if str(row.get("FP", "")).strip() == "0" else 1
        charged_val = 1 if str(row.get("Charged", "")).strip() == "1" else 0
        value_map[(fp_val, charged_val, step)] = str(row.get(col, "") or "0").strip()

    def series(fp: int, charged: int) -> str:
        values: List[str] = []
        for step in range(1, layout.max_step + 1):
            values.append(value_map.get((fp, charged, step), "0"))
        return ", ".join(values)

    def fp_block(fp: int) -> str:
        uncharged = series(fp, 0)
        if layout.has_charged:
            charged = series(fp, 1)
            return f"{uncharged} | {charged}"
        return uncharged

    parts: List[str] = []
    if layout.has_fp1:
        parts.append(fp_block(1))

    if layout.has_fp0:
        fp0_text = fp_block(0)
        bracket = f"[{fp0_text}]"
        if parts:
            return f"{parts[0]} {bracket}"
        return bracket

    if parts:
        return parts[0]
    return "-"


def build_step_layout(rows: List[Dict[str, str]]) -> StepLayout:
    max_step = 1
    has_fp0 = False
    has_fp1 = False
    has_charged = False
    for row in rows:
        try:
            step = int(str(row.get("Step", "") or "1"))
        except ValueError:
            step = 1
        max_step = max(max_step, step)
        fp_val = 0 if str(row.get("FP", "")).strip() == "0" else 1
        charged_val = 1 if str(row.get("Charged", "")).strip() == "1" else 0
        has_fp0 = has_fp0 or fp_val == 0
        has_fp1 = has_fp1 or fp_val == 1
        has_charged = has_charged or charged_val == 1

    return StepLayout(
        max_step=max_step,
        has_fp1=has_fp1,
        has_fp0=has_fp0,
        has_charged=has_charged,
    )


def fmt_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text


def collapse_weapons(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Second-pass collapse: merge rows that differ only by Weapon but share
    identical non-Weapon columns and numeric arrangement. Merge only when
    every Weapon in the Skill/Hand/Part/DmgType/WepStatus cluster has the
    same set of numeric shapes (symmetry guard).
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

    def shape(text: str) -> Tuple[tuple[str, ...], int]:
        tokens = tokenize(text)
        pattern: List[str] = []
        count = 0
        for kind, val in tokens:
            if kind == "num":
                pattern.append("{n}")
                count += 1
            else:
                pattern.append(val)
        return tuple(pattern), count

    # Cluster by non-weapon fields (treat Dmg Type "-" as wild and Overwrite Scaling "null" as wild).
    clusters: Dict[Tuple[str, ...], List[Dict[str, str]]] = {}
    for row in rows:
        dtype = row.get("Dmg Type", "")
        dtype_key = "__ANY_DMG__" if dtype == "-" else dtype
        overw = row.get("Overwrite Scaling", "")
        overw_key = "__NULL__" if overw == "null" else overw
        key_parts = []
        for col in fixed_cols:
            if col == "Dmg Type":
                key_parts.append(dtype_key)
            elif col == "Overwrite Scaling":
                key_parts.append(overw_key)
            else:
                key_parts.append(row.get(col, ""))
        key = tuple(key_parts)
        clusters.setdefault(key, []).append(row)

    merged: List[Dict[str, str]] = []
    for key, bucket in clusters.items():
        # Build weapon -> set of shapes to ensure symmetry.
        shapes_by_weapon: Dict[str, set] = {}
        rows_by_shape_weapon: Dict[Tuple[str, ...], Dict[str, List[Dict[str, str]]]] = {}
        for row in bucket:
            weapon = row.get("Weapon", "").strip()
            shape_key: Tuple[str, ...] = []
            for col in AGG_COLS:
                pat, _ = shape(row.get(col, "") or "")
                shape_key += pat
            shape_key = tuple(shape_key)
            shapes_by_weapon.setdefault(weapon, set()).add(shape_key)
            rows_by_shape_weapon.setdefault(shape_key, {}).setdefault(weapon, []).append(row)

        # Only merge if every weapon has identical shape set.
        shape_sets = list(shapes_by_weapon.values())
        if not shape_sets:
            merged.extend(bucket)
            continue
        if any(s != shape_sets[0] for s in shape_sets[1:]):
            merged.extend(bucket)
            continue

        # Merge per shape key.
        for shape_key, weapon_rows in rows_by_shape_weapon.items():
            # All weapons should be present; otherwise skip merge for safety.
            if len(weapon_rows) != len(shapes_by_weapon):
                for rows_list in weapon_rows.values():
                    merged.extend(rows_list)
                continue

            # Use first row as base.
            base_weapon = next(iter(weapon_rows))
            base_row = weapon_rows[base_weapon][0]
            out = dict(base_row)
            # Resolve Dmg Type preferring non-"-".
            dtype_candidates = [
                r.get("Dmg Type", "") for rows_list in weapon_rows.values() for r in rows_list
            ]
            chosen_dtype = next(
                (d for d in dtype_candidates if d and d != "-"), base_row.get("Dmg Type", ""))
            out["Dmg Type"] = chosen_dtype or "-"
            # Resolve Overwrite Scaling preferring non-"null"/non-empty.
            ovw_candidates = [
                r.get("Overwrite Scaling", "") for rows_list in weapon_rows.values() for r in rows_list
            ]
            chosen_ovw = next(
                (o for o in ovw_candidates if o and o != "null"), None
            )
            out["Overwrite Scaling"] = chosen_ovw if chosen_ovw is not None else "null"

            # Merge weapons.
            weapons: List[str] = []
            for weapon in weapon_rows:
                name = weapon.strip()
                if name and name not in weapons:
                    weapons.append(name)
            out["Weapon"] = " | ".join(weapons)

            # Merge numeric ranges using token shape of base.
            token_cache = {col: tokenize(out.get(col, "") or "") for col in AGG_COLS}
            for col in AGG_COLS:
                tokens = token_cache[col]
                num_positions = [i for i, (k, _) in enumerate(tokens) if k == "num"]
                all_nums_by_pos: List[List[float]] = [[] for _ in num_positions]
                for w_rows in weapon_rows.values():
                    row = w_rows[0]
                    row_tokens = tokenize(row.get(col, "") or "")
                    for idx, pos in enumerate(num_positions):
                        try:
                            num = float(row_tokens[pos][1])
                        except (IndexError, ValueError):
                            num = 0.0
                        all_nums_by_pos[idx].append(num)
                ranges: List[str] = []
                for vals in all_nums_by_pos:
                    mn, mx = min(vals), max(vals)
                    ranges.append(fmt_number(mn) if mn == mx else f"{fmt_number(mn)}-{fmt_number(mx)}")
                rebuilt: List[str] = []
                r_idx = 0
                for kind, val in tokens:
                    if kind == "num":
                        rebuilt.append(ranges[r_idx])
                        r_idx += 1
                    else:
                        rebuilt.append(val)
                out[col] = "".join(rebuilt)

            for col in AGG_COLS:
                if zeros_only(out.get(col, "")):
                    out[col] = "-"

            merged.append(out)

    return merged


def mask_zero_only_cells(rows: List[Dict[str, str]]) -> None:
    for row in rows:
        for col in AGG_COLS:
            if col in row and zeros_only(row.get(col, "")):
                row[col] = "-"


def build_layout_map(rows: List[Dict[str, str]]) -> Dict[Tuple[str, str, str], StepLayout]:
    """
    Build shared FP/Charged/Step layouts per (Skill, Follow-up, Hand) so all
    rows of a skill use the widest zero-padding even across different parts.
    """
    grouped: Dict[Tuple[str, str, str], List[Dict[str, str]]] = {}
    for row in rows:
        key = (
            row.get("Skill", ""),
            row.get("Follow-up", ""),
            row.get("Hand", ""),
        )
        grouped.setdefault(key, []).append(row)
    return {key: build_step_layout(rset) for key, rset in grouped.items()}


def collapse_rows(
    rows: List[Dict[str, str]],
    layout_map: Dict[Tuple[str, str, str], StepLayout],
) -> Tuple[List[Dict[str, str]], List[str]]:
    clusters: Dict[Tuple[str, ...], List[Dict[str, str]]] = {}
    for row in rows:
        key = tuple(
            row.get(col, "")
            for col in [
                "Skill",
                "Follow-up",
                "Hand",
                "Part",
                "Weapon Source",
                "Weapon",
                "Wep Status",
            ]
        )
        clusters.setdefault(key, []).append(row)

    output_rows: List[Dict[str, str]] = []
    for rowset in clusters.values():
        primary_dtype = next(
            (r.get("Dmg Type", "") for r in rowset if r.get("Dmg Type", "") not in {"", "-"}),
            "-",
        )
        primary_overwrite = next(
            (
                r.get("Overwrite Scaling", "")
                for r in rowset
                if r.get("Overwrite Scaling", "") not in {"", "-", "null"}
            ),
            "null",
        )

        subgroup_map: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
        for row in rowset:
            eff_dtype = (
                row.get("Dmg Type", "")
                if row.get("Dmg Type", "") not in {"", "-"}
                else primary_dtype
            )
            eff_overwrite = (
                row.get("Overwrite Scaling", "")
                if row.get("Overwrite Scaling", "") not in {"", "-", "null"}
                else primary_overwrite
            )
            subgroup_map.setdefault((eff_dtype, eff_overwrite), []).append(row)

        for (eff_dtype, eff_overwrite), subrows in subgroup_map.items():
            base = subrows[0]
            out: Dict[str, str] = {
                "Skill": base.get("Skill", ""),
                "Follow-up": base.get("Follow-up", ""),
                "Hand": base.get("Hand", ""),
                "Part": base.get("Part", ""),
                "Weapon Source": base.get("Weapon Source", ""),
                "Weapon": base.get("Weapon", ""),
                "Dmg Type": eff_dtype or "-",
                "Wep Status": base.get("Wep Status", ""),
            }
            subcats: List[str] = []
            overwrite_vals: List[str] = []
            for row in subrows:
                for col in ("subCategory1", "subCategory2", "subCategory3", "subCategory4"):
                    val = (row.get(col) or "").strip()
                    if val and val != "-" and val not in subcats:
                        subcats.append(val)
                ov = (row.get("Overwrite Scaling") or "").strip()
                if ov and ov not in {"-", "null"} and ov not in overwrite_vals:
                    overwrite_vals.append(ov)

            out["subCategorySum"] = " | ".join(subcats)
            out["Overwrite Scaling"] = (
                ", ".join(overwrite_vals)
                if overwrite_vals
                else (eff_overwrite if eff_overwrite else "null")
            )

            layout_key = (
                out["Skill"],
                out["Follow-up"],
                out["Hand"],
            )
            layout = layout_map.get(layout_key) or build_step_layout(subrows)
            for col in AGG_COLS:
                out[col] = aggregate_steps(subrows, col, layout)

            output_rows.append(out)

    merged_rows = collapse_weapons(output_rows)

    mask_zero_only_cells(merged_rows)

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
    layout_map = build_layout_map(filtered_rows)
    collapsed, output_fields = collapse_rows(filtered_rows, layout_map)
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
