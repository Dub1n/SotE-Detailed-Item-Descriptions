#!/usr/bin/env python3
"""
Quick helper to follow BehaviorParam_PC rows into Bullet / AtkParam_Pc / SpEffectParam,
and (optionally) to walk the Magic → Bullet → Atk/SpEffect chain for a skill ID.

Usage:
  python scripts/behavior_lookup.py --variation 0 --judge 430
  python scripts/behavior_lookup.py --variation 3100 --judge 430 440
  python scripts/behavior_lookup.py --skill 1043 --judge 430
  python scripts/behavior_lookup.py --skill 1043  # Magic-only trace, if you do not have TAE behavior IDs yet
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

PARAM_DIR = Path("PARAM")


def load_csv(path: Path) -> List[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def index_by_id(rows: Iterable[dict]) -> Dict[str, dict]:
    return {row["ID"]: row for row in rows}


def describe_atk(row: dict) -> str:
    parts = [
        f"phys {row.get('atkPhys')}",
        f"mag {row.get('atkMag')}",
        f"fire {row.get('atkFire')}",
        f"thun {row.get('atkThun')}",
        f"dark {row.get('atkDark')}",
        f"stance {row.get('atkStam')}",
        f"attr {row.get('atkAttribute')}",
        f"type {row.get('atkType')}",
    ]
    return ", ".join(parts)


def describe_spe(row: dict) -> str:
    parts = []
    for key in ("effectEndurance", "hpRecoverRate", "hpRecoverPower", "staminaRecoverRate"):
        val = row.get(key)
        if val and val != "-1":
            parts.append(f"{key}={val}")
    for key in ("poizonAttackPower", "diseaseAttackPower", "bloodAttackPower", "freezeAttackPower", "sleepAttackPower", "madnessAttackPower", "darkAttackPower", "fireAttackPower", "thunderAttackPower", "magicAttackPower", "physicsAttackPower"):
        val = row.get(key)
        if val and val != "-1" and val != "0":
            parts.append(f"{key}={val}")
    return ", ".join(parts) if parts else "no obvious stats"


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace BehaviorParam_PC -> Bullet/Atk/SpEffect (plus Magic shortcut if skill is known)")
    parser.add_argument("--variation", type=int, default=None, help="behaviorVariationId (EquipParamWeapon.behaviorVariationId or 0 for Ashes)")
    parser.add_argument("--judge", "--behavior", dest="judges", type=int, nargs="+", help="behaviorJudgeId values from TAE")
    parser.add_argument("--skill", type=int, help="Skill ID from work/responses/ready/skill.json (auto: find swordArtsParamId and variation)")
    parser.add_argument("--param-dir", default=PARAM_DIR, type=Path, help="Path to PARAM directory")
    args = parser.parse_args()

    param_dir: Path = args.param_dir
    behavior_rows = load_csv(param_dir / "BehaviorParam_PC.csv")
    bullet_rows = index_by_id(load_csv(param_dir / "Bullet.csv"))
    atk_rows = index_by_id(load_csv(param_dir / "AtkParam_Pc.csv"))
    spe_rows = index_by_id(load_csv(param_dir / "SpEffectParam.csv"))
    magic_rows = load_csv(param_dir / "Magic.csv")
    equip_weapon_rows = load_csv(param_dir / "EquipParamWeapon.csv")
    equip_gem_rows = load_csv(param_dir / "EquipParamGem.csv")

    sword_arts_id: str | None = None
    variation = str(args.variation) if args.variation is not None else None

    def derive_from_skill(skill_id: int) -> Tuple[str | None, str | None]:
        sid = str(skill_id)
        # Ashes: EquipParamGem.ID == skill, swordArtsParamId points to the behaviors
        for row in equip_gem_rows:
            if row["ID"] == sid:
                return row.get("swordArtsParamId", sid), "0"
        # Unique weapons: either swordArtsParamId matches skill, or ID matches skill text ID
        for row in equip_weapon_rows:
            if row.get("swordArtsParamId") == sid or row.get("ID") == sid:
                return row.get("swordArtsParamId", sid), row.get("behaviorVariationId") or None
        return sid, None

    if args.skill is not None:
        sword_arts_id, derived_var = derive_from_skill(args.skill)
        if variation is None:
            variation = derived_var or "0"
        print(f"[skill] ID {args.skill} -> swordArtsParamId {sword_arts_id} (variation {variation or 'unknown'})")
    else:
        sword_arts_id = None

    def gather_sp_effects(row: dict) -> List[str]:
        ids: List[str] = []
        for key in ("spEffectId0", "spEffectId1", "spEffectId2", "spEffectId3", "spEffectId4"):
            val = row.get(key)
            if val and val not in ("-1", "0"):
                ids.append(val)
        return ids

    def trace_behavior(judges: List[int], variation_id: str) -> None:
        judge_set = {str(j) for j in judges}
        matches = [
            row
            for row in behavior_rows
            if row["variationId"] == variation_id and row["behaviorJudgeId"] in judge_set and row.get("refId") not in (None, "-1")
        ]
        if not matches:
            print("No BehaviorParam_PC rows found for variation", variation_id, "judge", sorted(judge_set))
            return

        ref_type_label = {"0": "AtkParam_Pc", "1": "Bullet", "2": "SpEffectParam"}

        for row in sorted(matches, key=lambda r: int(r["ID"])):
            ref_type = row.get("refType", "")
            ref_id = row.get("refId")
            label = ref_type_label.get(ref_type, "unknown")
            print(f"BehaviorParam_PC ID {row['ID']} (var={row['variationId']}, judge={row['behaviorJudgeId']}, refType={ref_type} -> {label}, ezState={row.get('ezStateBehaviorType_old')})")

            if label == "AtkParam_Pc":
                atk = atk_rows.get(ref_id)
                if atk:
                    print(f"  AtkParam_Pc {ref_id}: {describe_atk(atk)}")
                else:
                    print(f"  AtkParam_Pc {ref_id}: not found")

            elif label == "Bullet":
                bullet = bullet_rows.get(ref_id)
                if not bullet:
                    print(f"  Bullet {ref_id}: not found")
                else:
                    spe_ids = gather_sp_effects(bullet)
                    print(f"  Bullet {ref_id}: atkId_Bullet={bullet.get('atkId_Bullet')} hitBullet={bullet.get('HitBulletID')} life={bullet.get('life')} dist={bullet.get('dist')} spEffects={spe_ids or 'none'}")
                    atk = atk_rows.get(bullet.get("atkId_Bullet"))
                    if atk:
                        print(f"    AtkParam_Pc {bullet['atkId_Bullet']}: {describe_atk(atk)}")
                    for sid in spe_ids:
                        spe = spe_rows.get(sid)
                        if spe:
                            print(f"    SpEffectParam {sid}: {describe_spe(spe)}")

            elif label == "SpEffectParam":
                spe = spe_rows.get(ref_id)
                if spe:
                    print(f"  SpEffectParam {ref_id}: {describe_spe(spe)}")
                else:
                    print(f"  SpEffectParam {ref_id}: not found")

            else:
                print(f"  Unknown refType {ref_type} with refId {ref_id}")

    def trace_magic(prefix: str) -> None:
        ref_label = { "0": "AtkParam_Pc", "1": "Bullet", "2": "SpEffectParam" }
        hits = []
        for row in magic_rows:
            for i in range(1, 11):
                rid = row.get(f"refId{i}")
                if rid and rid != "-1" and rid.startswith(prefix):
                    hits.append((row, i, rid, row.get(f"refCategory{i}")))
        if not hits:
            print(f"No Magic rows found with refId* starting {prefix}")
            return
        print(f"Magic rows for swordArtsParamId prefix {prefix}:")
        for row, idx, rid, cat in hits:
            label = ref_label.get(cat, "?")
            print(f" Magic {row['ID']} ref{idx} -> {label} {rid}")
            if label == "AtkParam_Pc":
                atk = atk_rows.get(rid)
                if atk:
                    print(f"   AtkParam_Pc {rid}: {describe_atk(atk)}")
            elif label == "Bullet":
                bullet = bullet_rows.get(rid)
                if bullet:
                    spe_ids = gather_sp_effects(bullet)
                    print(f"   Bullet {rid}: atkId_Bullet={bullet.get('atkId_Bullet')} hitBullet={bullet.get('HitBulletID')} life={bullet.get('life')} dist={bullet.get('dist')} spEffects={spe_ids or 'none'}")
                    atk = atk_rows.get(bullet.get("atkId_Bullet"))
                    if atk:
                        print(f"     AtkParam_Pc {bullet['atkId_Bullet']}: {describe_atk(atk)}")
                    for sid in spe_ids:
                        spe = spe_rows.get(sid)
                        if spe:
                            print(f"     SpEffectParam {sid}: {describe_spe(spe)}")
            elif label == "SpEffectParam":
                spe = spe_rows.get(rid)
                if spe:
                    print(f"   SpEffectParam {rid}: {describe_spe(spe)}")

    if sword_arts_id:
        trace_magic(sword_arts_id)

    if args.judges:
        if variation is None:
            print("Variation unknown; pass --variation explicitly to trace BehaviorParam_PC.")
        else:
            trace_behavior(args.judges, variation)
    elif not args.skill:
        parser.error("Either --skill (for Magic trace) or --judge/--behavior + --variation is required.")


if __name__ == "__main__":
    main()
