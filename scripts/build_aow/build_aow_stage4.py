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
COLOR_ENABLED = False

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
    "Overwrite Scaling",
}

ATK_COLUMNS = {
    "Text Phys": "AtkPhys",
    "Text Mag": "AtkMag",
    "Text Fire": "AtkFire",
    "Text Ltng": "AtkLtng",
    "Text Holy": "AtkHoly",
}

FALLBACK_LABEL = {
    "Text Phys": "Physical",
    "Text Mag": "Magic",
    "Text Fire": "Fire",
    "Text Ltng": "Lightning",
    "Text Holy": "Holy",
}


def find_damage_pairs(fieldnames: List[str]) -> List[Tuple[str, str]]:
    mv_pattern = re.compile(r"^Dmg MV(?: (\d+))?$")
    suffixes: List[str] = []
    for col in fieldnames:
        m = mv_pattern.match(col)
        if m:
            suffixes.append(m.group(1) or "")

    def sort_key(suffix: str) -> Tuple[int, int]:
        return (0 if suffix == "" else 1, int(suffix or "0"))

    pairs: List[Tuple[str, str]] = []
    for suffix in sorted(set(suffixes), key=sort_key):
        type_col = f"Dmg Type {suffix}".strip()
        mv_col = f"Dmg MV {suffix}".strip()
        if type_col in fieldnames and mv_col in fieldnames:
            pairs.append((type_col, mv_col))
    if not pairs and "Dmg Type" in fieldnames and "Dmg MV" in fieldnames:
        pairs.append(("Dmg Type", "Dmg MV"))
    return pairs


def parse_float(value: str) -> float | None:
    try:
        text = str(value).strip()
        if text == "":
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def zeros_only(text: str) -> bool:
    nums = re.findall(r"-?\d+(?:\.\d+)?", text or "")
    if not nums:
        return False
    return all(float(n) == 0 for n in nums)


def wrap_label(label: str, color: str | None) -> str:
    if not COLOR_ENABLED or not color:
        return label
    return f'<font color="{color}">{label}</font>' if color else label


def wrap_segment(text: str, color: str) -> str:
    if not text:
        return text
    if not COLOR_ENABLED:
        return text
    return f'<font color="{color}">{text}</font>'


def merge_segments(segments: List[Tuple[str | None, str]]) -> str:
    merged: List[Tuple[str | None, str]] = []
    for color, text in segments:
        if not text:
            continue
        if merged and merged[-1][0] == color:
            merged[-1] = (color, merged[-1][1] + text)
        else:
            merged.append((color, text))
    parts: List[str] = []
    for color, text in merged:
        parts.append(wrap_segment(text, color) if color else text)
    return "".join(parts)


def color_for_damage_type(label: str) -> str | None:
    l_raw = (label or "").strip().lower()
    if l_raw.startswith("weapon (") and l_raw.endswith(")"):
        l_raw = l_raw[len("weapon ("):-1].strip()
    if l_raw.endswith("physical"):
        l_raw = l_raw[: -len("physical")].strip()
    l = l_raw
    if l in {"standard", "physical", "phys", "pierce", "slash", "strike", "blunt", "weapon"} or "physical" in l:
        return PHYSICAL_COLOR
    if "magic" in l:
        return MAGIC_COLOR
    if "fire" in l:
        return FIRE_COLOR
    if "lightning" in l or "ltng" in l:
        return LIGHTNING_COLOR
    if "holy" in l:
        return HOLY_COLOR
    return None


def target_column_for_type(dtype: str) -> str:
    text = (dtype or "").strip().lower()
    if not text or text == "weapon":
        return "Text Phys"
    if text.startswith("weapon (") and text.endswith(")"):
        text = text[len("weapon ("):-1].strip()
    if text.endswith("physical"):
        text = text[: -len("physical")].strip()
    if text in {"standard", "physical", "phys", "slash", "strike", "pierce", "weapon"}:
        return "Text Phys"
    if "magic" in text:
        return "Text Mag"
    if "fire" in text:
        return "Text Fire"
    if "lightning" in text or "ltng" in text:
        return "Text Ltng"
    if "holy" in text:
        return "Text Holy"
    return "Text Phys"


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
    if "|" not in content:
        # Single FP value: wrap once to avoid redundant tags on brackets.
        return wrap_segment(block, FP_COLOR)
    left_raw, right_raw = content.split("|", 1)
    left_val = parse_float(left_raw.strip())
    right_val = parse_float(right_raw.strip())
    if left_val == 0 and right_val == 0:
        # Charged FP-less: keep a single wrapper.
        return wrap_segment(block, FP_COLOR)
    segments = [
        (FP_COLOR, "["),
        (FP_COLOR, left_raw),
        (FP_DIVIDER_COLOR, "|"),
        (FP_CHARGED_COLOR, right_raw),
        (FP_COLOR, "]"),
    ]
    return merge_segments(segments)


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


RANGE_TOKEN = re.compile(r"-?\d+(?:\.\d+)?(?:-?\d+(?:\.\d+)?)?")


def tokenize_with_ranges(text: str) -> List[tuple[str, str]]:
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
    for kind, _ in tokens:
        if kind == "num":
            pattern.append("{n}")
            count += 1
        else:
            pattern.append("sep")
    return tuple(pattern), count


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


def fmt_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text


def sum_numeric_strings_with_ranges(current: str, incoming: str) -> str | None:
    cur = (current or "").strip()
    inc = (incoming or "").strip()
    if not cur:
        return inc or None
    if not inc:
        return cur

    cur_tokens = tokenize_with_ranges(cur)
    inc_tokens = tokenize_with_ranges(inc)
    cur_shape, cur_count = shape_with_ranges(cur)
    inc_shape, inc_count = shape_with_ranges(inc)
    if cur_count != inc_count or cur_shape != inc_shape:
        return None

    cur_ranges = [parse_range_value(val) for kind, val in cur_tokens if kind == "num"]
    inc_ranges = [parse_range_value(val) for kind, val in inc_tokens if kind == "num"]
    summed: List[str] = []
    for (c_low, c_high), (i_low, i_high) in zip(cur_ranges, inc_ranges):
        low = c_low + i_low
        high = c_high + i_high
        summed.append(fmt_number(low) if low == high else f"{fmt_number(low)}-{fmt_number(high)}")

    rebuilt: List[str] = []
    idx = 0
    for kind, val in cur_tokens:
        if kind == "num":
            rebuilt.append(summed[idx])
            idx += 1
        else:
            rebuilt.append(val)
    return "".join(rebuilt)


def apply_row_operations(
    row: Dict[str, str], dmg_pairs: List[Tuple[str, str]]
) -> Dict[str, str]:
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
            p.strip() for p in subcat_raw.split("|") if p.strip() and p.strip() != "-"
        ]
        deduped: List[str] = []
        seen = set()
        for p in parts:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        row["subCategorySum"] = " | ".join(deduped)

    # Zero-only normalization (exclude Dmg MV columns so we can display them).
    zero_cols = [
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

    row["Text Wep Dmg"] = "-"
    for col in ["Text Phys", "Text Mag", "Text Fire", "Text Ltng", "Text Holy"]:
        row[col] = "-"

    dmg_by_target: Dict[str, Dict[str, str | None]] = {
        tgt: {"label": None, "mv": None, "atk": None} for tgt in ATK_COLUMNS
    }

    for type_col, mv_col in dmg_pairs:
        dtype = (row.get(type_col) or "").strip()
        dmv = (row.get(mv_col) or "").strip()
        if not dmv or dmv == "-":
            continue
        label = dtype if dtype else "Weapon"
        target = target_column_for_type(label)
        entry = dmg_by_target.setdefault(target, {"label": None, "mv": None, "atk": None})
        if not entry["label"]:
            entry["label"] = label
        entry["mv"] = (
            dmv
            if entry["mv"] is None
            else sum_numeric_strings_with_ranges(str(entry["mv"]), dmv) or entry["mv"]
        )

    for target, atk_col in ATK_COLUMNS.items():
        atk_val = (row.get(atk_col) or "").strip()
        if not atk_val or atk_val == "-" or zeros_only(atk_val):
            continue
        entry = dmg_by_target.setdefault(target, {"label": None, "mv": None, "atk": None})
        entry["atk"] = atk_val

    overwrite_val = (row.get("Overwrite Scaling") or "").strip()
    for target, entry in dmg_by_target.items():
        dmg_val = entry.get("mv") or ""
        atk_val = entry.get("atk") or ""
        has_dmg = bool(dmg_val) and dmg_val != "-"
        has_atk = bool(atk_val) and atk_val != "-"
        if not has_dmg and not has_atk:
            continue

        label_raw = entry.get("label") or FALLBACK_LABEL.get(target, "Physical")
        label_color = color_for_damage_type(label_raw)
        label_text = wrap_label(f"{label_raw}:", label_color)

        combined = ""
        suffixes: List[str] = []
        if has_dmg and has_atk:
            combined = sum_numeric_strings_with_ranges(str(dmg_val), str(atk_val)) or str(dmg_val)
            suffixes.append("[AR]")
            if overwrite_val and overwrite_val != "-":
                suffixes.append(f"[{overwrite_val}]")
        elif has_dmg:
            combined = str(dmg_val)
            suffixes.append("[AR]")
        elif has_atk:
            combined = str(atk_val)
            if overwrite_val and overwrite_val != "-":
                suffixes.append(f"[{overwrite_val}]")

        payload = f"{label_text} {colorize_numeric_payload(combined)}"
        if suffixes:
            payload = f"{payload} {' '.join(suffixes)}"

        existing = row.get(target, "-")
        if not existing or existing == "-":
            row[target] = payload
        else:
            row[target] = f"{existing} | {payload}"

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
        label = (
            "Status" if not wep_status_raw or wep_status_raw == "-" else wep_status_raw
        )
        label_color = color_for_status(label)
        label_with_percent = label if "(%)" in label else f"{label} (%)"
        label_text = wrap_label(f"{label_with_percent}:", label_color)
        row["Text Wep Status"] = f"{label_text} {colorize_numeric_payload(status_raw)}"

    stance_raw = (row.get("Stance Dmg") or "").strip()
    if stance_raw in {"", "-"}:
        row["Text Stance"] = "-"
    else:
        row["Text Stance"] = (
            f"{wrap_label('Stance:', HEADER_COLOR)} {colorize_numeric_payload(stance_raw)}"
        )

    skill_attr = (row.get("Skill Attr") or "").strip()
    overwrite_val = (row.get("Overwrite Scaling") or "").strip()
    if overwrite_val == "-" and skill_attr and skill_attr != "-":
        suffix = f" [Weapon {skill_attr} Scaling]"
        for target in ATK_COLUMNS:
            val = (row.get(target) or "").strip()
            if not val or val == "-":
                continue
            if val.rstrip().endswith("[AR]") or " [AR]" in val:
                continue
            row[target] = f"{val}{'' if val.endswith(' ') else ' '}{suffix}"

    return row


def transform_rows(
    rows: List[Dict[str, str]], fieldnames: List[str]
) -> Tuple[List[Dict[str, str]], List[str]]:
    dmg_pairs = find_damage_pairs(fieldnames)
    drop_cols = set(DROP_COLUMNS)
    for type_col, mv_col in dmg_pairs:
        drop_cols.update({type_col, mv_col})
    base_fields = [col for col in fieldnames if col not in drop_cols]
    output_fields = ensure_output_fields(base_fields)
    transformed: List[Dict[str, str]] = []

    for row in rows:
        new_row = apply_row_operations(dict(row), dmg_pairs)
        cleaned_row = {k: v for k, v in new_row.items() if k not in drop_cols}
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
    color_group = parser.add_mutually_exclusive_group()
    color_group.add_argument(
        "--color",
        action="store_true",
        help="Enable font color tags in generated text columns (default: off).",
    )
    color_group.add_argument(
        "--no-color",
        action="store_true",
        help="Disable font color tags (default).",
    )
    args = parser.parse_args()

    global COLOR_ENABLED
    COLOR_ENABLED = bool(args.color)

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
