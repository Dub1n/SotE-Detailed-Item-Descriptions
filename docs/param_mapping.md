## Param Mapping Playbook

The goal is to turn each skill entry in `work/responses/ready/skill.json` into a set of base damage, stance, and status values pulled straight from the PARAM CSVs. The data we need is spread across `EquipParam*`, `Magic`, `Bullet`, `AtkParam_Pc`, and `SpEffectParam`, plus the message XMLs when we need to confirm IDs.

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
   - Only read rows where `isAddBaseAtk == 0`. In those cases `atkPhys/atkMag/atkFire/atkThun/atkDark` are the “base” damage splits we need and `atkStam` is the stance damage (this is the same assumption we used in `csv_skill_extraction_notes.md`).
   - `guardAtkRate` and `guardBreakRate` often stay at defaults; ignore them unless the skill is explicitly about guard-breaking.
5. Use `SpEffectParam` for lasting buffs or on-hit statuses:
   - Follow the IDs surfaced either by `Magic` (`refCategory=2`) or by `Bullet.spEffectId*`.
   - Columns like `thunderAttackPower`, `freezeAttackPower`, `effectEndurance`, `poizonAttackPower`, etc., give you the numbers we surface in the description (“The armament retains its imbuement for 45 seconds, which adds 160 lightning damage and 80 frostbite accumulation.”).  
   - Example: `SpEffectParam` ID `1891` has `effectEndurance: 45`, `thunderAttackPower: 160`, and `freezeAttackPower: 0`, which matches the Ice Lightning buff we describe in docs/definitions.md. (`rg -n 1891 PARAM/SpEffectParam.csv`)

### 4. Filtering heuristics (per the CSV extraction notes)

1. Dummy hits are everywhere. Skip bullet rows when:
   - `atkAttribute == 254` (pure VFX or helper bullets).
   - `isAttackSFX == 0` **and** all damage columns are zero (wing effects, camera dust, etc.).
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
2. **Magic rows**: Searching for `refId` values starting with `1043` returns the full attack suite:
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

Following this workflow keeps the extraction deterministic: given a skill ID, you have a repeatable path to find its projectiles, their attack rows, and any status/buff data we need to surface. When fex_cache is missing a number, use the repo data; when the repo data is ambiguous, cross-reference the community breadcrumbs (Fextralife/Nexus) for the correct target IDs before you commit the numbers.
