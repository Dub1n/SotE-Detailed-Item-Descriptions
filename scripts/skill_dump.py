#!/usr/bin/env python3
"""
Aggregate skill data into a JSON bundle for quick jq lookups.

Pulls:
- swordArtsParamId + behaviorVariationId (from EquipParamWeapon/EquipParamGem)
- Magic → Bullet/Atk/SpEffect chains (by swordArtsParamId prefix)
- Optional BehaviorParam_PC → Bullet/Atk/SpEffect if a behavior ID list is provided per skill.

Usage:
  python scripts/skill_dump.py --skills work/responses/ready/skill.json --out work/skill_dump.json
  python scripts/skill_dump.py --skills work/responses/ready/skill.json --behavior-map configs/behavior_ids.json --out work/skill_dump.json

`behavior_ids.json` format:
{
  "1043": [430, 440],
  "214": [900]
}
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

PARAM_DIR = Path("PARAM")


def load_csv(path: Path) -> List[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def index_by_id(rows: Iterable[dict]) -> Dict[str, dict]:
    return {row["ID"]: row for row in rows}


def gather_sp_effects(row: dict) -> List[str]:
    ids: List[str] = []
    for key in ("spEffectId0", "spEffectId1", "spEffectId2", "spEffectId3", "spEffectId4"):
        val = row.get(key)
        if val and val not in ("-1", "0"):
            ids.append(val)
    return ids


def describe_atk(row: dict) -> dict:
    return {
        "id": row.get("ID"),
        "phys": row.get("atkPhys"),
        "mag": row.get("atkMag"),
        "fire": row.get("atkFire"),
        "thun": row.get("atkThun"),
        "dark": row.get("atkDark"),
        "stance": row.get("atkStam"),
        "attr": row.get("atkAttribute"),
        "type": row.get("atkType"),
    }


def trace_bullet(bullet: dict, atk_rows: Dict[str, dict], spe_rows: Dict[str, dict]) -> dict:
    spe_ids = gather_sp_effects(bullet)
    atk = atk_rows.get(bullet.get("atkId_Bullet"))
    return {
        "id": bullet.get("ID"),
        "life": bullet.get("life"),
        "dist": bullet.get("dist"),
        "hitBullet": bullet.get("HitBulletID"),
        "atkId": bullet.get("atkId_Bullet"),
        "atk": describe_atk(atk) if atk else None,
        "spEffects": [
            {"id": sid, "data": spe_rows.get(sid)} for sid in spe_ids if spe_rows.get(sid) is not None
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump per-skill data (Magic + optional BehaviorParam_PC) to JSON.")
    parser.add_argument("--skills", default=Path("work/responses/ready/skill.json"), type=Path, help="Path to skill.json")
    parser.add_argument("--param-dir", default=PARAM_DIR, type=Path, help="Path to PARAM directory")
    parser.add_argument("--behavior-map", type=Path, help="JSON file mapping skill_id -> [behaviorJudgeId, ...]")
    parser.add_argument("--out", default=Path("work/skill_dump.json"), type=Path, help="Output JSON path")
    args = parser.parse_args()

    param_dir: Path = args.param_dir
    magic_rows = load_csv(param_dir / "Magic.csv")
    bullet_rows = index_by_id(load_csv(param_dir / "Bullet.csv"))
    atk_rows = index_by_id(load_csv(param_dir / "AtkParam_Pc.csv"))
    spe_rows = index_by_id(load_csv(param_dir / "SpEffectParam.csv"))
    behavior_rows = load_csv(param_dir / "BehaviorParam_PC.csv")
    equip_weapon_rows = load_csv(param_dir / "EquipParamWeapon.csv")
    equip_gem_rows = load_csv(param_dir / "EquipParamGem.csv")

    behavior_map = {}
    if args.behavior_map and args.behavior_map.exists():
        behavior_map = json.loads(args.behavior_map.read_text())

    skills = json.loads(args.skills.read_text())

    def derive_swordarts_and_variation(skill_id: str) -> Tuple[str, str]:
        for row in equip_gem_rows:
            if row["ID"] == skill_id:
                return row.get("swordArtsParamId", skill_id), "0"
        for row in equip_weapon_rows:
            if row.get("ID") == skill_id or row.get("swordArtsParamId") == skill_id:
                return row.get("swordArtsParamId", skill_id), row.get("behaviorVariationId") or "0"
        return skill_id, "0"

    def magic_hits(sid_prefix: str) -> List[dict]:
        hits: List[dict] = []
        for row in magic_rows:
            for i in range(1, 11):
                rid = row.get(f"refId{i}")
                if not rid or rid == "-1" or not rid.startswith(sid_prefix):
                    continue
                cat = row.get(f"refCategory{i}")
                hit = {"magicId": row.get("ID"), "ref": rid, "refCategory": cat}
                if cat == "0":  # AtkParam
                    atk = atk_rows.get(rid)
                    if atk:
                        hit["atk"] = describe_atk(atk)
                elif cat == "1":  # Bullet
                    bullet = bullet_rows.get(rid)
                    if bullet:
                        hit["bullet"] = trace_bullet(bullet, atk_rows, spe_rows)
                elif cat == "2":  # SpEffectParam
                    spe = spe_rows.get(rid)
                    if spe:
                        hit["spEffect"] = {"id": rid, "data": spe}
                hits.append(hit)
        return hits

    def behavior_hits(skill_id: str, variation_id: str, judge_ids: List[int]) -> List[dict]:
        if not judge_ids:
            return []
        judge_set = {str(j) for j in judge_ids}
        matches = [
            row
            for row in behavior_rows
            if row["variationId"] == variation_id and row["behaviorJudgeId"] in judge_set and row.get("refId") not in (None, "-1")
        ]
        out: List[dict] = []
        for row in matches:
            ref_type = row.get("refType")
            ref_id = row.get("refId")
            entry = {
                "behaviorParamPcId": row.get("ID"),
                "judge": row.get("behaviorJudgeId"),
                "refType": ref_type,
                "refId": ref_id,
            }
            if ref_type == "0":  # AtkParam_Pc
                atk = atk_rows.get(ref_id)
                if atk:
                    entry["atk"] = describe_atk(atk)
            elif ref_type == "1":  # Bullet
                bullet = bullet_rows.get(ref_id)
                if bullet:
                    entry["bullet"] = trace_bullet(bullet, atk_rows, spe_rows)
            elif ref_type == "2":  # SpEffectParam
                spe = spe_rows.get(ref_id)
                if spe:
                    entry["spEffect"] = {"id": ref_id, "data": spe}
            out.append(entry)
        return out

    dump: List[dict] = []
    for item in skills:
        sid = str(item.get("id"))
        name = item.get("name")
        swordarts, variation = derive_swordarts_and_variation(sid)
        beh_ids = behavior_map.get(sid, [])
        dump.append(
            {
                "id": sid,
                "name": name,
                "swordArtsParamId": swordarts,
                "behaviorVariationId": variation,
                "magic": magic_hits(swordarts),
                "behavior": behavior_hits(sid, variation, beh_ids),
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dump, indent=2), encoding="utf-8")
    print(f"Wrote {args.out} for {len(dump)} skills (behavior hits only where provided in --behavior-map).")


if __name__ == "__main__":
    main()
