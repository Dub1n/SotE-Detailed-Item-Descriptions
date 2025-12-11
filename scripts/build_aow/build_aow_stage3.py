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


def fmt_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text


def normalize_overwrite(value: str) -> str:
    text = (value or "").strip()
    if text in {"", "-", "null"}:
        return "-"
    return text


def tokenize_numeric(text: str) -> List[tuple[str, str]]:
    parts = re.split(r"(-?\d+(?:\.\d+)?)", text or "")
    tokens: List[tuple[str, str]] = []
    for idx, part in enumerate(parts):
        if part == "":
            continue
        tokens.append(("num" if idx % 2 == 1 else "sep", part))
    return tokens


RANGE_TOKEN = re.compile(r"-?\d+(?:\.\d+)?(?:-?\d+(?:\.\d+)?)?")


def parse_range_value(value: str) -> Tuple[float, float]:
    text = (value or "").strip()
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)(?:-(-?\d+(?:\.\d+)?))?", text)
    if m:
        first = float(m.group(1))
        second = float(m.group(2)) if m.group(2) is not None else first
        return (first, second) if first <= second else (second, first)
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text)]
    if not nums:
        return 0.0, 0.0
    return (min(nums), max(nums))


def tokenize_with_ranges(text: str) -> List[tuple[str, str]]:
    """
    Tokenize a string, treating number ranges (e.g., 6-18) as a single token
    so we can compare shapes even when some weapons render ranges and others
    render single values.
    """
    tokens: List[tuple[str, str]] = []
    cursor = 0
    src = text or ""
    for match in RANGE_TOKEN.finditer(src):
        start, end = match.span()
        if start > cursor:
            tokens.append(("sep", src[cursor:start]))
        tokens.append(("num", match.group(0)))
        cursor = end
    if cursor < len(src):
        tokens.append(("sep", src[cursor:]))
    if not tokens:
        tokens.append(("sep", ""))
    return tokens


def shape_with_ranges(text: str) -> Tuple[tuple[str, ...], int]:
    tokens = tokenize_with_ranges(text)
    pattern: List[str] = []
    count = 0
    for kind, val in tokens:
        if kind == "num":
            pattern.append("{n}")
            count += 1
        else:
            pattern.append(val)
    return tuple(pattern), count


def shape(text: str) -> Tuple[tuple[str, ...], int]:
    tokens = tokenize_numeric(text)
    pattern: List[str] = []
    count = 0
    for kind, val in tokens:
        if kind == "num":
            pattern.append("{n}")
            count += 1
        else:
            pattern.append(val)
    return tuple(pattern), count


def sum_numeric_strings(current: str, incoming: str) -> str:
    """
    Sum numeric tokens when two values occupy the same FP/Charged/Step slot.
    Preserves the separators from the current value when shapes align; falls
    back to simple replacement when parsing fails.
    """
    cur = (current or "").strip()
    inc = (incoming or "").strip()
    if not cur:
        return inc
    if not inc or inc == "-":
        return cur
    if cur == "-":
        return inc

    cur_tokens = tokenize_numeric(cur)
    inc_tokens = tokenize_numeric(inc)
    cur_nums = [float(val) for kind, val in cur_tokens if kind == "num"]
    inc_nums = [float(val) for kind, val in inc_tokens if kind == "num"]

    if cur_nums and len(cur_nums) == len(inc_nums):
        summed = [fmt_number(a + b) for a, b in zip(cur_nums, inc_nums)]
        rebuilt: List[str] = []
        idx = 0
        for kind, val in cur_tokens:
            if kind == "num":
                rebuilt.append(summed[idx])
                idx += 1
            else:
                rebuilt.append(val)
        return "".join(rebuilt)

    try:
        return fmt_number(float(cur) + float(inc))
    except (TypeError, ValueError):
        return cur


class StepLayout(NamedTuple):
    max_step: int
    has_fp1: bool
    has_fp0: bool
    has_charged: bool


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
        key = (fp_val, charged_val, step)
        val = str(row.get(col, "") or "0").strip()
        if key in value_map:
            value_map[key] = sum_numeric_strings(value_map[key], val)
        else:
            value_map[key] = val

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
    # Precompute per-weapon signature sets across all Dmg Types for the same
    # Skill/Follow-up/Hand/Part/Wep Status combo so we can refuse to merge
    # when weapons have differing metadata anywhere in the cluster.
    overall_sigs: Dict[Tuple[str, str, str, str, str, str], set] = {}
    def normalize_subcat(value: str, hand: str) -> str:
        tokens = [t.strip() for t in (value or "").split("|") if t.strip()]
        if hand.strip() == "2h":
            tokens = [t for t in tokens if t != "2h Attack"]
        return "|".join(tokens)

    def row_signature(row: Dict[str, str]) -> Tuple[Tuple[str, str], ...]:
        sig_items: List[Tuple[str, str]] = []
        for k, v in row.items():
            if k in AGG_COLS or k in {"Weapon", "Weapon Source"}:
                continue
            if k == "subCategorySum":
                v = normalize_subcat(v, row.get("Hand", ""))
            sig_items.append((k, v))
        return tuple(sorted(sig_items))

    for row in rows:
        key = (
            row.get("Skill", ""),
            row.get("Follow-up", ""),
            row.get("Hand", ""),
            row.get("Part", ""),
            row.get("Wep Status", ""),
            row.get("Weapon", "").strip(),
        )
        overall_sigs.setdefault(key, set()).add(row_signature(row))

    fixed_cols = [
        "Skill",
        "Follow-up",
        "Hand",
        "Part",
        "Dmg Type",
        "Wep Status",
        "Overwrite Scaling",
    ]
    # Cluster by non-weapon fields.
    clusters: Dict[Tuple[str, ...], List[Dict[str, str]]] = {}
    for row in rows:
        dtype = row.get("Dmg Type", "")
        dtype_key = "__ANY_DMG__" if dtype == "-" else dtype
        overw = normalize_overwrite(row.get("Overwrite Scaling", ""))
        row["Overwrite Scaling"] = overw
        key_parts = []
        for col in fixed_cols:
            if col == "Dmg Type":
                key_parts.append(dtype_key)
            else:
                key_parts.append(row.get(col, ""))
        key = tuple(key_parts)
        clusters.setdefault(key, []).append(row)

    merged: List[Dict[str, str]] = []
    for key, bucket in clusters.items():
        # Build weapon -> set of shapes to ensure symmetry.
        shapes_by_weapon: Dict[str, set] = {}
        rows_by_shape_weapon: Dict[Tuple[str, ...], Dict[str, List[Dict[str, str]]]] = {}
        sources_by_weapon: Dict[str, List[str]] = {}
        sig_cache: Dict[str, Tuple[Tuple[Tuple[str, str], ...], ...]] = {}
        for row in bucket:
            weapon = row.get("Weapon", "").strip()
            shape_key: Tuple[str, ...] = []
            for col in AGG_COLS:
                pat, _ = shape_with_ranges(row.get(col, "") or "")
                shape_key += pat
            shape_key = tuple(shape_key)
            shapes_by_weapon.setdefault(weapon, set()).add(shape_key)
            rows_by_shape_weapon.setdefault(shape_key, {}).setdefault(weapon, []).append(row)
            src = (row.get("Weapon Source") or "").strip()
            if src:
                sources_by_weapon.setdefault(weapon, []).append(src)
            # Signatures of non-numeric fields excluding Weapon/Weapon Source (per row).
            sig = row_signature(row)
            sig_cache.setdefault(weapon, tuple())
            sig_cache[weapon] = tuple(sorted(set(sig_cache[weapon] + (sig,))))

        # Only merge if every weapon has identical shape set.
        shape_sets = list(shapes_by_weapon.values())
        if not shape_sets:
            merged.extend(bucket)
            continue
        if any(s != shape_sets[0] for s in shape_sets[1:]):
            merged.extend(bucket)
            continue

        # Guard: non-numeric fields (except Weapon/Weapon Source) must match per row set.
        sigs = list(sig_cache.values())
        if sigs and any(sig != sigs[0] for sig in sigs[1:]):
            for rows_list in rows_by_shape_weapon.values():
                for entries in rows_list.values():
                    merged.extend(entries)
            continue
        # Guard: across the full Skill/Follow-up/Hand/Part/Wep Status cluster,
        # every weapon must share the same set of non-numeric row signatures;
        # otherwise leave rows separate.
        cluster_key = (
            bucket[0].get("Skill", ""),
            bucket[0].get("Follow-up", ""),
            bucket[0].get("Hand", ""),
            bucket[0].get("Part", ""),
            bucket[0].get("Wep Status", ""),
        )
        sig_sets = [
            overall_sigs.get(cluster_key + (weapon,), set()) for weapon in shapes_by_weapon
        ]
        if sig_sets and any(sig != sig_sets[0] for sig in sig_sets[1:]):
            for rows_list in rows_by_shape_weapon.values():
                for entries in rows_list.values():
                    merged.extend(entries)
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
            # Merge Weapon Source across contributing rows.
            src_values: List[str] = []
            for w_rows in weapon_rows.values():
                for r in w_rows:
                    src = (r.get("Weapon Source") or "").strip()
                    if src:
                        src_values.append(src)
            out["Weapon Source"] = unique_join(src_values) or "-"
            # Resolve Dmg Type preferring non-"-".
            dtype_candidates = [
                r.get("Dmg Type", "") for rows_list in weapon_rows.values() for r in rows_list
            ]
            chosen_dtype = base_row.get("Dmg Type", "-")
            if dtype_candidates and any(d != chosen_dtype for d in dtype_candidates):
                for rows_list in weapon_rows.values():
                    merged.extend(rows_list)
                continue
            out["Dmg Type"] = chosen_dtype or "-"
            # Overwrite Scaling must match.
            ovw_candidates = {
                normalize_overwrite(r.get("Overwrite Scaling", ""))
                for rows_list in weapon_rows.values()
                for r in rows_list
            }
            if len(ovw_candidates) > 1:
                for rows_list in weapon_rows.values():
                    merged.extend(rows_list)
                continue
            out["Overwrite Scaling"] = ovw_candidates.pop() if ovw_candidates else "-"

            # Merge weapons.
            weapons: List[str] = []
            for weapon in weapon_rows:
                parts = [p.strip() for p in weapon.split("|")]
                for name in parts:
                    if name and name not in weapons:
                        weapons.append(name)
            out["Weapon"] = " | ".join(weapons)

            # subCategorySum is assumed identical across merge candidates.
            out["subCategorySum"] = base_row.get("subCategorySum", "")

            # Merge numeric ranges using token shape of base.
            token_cache = {col: tokenize_with_ranges(out.get(col, "") or "") for col in AGG_COLS}
            for col in AGG_COLS:
                tokens = token_cache[col]
                num_positions = [i for i, (k, _) in enumerate(tokens) if k == "num"]
                all_nums_by_pos: List[List[Tuple[float, float]]] = [[] for _ in num_positions]
                for w_rows in weapon_rows.values():
                    row = w_rows[0]
                    row_tokens = tokenize_with_ranges(row.get(col, "") or "")
                    row_ranges = [parse_range_value(val) for kind, val in row_tokens if kind == "num"]
                    if len(row_ranges) != len(num_positions):
                        continue
                    for idx, val in enumerate(row_ranges):
                        all_nums_by_pos[idx].append(val)
                ranges: List[str] = []
                for vals in all_nums_by_pos:
                    lows = [v[0] for v in vals]
                    highs = [v[1] for v in vals]
                    mn, mx = min(lows), max(highs)
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


def normalize_parts(rows: List[Dict[str, str]]) -> None:
    """
    When every row for a Skill/Follow-up/Hand shares the same Part, replace
    that Part with "-" to reduce redundant labels.
    """
    grouped: Dict[Tuple[str, str, str], List[int]] = {}
    for idx, row in enumerate(rows):
        key = (
            row.get("Skill", ""),
            row.get("Follow-up", ""),
            row.get("Hand", ""),
        )
        grouped.setdefault(key, []).append(idx)

    for idxs in grouped.values():
        parts = {rows[i].get("Part", "") for i in idxs}
        if len(parts) == 1:
            for i in idxs:
                rows[i]["Part"] = "-"


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
        row["Overwrite Scaling"] = normalize_overwrite(
            row.get("Overwrite Scaling", "")
        )
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
                if r.get("Overwrite Scaling", "") not in {"", "-"}
            ),
            "-",
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
                if row.get("Overwrite Scaling", "") not in {"", "-"}
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
                if ov and ov != "-" and ov not in overwrite_vals:
                    overwrite_vals.append(ov)

            out["subCategorySum"] = "|".join(subcats)
            out["Overwrite Scaling"] = (
                ", ".join(overwrite_vals)
                if overwrite_vals
                else (eff_overwrite if eff_overwrite and eff_overwrite != "-" else "-")
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
    normalize_parts(merged_rows)

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
