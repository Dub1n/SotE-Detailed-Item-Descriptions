# 2. instruction doc for agents / scripts

this is the “hand it to codex / another dev” part — concrete steps and expectations.

## 2.1 scope

* target game: **elden ring**, app v1.12.3+, with **shadow of the erdtree dlc** installed.
* base mod: **detailed item descriptions v1.3.4** (dziggy). ([Nexus Mods][1])
* goal:
  * add detailed “passive effect” descriptions for all dlc items (particularly talismans, armour with special effects, weapons, spells, ashes of war, spirit ashes),
  * update outdated descriptions for base items whose stats changed post‑1.09.0,
  * preserve original lore text as much as possible.

constraints:

* do not change gameplay behaviour unless explicitly requested (regulation.bin is read‑only for now).
* keep text localization scope to **engUS** only (`msg/engus`).

---

## 2.2 prerequisites

tools that must be installed:

1. **witchybnd** (or yabber) – for unpacking/repacking:

   * witchybnd description: supports DCX, BND4, FMG and is the successor to yabber. ([GitHub][7])

2. **smithbox**:

   * integrated modding tool with param editor + text editor; now the recommended replacement for yapped in many guides. ([Nexus Mods][25])

3. a scripting environment:

   * any language is acceptable; examples presuppose python‑like I/O and xml/json parsing.

4. local llm / codex agent:

   * must be able to take structured prompts + strings and return new descriptions.

input files:

* mod’s `msg/engus/item.msgbnd.dcx`
* mod’s `msg/engus/item_dlc01.msgbnd.dcx`
* mod’s `msg/engus/item_dlc02.msgbnd.dcx`
* mod’s `regulation.bin` (current game version 1.12.x)
* optionally, **vanilla** message + regulation dumps if available.

---

## 2.3 step‑by‑step pipeline for agents

### step 1 – extract FMG text

1. copy the three message bundles into a working directory:

   ```text
   work/msg/engus/item.msgbnd.dcx
   work/msg/engus/item_dlc01.msgbnd.dcx
   work/msg/engus/item_dlc02.msgbnd.dcx
   ```

2. run witchybnd on each:

   * expected result: folders like `item-msgbnd-dcx`, `item_dlc01-msgbnd-dcx`, `item_dlc02-msgbnd-dcx` containing FMGs under something like `GR\data\INTERROOT_win64\msg\engUS\*.fmg`. this structure is consistent with other mods’ docs. ([Nexus Mods][16])

3. for each `.fmg` in those folders:

   * run witchybnd again to produce `*.fmg.xml` (or configure for json).
   * keep the xml form; multiple mods and references (Carian Archive, TalkMsg examples) show `<text id="...">` entries there. ([GitHub][5])

4. identify and catalogue the **item‑relevant FMGs**, at least:

   * `GoodsName.fmg.xml`, `GoodsInfo.fmg.xml`, `GoodsCaption.fmg.xml`
   * `AccessoryName.fmg.xml`, `AccessoryInfo.fmg.xml`, `AccessoryCaption.fmg.xml`
   * `WeaponName.fmg.xml`, `WeaponCaption.fmg.xml`
   * `ProtectorName.fmg.xml`, `ProtectorCaption.fmg.xml`
   * `ArtsName.fmg.xml`, `ArtsCaption.fmg.xml` (ashes of war)
   * `GemName.fmg.xml`, `GemInfo.fmg.xml` (special case, used for some weapon skill text) ([Nexus Mods][1])

### step 2 – export param tables

1. in smithbox:

   * create/open a project containing the mod’s `regulation.bin` and (optionally) base game unpacked data.
   * in param editor, for each relevant param (`EquipParamAccessory`, `EquipParamGoods`, `EquipParamWeapon`, `EquipParamProtector`, `SpEffectParam`, and optionally `Magic`, `AtkParam_Pc`, `Bullet`):

     * export to csv via data → export/CSV (or equivalent).

2. store CSVs as e.g.:

   ```text
   params/EquipParamAccessory.csv
   params/EquipParamGoods.csv
   params/EquipParamWeapon.csv
   params/EquipParamProtector.csv
   params/SpEffectParam.csv
   ...
   ```

### step 3 – build the item index

write a script to:

1. parse all `*Name.fmg.xml`:

   * for each `<text id="N">NAME</text>`, create a record:

     ```json
     {
       "name": "Consort's Mask",
       "name_fmg": "AccessoryName.fmg",
       "name_id": N,
       "category": "head/armour or accessory, determine via fmg filename",
       "source": "item.msgbnd.dcx" or "item_dlc02.msgbnd.dcx"
     }
     ```

2. attach descriptions:

   * for each record, look up `<text id="N">` in the matching `*Info.fmg.xml` and `*Caption.fmg.xml` (if present); attach `base_description` and `caption`.

3. optionally, attach param data:

   * load CSVs and join using:

     * either a `textId`/`nameId` field matching `name_id`, or
     * if that is awkward, attempt string matching between item names and a param’s internal `row name` (some modders import stock row names to make this easier). ([soulsmodding.wikidot.com][22])

4. flag dlc vs base:

   * anything from `item_dlc01` or `item_dlc02` is dlc; mark accordingly.
   * base items are in `item.msgbnd`.

5. output the full index as `items.json` for later stages.

### step 4 – collect effect summaries

two variants; you can implement either or both.

#### 4A. param‑only summariser

for each `items.json` entry:

1. based on `category` and param join, fetch:

   * `EquipParamAccessory` row if it exists;
   * `EquipParamGoods` row for consumables/spells;
   * `EquipParamWeapon` for weapons;
   * relevant `SpEffectParam` rows referenced by those entries. ([Nexus Mods][11])

2. create a compact **machine summary**:

   ```json
   {
     "hpBonus": 0,
     "fpBonus": 0,
     "dexBonus": +1,
     "strBonus": 0,
     "vigorBonus": 0,
     "damageTakenMult": 1.0,
     "notes": [...]
   }
   ```

3. pass that object + item category to the llm with instructions:

   * generate 1–3 human‑readable effect lines suitable for players, with numeric values baked in, e.g.:
     * “Increases Dexterity by 1.”
     * “Greatly increases stance damage dealt but reduces your own poise by 20%.”

store that as `effect_lines` on the item record.

#### 4B. wiki‑assisted (if you also scrape sites)

if the environment can fetch Fextralife/GameWith/etc (it couldn’t for me, but it should for you), implement:

1. for each item name, send a request to chosen wiki endpoint(s).
2. parse html to extract:
   * either explicit “Effect:” fields (e.g., tables as seen for consort’s mask), or
   * bullet items in “Notes & Tips” or “Notes & Tips – Shadow of the Erdtree” sections. ([GameWith][19])
3. filter down to only effect‑like sentences (regex on verbs + stat words; drop sell values, lore, farming tips).
4. store cleaned lines as `effect_lines`.
5. cross‑validate with param numbers (optional but recommended).

output a consolidated `items_effects.json` that merges `items.json` + `effect_lines`.

### step 5 – generate new descriptions via llm

for each item in `items_effects.json` that either:

* is in dlc (`source` is `item_dlc01` / `item_dlc02`), or  
* is flagged as “changed” based on param diffs (optional advanced step),

perform the following:

1. construct an llm prompt with:

   * `orig_desc` — the base description text from the corresponding `*Info.fmg.xml`.
   * `orig_caption` — optional caption text (if present).
   * `effect_lines` — the cleaned mechanical effect lines generated in step 4.
   * `style_spec` — **a directive to follow *exactly* the formatting, colour rules, spacing, and per-category templates defined in** `description_style_spec.md`.

   the llm must:
   * preserve all flavour/lore text verbatim (except for removing embedded mechanical statements).
   * separate lore from mechanics exactly as documented in the style spec.
   * format the mechanical section(s) according to the correct **category template**  
     (armour, talisman/seal, spell, skill, consumable buff, consumable damage, etc).
   * apply all required `<font>` colour codes from the style spec.
   * use only numbers derived from `effect_lines` or the param summary.

2. llm outputs `new_desc` — a fully formatted description string compliant with the style spec.

3. if the item is a spell, ash of war, or skill, the llm must also generate the appropriate additional sections defined in the spec (e.g. behaviour description, frost/bleed formula blocks, base damage/buildup lines, category lines).

4. assign `new_desc` to the item record for reinsertion into its target `*Info.fmg.xml`.

### step 6 – patch FMG xmls

script:

1. load the relevant `*Info.fmg.xml` file for each item.
2. find `<text id="id">OLD_TEXT</text>` node.
3. replace `OLD_TEXT` with `new_desc` (taking care not to break xml escaping).
4. write modified xml back to disk.

after processing all items, you’ll have updated FMG xmls for `item.msgbnd`, `item_dlc01.msgbnd` and `item_dlc02.msgbnd`.

### step 7 – repack and integrate

1. run witchybnd on each modified `.fmg.xml` to regenerate `.fmg`.
2. re‑run witchybnd on each `item*-msgbnd-dcx` folder to repack into `item*.msgbnd.dcx` files. ([Nexus Mods][8])
3. place updated `msg/engus/` into the mod folder used by **mod engine 2** (or your existing loader). ([Nexus Mods][24])
4. test in game:

   * use cheat table / item‑giving mod (as Dziggy did) to quickly check a sampling of items. ([Nexus Mods][1])
   * confirm:
     * descriptions show as expected,
     * no broken markup,
     * numbers match game behaviour.

---

## 2.4 notes on `.gfx` / menu files

* `.gfx` files (e.g., `02_057_itemdetailtext.gfx`) are SWF‑like ui layouts. ([Souls Modding][4])
* they **do not** need to be edited to change plain text descriptions; FMGs control the strings themselves. examples include “YOU DIED” replacements that only modify `GR_MenuText.fmg` in `menu_dlc02.msgbnd.dcx`. ([Nexus Mods][15])
* only touch `.gfx` (using jpexs) if:
  * you want to rearrange layout, add new text fields, change fonts, etc; or
  * you discover that SOTE adds separate `.gfx` controls that reference new FMG ids, and you want to visually tweak them.

for this project, focus automation on FMG + param; consider `.gfx` “out of scope”.

---

## 2.5 division of labour (who does what)

### scripts / codex agents

* implement:
  * fmgs extraction/patching,
  * param export reading,
  * wiki/param effect summarisation,
  * llm‑driven description rewriting,
  * repacking.

### you

* choose style for the descriptions (how verbose; which effects matter).
* decide on prioritisation (dlc talismans + special armour first; spells later, etc).
* sanity‑check the outputs inside smithbox and in‑game.
* handle any weird edge‑cases manually (items whose effects are too complex or poorly documented).

---

if you want, next step we can sketch **concrete prompt templates** for the local llm (one for “extract effect lines from wiki html”, one for “given param snippet, summarise in english”, one for “rewrite description into lore + passive effect block”). Ꮚ˘ ꈊ ˘ Ꮚ

[1]: https://www.nexusmods.com/eldenring/mods/1356 "Detailed Item Descriptions at Elden Ring Nexus - Mods and Community"
[4]: https://www.soulsmodding.com/doku.php?id=format%3Amain&utm_source=chatgpt.com "Formats [?WikiName?"
[5]: https://raw.githubusercontent.com/AsteriskAmpersand/Carian-Archive/main/Master.html?utm_source=chatgpt.com "https://raw.githubusercontent.com/AsteriskAmpersan..."
[7]: https://github.com/ividyon/WitchyBND?utm_source=chatgpt.com "ividyon/WitchyBND: Unpacks/repacks FromSoftware ..."
[8]: https://www.nexusmods.com/eldenring/articles/115?utm_source=chatgpt.com "How to get the msgbnd.dcx files from game - Elden Ring"
[11]: https://www.nexusmods.com/eldenring/articles/396?utm_source=chatgpt.com "How These Spells Were Created at Elden Ring Nexus"
[15]: https://www.nexusmods.com/eldenring/mods/5528?utm_source=chatgpt.com "MORTIS YOU DIED Replacement - Elden Ring"
[16]: https://www.nexusmods.com/eldenring/mods/1482?utm_source=chatgpt.com "Kairotox's Elden Ring Tweaks (KERT) (AKA MoreDew)"
[19]: https://gamewith.net/elden-ring/article/show/33045?utm_source=chatgpt.com "Elden Ring | Best Armor & Equipment List"
[22]: https://soulsmodding.wikidot.com/yapped-parameter-editing-items?utm_source=chatgpt.com "Yapped Parameter Editing - Items - Souls Modding Wiki"
[24]: https://www.nexusmods.com/eldenring/mods/3202?tab=description&utm_source=chatgpt.com "Stellar Meteoric ore blade - Elden Ring"
[25]: https://www.nexusmods.com/eldenring/mods/4928?utm_source=chatgpt.com "Smithbox - Elden Ring"
