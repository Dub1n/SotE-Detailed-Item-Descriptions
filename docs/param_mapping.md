## Param Mapping Playbook

The goal is to turn each skill entry in `work/responses/ready/skill.json` into a set of base damage, stance, and status values pulled straight from the PARAM CSVs. The data we need is spread across `EquipParam*`, `Magic`, `Bullet`, `AtkParam_Pc`, and `SpEffectParam`, plus the message XMLs when we need to confirm IDs.

### Global orientation (what points to what)

All of the numbers we care about sit on this graph. It helps to keep the join keys in mind before diving in:

```
Animation (TAE) ──> BehaviorParam[_PC] ──┬──> AtkParam_Pc ──> SpEffectParam (on-hit)
                                         ├──> Bullet ──────> AtkParam_Pc + SpEffectParam
                                         └──> SpEffectParam (pure buffs)

Magic ──────────────┬──> BehaviorParam (behaviorId)
                    └──> Atk/Bullet/SpEffect (refId + refCategory)

EquipParamWeapon ───┬──> BehaviorParam (behaviorVariationId + TAE)
                    ├──> SwordArtsParam (swordArtsParamId)
                    └──> SpEffectParam (resident/on-hit)

EquipParamGem ──────└──> SwordArtsParam (swordArtsParamId)

EquipParamGoods ────┬──> BehaviorParam (behaviorId)
                    └──> Atk/Bullet/SpEffect (ref fields)

Armor / Talismans ──└──> SpEffectParam
```

Every arrow is an equality join on an ID field (e.g., `Magic.refId → Bullet.ID`, `Bullet.atkId_Bullet → AtkParam_Pc.ID`, `Bullet.spEffectId0 → SpEffectParam.ID`, and so on).

**Big caveat:** Sorceries and incantations really do funnel through `Magic → Behavior → Bullet/Atk/SpEffect`, but skills/Ashes of War are ultimately driven by `SwordArtsParam + TAE + BehaviorParam_PC`. The `Magic` table happens to contain “shadow” rows whose `refId*` share the sword arts’ prefixes (which is why our `1043xxxx` trick works), yet FromSoftware’s actual execution path relies on animation events. If we ever run into a skill where the Magic shortcut fails, the fallback is to use a precomputed map `skill_id, variation_id → [BehaviorParam_PC IDs]` built from the TAEs (exactly what modders do in DSAnimStudio/DSMapStudio). Keep that limitation in mind before trusting an automated extraction for a brand-new DLC skill.

### 1. Start from the skill ID and confirm the text row

1. Skill IDs in `skill.json` match:
   - The `ID` column in `PARAM/EquipParamGem.csv` for Ashes of War.
   - The `ID` column in `PARAM/EquipParamWeapon.csv` for weapons with unique skills (`ID` equals the FMG text ID, which you can verify in `vanilla/item-msgbnd-dcx/SkillName.fmg.xml` or `WeaponName.fmg.xml`).  
     Example: `Dragonscale Blade` has text ID `9070000`, and the matching `EquipParamWeapon` row also uses `ID=9070000`.
2. Use the FMG XMLs (either `vanilla/...` or `mod/msg/engus/item_dlc01-msgbnd-dcx/...`) when you need to confirm that an item/skill name is tied to the ID you are about to touch. The XMLs let you double-check that a number coming from `fex_cache` is still correct in the bundled data.

### 2. Resolve the sword arts pointer

1. Read the `swordArtsParamId` column:
   - On Ashes this value usually equals the skill `ID`.
   - On unique skills, `EquipParamWeapon.swordArtsParamId` points to the correct skill even if the weapon has multiple innate behaviors.
2. A Dragonscale Blade modder on Nexus noted they had to move `EquipParamWeapon.swordArtsParamId` along with the `BehaviorParam_Pc`, `Bullet`, `SpEffectParam`, and `AtkParam_Pc` rows when porting the move-set, so treat this as the “key” that ties all the downstream tables together (DuckDuckGo search for `"swordArtsParamId"`, Nexus, Feb 2025).
3. **TAE caveat:** Everything downstream of `swordArtsParamId` depends on which animation events fire during the skill. When the `Magic` table exposes clean `refId` prefixes (as it does for 1.10 skills), we can stay inside CSV-land. If it doesn’t, you must fall back to a prebuilt behavior map from TAE: `BehaviorParam_PC ID = 30 | variation_id | behaviorJudgeId`. Unique skills use their weapon’s `behaviorVariationId`; transferrable Ashes typically use `variation_id = 0`. Without that map you cannot find every Atk/Bullet row a skill triggers.

### 2.5 When Magic is incomplete: go straight through BehaviorParam_PC

- We now ship `PARAM/BehaviorParam_PC.csv` (DSMS portable export). It only contains the essentials: `variationId`, `behaviorJudgeId`, `ezStateBehaviorType_old`, `refType`, and `refId`. There is no `isAddBaseAtk`/`isAttackSFX` flag in the Atk CSVs, so lean on `atkAttribute` (254 = dummy/helper) and sensible damage splits when filtering.
- Keys to find the right behavior row:
  - `variationId` = `EquipParamWeapon.behaviorVariationId` for unique skills, or `0` for Ashes of War/gems. (`rg -n ",<skill id>," PARAM/EquipParamWeapon.csv` is the fastest way to confirm a weapon’s variation.)
  - `behaviorJudgeId` comes from the TAE event for the skill (DSAnimStudio → Behavior event → Behavior ID column).
  - The player block lives in the `100000000 + variationId * 1000 + behaviorJudgeId` ID band. DSMapStudio also exports parallel `300...` and `700...` bands; start with the `100...` rows unless you know the animation calls one of the others.
- `refType` tells you which table to open next: `0 = AtkParam_Pc`, `1 = Bullet`, `2 = SpEffectParam`. The `refId` is the lookup key. Ignore rows with `refId = -1`.
- Once you have the Atk or Bullet IDs:
  - Atk rows expose the base splits directly: `atkPhys/atkMag/atkFire/atkThun/atkDark` and `atkStam` (stance). Drop rows with `atkAttribute = 254` as VFX/dummy hits.
  - Bullet rows give you `atkId_Bullet` (then open `AtkParam_Pc.csv`) plus `spEffectId0-4` and `HitBulletID` chains for buffs/secondary hits.
- Helper script: `python scripts/behavior_lookup.py --variation 0 --judge 430` will print the matching BehaviorParam_PC rows and follow them into Bullet/Atk/SpEffect. Swap `--variation` to the weapon’s `behaviorVariationId` and pass every Behavior ID you see in the TAE for that skill. `--skill <id>` adds a Magic trace (and auto-fills variation for uniques); still supply `--judge` once you have the TAE behavior IDs.
- TAE dump helper: `python scripts/tae_dump_behaviors.py --tae-root /path/to/unpacked/chr --out PARAM/tae_behavior_map/behaviors.json` walks every `.tae` under an unpacked `chr/` (e.g., `.../c0000-anibnd/GR/data/INTERROOT_win64/chr/c0000/tae/`) and records Behavior events (type 304 / BehaviorListID). The output is stored in `PARAM/tae_behavior_map/behaviors.json`. If a behavior ID you need is missing, open the matching `.tae` in DSAnimStudio and grab the Behavior ID manually, then feed it to `behavior_lookup.py`.
- Bulk export helper: `python scripts/skill_dump.py --skills work/responses/ready/skill.json --out work/skill_dump.json` emits a JSON bundle per skill with swordArtsParamId, behaviorVariationId, and all Magic → Bullet/Atk/SpEffect hits (by refId prefix). If you have per-skill behavior IDs from TAE, pass `--behavior-map my_behavior_ids.json` (mapping `skill_id -> [behaviorJudgeId,...]`) to include BehaviorParam_PC → Atk/Bullet/SpEffect chains in the dump. This lets you `jq` the numbers instead of running the per-skill helper repeatedly.
- This is the path to unblock the “need BehaviorParam_PC map” notes in `work/responses/ready/skill.json`: pull the Behavior IDs from the TAE, run the helper, and surface the Atk/Bullet/SpEffect values it reports instead of trusting the shadow `Magic` rows.

### 3. Walk Magic → Bullet → AtkParam (with SpEffect detours)

1. `PARAM/Magic.csv` is the bridge from a skill to the data it spawns:
   - Filter to rows where any `refId*` begins with the `swordArtsParamId`. The skill ID is literally baked into the `refId` prefix (e.g., `swordArtsParamId=1043` yields `refId` values such as `10430000` for the bolt, `10439000` for the shockwave, etc.).
   - `Magic` rows with `ID < 6000` are usually the player-facing entries. Higher IDs (e.g., `53xxx`) are enemy/NPC duplicates with the same `refId`s and can be ignored for our purposes.
   - `refCategory*` tells you the table to open next (`0 = AtkParam_Pc`, `1 = Bullet`, `2 = SpEffectParam`, per `Paramdex/ER/Defs/MagicParam.xml`).
2. If `refCategory` is `1`, load `PARAM/Bullet.csv` with the referenced `refId`:
   - `atkId_Bullet` contains the `AtkParam_Pc` ID you actually need for damage numbers.
   - `HitBulletID` chains to follow-up bullets (lingering clouds, delayed explosions, etc.).
   - `spEffectId0-4` directly reference `SpEffectParam` rows (weapon buffs, self-buffs, delayed detonations). When a skill adds an elemental buff, that buff usually shows up here.
3. If `refCategory` is `0`, you are already holding an `AtkParam_Pc` ID and can skip the bullet step.
4. When you finally open `PARAM/AtkParam_Pc.csv`:
   - Use `atkPhys/atkMag/atkFire/atkThun/atkDark` as the base damage splits and `atkStam` as stance damage. Filter out rows with `atkAttribute = 254` or where every damage column is `0` (helpers/VFX).
   - `guardAtkRate` and `guardBreakRate` often stay at defaults; ignore them unless the skill is explicitly about guard-breaking.
5. Use `SpEffectParam` for lasting buffs or on-hit statuses:
   - Follow the IDs surfaced either by `Magic` (`refCategory=2`) or by `Bullet.spEffectId*`.
   - Columns like `thunderAttackPower`, `freezeAttackPower`, `effectEndurance`, `poizonAttackPower`, etc., give you the numbers we surface in the description (“The armament retains its imbuement for 45 seconds, which adds 160 lightning damage and 80 frostbite accumulation.”).  
   - Example: `SpEffectParam` ID `1891` has `effectEndurance: 45`, `thunderAttackPower: 160`, and `freezeAttackPower: 0`, which matches the Ice Lightning buff we describe in docs/definitions.md. (`rg -n 1891 PARAM/SpEffectParam.csv`)

### 4. Filtering heuristics (per the CSV extraction notes)

1. Dummy hits are everywhere. Skip bullet rows when:
   - `atkAttribute == 254` (pure VFX or helper bullets).
   - All damage columns are zero and the bullet has trivial `life/dist` (wing effects, camera dust, etc.).
   - `atkId_Bullet` is `0` or `1`.
2. If several bullets share the same `atkId_Bullet`, prioritize the ones with sensible `life/dist` values and non-zero damage splits.
3. Always cross-check `Magic` and `Bullet` data against expected behavior from the `descriptions-*` JSON bundles or Fextralife. A Feb 28 2025 Fextralife comment on the Ice Lightning Sword explicitly named `AtkParam_Pc` row `30090011` as the lightning bolt and pointed out that its INT/FTH scaling was bugged because Dragonscale Blade has zero in those stats. That comment lined up perfectly with the `Magic → Bullet → AtkParam` chain and confirmed that the first four digits of the `AtkParam` IDs still mirror the skill ID.
4. When numbers look implausible (e.g., “Wing Stance trail uses atkAttribute=254 with 297 magic damage”), drop them—they are usually effect helpers and were the root cause of the bad values we deleted during the last CSV pass.

### 5. Buffs, debuffs, and lasting effects

1. Weapon/self buffs can show up in three places, so check all three:
   - `Bullet.spEffectId*` (most AoWs, including Ice Lightning Sword, inject the buff via the projectile hit).
   - `Magic.refCategory=2` entries (some skills attach the buff directly without a bullet).
   - `EquipParamWeapon.residentSpEffectId*` when the weapon always carries a passive (not common for skills but worth checking).
2. When a single effect adds multiple stats (e.g., 160 lightning and 80 frost), there are often two `SpEffectParam` rows chained together. For Ice Lightning the `spEffectId` chain leads to `1891` (lightning addition) and `1893`/`1894` for frost. If you cannot find a direct match, search `SpEffectParam` for rows with the desired `thunderAttackPower` or `freezeAttackPower` values; in most cases the ID differs only in the last two digits from the skill’s main block.
3. Use `effectEndurance` for duration, `*_AttackPower`/`*_AttackRate` for additive vs. multiplicative bonuses, and `*_DamageRate` for DOTs.

### 6. Worked example: Ice Lightning Sword (swordArtsParamId = 1043)

1. **Locate the skill**: `EquipParamWeapon` row `9070000` (Dragonscale Blade) reports `swordArtsParamId=1043`.
2. **Magic rows (shortcut when available)**: Searching for `refId` values starting with `1043` returns the full attack suite:
   - `MagicID 4300/4301/4302` → Bullets `10430000/10430100/10430200` (the downward bolt and its chained hits).
   - `MagicID 4360/4361` → Bullets `10436000/10436100` (shockwave variants, one of which embeds `spEffectId0=1436000` for the buff trigger).
   - `MagicID 4370/4390` → Bullets `10437000` and `10439000` (close-range shockwave and lingering lightning puddle).
3. **Bullets → AtkParam**:
   - `Bullet 10430000` → `atkId_Bullet 43000` for the bolt’s strike (`atkThun` holds the lightning number we surface).
   - `Bullet 10439000` → `atkId_Bullet 43900` for the shockwave.
   - Each bullet stores the radius/life data we mention in prose if needed (e.g., how far the shockwave extends).
4. **Buffs**:
   - `Bullet 10436001` and `10436101` both reference `SpEffectParam` IDs `1436000` and `1436100` (temporary internal helpers) and eventually chain into `SpEffectParam 1891`/`1893` for the actual weapon buff. Those rows contain `effectEndurance: 45`, `thunderAttackPower: 160`, and `freezeAttackPower: 80`, which matches the wording in `docs/definitions.md`.
   - If the `1436xxx` IDs look opaque, search `SpEffectParam.csv` for the concrete numbers you expect (160 lightning, 80 frost) and follow the `replaceSpEffectId`/`cycleOccurrenceSpEffectId` columns—they point to the final effect that sticks to the player.
5. **Cross-check**: Compare the `AtkParam` values to the wiki/Fextralife entry and our existing `descriptions-mod` text. Fextralife’s `AtkParam_Pc 30090011` quote gives us extra confidence that we are looking at the right row.

### 7. Recommended tooling and references

- `Paramdex` (`https://github.com/soulsmods/Paramdex/tree/master/ER/Defs`) documents every field used above (`MagicParam`, `BehaviorParam`, `SwordArtsParam`, etc.). Use it when you are not sure what a flag or enum represents.
- Quick Python snippets are the fastest way to chase a skill through the CSVs. Example:  

  ```bash
  python - <<'PY'
  import csv
  sid = '1043'
  with open('PARAM/Magic.csv') as f:
      reader = csv.DictReader(f)
      for row in reader:
          if any(row[f'refId{i}'].startswith(sid) for i in range(1, 11)
                 if row.get(f'refId{i}') not in (None, '-1')):
              print(row['ID'], row['refCategory1'], row['refId1'])
  PY
  ```

- Use `rg '^1043' PARAM/Bullet.csv` (or the Python equivalent) to dump every bullet tied to a skill. This is much faster than scrolling through the CSV in a spreadsheet.
- Keep `csv_skill_extraction_notes.md` handy; it contains the sanity checks that prevented the earlier bad extractions (skip `atkAttribute=254`, insist on `isAttackSFX=1`, etc.).
- If the `Magic` table fails to mention a buff you see in-game, double-check `EquipParamWeapon.residentSpEffectId*`, `SpEffectParam.replaceSpEffectId`, and the FMGs. Sometimes FromSoftware hard-codes an effect onto the weapon instead of the skill.
- For team members new to the data: build one-time lookup tables from the FMGs (e.g., `skill name → ID`, `spell name → Magic ID`, `goods name → EquipParamGoods ID`). It keeps the CSV workflow deterministic and avoids repeated XML scraping.
- If we ever need perfect skill coverage, invest time in generating a TAE-derived map `SwordArtsParam ID + behaviorVariationId → [BehaviorParam_PC IDs]`. Once that file exists we can feed it to the same extraction pipeline we use for spells and items.

Following this workflow keeps the extraction deterministic: given a skill ID, you have a repeatable path to find its projectiles, their attack rows, and any status/buff data we need to surface. When fex_cache is missing a number, use the repo data; when the repo data is ambiguous, cross-reference the community breadcrumbs (Fextralife/Nexus) for the correct target IDs before you commit the numbers.
