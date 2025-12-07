import argparse
import csv
import json
import re
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Optional


ROOT = Path(__file__).resolve().parent.parent
ATTACK_DATA_CSV = ROOT / "docs/(1.16.1)-Ashes-of-War-Attack-Data.csv"
POISE_MV_CSV = ROOT / "docs/(1.16.1)-Poise-Damage-MVs.csv"
EQUIP_PARAM_GEM_CSV = ROOT / "PARAM/EquipParamGem.csv"
CATEGORY_POISE_JSON = ROOT / "docs/weapon_categories_poise.json"
SKILL_LIST_TXT = ROOT / "docs/skill_names_from_gem_and_behavior.txt"
DEFAULT_OUTPUT = ROOT / "work/aow_pipeline/AoW-data-1.csv"

IGNORED_PREFIXES = {"Slow", "Var1", "Var2"}

CATEGORY_FLAG_PREFIX = "canMountWep_"
OUTPUT_COLUMNS = [
    "Skill",
    "Weapon",
    "Weapon Poise",
    "Weapon Source",
    "FP",
    "Charged",
    "Part",
    "Follow-up",
    "Hand",
    "Step",
    "Bullet",
    "Name",
    "AtkId",
    "Phys MV",
    "Magic MV",
    "Fire MV",
    "Ltng MV",
    "Holy MV",
    "Status MV",
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
    "overwriteAttackElementCorrectId",
    "Overwrite Scaling",
    "subCategory1",
    "subCategory2",
    "subCategory3",
    "subCategory4",
    "spEffectId0",
    "spEffectId1",
    "spEffectId2",
    "spEffectId3",
    "spEffectId4",
]


def load_category_flags() -> Tuple[Dict[str, Dict[str, float]], Dict[str, float]]:
    data = json.loads(CATEGORY_POISE_JSON.read_text())
    flag_to_info: Dict[str, Dict[str, float]] = {}
    name_to_poise: Dict[str, float] = {}
    for flag, payload in data.items():
        name = payload["name"]
        poise_val = payload["poise"]
        flag_to_info[flag] = {"name": name, "poise": poise_val}
        name_to_poise[name] = poise_val
    return flag_to_info, name_to_poise


def base_skill_name(name: str) -> str:
    text = strip_weapon_prefix(name)
    text = text.replace("(Lacking FP)", "")
    text = re.sub(r"\([^)]*\)", "", text)  # drop parenthetical suffixes
    text = re.sub(r"#\d+", "", text)
    text = re.sub(r"\bR[12]\b", "", text)
    text = re.sub(r"\b(1h|2h)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bCharged\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bBullet\b", "", text, flags=re.IGNORECASE)
    text = text.strip()
    text = re.split(r"\s*-\s*", text, 1)[0].strip()
    text = re.split(r"\s*\[", text)[0].strip()
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def load_skill_names() -> List[str]:
    if not SKILL_LIST_TXT.exists():
        return []
    names = [line.strip() for line in SKILL_LIST_TXT.read_text().splitlines() if line.strip()]
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
        base = re.sub(rf"(?i)\b{re.escape(matched_skill)}\b", "", base, count=1)
    base = re.sub(r"\(Lacking FP\)", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\b(1h|2h)\b", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\bCharged\b", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\bBullet\b", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\bR[12]\b", "", base)
    base = re.sub(r"#\d+", "", base)
    base = re.sub(r"\[\s*\d+\s*\]", "", base)
    # Trim leading " - " if present
    base = base.split(" - ", 1)[1] if " - " in base else base
    base = base.strip(" -:\t")
    if base.startswith("(") and base.endswith(")") and len(base) > 1:
        base = base[1:-1].strip()
    base = re.sub(r"\s{2,}", " ", base).strip()
    if not base:
        return "Loop" if "Loop" in name else "Main"
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
        suffix = text[closing + 1 :].strip()
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


def build_gem_mount_map(flag_to_info: Dict[str, Dict[str, float]], skill_names: List[str]) -> Dict[str, List[str]]:
    """Map canonical skill -> list of weapon category names."""
    mount_map: Dict[str, List[str]] = {}
    flag_order = [flag for flag in flag_to_info if flag.startswith(CATEGORY_FLAG_PREFIX)]
    with EQUIP_PARAM_GEM_CSV.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = (row.get("Name") or "").strip()
            if not raw_name:
                continue
            mount_text_id = (row.get("mountWepTextId") or "").strip()
            if mount_text_id == "-1" or mount_text_id == "":
                continue
            clean_name = raw_name
            if clean_name.lower().startswith("ash of war:"):
                clean_name = clean_name.split(":", 1)[1].strip()
            resolved = resolve_skill_from_list(clean_name, skill_names)
            canon = resolved.lower()
            mounts: List[str] = []
            for flag in flag_order:
                if row.get(flag, "").strip() == "1":
                    mounts.append(flag_to_info[flag]["name"])
            if mounts:
                existing = mount_map.setdefault(canon, [])
                for m in mounts:
                    if m not in existing:
                        existing.append(m)
    return mount_map


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
    return " ".join(out).strip()


def build_rows(
    mount_map: Dict[str, List[str]],
    category_poise: Dict[str, float],
    poise_lookup: Dict[str, str],
    skill_names: List[str],
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
            fp_flag = parse_fp_flag(raw_name)
            part = infer_part(raw_name, matched_skill=skill)
            follow_up = detect_follow_up(raw_name)
            hand = detect_hand(raw_name)
            charged = detect_charged(raw_name)
            step = detect_step(raw_name)
            bullet_flag = detect_bullet(raw_name)

            weapon_list: List[str] = []
            poise_list: List[str] = []
            weapon_source = ""

            if unique_weapon:
                weapon_source = "unique"
                weapon_list = [unique_weapon]
                poise_val = poise_lookup.get(unique_weapon.lower())
                if poise_val is None:
                    for candidate in expand_weapon_names(unique_weapon):
                        poise_val = poise_lookup.get(candidate.lower())
                        if poise_val is not None:
                            break
                if poise_val is None:
                    for candidate in expand_weapon_names(unique_weapon):
                        fallback = category_poise.get(candidate)
                        if fallback is not None:
                            poise_val = str(fallback)
                            warnings["unique_poise_from_category"].append(unique_weapon)
                            break
                if poise_val is None:
                    warnings["missing_poise"].append(unique_weapon)
                    poise_list = [None]
                else:
                    poise_list = [poise_val]
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

            weapon_field = " ".join(weapon_list).strip()
            poise_field = align_join(poise_list, len(weapon_list)) if weapon_list else ""

            out = OrderedDict()
            out["Skill"] = skill
            out["Weapon"] = weapon_field
            out["Weapon Poise"] = poise_field
            out["Weapon Source"] = weapon_source
            out["FP"] = fp_flag
            out["Charged"] = charged
            out["Part"] = part
            out["Follow-up"] = follow_up
            out["Hand"] = hand
            out["Step"] = step
            out["Bullet"] = bullet_flag
            out["Name"] = raw_name
            out["AtkId"] = row.get("AtkId", "")
            out["Phys MV"] = row.get("Phys MV", "")
            out["Magic MV"] = row.get("Magic MV", "")
            out["Fire MV"] = row.get("Fire MV", "")
            out["Ltng MV"] = row.get("Ltng MV", "")
            out["Holy MV"] = row.get("Holy MV", "")
            out["Status MV"] = row.get("Status MV", "")
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
            out["overwriteAttackElementCorrectId"] = row.get("overwriteAttackElementCorrectId", "")
            out["Overwrite Scaling"] = row.get("Overwrite Scaling", "")
            out["subCategory1"] = row.get("subCategory1", "")
            out["subCategory2"] = row.get("subCategory2", "")
            out["subCategory3"] = row.get("subCategory3", "")
            out["subCategory4"] = row.get("subCategory4", "")
            out["spEffectId0"] = row.get("spEffectId0", "")
            out["spEffectId1"] = row.get("spEffectId1", "")
            out["spEffectId2"] = row.get("spEffectId2", "")
            out["spEffectId3"] = row.get("spEffectId3", "")
            out["spEffectId4"] = row.get("spEffectId4", "")
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
    parser = argparse.ArgumentParser(description="Build AoW-data-1.csv from source CSVs.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to write AoW-data-1.csv (default: docs/AoW-data-1.csv)",
    )
    args = parser.parse_args()

    skill_names = load_skill_names()
    flag_to_info, category_poise = load_category_flags()
    mount_map = build_gem_mount_map(flag_to_info, skill_names)
    poise_lookup = load_poise_lookup()
    rows, warnings = build_rows(mount_map, category_poise, poise_lookup, skill_names)
    write_csv(rows, args.output)

    print(f"Wrote {len(rows)} rows to {args.output}")
    if warnings:
        for kind, items in warnings.items():
            uniq = sorted(set(items))
            print(f"Warning: {kind} ({len(uniq)}) -> {', '.join(uniq)}")


if __name__ == "__main__":
    main()
