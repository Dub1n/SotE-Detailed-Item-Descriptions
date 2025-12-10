import argparse
import csv
import json
import re
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Optional


ROOT = Path(__file__).resolve().parents[2]
HELPERS_DIR = ROOT / "scripts"
if str(HELPERS_DIR) not in sys.path:
    sys.path.append(str(HELPERS_DIR))

from helpers.diff import (  # noqa: E402
    load_rows_by_key,
    report_row_deltas,
)
from helpers.output import format_path_for_console  # noqa: E402
ATTACK_DATA_CSV = ROOT / "docs/(1.16.1)-Ashes-of-War-Attack-Data.csv"
POISE_MV_CSV = ROOT / "docs/(1.16.1)-Poise-Damage-MVs.csv"
EQUIP_PARAM_GEM_CSV = ROOT / "PARAM/EquipParamGem.csv"
EQUIP_PARAM_WEAPON_CSV = ROOT / "PARAM/EquipParamWeapon.csv"
SP_EFFECT_PARAM_CSV = ROOT / "PARAM/SpEffectParam.csv"
CATEGORY_POISE_JSON = ROOT / "docs/weapon_categories_poise.json"
SKILL_LIST_TXT = ROOT / "docs/skill_names_from_gem_and_behavior.txt"
SKILL_ATTR_SCALING_JSON = ROOT / "work/aow_pipeline/skill_attr_scaling.json"
DEFAULT_OUTPUT = ROOT / "work/aow_pipeline/AoW-data-1.csv"

IGNORED_PREFIXES = {"Slow", "Var1", "Var2"}

CATEGORY_FLAG_PREFIX = "canMountWep_"
OUTPUT_COLUMNS = [
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
    "Weapon Source",
    "Weapon",
    "Weapon Poise",
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
    "Status MV",
    "Wep Status",
    "Weapon Buff MV",
    "Poise Dmg MV",
    "PhysAtkAttribute",
    "AtkPhys",
    "AtkMag",
    "AtkFire",
    "AtkLtng",
    "AtkHoly",
    "AtkSuperArmor",
    "isAddBaseAtk",
    "Overwrite Scaling",
    "Bullet Stat",
    "subCategory1",
    "subCategory2",
    "subCategory3",
    "subCategory4",
]


def load_category_flags() -> Tuple[
    Dict[str, Dict[str, float]], Dict[str, float]
]:
    data = json.loads(CATEGORY_POISE_JSON.read_text())
    flag_to_info: Dict[str, Dict[str, float]] = {}
    name_to_poise: Dict[str, float] = {}
    for flag, payload in data.items():
        name = payload["name"]
        poise_val = payload["poise"]
        flag_to_info[flag] = {"name": name, "poise": poise_val}
        name_to_poise[name] = poise_val
    return flag_to_info, name_to_poise


def load_attr_scaling() -> Dict[str, str]:
    raw = json.loads(SKILL_ATTR_SCALING_JSON.read_text())
    scaling: Dict[str, str] = {}
    for key, payload in raw.items():
        stat = "-"
        if isinstance(payload, dict):
            value = payload.get("stat")
            if value not in {None, ""}:
                stat = str(value)
        scaling[str(key)] = stat
    return scaling


def base_skill_name(name: str) -> str:
    text = strip_weapon_prefix(name)
    text = text.replace("(Lacking FP)", "")
    text = re.sub(r"\([^)]*\)", "", text)  # drop parenthetical suffixes
    text = re.sub(r"#\d+", "", text)
    text = re.sub(r"\bR[12]\b", "", text)
    text = re.sub(r"\b(1h|2h)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bCharged\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bTick\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bBullet\b", "", text, flags=re.IGNORECASE)
    text = text.strip()
    text = re.split(r"\s*-\s*", text, 1)[0].strip()
    text = re.split(r"\s*\[", text)[0].strip()
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def load_skill_names() -> List[str]:
    if not SKILL_LIST_TXT.exists():
        return []
    names = [
        line.strip()
        for line in SKILL_LIST_TXT.read_text().splitlines()
        if line.strip()
    ]
    # Sort by length desc for longest-match search.
    names.sort(key=len, reverse=True)
    return names


def resolve_skill_from_list(name: str, skill_names: List[str]) -> str:
    prefix, remainder = extract_prefix(name)
    target = remainder if prefix and prefix in IGNORED_PREFIXES else name
    working = strip_weapon_prefix(target)
    for skill in skill_names:
        pattern = rf"(?i)(^|[\s\[\(-]){re.escape(skill)}(?=$|[\s\]\)-])"
        if re.search(pattern, working):
            return skill
    return base_skill_name(target)


def strip_weapon_prefix(name: str) -> str:
    if not name.startswith("["):
        return name
    match = re.match(r"^\[[^\]]+\]\s*(.*)$", name)
    return match.group(1) if match else name


def extract_prefix(name: str) -> Tuple[str, str]:
    if not name.startswith("["):
        return "", name
    match = re.match(r"^\[([^\]]+)\]\s*(.*)$", name)
    if not match:
        return "", name
    return match.group(1).strip(), match.group(2).strip()


def infer_part(name: str, matched_skill: Optional[str] = None) -> str:
    base = strip_weapon_prefix(name)
    if matched_skill:
        pattern = (
            rf"(?i)(^|[\s\[\(-]){re.escape(matched_skill)}(?=$|[\s\]\)-])"
        )
        base = re.sub(pattern, " ", base, count=1)
    base = re.sub(r"\(Lacking FP\)", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\b(1h|2h)\b", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\bCharged\b", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\bTick\b", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\bBullet\b", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\bR[12]\b", "", base)
    base = re.sub(r"#\d+", "", base)
    base = re.sub(r"\[\s*\d+\s*\]", "", base)
    # Trim leading " - " if present
    base = base.split(" - ", 1)[1] if " - " in base else base
    base = base.strip(" -:\t")
    if "(" in base or ")" in base:
        parts: List[str] = []
        cursor = 0
        for match in re.finditer(r"\([^)]*\)", base):
            before = base[cursor:match.start()].strip(" -:\t")
            if before:
                parts.append(re.sub(r"\s{2,}", " ", before).strip())
            inner = match.group(0)[1:-1].strip()
            if inner:
                parts.append(re.sub(r"\s{2,}", " ", inner).strip())
            cursor = match.end()
        trailing = base[cursor:].strip(" -:\t")
        if trailing:
            parts.append(re.sub(r"\s{2,}", " ", trailing).strip())
        if parts:
            base = ", ".join(parts)
        elif re.fullmatch(r"[()\s:-]*", base):
            base = ""
    base = re.sub(r"\s{2,}", " ", base).strip()
    if not base:
        return "Loop" if "Loop" in name else "Hit"
    return base


def parse_fp_flag(name: str) -> int:
    return 0 if "(Lacking FP)" in name else 1


def weapon_prefix(name: str) -> str:
    if not name.startswith("["):
        return ""
    match = re.match(r"^\[([^\]]+)\]", name)
    return match.group(1).strip() if match else ""


def expand_weapon_names(raw: str) -> List[str]:
    names: List[str] = []
    text = raw.strip()
    if text.startswith("(") and ")" in text:
        closing = text.find(")")
        inner = text[1:closing]
        suffix = text[closing + 1:].strip()
        parts = [p.strip() for p in inner.split("/") if p.strip()]
        for part in parts:
            candidate = f"{part} {suffix}".strip()
            if candidate:
                names.append(candidate)
        if suffix:
            names.append(suffix)
    for part in [p.strip() for p in text.split("/") if p.strip()]:
        if part not in names:
            names.append(part)
    if text and text not in names:
        names.append(text)
    return names


def parse_unique_weapon_variants(raw: str) -> List[str]:
    """
    Expand slash-delimited unique weapon labels into explicit variants.
    - "A / B" -> ["A", "B"]
    - "(A / B) C" -> ["A C", "B C"]
    - "C (A / B)" -> ["C A", "C B"]
    When no slash is present, returns the cleaned name as a single entry.
    """
    text = raw.strip()
    if not text:
        return []

    def clean(name: str) -> str:
        return re.sub(r"\s{2,}", " ", name.strip())

    match = re.search(r"\(([^()]*/[^()]*)\)", text)
    if match:
        inner = match.group(1)
        prefix = text[: match.start()].strip()
        suffix = text[match.end():].strip()
        parts = [p.strip() for p in inner.split("/") if p.strip()]
        variants = []
        for part in parts:
            combined = " ".join(
                segment
                for segment in [prefix, part, suffix]
                if segment.strip()
            )
            if combined:
                variants.append(clean(combined))
        if variants:
            return variants

    parts = [p.strip() for p in text.split("/") if p.strip()]
    if len(parts) > 1:
        return [clean(p) for p in parts]

    return [clean(text)]


def detect_follow_up(name: str) -> str:
    if "R1" in name:
        return "Light"
    if "R2" in name:
        return "Heavy"
    return "-"


def detect_hand(name: str) -> str:
    lowered = name.lower()
    if "2h" in lowered:
        return "2h"
    if "1h" in lowered:
        return "1h"
    return "-"


def detect_charged(name: str) -> int:
    return 1 if "Charged" in name else 0


def detect_step(name: str) -> str:
    match = re.search(r"#(\d+)", name)
    if match:
        return match.group(1)
    return "1"


def detect_bullet(name: str) -> int:
    return 1 if "Bullet" in name else 0


def detect_tick(name: str) -> int:
    return 1 if re.search(r"\bTick\b", name, flags=re.IGNORECASE) else 0


def load_sp_effect_names() -> Dict[str, str]:
    effects: Dict[str, str] = {}
    with SP_EFFECT_PARAM_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = (row.get("Name") or "").strip()
            if not raw_name:
                continue
            clean = raw_name.split("-", 1)[0].strip()
            clean = re.sub(r"^\[[^\]]+\]\s*", "", clean)
            if clean == "Thiollier's Hidden Needle":
                clean = "Sleep"
            effects[str(row.get("ID", "")).strip()] = clean
    return effects


def load_weapon_base_stats(
    sp_effect_names: Dict[str, str]
) -> Dict[str, Dict[str, str]]:
    stats: Dict[str, Dict[str, str]] = {}
    with EQUIP_PARAM_WEAPON_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Name") or "").strip()
            if not name:
                continue
            key = name.lower()
            status_effects: List[str] = []
            for col in ("spEffectBehaviorId0", "spEffectBehaviorId1", "spEffectBehaviorId2"):
                raw_id = (row.get(col) or "").strip()
                if not raw_id or raw_id == "-1":
                    continue
                effect_name = sp_effect_names.get(raw_id, "").strip()
                if effect_name and effect_name not in status_effects:
                    status_effects.append(effect_name)
            stats[key] = {
                "disable_gem_attr": row.get("disableGemAttr", "") or "0",
                "phys": row.get("attackBasePhysics", "") or "-",
                "magic": row.get("attackBaseMagic", "") or "-",
                "fire": row.get("attackBaseFire", "") or "-",
                "ltng": row.get("attackBaseThunder", "") or "-",
                "holy": row.get("attackBaseDark", "") or "-",
                "status_effects": status_effects,
            }
    return stats


def build_gem_mount_map(
    flag_to_info: Dict[str, Dict[str, float]], skill_names: List[str]
) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    """Map canonical skill -> list of weapon category names + default attr."""
    mount_map: Dict[str, List[str]] = {}
    default_attr_map: Dict[str, str] = {}
    flag_order = [
        flag for flag in flag_to_info if flag.startswith(CATEGORY_FLAG_PREFIX)
    ]
    with EQUIP_PARAM_GEM_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = (row.get("Name") or "").strip()
            if not raw_name:
                continue
            clean_name = raw_name
            if clean_name.lower().startswith("ash of war:"):
                clean_name = clean_name.split(":", 1)[1].strip()
            resolved = resolve_skill_from_list(clean_name, skill_names)
            canon = resolved.lower()
            default_attr = (row.get("defaultWepAttr") or "").strip()
            mount_text_id = (row.get("mountWepTextId") or "").strip()
            if mount_text_id not in {"-1", ""}:
                default_attr_map[canon] = default_attr
            elif canon not in default_attr_map:
                default_attr_map[canon] = default_attr
            if mount_text_id == "-1" or mount_text_id == "":
                continue
            mounts: List[str] = []
            for flag in flag_order:
                if row.get(flag, "").strip() == "1":
                    mounts.append(flag_to_info[flag]["name"])
            if mounts:
                existing = mount_map.setdefault(canon, [])
                for m in mounts:
                    if m not in existing:
                        existing.append(m)
    return mount_map, default_attr_map


def load_poise_lookup() -> Dict[str, str]:
    """Map weapon name (case-insensitive) -> Base poise string."""
    lookup: Dict[str, str] = {}
    with POISE_MV_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            weapon = (row.get("Weapon") or "").strip()
            base = (row.get("Base") or "").strip()
            if not weapon:
                continue
            key = weapon.lower()
            if key not in lookup:
                lookup[key] = base
    return lookup


def fmt_poise(val: str) -> str:
    if val is None:
        return "-"
    # Preserve non-numeric composites like "60 + 60".
    try:
        num = float(val)
    except ValueError:
        return val
    text = f"{num}".rstrip("0").rstrip(".")
    return text


def align_join(values: Iterable[str], count: int) -> str:
    out: List[str] = []
    vals = list(values)
    for idx in range(count):
        val = vals[idx] if idx < len(vals) else None
        out.append(fmt_poise(val))
    return " | ".join(out).strip()


def parse_float(value: str) -> Optional[float]:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def avg_stat(values: List[str]) -> str:
    nums = [parse_float(val) for val in values]
    nums = [n for n in nums if n is not None]
    if not nums:
        return "-"
    avg = sum(nums) / len(nums)
    if avg.is_integer():
        return str(int(avg))
    text = f"{avg:.1f}"
    return text.rstrip("0").rstrip(".")


def build_rows(
    mount_map: Dict[str, List[str]],
    default_attr_map: Dict[str, str],
    attr_scaling: Dict[str, str],
    category_poise: Dict[str, float],
    poise_lookup: Dict[str, str],
    skill_names: List[str],
    weapon_base_stats: Dict[str, Dict[str, str]],
) -> Tuple[List[OrderedDict], Dict[str, List[str]]]:
    rows: List[OrderedDict] = []
    warnings: Dict[str, List[str]] = defaultdict(list)
    with ATTACK_DATA_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = (row.get("Name") or "").strip()
            if not raw_name:
                continue
            prefix = weapon_prefix(raw_name)
            if prefix and prefix in IGNORED_PREFIXES:
                prefix = ""
            unique_weapon = (row.get("Unique Skill Weapon") or "").strip()
            skill = resolve_skill_from_list(raw_name, skill_names)
            canonical = skill.lower()
            default_attr_val = default_attr_map.get(canonical, "")
            default_attr_val = (
                str(default_attr_val).strip() if default_attr_val is not None else ""
            )
            bullet_stat = attr_scaling.get(default_attr_val, "-") if default_attr_val else "-"
            fp_flag = parse_fp_flag(raw_name)
            part = infer_part(raw_name, matched_skill=skill)
            follow_up = detect_follow_up(raw_name)
            hand = detect_hand(raw_name)
            charged = detect_charged(raw_name)
            step = detect_step(raw_name)
            bullet_flag = detect_bullet(raw_name)
            tick_flag = detect_tick(raw_name)
            if bullet_flag and part == "Hit":
                part = "Bullet"

            weapon_list: List[str] = []
            poise_list: List[str] = []
            weapon_source = ""
            wep_disable_attr = (
                wep_phys
            ) = wep_magic = wep_fire = wep_ltng = wep_holy = "-"
            status_by_weapon: List[str] = []

            if unique_weapon:
                weapon_source = "unique"
                weapon_list = (
                    parse_unique_weapon_variants(unique_weapon)
                    or [unique_weapon]
                )
                disable_values: List[str] = []
                phys_values: List[str] = []
                magic_values: List[str] = []
                fire_values: List[str] = []
                ltng_values: List[str] = []
                holy_values: List[str] = []
                status_values: List[str] = []

                for weapon_name in weapon_list:
                    poise_val = poise_lookup.get(weapon_name.lower())
                    if poise_val is None:
                        for candidate in expand_weapon_names(weapon_name):
                            poise_val = poise_lookup.get(candidate.lower())
                            if poise_val is not None:
                                break
                    if poise_val is None:
                        for candidate in expand_weapon_names(weapon_name):
                            fallback = category_poise.get(candidate)
                            if fallback is not None:
                                poise_val = str(fallback)
                                warnings["unique_poise_from_category"].append(
                                    weapon_name
                                )
                                break
                    if poise_val is None:
                        warnings["missing_poise"].append(weapon_name)
                        poise_list.append(None)
                    else:
                        poise_list.append(poise_val)

                    stats = weapon_base_stats.get(weapon_name.lower())
                    if not stats:
                        status_by_weapon.append("-")
                        continue
                    disable_flag = stats.get("disable_gem_attr", "-")
                    disable_values.append(disable_flag)
                    phys_values.append(stats.get("phys", "-"))
                    magic_values.append(stats.get("magic", "-"))
                    fire_values.append(stats.get("fire", "-"))
                    ltng_values.append(stats.get("ltng", "-"))
                    holy_values.append(stats.get("holy", "-"))
                    effects = stats.get("status_effects", [])
                    per_weapon_effects: List[str] = []
                    for effect in effects:
                        if effect not in status_values:
                            status_values.append(effect)
                        if effect not in per_weapon_effects:
                            per_weapon_effects.append(effect)
                    if str(disable_flag).strip() == "1":
                        if per_weapon_effects:
                            status_by_weapon.append(" | ".join(per_weapon_effects))
                        else:
                            status_by_weapon.append("None")
                    else:
                        status_by_weapon.append("-")

                if disable_values:
                    if len(set(disable_values)) == 1:
                        wep_disable_attr = disable_values[0]
                    else:
                        wep_disable_attr = " | ".join(disable_values)
                        warnings["mixed_disable_attr"].append(unique_weapon)
                wep_phys = avg_stat(phys_values)
                wep_magic = avg_stat(magic_values)
                wep_fire = avg_stat(fire_values)
                wep_ltng = avg_stat(ltng_values)
                wep_holy = avg_stat(holy_values)
            elif prefix:
                weapon_source = "prefix"
                weapon_list = [prefix]
                poise_val = category_poise.get(prefix)
                if poise_val is None:
                    warnings["missing_prefix_poise"].append(prefix)
                    poise_list = [None]
                else:
                    poise_list = [str(poise_val)]
            else:
                categories = mount_map.get(canonical, [])
                if categories:
                    weapon_source = "category"
                    weapon_list = categories
                    for cat in categories:
                        poise_val = category_poise.get(cat)
                        if poise_val is None:
                            warnings["missing_category_poise"].append(cat)
                            poise_list.append(None)
                        else:
                            poise_list.append(str(poise_val))
                else:
                    warnings["missing_mounts"].append(skill)

            if not weapon_list:
                weapon_source = "missing"
                weapon_list = ["Unmapped"]
                poise_list = ["-"]

            weapon_field = " | ".join(weapon_list).strip()
            poise_field = (
                align_join(poise_list, len(weapon_list)) if weapon_list else ""
            )
            wep_status_field = "-"
            if weapon_source == "unique" and status_by_weapon:
                if all(val == "None" for val in status_by_weapon):
                    wep_status_field = "None"
                elif all(val == "-" for val in status_by_weapon):
                    wep_status_field = "-"
                elif len(status_by_weapon) == 1:
                    wep_status_field = status_by_weapon[0]
                else:
                    wep_status_field = " | ".join(status_by_weapon)

            out = OrderedDict()
            out["Name"] = raw_name
            out["Skill"] = skill
            out["Part"] = part
            out["Follow-up"] = follow_up
            out["Hand"] = hand
            out["FP"] = fp_flag
            out["Charged"] = charged
            out["Step"] = step
            out["Bullet"] = bullet_flag
            out["Tick"] = tick_flag
            out["Weapon Source"] = weapon_source
            out["Weapon"] = weapon_field
            out["Weapon Poise"] = poise_field
            out["Disable Gem Attr"] = wep_disable_attr
            out["Wep Phys"] = wep_phys
            out["Wep Magic"] = wep_magic
            out["Wep Fire"] = wep_fire
            out["Wep Ltng"] = wep_ltng
            out["Wep Holy"] = wep_holy
            out["Phys MV"] = row.get("Phys MV", "")
            out["Magic MV"] = row.get("Magic MV", "")
            out["Fire MV"] = row.get("Fire MV", "")
            out["Ltng MV"] = row.get("Ltng MV", "")
            out["Holy MV"] = row.get("Holy MV", "")
            out["Status MV"] = row.get("Status MV", "")
            out["Wep Status"] = wep_status_field
            out["Weapon Buff MV"] = row.get("Weapon Buff MV", "")
            out["Poise Dmg MV"] = row.get("Poise Dmg MV", "")
            out["PhysAtkAttribute"] = row.get("PhysAtkAttribute", "")
            out["AtkPhys"] = row.get("AtkPhys", "")
            out["AtkMag"] = row.get("AtkMag", "")
            out["AtkFire"] = row.get("AtkFire", "")
            out["AtkLtng"] = row.get("AtkLtng", "")
            out["AtkHoly"] = row.get("AtkHoly", "")
            out["AtkSuperArmor"] = row.get("AtkSuperArmor", "")
            out["isAddBaseAtk"] = row.get("isAddBaseAtk", "")
            out["Overwrite Scaling"] = row.get("Overwrite Scaling", "")
            out["Bullet Stat"] = bullet_stat
            out["subCategory1"] = row.get("subCategory1", "")
            out["subCategory2"] = row.get("subCategory2", "")
            out["subCategory3"] = row.get("subCategory3", "")
            out["subCategory4"] = row.get("subCategory4", "")
            rows.append(out)
    return rows, warnings


def write_csv(rows: List[OrderedDict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build AoW-data-1.csv from source CSVs."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write AoW-data-1.csv (default: docs/AoW-data-1.csv)",
    )
    args = parser.parse_args()

    skill_names = load_skill_names()
    attr_scaling = load_attr_scaling()
    flag_to_info, category_poise = load_category_flags()
    mount_map, default_attr_map = build_gem_mount_map(
        flag_to_info, skill_names
    )
    poise_lookup = load_poise_lookup()
    sp_effect_names = load_sp_effect_names()
    weapon_base_stats = load_weapon_base_stats(sp_effect_names)
    before_rows = load_rows_by_key(args.output, ["Name"])
    rows, warnings = build_rows(
        mount_map,
        default_attr_map,
        attr_scaling,
        category_poise,
        poise_lookup,
        skill_names,
        weapon_base_stats,
    )
    write_csv(rows, args.output)

    path_text = format_path_for_console(args.output, ROOT)
    print(f"Wrote {len(rows)} rows to {path_text}")
    report_row_deltas(
        before_rows=before_rows,
        after_rows=rows,
        fieldnames=OUTPUT_COLUMNS,
        key_fields=["Name"],
        align_columns=True,
    )
    if warnings:
        for kind, items in warnings.items():
            uniq = sorted(set(items))
            print(f"Warning: {kind} ({len(uniq)}) -> {', '.join(uniq)}")


if __name__ == "__main__":
    main()
