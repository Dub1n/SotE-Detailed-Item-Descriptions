#!/usr/bin/env python3
"""Generate stats-block lines from the attack data sheet."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

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
    parser = argparse.ArgumentParser(
        description="Build stats block lines from the motion-value CSV."
    )
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
    parser.add_argument(
        "--ready-only",
        action="store_true",
        help="Limit output to items present in work/responses/ready/skill.json (and their variants).",
    )
    parser.add_argument(
        "--ready-path",
        default="work/responses/ready/skill.json",
        help="Path to ready skill JSON used when --ready-only is specified.",
    )
    return parser.parse_args()


def format_number(raw: str) -> str:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return raw
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def normalize_scaling(raw: str) -> List[str]:
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
    formatted = [
        f'<font color="{COLOR_GOLD}">{short.get(stat, stat)}</font>' for stat in stats
    ]
    return f" ({', '.join(formatted)})"


def parse_label(label: str | None) -> Tuple[str, bool]:
    if not label:
        return "", False
    is_lacking = "Lacking FP" in label
    phase = label.replace("Lacking FP", "").strip()
    return phase, is_lacking


def extract_weapon_prefix(name: str) -> Tuple[str | None, str]:
    if not name:
        return None, ""
    match = re.match(r"\s*\[([^\]]+)\]\s*(.*)", name)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, name.strip()


def canonical_skill_name(name: str) -> str:
    cleaned = re.sub(r"\s*\[\d+\]", "", name).strip()
    cleaned = re.sub(r"\s*#\d+", "", cleaned)
    cleaned = re.sub(r"\s\d+(?=$|\s\()", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned


def strip_hash_variant(name: str) -> Tuple[str, str]:
    match = re.search(r"\s#(\d+)", name) or re.search(r"\s(\d+)(?=$|\s\()", name)
    if not match:
        return name.strip(), ""
    hash_id = f"#{match.group(1)}"
    stripped = (name[: match.start()] + name[match.end() :]).strip()
    stripped = re.sub(r"\s{2,}", " ", stripped)
    return stripped, hash_id


def physical_type_label(row: Dict[str, str]) -> str:
    raw = (row.get("PhysAtkAttribute") or "").strip()
    lookup = {
        "Standard": "standard",
        "Strike": "strike",
        "Slash": "slash",
        "Pierce": "pierce",
    }
    return lookup.get(raw, "physical")


def split_skill_name(name: str) -> Tuple[str, str | None]:
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

    bracket_tokens = re.findall(r"\s*\[\d+\]", base_candidate)
    if bracket_tokens:
        base_candidate = re.sub(r"\s*\[\d+\]", "", base_candidate)
        for tok in bracket_tokens:
            label_parts.insert(0, tok.strip())

    base_name = base_candidate.strip()
    label = " ".join(label_parts).strip() or None
    return base_name, label


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


def build_bullet_lines(
    row: Dict[str, str], label: str | None
) -> List[Dict[str, object]]:
    lines: List[Dict[str, object]] = []
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


def build_weapon_lines(
    row: Dict[str, str], label: str | None
) -> List[Dict[str, object]]:
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


def build_status_multiplier_lines(
    row: Dict[str, str], label: str | None
) -> List[Dict[str, object]]:
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


def build_stance_lines(
    row: Dict[str, str],
    label: str | None,
    stance_base: float | None = None,
    stance_categories: List[Dict[str, object]] | None = None,
) -> List[Dict[str, object]]:
    raw = row.get("Poise Dmg MV", "") or "0"
    try:
        value = float(raw)
    except ValueError:
        value = 0.0

    super_raw = row.get("AtkSuperArmor", "") or "0"
    try:
        super_armor = float(super_raw)
    except ValueError:
        super_armor = 0.0
    if value <= 0 and super_armor <= 0:
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
            "stance_cat_key": tuple((c.get("name") for c in stance_categories))
            if stance_categories
            else (),
            "stance_super_armor": super_armor if super_armor > 0 else 0.0,
        }
    ]


def load_unique_poise_bases(path: Path) -> Dict[str, float]:
    base_map: Dict[str, float] = {}
    with path.open() as f:
        reader = csv.DictReader(f)
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


def load_aow_categories(
    equip_path: Path, category_map: Dict[str, Dict[str, object]]
) -> Dict[str, List[Dict[str, object]]]:
    mapping: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    cat_keys = set(category_map.keys())
    with equip_path.open() as f:
        reader = csv.DictReader(f)
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
            for cat_key in cat_keys:
                if row.get(cat_key, "0") == "1":
                    mapping[key_name].append(
                        {
                            "key": cat_key,
                            "name": category_map[cat_key]["name"],
                            "poise": category_map[cat_key]["poise"],
                        }
                    )
    return mapping


def load_ready_names(ready_path: Path, required: bool) -> List[str]:
    if not required:
        return []
    if not ready_path.exists():
        raise FileNotFoundError(
            f"--ready-only requested but missing ready file: {ready_path}"
        )
    with ready_path.open() as f:
        ready_data = json.load(f)
    return [
        item["name"] for item in ready_data if isinstance(item, dict) and "name" in item
    ]


def make_ready_filter(ready_names: List[str]):
    def is_ready_allowed(name: str, weapon_label: str | None = None) -> bool:
        if not ready_names:
            return True
        if name in ready_names:
            return True
        canonical = canonical_skill_name(name)
        if canonical in ready_names:
            return True
        _, stripped = extract_weapon_prefix(name)
        if stripped and stripped in ready_names:
            return True
        for base in ready_names:
            if (
                name.startswith(f"{base} ")
                or name.startswith(f"{base}(")
                or canonical.startswith(f"{base} ")
            ):
                return True
            if weapon_label and f"[{weapon_label}]" in base:
                return True
        return False

    return is_ready_allowed


def find_aow_categories(
    skill_name: str, aow_categories: Dict[str, List[Dict[str, object]]]
) -> List[Dict[str, object]] | None:
    candidates: List[str] = []
    lower = skill_name.lower()
    candidates.append(lower)
    canonical_lower = canonical_skill_name(skill_name).lower()
    if canonical_lower not in candidates:
        candidates.append(canonical_lower)
    trimmed_charged = re.sub(
        r"\s+charged$", "", skill_name, flags=re.IGNORECASE
    ).strip()
    if trimmed_charged:
        trimmed_lower = trimmed_charged.lower()
        if trimmed_lower not in candidates:
            candidates.append(trimmed_lower)
        canonical_trimmed = canonical_skill_name(trimmed_charged).lower()
        if canonical_trimmed not in candidates:
            candidates.append(canonical_trimmed)
    for cand in candidates:
        cats = aow_categories.get(cand)
        if cats:
            return cats
    return None


def build_lines_for_row(
    row: Dict[str, str],
    stance_base: float | None,
    stance_categories: List[Dict[str, object]] | None,
) -> List[Dict[str, object]]:
    weapon_lines = build_weapon_lines(row, row.get("label"))
    bullet_lines = (
        build_bullet_lines(row, row.get("label"))
        if (row.get("isAddBaseAtk", "").upper() == "TRUE" or has_base_damage(row))
        else []
    )
    status_lines = build_status_multiplier_lines(row, row.get("label"))
    stance_lines = build_stance_lines(
        row,
        row.get("label"),
        stance_base=stance_base,
        stance_categories=stance_categories,
    )
    lines = bullet_lines + weapon_lines + status_lines + stance_lines
    for line in lines:
        line["hash_id"] = row.get("hash_id", "")
    return lines


def normalize_stance_fields(entry: Dict[str, object]) -> Dict[str, object]:
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


def collapse_group(entries: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    re_any_bracket = re.compile(r"\[\d+\]")

    combined: Dict[
        Tuple[str, str, str, bool, str, bool, str, float | None, Tuple],
        Dict[str, object],
    ] = {}
    others: List[Dict[str, object]] = []
    for entry in entries:
        entry = normalize_stance_fields(entry)
        phase = entry.get("phase", "")
        stripped_phase = re_any_bracket.sub("", phase).strip()
        if re_any_bracket.search(phase):
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
                    "stance_super_armor": 0.0,
                },
            )
            bucket["value"] += float(entry.get("value", 0) or 0)
            bucket["stance_super_armor"] += float(
                entry.get("stance_super_armor", 0) or 0
            )
            bucket["count"] += 1
        else:
            others.append(entry)

    combined_entries = list(combined.values()) + others

    paired_output: List[Dict[str, object]] = []
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
    has_any_lacking = bool(lacking_map)
    for key in all_keys:
        base_entry = dict(base_map.get(key, {})) if key in base_map else None
        lacking_entry = lacking_map.get(key)
        derived_from_lacking = False

        if base_entry is None and lacking_entry is not None:
            base_entry = dict(lacking_entry)
            base_entry["is_lacking"] = False
            base_entry["value"] = 0
            derived_from_lacking = True
        elif base_entry is None:
            continue

        if lacking_entry:
            base_entry["lacking_value"] = lacking_entry.get("value")
            base_entry["_has_lacking"] = True
        elif has_any_lacking:
            base_entry["lacking_value"] = 0
            base_entry["_has_lacking"] = True

        if base_entry.get("kind") == "stance":
            base_entry["stance_super_armor"] = float(
                base_entry.get("stance_super_armor", 0) or 0
            )
            if derived_from_lacking:
                base_entry["stance_super_armor"] = 0.0
            if lacking_entry:
                base_entry["stance_super_armor_lacking"] = float(
                    lacking_entry.get("stance_super_armor", 0) or 0
                )
            elif has_any_lacking:
                base_entry["stance_super_armor_lacking"] = 0.0

        paired_output.append(base_entry)
    return paired_output


def hash_sort_key(hid: str) -> Tuple[int, int]:
    if not hid:
        return (0, 0)
    m = re.match(r"#(\d+)", hid)
    if m:
        return (1, int(m.group(1)))
    return (1, 9999)


def follow_up_priority(phase_value: str) -> int:
    if "Light Follow-up" in phase_value or "R1" in phase_value:
        return 1
    if "Heavy Follow-up" in phase_value or "R2" in phase_value:
        return 2
    return 0


def stance_factors(meta_entry: Dict[str, object] | None) -> List[float]:
    if not meta_entry:
        return [1.0]
    factors: List[float] = []
    stance_categories = meta_entry.get("stance_categories")
    stance_base = meta_entry.get("stance_base")
    if stance_categories:
        for cat in stance_categories:
            try:
                val = float(cat.get("poise") or 0) / 100.0
                if val > 0:
                    factors.append(val)
            except Exception:
                continue
    elif stance_base is not None:
        try:
            val = float(stance_base) / 100.0
            if val > 0:
                factors.append(val)
        except Exception:
            factors.append(1.0)
    if not factors:
        factors = [1.0]
    return factors


def apply_stance_scaling(
    values: List[object],
    lacking_values: List[object],
    super_values: List[float],
    super_lacking_values: List[float],
    factors: List[float],
    present_flags: List[bool],
) -> Tuple[List[object], List[object]]:
    lacking_src = lacking_values if lacking_values else [0] * max(1, len(values))
    super_src = super_values if super_values else [0] * max(1, len(values))
    super_lacking_src = (
        [0] * len(lacking_src)
        if not super_lacking_values or all(v is None for v in super_lacking_values)
        else [float(v or 0) for v in super_lacking_values]
    )
    if len(super_lacking_src) < len(lacking_src):
        super_lacking_src.extend([0] * (len(lacking_src) - len(super_lacking_src)))

    max_len_local = max(len(values), len(lacking_src))
    combined_vals: List[object] = []
    combined_lacks: List[object] = []
    for idx in range(max_len_local):
        base_val = values[idx] if idx < len(values) else 0
        base_super = super_src[idx] if idx < len(super_src) else 0
        scaled = [
            (base_val if base_val is not None else 0) * f + base_super for f in factors
        ]
        mn, mx = min(scaled), max(scaled)
        combined_vals.append((mn, mx) if abs(mx - mn) > 1e-9 else mn)

        lack_val = lacking_src[idx] if idx < len(lacking_src) else 0
        lack_super = super_lacking_src[idx] if idx < len(super_lacking_src) else 0
        scaled_lack = [
            (lack_val if lack_val is not None else 0) * f + lack_super for f in factors
        ]
        mn_l, mx_l = min(scaled_lack), max(scaled_lack)
        combined_lacks.append((mn_l, mx_l) if abs(mx_l - mn_l) > 1e-9 else mn_l)

    while combined_vals and present_flags and not present_flags[len(combined_vals) - 1]:
        last_idx = len(combined_vals) - 1
        last_val = combined_vals[last_idx]
        last_lack = combined_lacks[last_idx] if last_idx < len(combined_lacks) else None

        def is_zero(v):
            if v is None:
                return True
            if isinstance(v, (list, tuple)):
                return all((x or 0) == 0 for x in v)
            try:
                return float(v) == 0.0
            except Exception:
                return False

        if not is_zero(last_val) or (combined_lacks and not is_zero(last_lack)):
            break
        combined_vals.pop()
        if combined_lacks:
            combined_lacks.pop()
        present_flags.pop()

    return combined_vals, combined_lacks


def build_line_entries(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
    order = {"physical": 0, "elemental": 1, "status": 2, "stance": 3}

    hash_groups: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for entry in entries:
        hash_groups[entry.get("hash_id", "")].append(entry)

    collapsed_by_hash: Dict[str, List[Dict[str, object]]] = {
        hid: collapse_group(group_entries) for hid, group_entries in hash_groups.items()
    }
    hash_ids_sorted = sorted(collapsed_by_hash.keys(), key=hash_sort_key)

    key_fields = ("kind", "descriptor", "suffix", "is_multiplier", "color", "phase")
    all_keys = set()
    for entries_list in collapsed_by_hash.values():
        for entry in entries_list:
            all_keys.add(tuple(entry.get(k, "") for k in key_fields))

    line_entries: List[Dict[str, object]] = []
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
        values: List[object] = []
        lacking_values: List[object] = []
        super_values: List[float] = []
        super_lacking_values: List[float] = []
        present_flags: List[bool] = []
        has_lacking = False
        has_flag = False
        meta_entry: Dict[str, object] | None = None
        for hid in hash_ids_sorted:
            entries_list = collapsed_by_hash[hid]
            match_entry = next(
                (
                    entry
                    for entry in entries_list
                    if tuple(entry.get(k, "") for k in key_fields) == key
                ),
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
                super_values.append(
                    float(match_entry.get("stance_super_armor", 0) or 0)
                )
                super_lacking_values.append(
                    match_entry.get("stance_super_armor_lacking")
                )
                present_flags.append(True)
            else:
                values.append(0)
                lacking_values.append(None)
                super_values.append(0)
                super_lacking_values.append(0)
                present_flags.append(False)
        has_lacking = (
            has_flag or has_lacking or any(v is not None for v in lacking_values)
        )

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

        base_sort_key = (
            follow_up_priority(phase),
            order.get(kind, 99),
            descriptor,
            phase,
        )

        def add_line_entry(
            label_text_local: str,
            base_vals: List[object],
            lacking_vals: List[object],
            cat_names: str | None = None,
        ):
            entry_label = label_text_local
            if cat_names:
                entry_label = f"{label_text_local} ({cat_names})"
            base_label_body = label_text_local[len(prefix) :]
            line_entries.append(
                {
                    "prefix": prefix,
                    "label_body": entry_label[len(prefix) :],
                    "label_body_base": base_label_body,
                    "color": color or COLOR_GOLD,
                    "suffix": suffix,
                    "values": base_vals,
                    "lacking_values": lacking_vals,
                    "has_lacking": has_lacking,
                    "is_multiplier": is_multiplier,
                    "merge_key": (
                        prefix,
                        entry_label[len(prefix) :],
                        suffix,
                        color or COLOR_GOLD,
                        kind,
                    ),
                    "merge_label": entry_label,
                    "kind": kind,
                    "sort_key": base_sort_key,
                    "is_multiplier_flag": is_multiplier,
                }
            )

        if kind == "stance":
            factors = stance_factors(meta_entry)
            combined_vals, combined_lacks = apply_stance_scaling(
                values,
                lacking_values,
                super_values,
                super_lacking_values,
                factors,
                present_flags,
            )
            add_line_entry(label_text, combined_vals, combined_lacks)
            if line_entries:
                line_entries[-1]["has_lacking"] = True
        else:
            add_line_entry(label_text, values, lacking_values)

    stance_buckets: Dict[Tuple, Dict[str, object]] = {}
    filtered_entries: List[Dict[str, object]] = []
    for entry in line_entries:
        if entry.get("kind") != "stance":
            filtered_entries.append(entry)
            continue
        key = (
            entry.get("prefix", ""),
            entry.get("label_body_base") or entry.get("label_body", ""),
            entry.get("suffix", ""),
            entry.get("color", COLOR_STANCE),
            entry.get("sort_key"),
        )
        bucket = stance_buckets.setdefault(
            key,
            {
                "prefix": entry.get("prefix", ""),
                "label_body": entry.get("label_body_base")
                or entry.get("label_body", ""),
                "color": entry.get("color", COLOR_STANCE),
                "suffix": entry.get("suffix", ""),
                "values_lists": [],
                "lacking_lists": [],
                "has_lacking": False,
                "is_multiplier": entry.get("is_multiplier", False),
                "merge_key": (
                    entry.get("prefix", ""),
                    entry.get("label_body_base") or entry.get("label_body", ""),
                    entry.get("suffix", ""),
                    entry.get("color", COLOR_STANCE),
                    "stance",
                ),
                "merge_label": entry.get("merge_label", ""),
                "sort_key": entry.get("sort_key"),
                "is_multiplier_flag": entry.get("is_multiplier_flag", False),
                "kind": "stance",
            },
        )
        vals = entry.get("values") or []
        for idx, val in enumerate(vals):
            while len(bucket["values_lists"]) <= idx:
                bucket["values_lists"].append([])
            bucket["values_lists"][idx].append(val if val is not None else 0)
        if entry.get("has_lacking"):
            bucket["has_lacking"] = True
        lacks = entry.get("lacking_values") or []
        for idx, val in enumerate(lacks):
            while len(bucket["lacking_lists"]) <= idx:
                bucket["lacking_lists"].append([])
            bucket["lacking_lists"][idx].append(val if val is not None else 0)

    def to_range_lists(source_lists: List[List[float]]) -> List[object]:
        out: List[object] = []
        for lst in source_lists:
            if not lst:
                out.append(0)
                continue
            mn = min(lst)
            mx = max(lst)
            try:
                mn_r = int(math.ceil(float(mn)))
                mx_r = int(math.ceil(float(mx)))
            except Exception:
                mn_r, mx_r = mn, mx
            if mn_r == mx_r:
                out.append(mn_r)
            else:
                out.append((mn_r, mx_r))
        return out

    for bucket in stance_buckets.values():
        bucket["values"] = to_range_lists(bucket.pop("values_lists"))
        if bucket.get("has_lacking"):
            bucket["lacking_values"] = to_range_lists(bucket.pop("lacking_lists"))
        else:
            bucket["lacking_values"] = []
        filtered_entries.append(bucket)

    return filtered_entries


def render_combined_line(
    template: Dict[str, object], variant_lines: List[Dict[str, object] | None]
) -> str:
    desc_text = " ".join(
        str(template.get(k, "") or "")
        for k in ("label_body", "descriptor", "merge_label")
    )
    is_stance = template.get("kind") == "stance" or "stance" in desc_text.lower()
    overall_has_lacking = any(
        line and line.get("has_lacking") for line in variant_lines
    )

    def fmt(val, is_multiplier: bool) -> str:
        s = format_number(str(val))
        return f"{s}x" if is_multiplier else s

    def fmt_stance_vals(vals: List[object]) -> str:
        if not vals:
            return "0"
        if len(vals) == 1 and isinstance(vals[0], str):
            nums = [n for n in re.findall(r"-?\d+\.\d+|-?\d+", vals[0])]
            if nums:
                parsed = []
                for i in range(0, len(nums), 2):
                    pair = nums[i : i + 2]
                    if len(pair) == 2:
                        parsed.append((float(pair[0]), float(pair[1])))
                    else:
                        parsed.append(float(pair[0]))
                vals = parsed

        def format_val(v):
            if isinstance(v, str):
                v_str = v.strip()
                if v_str.startswith("(") and "," in v_str:
                    try:
                        inner = v_str.strip("()")
                        a, b = [s.strip() for s in inner.split(",", 1)]
                        a_num = int(math.ceil(float(a)))
                        b_num = int(math.ceil(float(b)))
                        return f"{a_num}-{b_num}" if a_num != b_num else str(a_num)
                    except Exception:
                        pass
                if "-" in v_str:
                    try:
                        a, b = v_str.split("-", 1)
                        a_num = int(math.ceil(float(a)))
                        b_num = int(math.ceil(float(b)))
                        return f"{a_num}-{b_num}" if a_num != b_num else str(a_num)
                    except Exception:
                        pass
            try:
                if isinstance(v, (list, tuple)) and len(v) == 2:
                    a = int(math.ceil(float(v[0])))
                    b = int(math.ceil(float(v[1])))
                    return f"{a}-{b}" if a != b else str(a)
                num = int(math.ceil(float(v)))
                return str(num)
            except Exception:
                return str(v)

        return ", ".join(format_val(v) for v in vals)

    value_parts: List[str] = []
    lacking_parts: List[str] = []
    for line in variant_lines:
        vals = (line.get("values") if line else []) or []
        lacks = (line.get("lacking_values") if line else []) or []
        if not vals:
            vals = [0]
        if is_stance:
            val_str = fmt_stance_vals(vals)
        else:
            val_str = ", ".join(
                fmt(
                    v if v is not None else 0, template.get("is_multiplier_flag", False)
                )
                for v in vals
            )
        value_parts.append(val_str)

        if overall_has_lacking:
            if is_stance:
                lack_str = fmt_stance_vals(lacks if lacks else [0])
            else:
                target_len = max(len(vals), len(lacks)) if lacks else len(vals)
                lacks = list(lacks) if lacks else []
                while len(lacks) < target_len:
                    lacks.append(0)
                lack_str = ", ".join(
                    fmt(
                        v if v is not None else 0,
                        template.get("is_multiplier_flag", False),
                    )
                    for v in lacks
                )
            lacking_parts.append(lack_str)

    combined_base = " | ".join(value_parts)
    value_str = combined_base
    if overall_has_lacking:
        combined_lacking = " | ".join(lacking_parts)
        value_str = f"{combined_base} [{combined_lacking}]"

    return f'\n{template.get("prefix", "")}<font color="{template.get("color", COLOR_GOLD)}">{template.get("label_body", "")}:</font> {value_str}{template.get("suffix", "")}'


def collapse_variants(group: List[Dict[str, object]]) -> List[str]:
    merged_lines = []
    variant_count = len(group)
    merge_map: Dict[Tuple, List[Dict[str, object] | None]] = {}
    for idx, variant in enumerate(group):
        for line in variant["lines"]:
            bucket = merge_map.setdefault(line["merge_key"], [None] * variant_count)
            bucket[idx] = line

    if variant_count == 2:
        for bucket in merge_map.values():
            if bucket[0] and not bucket[1]:
                if "water aoe" in bucket[0].get("merge_label", "").lower():
                    bucket[1] = dict(bucket[0])

    for bucket in merge_map.values():
        template = next((b for b in bucket if b), None)
        if not template:
            continue
        merged_lines.append(
            {
                "text": render_combined_line(template, bucket),
                "sort_key": template["sort_key"],
            }
        )

    merged_lines.sort(key=lambda x: x["sort_key"])
    return [m["text"] for m in merged_lines]


def combine_variant_group(entries: List[Dict[str, object]]) -> Dict[str, object]:
    weapons: List[str] = []
    merge_map: Dict[Tuple, List[Dict[str, object] | None]] = {}
    for idx, variant in enumerate(entries):
        w = variant.get("weapon")
        if isinstance(w, list):
            weapons.extend(w)
        elif w:
            weapons.append(w)
        for line in variant["lines"]:
            bucket = merge_map.setdefault(line["merge_key"], [None] * len(entries))
            bucket[idx] = line

    combined_lines: List[Dict[str, object]] = []
    for bucket in merge_map.values():
        template = next((b for b in bucket if b), None)
        if not template:
            continue
        values_combined: List[object] = []
        lacks_combined: List[object] = []
        has_lacking = False
        max_len = 0
        for line in bucket:
            if not line:
                continue
            max_len = max(max_len, len(line.get("values") or []))
            if line.get("has_lacking"):
                has_lacking = True
                max_len = max(max_len, len(line.get("lacking_values") or []))
            elif line.get("kind") == "stance":
                has_lacking = True

        for idx in range(max_len):
            vals_at_idx = []
            lacks_at_idx = []
            for line in bucket:
                if not line:
                    continue
                vals = line.get("values") or []
                if idx < len(vals):
                    val = vals[idx]
                    if template.get("kind") == "stance":
                        if isinstance(val, (list, tuple)):
                            vals_at_idx.extend(list(val))
                        elif isinstance(val, str) and "-" in val:
                            try:
                                a, b = val.split("-", 1)
                                vals_at_idx.extend([float(a), float(b)])
                            except Exception:
                                try:
                                    vals_at_idx.append(float(val))
                                except Exception:
                                    vals_at_idx.append(val)
                        else:
                            vals_at_idx.append(val)
                    else:
                        vals_at_idx.append(val)
                if has_lacking:
                    lacks = line.get("lacking_values") or []
                    if idx < len(lacks):
                        lv = lacks[idx]
                        if template.get("kind") == "stance":
                            if isinstance(lv, (list, tuple)):
                                lacks_at_idx.extend(list(lv))
                            elif isinstance(lv, str) and "-" in lv:
                                try:
                                    a, b = lv.split("-", 1)
                                    lacks_at_idx.extend([float(a), float(b)])
                                except Exception:
                                    try:
                                        lacks_at_idx.append(float(lv))
                                    except Exception:
                                        lacks_at_idx.append(lv)
                            else:
                                lacks_at_idx.append(lv)
                        else:
                            lacks_at_idx.append(lv)
                    elif template.get("kind") == "stance":
                        lacks_at_idx.append(0)
            if template.get("kind") == "stance":

                def round_num(x):
                    try:
                        return int(math.ceil(float(x)))
                    except Exception:
                        return x

                if vals_at_idx:
                    mn = min(vals_at_idx)
                    mx = max(vals_at_idx)
                    mn = round_num(mn)
                    mx = round_num(mx)
                    values_combined.append((mn, mx) if mn != mx else mn)
                else:
                    values_combined.append(0)
                if has_lacking:
                    if lacks_at_idx:
                        mn = min(lacks_at_idx)
                        mx = max(lacks_at_idx)
                        mn = round_num(mn)
                        mx = round_num(mx)
                        lacks_combined.append((mn, mx) if mn != mx else mn)
                    else:
                        lacks_combined.append(0)
            else:
                if vals_at_idx:
                    try:
                        values_combined.append(min(vals_at_idx))
                    except Exception:
                        values_combined.append(vals_at_idx[0])
                else:
                    values_combined.append(0)
                if has_lacking:
                    if lacks_at_idx:
                        try:
                            lacks_combined.append(min(lacks_at_idx))
                        except Exception:
                            lacks_combined.append(lacks_at_idx[0])
                    else:
                        lacks_combined.append(0)

        new_line = dict(template)
        new_line["values"] = values_combined
        if has_lacking:
            new_line["lacking_values"] = lacks_combined
            new_line["has_lacking"] = True
        combined_lines.append(new_line)

    return {
        "name": entries[0]["name"],
        "weapon": weapons,
        "lines": combined_lines,
        "is_charged": entries[0].get("is_charged", False),
        "base_key": entries[0].get("base_key"),
        "is_unique": entries[0].get("is_unique", False),
    }


def normalize_stance_strings(lines: List[str]) -> List[str]:
    out_lines = []
    for line in lines:
        if "stance damage" not in line.lower():
            out_lines.append(line)
            continue
        try:
            prefix, tail = (line.split(":</font>", 1) + [""])[:2]
            base_part, lack_part = tail, ""
            if "[" in tail:
                base_part, rest = tail.split("[", 1)
                lack_part = rest.split("]", 1)[0]

            def normalize_section(section: str, use_ceil: bool) -> str:
                if not section:
                    return "0"
                segments = [seg.strip() for seg in section.split("|")]
                norm_segments: List[str] = []
                for seg in segments:
                    cleaned = re.sub(r"--+", "-", seg.strip())
                    tokens = [tok.strip() for tok in cleaned.split(",") if tok.strip()]
                    parts: List[str] = []
                    for tok in tokens:
                        if "-" in tok:
                            left, right = tok.split("-", 1)
                            try:
                                a_val = float(left)
                                b_val = float(right)
                            except Exception:
                                parts.append(tok)
                                continue
                            a_out = (
                                int(math.ceil(a_val)) if use_ceil else int(round(a_val))
                            )
                            b_out = (
                                int(math.ceil(b_val)) if use_ceil else int(round(b_val))
                            )
                            parts.append(
                                f"{a_out}-{b_out}" if a_out != b_out else str(a_out)
                            )
                        else:
                            try:
                                num = float(tok)
                                num_out = (
                                    int(math.ceil(num)) if use_ceil else int(round(num))
                                )
                                parts.append(str(num_out))
                            except Exception:
                                parts.append(tok)
                    norm_segments.append(", ".join(parts) if parts else "0")
                return " | ".join(norm_segments)

            base_str = normalize_section(base_part, use_ceil=False)
            lack_str = (
                normalize_section(lack_part, use_ceil=True) if lack_part else None
            )
            rebuilt = f"{prefix}:</font> {base_str.strip()}"
            if lack_str is not None:
                rebuilt += f" [{lack_str.strip()}]"
            out_lines.append(rebuilt)
        except Exception:
            out_lines.append(line)
    return out_lines


def collapse_variant_group(
    base_name: str,
    variants_sorted: List[Dict[str, object]],
    output: List[Dict[str, object]],
) -> None:
    def emit_entry(out_name: str, variant_group: List[Dict[str, object]]) -> None:
        lines_out = collapse_variants(variant_group)
        lines_out = normalize_stance_strings(lines_out)
        weapons: List[str] = []
        for variant in variant_group:
            w = variant.get("weapon") or []
            if isinstance(w, str):
                w = [w]
            weapons.extend(w)
        weapons = sorted(set(w for w in weapons if w))
        output.append({"name": out_name, "weapon": weapons, "stats": lines_out})

    has_charged = any(v.get("is_charged") for v in variants_sorted)
    has_uncharged = any(not v.get("is_charged") for v in variants_sorted)

    if has_charged and has_uncharged:

        def weapon_key(v: Dict[str, object]) -> Tuple[Tuple[str, ...], bool]:
            w = v.get("weapon") or []
            if isinstance(w, str):
                w = [w]
            return (tuple(sorted(set(w))), bool(v.get("is_unique")))

        uncharged_map: Dict[Tuple[Tuple[str, ...], bool], Dict[str, object]] = {}
        charged_map: Dict[Tuple[Tuple[str, ...], bool], Dict[str, object]] = {}
        for variant in variants_sorted:
            key = weapon_key(variant)
            if variant.get("is_charged"):
                charged_map[key] = variant
            else:
                uncharged_map[key] = variant

        all_keys = sorted(set(uncharged_map.keys()) | set(charged_map.keys()))
        for key in all_keys:
            base_variant = uncharged_map.get(
                key,
                {
                    "name": base_name,
                    "weapon": list(key[0]),
                    "lines": [],
                    "is_charged": False,
                    "base_key": base_name,
                    "is_unique": key[1],
                },
            )
            charged_variant = charged_map.get(
                key,
                {
                    "name": f"{base_name} Charged",
                    "weapon": list(key[0]),
                    "lines": [],
                    "is_charged": True,
                    "base_key": base_name,
                    "is_unique": key[1],
                },
            )
            emit_entry(base_name, [base_variant, charged_variant])
    else:
        for variant in variants_sorted:
            emit_entry(variant["name"], [variant])


def merge_identical_stats(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
    merged_output: Dict[Tuple[str, Tuple[str, ...]], Dict[str, object]] = {}
    for entry in entries:
        base_name = entry["name"]
        stats_tuple = tuple(entry["stats"])
        key = (base_name, stats_tuple)
        bucket = merged_output.setdefault(
            key, {"name": base_name, "stats": list(stats_tuple), "weapon": []}
        )
        bucket["weapon"].extend(entry.get("weapon") or [])

    output: List[Dict[str, object]] = []
    for bucket in merged_output.values():
        weapons = sorted(set(w for w in bucket.get("weapon") or [] if w))
        bucket["weapon"] = weapons
        output.append(bucket)
    return output


def populate_ready(skill_path: Path, output: List[Dict[str, object]]) -> None:
    if not skill_path.exists():
        print(f"Cannot populate skill file; missing {skill_path}")
        return
    print(f"Populating {skill_path} with stats fields...")
    with skill_path.open() as f:
        skill_data = json.load(f)

    stats_lookup: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for entry in output:
        stats_lookup[entry["name"]].append(
            {"weapon": entry.get("weapon") or [], "stats": entry["stats"]}
        )

    def matching_variants(item_name: str) -> List[Dict[str, object]]:
        matches: List[Dict[str, object]] = []
        base = stats_lookup.get(item_name)
        if base:
            matches.extend(base)
        for name, variants in stats_lookup.items():
            if name == item_name:
                continue
            if name.startswith(f"{item_name} ") or name.startswith(f"{item_name}("):
                matches.extend(variants)
        return matches

    updated: List[Dict[str, object]] = []
    for item in skill_data:
        if not isinstance(item, dict) or "name" not in item:
            updated.append(item)
            continue
        variant_matches = matching_variants(item["name"])
        if not variant_matches:
            updated.append(item)
            continue

        existing_variant_keys = {
            k
            for k in item.keys()
            if k == item["name"] or (isinstance(k, str) and k.startswith("["))
        }
        new_item: Dict[str, object] = {}
        all_weapons: List[str] = []

        merged_variants: List[Dict[str, object]] = []
        merge_map: Dict[Tuple[str, ...], List[str]] = {}
        for variant in variant_matches:
            stats_tuple = tuple(variant["stats"])
            merge_map.setdefault(stats_tuple, []).extend(variant.get("weapon") or [])
        for stats_tuple, weapons in merge_map.items():
            merged_variants.append(
                {
                    "stats": list(stats_tuple),
                    "weapon": sorted(set(w for w in weapons if w)),
                }
            )

        def variant_key_for(weapon_list: List[str]) -> str:
            if not weapon_list:
                return item["name"]
            joined = "/".join(weapon_list)
            return f"[{joined}] {item['name']}"

        for key, value in item.items():
            if key in existing_variant_keys:
                continue
            new_item[key] = value

        inserted = False
        for key in list(new_item.keys()):
            if key != "info":
                continue
            for variant in merged_variants:
                weapons = variant.get("weapon") or []
                all_weapons.extend(weapons)
                v_key = variant_key_for(weapons)
                new_item[v_key] = variant["stats"]
            inserted = True
            break

        if not inserted:
            for variant in merged_variants:
                weapons = variant.get("weapon") or []
                all_weapons.extend(weapons)
                v_key = variant_key_for(weapons)
                new_item[v_key] = variant["stats"]

        if all_weapons:
            new_item["weapon"] = sorted(set(all_weapons))
        updated.append(new_item)

    with skill_path.open("w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)
    print(f"Populated stats into {skill_path}")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    ready_names = load_ready_names(Path(args.ready_path), args.ready_only)
    ready_filter = make_ready_filter(ready_names)

    unique_poise_bases = load_unique_poise_bases(
        Path("docs/(1.16.1)-Poise-Damage-MVs.csv")
    )
    weapon_category_map = json.loads(
        Path("docs/weapon_categories_poise.json").read_text()
    )
    aow_categories = load_aow_categories(
        Path("PARAM/EquipParamGem.csv"), weapon_category_map
    )

    grouped_variants: Dict[Tuple[str, str], Dict[str, object]] = {}
    with input_path.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            weapon_prefix, name_wo_prefix = extract_weapon_prefix(row["Name"])
            unique_weapon = (row.get("Unique Skill Weapon") or "").strip()
            weapon_label = unique_weapon or (weapon_prefix or "")

            base_name, label = split_skill_name(name_wo_prefix)
            base_no_hash, hash_id = strip_hash_variant(base_name)

            stance_base = None
            stance_categories = None
            if unique_weapon:
                stance_base = unique_poise_bases.get(unique_weapon.lower())
            else:
                stance_categories = find_aow_categories(base_no_hash, aow_categories)

            row = dict(row)
            row["label"] = label
            row["hash_id"] = hash_id

            lines = build_lines_for_row(row, stance_base, stance_categories)
            if not lines:
                continue

            key = (canonical_skill_name(base_no_hash), weapon_label)
            entry = grouped_variants.setdefault(
                key,
                {
                    "raw_name": base_no_hash,
                    "weapon": weapon_label,
                    "lines": [],
                    "is_unique": bool(unique_weapon),
                },
            )
            entry["lines"].extend(lines)

    variant_entries: List[Dict[str, object]] = []
    for (_, weapon_label), data in grouped_variants.items():
        canon_name = canonical_skill_name(data["raw_name"])
        if args.ready_only and not ready_filter(canon_name, weapon_label):
            continue
        variant_entries.append(
            {
                "name": data["raw_name"],
                "weapon": weapon_label,
                "lines": build_line_entries(data["lines"]),
                "is_charged": bool(
                    re.search(r"\s+charged$", data["raw_name"], flags=re.IGNORECASE)
                ),
                "base_key": re.sub(
                    r"\s+charged$", "", data["raw_name"], flags=re.IGNORECASE
                ).strip(),
                "is_unique": data.get("is_unique", False),
            }
        )

    grouped_variants_by_base: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for entry in variant_entries:
        grouped_variants_by_base[entry["base_key"]].append(entry)

    output: List[Dict[str, object]] = []
    for base_name, variants in grouped_variants_by_base.items():
        unique_variants = [v for v in variants if v.get("is_unique")]
        generic_variants = [v for v in variants if not v.get("is_unique")]

        var_generic = [
            v
            for v in generic_variants
            if isinstance(v.get("weapon"), str)
            and v.get("weapon").lower().startswith("var")
        ]
        generic_variants = [v for v in generic_variants if v not in var_generic]

        combined_variants: List[Dict[str, object]] = []
        if generic_variants:
            grouped_by_name: Dict[str, List[Dict[str, object]]] = defaultdict(list)
            for variant in generic_variants:
                grouped_by_name[variant["name"]].append(variant)
            for name in sorted(grouped_by_name.keys()):
                combined_variants.append(combine_variant_group(grouped_by_name[name]))
        if var_generic:
            grouped_var_by_name: Dict[str, List[Dict[str, object]]] = defaultdict(list)
            for variant in var_generic:
                grouped_var_by_name[variant["name"]].append(variant)
            for name in sorted(grouped_var_by_name.keys()):
                combined_variants.append(
                    combine_variant_group(grouped_var_by_name[name])
                )
        combined_variants.extend(unique_variants)

        variants_sorted = sorted(
            combined_variants, key=lambda v: (1 if v["is_charged"] else 0, v["name"])
        )
        collapse_variant_group(base_name, variants_sorted, output)

    output = merge_identical_stats(output)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(output)} skill entries to {output_path}")

    if args.populate:
        populate_ready(Path(args.ready_path), output)


if __name__ == "__main__":
    main()
