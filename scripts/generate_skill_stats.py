#!/usr/bin/env python3
"""Generate stats-block lines from the motion value sheet.

This ingests the motion-value / attack-data CSV (`docs/ER-Motion-Values-and-Attack-Data_(1.16.1).csv`)
and emits a JSON file with `name` and `stats` fields that mirror the stats block format
used in `skill.json`. Each entry groups all rows that belong to the same skill name and
formats both bullet-style base damages and weapon-hit motion values, along with stance
damage when present.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
import csv as stdcsv

# Colour constants match docs/definitions.md
COLOR_GOLD = "#E0B985"
COLOR_STANCE = "#C0B194"
COLOR_DAMAGE = {
    "physical": "#F395C4",
    "magic": "#57DBCE",
    "fire": "#F48C25",
    "lightning": "#FFE033",
    "holy": "#F5EB89",
}

ELEMENT_BASE_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("physical", "AtkPhys"),
    ("magic", "AtkMag"),
    ("fire", "AtkFire"),
    ("lightning", "AtkLtng"),
    ("holy", "AtkHoly"),
)

MV_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("physical", "Phys MV"),
    ("magic", "Magic MV"),
    ("fire", "Fire MV"),
    ("lightning", "Ltng MV"),
    ("holy", "Holy MV"),
)

SCALING_LOOKUP: Dict[str, List[str]] = {
    "-": [],
    "No Scaling": [],
    "Strength": ["Strength"],
    "Dexterity": ["Dexterity"],
    "Intelligence": ["Intelligence"],
    "Faith": ["Faith"],
    "Arcane": ["Arcane"],
    "Arc - Complex": ["Arcane"],
    "Str/Dex": ["Strength", "Dexterity"],
    "Dex/Int": ["Dexterity", "Intelligence"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build stats block lines from the motion-value CSV.")
    parser.add_argument(
        "--input",
        default="docs/(1.16.1)-Ashes-of-War-Attack-Data.csv",
        help="Path to the motion value CSV.",
    )
    parser.add_argument(
        "--output",
        default="work/skill_stats_from_sheet.json",
        help='Where to write the JSON output (list of {"name": ..., "stats": [...]}).',
    )
    parser.add_argument(
        "--populate",
        action="store_true",
        help="If set, also populate work/responses/ready/skill.json with the generated stats.",
    )
    return parser.parse_args()


def format_number(raw: str) -> str:
    """Format numeric strings while trimming trailing .0."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return raw
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def normalize_scaling(raw: str) -> List[str]:
    """Return normalized stat names used for scaling tags."""
    raw = (raw or "").strip()
    if raw in SCALING_LOOKUP:
        return SCALING_LOOKUP[raw]
    cleaned = raw.replace(" ", "")
    parts = [p for p in re.split(r"[\\/,+]", cleaned) if p]
    normalized: List[str] = []
    for part in parts:
        normalized.extend(SCALING_LOOKUP.get(part, [part]))
    return normalized


def scaling_suffix(stats: Iterable[str]) -> str:
    stats = list(stats)
    if not stats:
        return ""
    short = {
        "Strength": "Str",
        "Dexterity": "Dex",
        "Intelligence": "Int",
        "Faith": "Fth",
        "Arcane": "Arc",
    }
    formatted = [f'<font color="{COLOR_GOLD}">{short.get(stat, stat)}</font>' for stat in stats]
    return f" ({', '.join(formatted)})"


def parse_label(label: str | None) -> Tuple[str, bool]:
    """Return (phase, is_lacking_fp) from the label string."""
    if not label:
        return "", False
    is_lacking = "Lacking FP" in label
    phase = label.replace("Lacking FP", "").strip()
    return phase, is_lacking


def canonical_skill_name(name: str) -> str:
    """Drop simple numeric bracket variants from the skill name (e.g., '[1]')."""
    cleaned = re.sub(r"\s*\[\d+\]", "", name).strip()
    cleaned = re.sub(r"\s*#\d+", "", cleaned)
    cleaned = re.sub(r"\s\d+(?=$|\s\()", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned


def strip_hash_variant(name: str) -> Tuple[str, str]:
    """Remove '#n' from a name, returning (stripped_name, hash_id or '')."""
    match = re.search(r"\s#(\d+)", name)
    if not match:
        match = re.search(r"\s(\d+)(?=$|\s\()", name)
    if not match:
        return name.strip(), ""
    hash_id = f"#{match.group(1)}"
    stripped = (name[: match.start()] + name[match.end() :]).strip()
    stripped = re.sub(r"\s{2,}", " ", stripped)
    return stripped, hash_id


def load_unique_poise_bases(path: Path) -> Dict[str, float]:
    base_map: Dict[str, float] = {}
    with path.open() as f:
        reader = stdcsv.DictReader(f)
        for row in reader:
            weapon = (row.get("Weapon") or "").strip().lower()
            if not weapon:
                continue
            try:
                base = float(row.get("Base") or 0)
            except ValueError:
                continue
            base_map[weapon] = base
    return base_map


def load_aow_categories(equip_path: Path, category_map: Dict[str, Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    mapping: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    cat_keys = set(category_map.keys())
    with equip_path.open() as f:
        reader = stdcsv.DictReader(f)
        for row in reader:
            try:
                mount_text = int(row.get("mountWepTextId", "0"))
            except ValueError:
                mount_text = -1
            if mount_text == -1:
                continue
            name = (row.get("Name") or "").replace("Ash of War:", "").strip()
            if not name:
                continue
            key_name = name.lower()
            found = False
            for cat_key in cat_keys:
                if row.get(cat_key, "0") == "1":
                    mapping[key_name].append(
                        {"key": cat_key, "name": category_map[cat_key]["name"], "poise": category_map[cat_key]["poise"]}
                    )
                    found = True
            if not found:
                continue
    return mapping


def physical_type_label(row: Dict[str, str]) -> str:
    raw = (row.get("PhysAtkAttribute") or "").strip()
    lookup = {
        "Standard": "standard",
        "Strike": "strike",
        "Slash": "slash",
        "Pierce": "pierce",
    }
    if raw in lookup:
        return lookup[raw]
    return "physical"


def split_skill_name(name: str) -> Tuple[str, str | None]:
    """Split the sheet name into a base skill name and an optional label/phase."""
    label_parts: List[str] = []
    base_candidate = name.strip()

    if base_candidate.endswith("(Lacking FP)"):
        base_candidate = base_candidate.replace(" (Lacking FP)", "")
        label_parts.append("Lacking FP")

    if " - " in base_candidate:
        base_candidate, remainder = base_candidate.split(" - ", 1)
        if remainder:
            label_parts.insert(0, remainder.strip())

    r_match = re.search(r"(.*?)( R\d(?:\s*\[.*\])?)$", base_candidate)
    if r_match:
        base_candidate, suffix = r_match.group(1), r_match.group(2)
        label_parts.insert(0, suffix.strip())

    bracket_match = re.search(r"(.*?)(\s*\[[^\]]+\])$", base_candidate)
    if bracket_match:
        base_candidate, suffix = bracket_match.group(1), bracket_match.group(2)
        label_parts.insert(0, suffix.strip())

    # Pull out any remaining numeric bracket markers embedded in the name (e.g., "[1]" before "(AoE)").
    bracket_tokens = re.findall(r"\s*\[\d+\]", base_candidate)
    if bracket_tokens:
        base_candidate = re.sub(r"\s*\[\d+\]", "", base_candidate)
        for tok in bracket_tokens:
            label_parts.insert(0, tok.strip())

    base_name = base_candidate.strip()
    label = " ".join(label_parts).strip() or None
    return base_name, label


def build_bullet_lines(row: Dict[str, str], label: str | None) -> List[Dict[str, str]]:
    lines: List[Dict[str, str]] = []
    phase, is_lacking = parse_label(label)
    suffix = scaling_suffix(normalize_scaling(row.get("Overwrite Scaling", "")))
    for element, column in ELEMENT_BASE_COLUMNS:
        raw = row.get(column, "") or "0"
        try:
            value = float(raw)
        except ValueError:
            continue
        if value <= 0:
            continue
        lines.append(
            {
                "descriptor": f"{physical_type_label(row) if element == 'physical' else element} damage",
                "value": value,
                "color": COLOR_DAMAGE[element],
                "kind": "physical" if element == "physical" else "elemental",
                "phase": phase,
                "is_lacking": is_lacking,
                "suffix": suffix,
                "is_multiplier": False,
                "label": label or "",
            }
        )
    return lines


def has_base_damage(row: Dict[str, str]) -> bool:
    for _, column in ELEMENT_BASE_COLUMNS:
        try:
            if float(row.get(column, "") or 0) > 0:
                return True
        except ValueError:
            continue
    return False


def pick_mv_element(row: Dict[str, str]) -> Tuple[str, float]:
    values = []
    for element, column in MV_COLUMNS:
        try:
            value = float(row.get(column, "") or 0)
        except ValueError:
            value = 0.0
        values.append((element, value))
    max_value = max(values, key=lambda item: item[1])[1]
    if max_value <= 0:
        return "", 0.0
    for element, value in values:
        if value == max_value and value > 0:
            return element, value
    return "", 0.0


def build_weapon_lines(row: Dict[str, str], label: str | None) -> List[Dict[str, str]]:
    phase, is_lacking = parse_label(label)
    element, value = pick_mv_element(row)
    if value <= 0:
        return []
    suffix = scaling_suffix(normalize_scaling(row.get("Overwrite Scaling", "")))
    return [
        {
            "descriptor": f"{physical_type_label(row) if element == 'physical' else element} damage",
            "value": value,
            "color": COLOR_DAMAGE[element],
            "kind": "physical" if element == "physical" else "elemental",
            "phase": phase,
            "is_lacking": is_lacking,
            "suffix": suffix,
            "is_multiplier": False,
            "label": label or "",
        }
    ]


def build_stance_lines(
    row: Dict[str, str],
    label: str | None,
    stance_base: float | None = None,
    stance_categories: List[Dict[str, object]] | None = None,
) -> List[Dict[str, str]]:
    raw = row.get("Poise Dmg MV", "") or "0"
    try:
        value = float(raw)
    except ValueError:
        return []
    if value <= 0:
        return []
    phase, is_lacking = parse_label(label)
    return [
        {
            "descriptor": "stance damage",
            "value": value,
            "color": COLOR_STANCE,
            "kind": "stance",
            "phase": phase,
            "is_lacking": is_lacking,
            "suffix": "",
            "is_multiplier": False,
            "label": label or "",
            "stance_base": stance_base,
            "stance_categories": stance_categories or [],
            "stance_cat_key": tuple((c.get("name") for c in stance_categories)) if stance_categories else (),
        }
    ]


def build_status_multiplier_lines(row: Dict[str, str], label: str | None) -> List[Dict[str, str]]:
    raw = row.get("Status MV", "") or "0"
    try:
        value = float(raw)
    except ValueError:
        return []
    if value <= 0:
        return []
    phase, is_lacking = parse_label(label)
    multiplier = value / 100.0
    return [
        {
            "descriptor": "status buildup",
            "value": multiplier,
            "color": COLOR_GOLD,
            "kind": "status",
            "phase": phase,
            "is_lacking": is_lacking,
            "suffix": "",
            "is_multiplier": True,
            "label": label or "",
        }
    ]


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    unique_poise_bases = load_unique_poise_bases(Path("docs/(1.16.1)-Poise-Damage-MVs.csv"))
    weapon_category_map = json.loads(Path("docs/weapon_categories_poise.json").read_text())
    aow_categories = load_aow_categories(Path("PARAM/EquipParamGem.csv"), weapon_category_map)

    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    with input_path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            base_name, label = split_skill_name(row["Name"])
            base_no_hash, hash_id = strip_hash_variant(base_name)
            base_no_hash_lower = base_no_hash.lower()

            stance_base = None
            stance_categories = None
            unique_weapon = (row.get("Unique Skill Weapon") or "").strip()
            if unique_weapon:
                stance_base = unique_poise_bases.get(unique_weapon.lower())
            else:
                cats = aow_categories.get(base_no_hash_lower)
                if cats:
                    stance_categories = cats

            is_bullet = (row.get("isAddBaseAtk") or "").upper() == "TRUE" or has_base_damage(row)
            bullet_lines = build_bullet_lines(row, label) if is_bullet else []
            weapon_lines = build_weapon_lines(row, label)
            stance_lines = build_stance_lines(row, label, stance_base=stance_base, stance_categories=stance_categories)
            status_lines = build_status_multiplier_lines(row, label)

            lines = bullet_lines + weapon_lines + status_lines + stance_lines
            if lines:
                for line in lines:
                    line["hash_id"] = hash_id
                grouped[base_no_hash].extend(lines)

    order = {"physical": 0, "elemental": 1, "status": 2, "stance": 3}
    re_bracket = re.compile(r"^\[\d+\]$")
    re_any_bracket = re.compile(r"\[\d+\]")
    canonical_grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for base_name, entries in grouped.items():
        canonical_grouped[canonical_skill_name(base_name)].extend(entries)

    output: List[Dict[str, object]] = []
    for name in sorted(canonical_grouped.keys()):
        entries = canonical_grouped[name]

        # Group by hash variant.
        hash_groups: Dict[str, List[Dict[str, object]]] = defaultdict(list)
        for entry in entries:
            hash_groups[entry.get("hash_id", "")].append(entry)

        def collapse_group(group_entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
            def normalize_stance_fields(entry: Dict[str, object]) -> Dict[str, object]:
                """Normalize stance-related fields so FP/Lacking FP share the same keys."""
                normalized = dict(entry)
                stance_base = normalized.get("stance_base")
                normalized["stance_base"] = None if stance_base in ("", None) else stance_base

                stance_cat_key = normalized.get("stance_cat_key")
                if not stance_cat_key:
                    stance_cat_key = ()
                elif isinstance(stance_cat_key, list):
                    stance_cat_key = tuple(stance_cat_key)
                elif not isinstance(stance_cat_key, tuple):
                    stance_cat_key = (stance_cat_key,)
                normalized["stance_cat_key"] = stance_cat_key
                return normalized

            combined: Dict[Tuple[str, str, str, bool, str, bool, str, float | None, Tuple], Dict[str, object]] = {}
            others: List[Dict[str, object]] = []
            for entry in group_entries:
                entry = normalize_stance_fields(entry)
                phase = entry.get("phase", "")
                canonical_phase = phase
                stripped_phase = re_any_bracket.sub("", canonical_phase).strip()
                bracket_group = re_any_bracket.search(phase) is not None
                if bracket_group:
                    key = (
                        entry["kind"],
                        entry["descriptor"],
                        entry["suffix"],
                        entry["is_multiplier"],
                        entry.get("color", ""),
                        entry.get("is_lacking", False),
                        stripped_phase,
                        entry.get("stance_base"),
                        entry.get("stance_cat_key", ()),
                    )
                    bucket = combined.setdefault(
                        key,
                        {
                            "value": 0.0,
                            "count": 0,
                            "kind": entry["kind"],
                            "descriptor": entry["descriptor"],
                            "suffix": entry.get("suffix", ""),
                            "is_multiplier": entry.get("is_multiplier", False),
                            "color": entry.get("color", COLOR_GOLD),
                            "phase": stripped_phase,
                            "is_lacking": entry.get("is_lacking", False),
                            "stance_base": entry.get("stance_base"),
                            "stance_categories": entry.get("stance_categories", []),
                            "stance_cat_key": entry.get("stance_cat_key", ()),
                        },
                    )
                    bucket["value"] += float(entry.get("value", 0) or 0)
                    bucket["count"] += 1
                else:
                    others.append(entry)

            combined_entries = list(combined.values()) + others

            # Pair FP/Lacking FP variants by shared key (ignoring is_lacking).
            paired_output = []
            key_fields = (
                "kind",
                "descriptor",
                "suffix",
                "is_multiplier",
                "color",
                "phase",
                "stance_base",
                "stance_cat_key",
            )
            base_map: Dict[Tuple, Dict[str, object]] = {}
            lacking_map: Dict[Tuple, Dict[str, object]] = {}
            for entry in combined_entries:
                key = tuple(entry.get(k, "") for k in key_fields)
                if entry.get("is_lacking"):
                    lacking_map[key] = entry
                else:
                    base_map[key] = entry

            all_keys = set(base_map.keys()) | set(lacking_map.keys())
            for key in all_keys:
                base_entry = dict(base_map.get(key, {})) if key in base_map else None
                lacking_entry = lacking_map.get(key)

                if base_entry is None and lacking_entry is not None:
                    base_entry = dict(lacking_entry)
                    base_entry["is_lacking"] = False
                    base_entry["value"] = 0
                elif base_entry is None:
                    continue

                if lacking_entry:
                    base_entry["lacking_value"] = lacking_entry.get("value")
                    base_entry["_has_lacking"] = True

                paired_output.append(base_entry)
            return paired_output

        collapsed_by_hash: Dict[str, List[Dict[str, object]]] = {
            hid: collapse_group(group_entries) for hid, group_entries in hash_groups.items()
        }

        def hash_sort_key(hid: str) -> Tuple[int, int]:
            if not hid:
                return (0, 0)
            m = re.match(r"#(\\d+)", hid)
            if m:
                return (1, int(m.group(1)))
            return (1, 9999)

        hash_ids_sorted = sorted(collapsed_by_hash.keys(), key=hash_sort_key)

        # Collect all keys across hash variants.
        key_fields = ("kind", "descriptor", "suffix", "is_multiplier", "color", "phase")
        all_keys = set()
        for entries_list in collapsed_by_hash.values():
            for entry in entries_list:
                all_keys.add(tuple(entry.get(k, "") for k in key_fields))

        def follow_up_priority(phase_value: str) -> int:
            if "Light Follow-up" in phase_value or "R1" in phase_value:
                return 1
            if "Heavy Follow-up" in phase_value or "R2" in phase_value:
                return 2
            return 0

        formatted_lines: List[str] = []
        for key in sorted(
            all_keys,
            key=lambda e: (
                follow_up_priority(e[5]),
                order.get(e[0], 99),
                e[1],
                e[5],
            ),
        ):
            kind, descriptor, suffix, is_multiplier, color, phase = key
            values = []
            lacking_values = []
            has_lacking = False
            has_flag = False
            meta_entry = None
            for hid in hash_ids_sorted:
                entries_list = collapsed_by_hash[hid]
                match_entry = next(
                    (entry for entry in entries_list if tuple(entry.get(k, "") for k in key_fields) == key),
                    None,
                )
                if match_entry:
                    if meta_entry is None:
                        meta_entry = match_entry
                    values.append(match_entry.get("value", 0))
                    lv = match_entry.get("lacking_value")
                    if lv is not None:
                        has_lacking = True
                    if match_entry.get("_has_lacking"):
                        has_flag = True
                    lacking_values.append(lv)
                else:
                    values.append(0)
                    lacking_values.append(None)
            has_lacking = has_flag or has_lacking or any(v is not None for v in lacking_values)

            desc = descriptor[:1].upper() + descriptor[1:]
            label_phase = phase.strip()
            prefix = ""
            if "R1" in label_phase:
                prefix = "(Light Follow-up) "
                label_phase = label_phase.replace("R1", "").strip()
            if "R2" in label_phase:
                prefix = "(Heavy Follow-up) "
                label_phase = label_phase.replace("R2", "").strip()

            label_text = f"{prefix}{desc}"
            if label_phase:
                label_text += f" ({label_phase})"

            def fmt(val):
                s = format_number(str(val))
                return f"{s}x" if is_multiplier else s

            def is_nonzero(val):
                try:
                    return float(val) != 0
                except (TypeError, ValueError):
                    return bool(val)

            def format_value_lists(base_vals, lacking_vals):
                base_parts = [fmt(v) for v in base_vals]
                lacking_parts = [fmt(v if v is not None else 0) for v in lacking_vals]
                base_has_any = any(v is not None for v in base_vals)
                lacking_has_any = has_lacking and any(v is not None for v in lacking_vals)
                if not base_has_any and has_lacking:
                    return f"0 [{', '.join(lacking_parts)}]"
                if base_has_any and not lacking_has_any:
                    return ", ".join(base_parts)
                value_str_inner = ", ".join(base_parts)
                if has_lacking:
                    lv_str = ", ".join(lacking_parts)
                    value_str_inner = f"{value_str_inner} [{lv_str}]"
                return value_str_inner

            if kind == "stance":
                stance_categories = meta_entry.get("stance_categories") if meta_entry else []
                stance_base = meta_entry.get("stance_base") if meta_entry else None
                if stance_categories:
                    cat_groups: Dict[Tuple[Tuple, Tuple | None], List[str]] = defaultdict(list)
                    for cat in stance_categories:
                        poise_val = cat.get("poise")
                        try:
                            poise_num = float(poise_val)
                        except (TypeError, ValueError):
                            continue
                        factor = poise_num / 100.0
                        scaled_base = [(v if v is not None else 0) * factor for v in values]
                        scaled_lacking = [(v if v is not None else 0) * factor for v in lacking_values]
                        key_vals = (tuple(scaled_base), tuple(scaled_lacking) if has_lacking else None)
                        cat_groups[key_vals].append(cat.get("name", ""))

                    for (base_tuple, lacking_tuple), names in sorted(cat_groups.items(), key=lambda x: x[0][0]):
                        label_text_local = f"{prefix}{desc}"
                        label_parts = []
                        if names:
                            label_parts.append(", ".join(filter(None, names)))
                        if label_phase:
                            label_parts.append(label_phase)
                        if label_parts:
                            label_text_local += f" ({', '.join(label_parts)})"
                        value_str = format_value_lists(list(base_tuple), list(lacking_tuple or []))
                        line = f'\n{prefix}<font color="{color or COLOR_GOLD}">{label_text_local[len(prefix):]}:</font> {value_str}{suffix}'
                        formatted_lines.append(line)
                elif stance_base is not None:
                    factor = (stance_base or 0) / 100.0
                    scaled_base = [(v if v is not None else 0) * factor for v in values]
                    scaled_lacking = [(v if v is not None else 0) * factor for v in lacking_values]
                    value_str = format_value_lists(scaled_base, scaled_lacking)
                    label_text_local = f"{prefix}{desc}"
                    if label_phase:
                        label_text_local += f" ({label_phase})"
                    line = f'\n{prefix}<font color="{color or COLOR_GOLD}">{label_text_local[len(prefix):]}:</font> {value_str}{suffix}'
                    formatted_lines.append(line)
                else:
                    value_str = format_value_lists(values, lacking_values)
                    line = f'\n{prefix}<font color="{color or COLOR_GOLD}">{label_text[len(prefix):]}:</font> {value_str}{suffix}'
                    formatted_lines.append(line)
            else:
                value_str = format_value_lists(values, lacking_values)
                line = f'\n{prefix}<font color="{color or COLOR_GOLD}">{label_text[len(prefix):]}:</font> {value_str}{suffix}'
                formatted_lines.append(line)

        output.append({"name": name, "stats": formatted_lines})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(output)} skill entries to {output_path}")

    if args.populate:
        skill_path = Path("work/responses/ready/skill.json")
        if not skill_path.exists():
            print(f"Cannot populate skill file; missing {skill_path}")
            return
        print(f"Populating {skill_path} with stats fields...")
        with skill_path.open() as f:
            skill_data = json.load(f)

        # Build lookup of generated stats by name.
        stats_lookup: Dict[str, List[str]] = {entry["name"]: entry["stats"] for entry in output}

        def matching_variants(item_name: str) -> Dict[str, List[str]]:
            matches: Dict[str, List[str]] = {}
            base = stats_lookup.get(item_name)
            if base:
                matches[item_name] = base
            for name, stats in stats_lookup.items():
                if name == item_name:
                    continue
                if name.startswith(f"{item_name} "):
                    matches[name] = stats
                elif name.startswith(f"{item_name}("):
                    matches[name] = stats
            return matches

        updated: List[Dict[str, object]] = []
        for item in skill_data:
            if not isinstance(item, dict) or "name" not in item:
                updated.append(item)
                continue
            matches = matching_variants(item["name"])
            if not matches:
                updated.append(item)
                continue

            skip_keys = set(matches.keys())
            # Keep 'stats' and variant keys from previous run out.
            skip_keys.update(k for k in item.keys() if k == "stats" or k in matches)

            inserted = False
            new_item: Dict[str, object] = {}
            match_keys = []
            if item["name"] in matches:
                match_keys.append(item["name"])
            match_keys.extend(sorted(k for k in matches.keys() if k != item["name"]))

            for key, value in item.items():
                if key in skip_keys:
                    continue
                new_item[key] = value
                if key == "info":
                    # Insert stats/variant blocks after info.
                    for m_key in match_keys:
                        new_item[m_key] = matches[m_key]
                    inserted = True
            if not inserted:
                for m_key in match_keys:
                    new_item[m_key] = matches[m_key]
            updated.append(new_item)

        with skill_path.open("w", encoding="utf-8") as f:
            json.dump(updated, f, indent=2, ensure_ascii=False)
        print(f"Populated stats into {skill_path}")


if __name__ == "__main__":
    main()
