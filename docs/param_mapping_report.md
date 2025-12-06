# Parameter Mapping Guide (Skill + Spell Damage Extraction)

This document explains **exactly** how to extract every number we need for  
`work/responses/ready/skill.json` — including:

- base damage splits  
- stance damage  
- status / elemental buildup  
- buffs from SpEffect chains  
- correct behavior chains for skills and ashes  
- spell attack mapping  

This guide assumes **no DSAnimStudio**, no “GameParam.parambnd”, and no guessing.  
Everything comes from:

- exported PARAM CSVs  
- TAE behavior IDs dumped from `c0000`  
- the scripts already in our repo  

Use this instead of ad-hoc exploration.  
This is the authoritative, correct procedure.

---

## 0. Required Inputs

After exporting all params from Smithbox, place these into `PARAM/`:

```filesystem
EquipParamWeapon.csv
EquipParamGem.csv
EquipParamGoods.csv
Magic.csv
Bullet.csv
AtkParam_Pc.csv
SpEffectParam.csv
BehaviorParam_PC.csv
AttackElementCorrectParam.csv
```

Also generate a TAE behavior map:

```bash
python scripts/tae_dump_behaviors.py 
--tae-root dump/Data3bdt/chr 
--out PARAM/tae_behavior_map/behaviors.json
```

This becomes our replacement for DSAS’s “Behavior events” view.

---

## 1. The Core Graph (what points to what)

```graph
Animation (TAE) → BehaviorParam_PC → AtkParam_Pc → SpEffectParam
                                   → Bullet       → AtkParam_Pc + SpEffectParam
                                   → SpEffectParam (direct buffs)

Magic → Bullet/Atk/SpEffect (via refCategory/refId)
EquipParamWeapon/EquipParamGem → swordArtsParamId → Magic/Behavior/Atk/Bullet chain
```

Every arrow is a direct key match:  

- `Magic.refId* → Bullet.ID` or `AtkParam_Pc.ID`  
- `Bullet.atkId_Bullet → AtkParam_Pc.ID`  
- `Bullet.spEffectId* → SpEffectParam.ID`  
- `BehaviorParam_PC.refId → Atk/Bullet/SpEffect IDs`

---

## 2. Find the Skill Entry

Skills come from:  

- `EquipParamWeapon.ID` (unique skills; must check `swordArtsParamId`)  
- `EquipParamGem.ID` (Ashes of War)  

Confirm these against FMG XMLs if needed.

---

## 3. swordArtsParamId (the true root)

Read:

- `EquipParamWeapon.swordArtsParamId`  
- `EquipParamGem.swordArtsParamId`

This ID binds *everything* that follows:  
Magic rows, Bullet/Atk clusters, behaviors, and buff SpEffects.

Example: Ice Lightning Sword → `swordArtsParamId = 1043`.

---

## 4. Behavior Variation

For **unique skills**: `variationId = EquipParamWeapon.behaviorVariationId`

For **Ashes of War**: `variationId = 0`

TAE behavior events use: `BehaviorParam_PC.ID = 100000000 + variationId * 1000 + behaviorJudgeId`
`behaviorJudgeId` comes from TAE dumps (type 304 Behavior events).

---

## 5. Getting Behavior IDs (NO DSAS REQUIRED)

Use our automatic TAE dumper: `python scripts/tae_dump_behaviors.py --tae-root dump/Data3bdt/chr --out PARAM/tae_behavior_map/behaviors.json`

This file maps: `{ "<swordArtsParamId>": [<behaviorJudgeId>, <behaviorJudgeId>, ...] }`
If any behavior is missing, manually inspect the `.tae` but DSAS GUI is **not** required.

---

## 6. BehaviorParam_PC → What to Load

Open `BehaviorParam_PC.csv`.

For each behaviorJudgeId in our map AND matching variationId:

- `refType = 0` → AtkParam_Pc  
- `refType = 1` → Bullet  
- `refType = 2` → SpEffect  

Ignore rows with `refId = -1`.

This resolves *all* hits a skill performs, including melee, shockwaves, projectiles, and imbues.

---

## 7. Magic Table (shortcut when available)

Magic rows often mirror skill structure:

Filter `Magic.csv` to rows where any: `refId* begins with swordArtsParamId`
These rows give immediate entry into Bullet/Atk/SpEffect.

If Magic rows are incomplete (rare for DLC2), fall back to BehaviorParam_PC chain.

---

## 8. Bullet Resolution

Open `Bullet.csv` for each bullet ID from:

- BehaviorParam_PC.refId  
- Magic.refId*  

Bullet fields:

```map
atkId_Bullet → AtkParam_Pc
spEffectId0–4 → buff/status SpEffects
HitBulletID → chained bullets (lingers, clouds, explosions)
```

Drop bullets when:

- `atkAttribute = 254` (dummy)  
- all damage splits are zero  
- range/life values indicate VFX with no gameplay effect  

---

## 9. AtkParam_Pc (damage + stance)

Open `AtkParam_Pc.csv`.

Columns:

```map
atkPhys, atkMag, atkFire, atkThun, atkDark
atkStam        (stance damage)
atkAttribute   (254 = ignore)
```

Pick all non-dummy rows.

These numbers fill the “base phys/mag/fire/etc” and “stance damage per hit”.

---

## 10. SpEffectParam (buffs + statuses)

Open `SpEffectParam.csv`.

These fields matter:

### Status buildup

```map
freezeAttackPower
poizonAttackPower
bloodAttackPower
sleepAttackPower
madnessAttackPower
```

### Elemental buffs

```map
<element>AttackPower <element>AttackRate
effectEndurance (duration)
```

Follow chains:

- from `Bullet.spEffectId*`  
- from `Magic.refCategory=2`  
- from `SpEffectParam.replaceSpEffectId`  
- from `SpEffectParam.cycleOccurrenceSpEffectId`  

This yields everything like:

- added lightning damage  
- added frostbite buildup  
- buff duration  
- self-buffs applied on weapon activation  

---

## 11. Scaling (“fire damage scales with …”)

Use **AttackElementCorrectParam.csv**.

1. From `EquipParamWeapon.attackElementCorrectId`  
2. Open the corresponding row in `AttackElementCorrectParam.csv`  

Flags show which stats contribute to each element:

Examples:

```map
Physical: STR + DEX
Magic: INT
Fire: FTH
Lightning: DEX
Holy: FTH
```

Convert this directly into text like:

> “fire damage scales with faith; physical damage scales with strength and dexterity.”

Spells have analogous mappings through their scaling fields → same table.

---

## 12. Driving Everything With Our Script Suite

### 12.1 Build behavior map

```bash
python scripts/tae_dump_behaviors.py \
  --tae-root dump/Data3bdt/chr \
  --out PARAM/tae_behavior_map/behaviors.json
```

### 12.2 Full skill dump

```bash
python scripts/skill_dump.py \
  --skills work/responses/ready/skill.json \
  --behavior-map PARAM/tae_behavior_map/behaviors.json \
  --out work/skill_dump.json
```

This produces structured records for **every hit**, with:

- bullets used  
- atk rows  
- stance  
- spEffects  
- scaling IDs  
- per-hit damage  

Agents should ALWAYS read off values from `work/skill_dump.json` once generated.

---

## 13. Worked Example (Ice Lightning Sword, 1043)

1. `swordArtsParamId = 1043`  
2. Behavior IDs from TAE → e.g. `[430, 436, 439, …]`  
3. Each → BehaviorParam_PC row → Bullet / Atk / SpEffect chain  
4. Bullet `10430000` → `atkId_Bullet = 43000` (main bolt)  
5. Bullet `10439000` → `atkId_Bullet = 43900` (shockwave)  
6. Buff SpEffects found via bullets:  
   - `effectEndurance = 45`  
   - `thunderAttackPower = 160`  
   - `freezeAttackPower = 80`  
7. Scaling from AttackElementCorrectParam gives the “… scales with …” line.  

Everything matches in-game behavior.

---

## 14. Rules for Agents (must follow)

1. **Never** look for “GameParam.parambnd” or “GameParam” bundles — Elden Ring’s regulation.bin exports as loose params.  
2. Use only:  
   - the PARAM CSVs in `PARAM/`  
   - the TAE behavior map  
   - the python scripts in this repo
3. Always follow the graph:  

    ```graph
    Behavior → Bullet → Atk → SpEffect
    Magic → Bullet/Atk/SpEffect
    ```

4. Always drop dummy hits.  
5. Scaling always comes from AttackElementCorrectParam.  
6. Final numbers must come from `work/skill_dump.json` after running the scripts.  
7. If any mapping is missing: regenerate behavior map or inspect `.tae` for missing Behavior IDs.

---

## 15. Output Targets

Agents should be able to produce, per skill/spell:

- base damage splits per hit  
- stance damage per hit  
- all statuses (frost, bleed, etc.)  
- self-buffs and their durations  
- elemental additions  
- scaling text (“X scales with Y”)  
- any chained hits (burst → shockwave → lingering field, etc.)

All with NO DSAS, NO extra tooling, and NO guesswork.
