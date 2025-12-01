CSV skill extraction attempt (rolled back)
=========================================

What I pulled from the params (now reverted in `work/responses/ready/skill.json`)

- Palm Blast: Base magic damage 114; stance 20 / 36.
- Piercing Throw: Base magic damage 259 / 324; stance 40 / 45.
- Scattershot Throw: Base magic damage 92 / 110; stance 20 / 26.
- Swift Slash: Base magic damage 182 / 205 / 52 (vacuum/charged/trail); stance 10 / 20.
- Shield Strike: Base magic damage 55 / 75 / 100 / 55; stance 10 / 10 / 20 / 20 (first, second, third, shockwave).
- Dragonwound Slash: Base magic damage 54 / 57; stance 11 / 14.
- Needle Piercer: Base magic damage 312; stance 340.

How I derived them

1) Look up the skill ID in `PARAM/Magic.csv` and collect `refId*` entries where `refCategory* == 1`.
2) For each refId, check `PARAM/Bullet.csv`: if present, take its `atkId_Bullet`, then open that row in `PARAM/AtkParam_Pc.csv`. If the refId is itself an AtkParam row, read it directly.
3) When `isAddBaseAtk == 0`, read the damage splits (`atkPhys`, `atkMag`, `atkFire`, `atkThun`, `atkDark`) as “Base … damage” and `atkStam` as stance damage.

Why this looks wrong

- Wing Stance is a good example of a bad trail: its refIds point to bullets with `atkAttribute=254`, `isAttackSFX=0`, zero radii, and AtkParam rows that carry huge “magic” and “stance” numbers (e.g., 297 magic / 260 stance) that clearly aren’t player-facing hits. Those effect/dummy bullets made the pulled numbers nonsensical.
- Several other non-unique skills show refIds that resolve to atkIds 0/1 or the same 254-style effect bullets, so blindly reading AtkParam gives misleading values (e.g., Dragonwound Slash marked as “pure physical” in the wiki, but the trail above yielded magic-only damage).
- The params mix real hitboxes with helper/effect bullets; without filtering for attack attributes/SFX flags, the extraction grabs the wrong rows.

How to repeat (and what to watch for)

1) Use the Magic → Bullet → AtkParam chain above (small Python snippet works well; see session logs).
2) Before trusting a value, check the Bullet row for `isAttackSFX=1`, sensible radii/velocity, and `atkAttribute` not set to 254. Skip rows with atkIds 0/1 or empty damage splits.
3) Cross-check against known behavior (e.g., whether the skill should be physical-only) and against `descriptions-mod` values before adding to `skill.json`.

Current state

- All CSV-derived stat lines listed above were removed from `work/responses/ready/skill.json` pending a safer extraction filter.
