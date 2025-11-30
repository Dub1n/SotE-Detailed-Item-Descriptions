## 1. design doc / overall plan

> note: files are currently in "/mnt/c/Users/gabri/Applications/Games/Modding/Elden Ring/Detailed Item Descriptions v1.3.4-1356-1-3-4-1720317354"

### 1.1 what the existing mod is doing

from the nexus page for “detailed item descriptions”:

* it “adds much more detailed descriptions for what items do, including exact numbers for how much damage items/spells/skills do or how much a buff actually increases a stat by” ([Nexus Mods][1])
* author used:
  * **yabber** to unpack archives and convert `.fmg` text files
  * **jpexs flash decompiler** to edit `.gfx` ui files
  * **yapped rune bear** for `regulation.bin` param research/edits
  * **ds anim studio** for skill data ([Nexus Mods][1])
* current version 1.3.4 is for game **1.12.3 / regulation 1.12.4** and is explicitly marked as a **compatibility‑only** update:
  > “NO CHANGES TO NEW DLC ITEM DESCRIPTIONS, NO CHANGES TO ACCOUNT FOR BALANCE CHANGES TO BASE GAME ITEMS… THESE WILL BE ADDRESSED IN FUTURE UPDATES.” ([Nexus Mods][1])

so:

* base‑game items are detailed up to around patch 1.09.x (see changelog listing specific `GoodsInfo`, `AccessoryInfo`, `ArtsCaption`, etc ids). ([Nexus Mods][1])
* dlc items (SotE) are **not** in the detailed style yet.
* the mod also includes some optional “cleaner menu text” changes, touching various `GR_MenuText`, `TutorialBody`, etc FMGs in `menu*.msgbnd` ([Nexus Mods][1]) — nice, but not required for your project.

your folder:

```text
├── menu
│   ├── 02_048_detailstatus_buddy.gfx
│   ├── 02_049_detailstatus_gem.gfx
│   ├── 02_051_detailstatus_item.gfx
│   ├── 02_053_detailstatus_spell.gfx
│   ├── 02_054_detailstatus_arrow.gfx
│   ├── 02_055_detailstatus_weapon1.gfx
│   ├── 02_056_detailstatus_recipe.gfx
│   ├── 02_057_itemdetailtext.gfx
│   └── 02_059_detailstatus_elixir.gfx
├── msg
│   └── engus
│       ├── item.msgbnd.dcx
│       ├── item_dlc01.msgbnd.dcx
│       └── item_dlc02.msgbnd.dcx
├── regulation.bin
└── regulation.bin.prev
```

* `msg/engus/item*.msgbnd.dcx` are **message bundles** that contain fmg text files (`GoodsInfo.fmg`, `AccessoryInfo.fmg`, `WeaponCaption.fmg`, etc). these hold all localized item names, descriptions, spell text, etc. ([Souls Modding][2])
* `item_dlc02.msgbnd.dcx` is *specifically* used for **dlc2 amulet/talisman descriptions**, confirmed by another mod (`Spirit Summon Overhaul`):
  > “item_dlc02.msgbnd.dcx is for amulet descriptions. The edited files in there are AccessoryInfo.fmg and AccessoryCaption.fmg.” ([Nexus Mods][3])
* `.gfx` files are not where the text lives; they are **ui swf variants** (“GFX – SWF variant used for UIs” ([Souls Modding][4])) and typically reference FMG text by id. they control layout, fonts, positions.
* text itself is inside FMGs: each FMG is a set of entries like `<text id="100">Creates a summon sign for cooperative multiplayer</text>` ([GitHub][5]).

therefore, to do **what you want** (update descriptions, add detailed effects for dlc items) you only need to touch:

* msg/engus/**item.msgbnd.dcx**
* msg/engus/**item_dlc01.msgbnd.dcx**
* msg/engus/**item_dlc02.msgbnd.dcx**

and maybe read (not modify) `regulation.bin` for numbers.

### 1.2 essential data / tool landscape

short version of the tech stack, all corroborated by sources:

* **FMG (text)**

  * generic localization/text containers; hold item descriptions, menu strings, etc. ([Souls Modding][2])
  * stored inside `*.msgbnd.dcx` bundles; typical files for items: `GoodsName.fmg`, `GoodsInfo.fmg`, `AccessoryName.fmg`, `AccessoryInfo.fmg`, `WeaponName.fmg`, `WeaponCaption.fmg`, `ArtsName.fmg`, `ArtsCaption.fmg`, etc. multiple mods reference editing these exact files for item / talisman / ash descriptions. ([Nexus Mods][6])
  * can be unpacked and repacked using **yabber** or **witchybnd**; witchybnd is the modern successor and explicitly supports DCX, BND4, FMG. ([GitHub][7])
  * exemplar: “goodsinfo.fmg” sample from carian archive shows index → text mapping. ([GitHub][5])

* **msgbnd.dcx (message bundles)**

  * e.g. `item.msgbnd.dcx`, `menu_dlc02.msgbnd.dcx`.
  * extracted from `Data0.bdt` using tools like **UXM** / ER.BDT.Tool, then further decompressed to FMG using yabber/witchybnd. a nexus guide shows this for `item.msgbnd` and `menu.msgbnd`. ([Nexus Mods][8])

* **regulation.bin (params)**

  * contains param tables like `EquipParamGoods`, `EquipParamAccessory`, `EquipParamWeapon`, `SpEffectParam`, etc, which define actual item effects, damage, fp cost, etc. ([Nexus Mods][9])
  * param docs show, e.g., `EquipParamGoods` covers inventory items and references icons and various stats ([Souls Modding][10]); guides confirm `EquipParamGoods` and `EquipParamWeapon` control item and weapon stats and special effects. ([Nexus Mods][11])
  * edited nowadays via **smithbox** (or DSMapStudio). smithbox provides:
    * **param editor** for these tables,
    * **text editor** for FMGs. ([GitHub][12])

* **smithbox text workflows**

  * smithbox text editor can merge FMG data from external files: e.g. “Open Project > Text Editor > Data > Import Text Entries > Merge Entries” is the recommended way to merge FMG modifications. ([Nexus Mods][13])
  * several mods rely on this pattern (supplying FMG/JSON “merge files”). ([Nexus Mods][14])

* **UI `.gfx`**

  * GFX files are ui swf; text is *not* hard‑coded there in most cases; they reference FMG ids. formats reference article explicitly notes GFX is the SWF‑like ui format. ([Souls Modding][4])
  * many text‑only mods (like changing “YOU DIED” text) work by editing `GR_MenuText.fmg` only; instructions: unpack `menu_dlc02.msgbnd.dcx`, edit `GR_MenuText.fmg` via yabber to change `<text id="331305">YOU DIED</text>`, repack – no .gfx edits involved. ([Nexus Mods][15])

so: for your purposes, **you can ignore `.gfx`** unless you later want to change layout or new labels. your text changes all live in FMG.

---

### 1.3 desired behaviour (what we want the mod to do)

for each relevant item (base + dlc):

* keep the **flavour/lore** section (what the item is, who used it, etc).
* inject a **mechanical summary** block, e.g.:

```text
<font color="#C0B194">Passive Effect:</font>
Increases <font color="#E0B985">Dexterity</font> by 1.
```

the consort’s mask example you gave matches this pattern: base “Increase dexterity.” line is removed from the lore paragraph, and the mechanical detail is moved to a formatted “passive effect” block with exact value. that’s consistent with the mod’s stated intent (exact numbers for buffs, etc.). ([Nexus Mods][1])

we want to do that in bulk for:

* all **shadow of the erdtree** items (especially:
  * talismans / accessories,
  * armour with passive bonuses,
  * special weapons,
  * spells / incantations / skills that gained new DLC variants),
* any **base game items** whose stats changed after the mod’s last “content” update (post‑1.09.0).

and we want a pipeline where:

* scripts/agents do the repetitive “find item → pull effect → write new string”;
* you use smithbox as a comfortable UI for **spot‑checking and hand‑fixing**.

---

### 1.4 core workflow for a single item

this is the conceptual pipeline per item (which we’ll later automate):

1. **locate item text in FMG**

   * find the item’s *name* in `*Name.fmg` (GoodsName, AccessoryName, etc).
     * mods like *Kairotox’s Elden Ring Tweaks* explicitly list these for item text. ([Nexus Mods][16])
   * record its `id` (e.g. 2120).
   * in the corresponding `*Info.fmg` (GoodsInfo, AccessoryInfo, etc), locate the entry with the same id; that’s the description text. patterns from carian archive show `[100]` style indexing, and multiple mods rely on same‑id mapping between Name and Info. ([GitHub][5])

2. **get ground‑truth mechanics**

   two main options:

   **A. param‑first (in‑game data)**

   * in smithbox param editor, identify the row for this item in:
     * `EquipParamAccessory` for talismans,
     * `EquipParamGoods` for consumables, spells, physick tears, etc,
     * `EquipParamWeapon` for weapons,
     * `EquipParamProtector` for armour. ([Nexus Mods][9])
   * read the special effect references (fields referencing `SpEffectParam` rows, attack params, etc). eld modding guides describe `SpEffectParam` controlling special effects, and `EquipParamWeapon` / `EquipParamGoods` referencing them. ([Souls Modding][17])
   * from these, infer simple player‑facing facts:
     * “Increases Dexterity by +1” (stat bonus)
     * “Reduces damage taken by 10% while blocking”
     * “Grants +X% damage to incantations of Y school”, etc

   **B. wiki‑assisted (external data)**

   * use one or more external wikis to read human‑written effect summaries:
     * Fextralife “equipment with special effects” lists rows like “Consort’s Mask – Head – Increases Dexterity (+1)” ([Elden Ring Wiki][18])
     * GameWith/Game8/GameRant style pages show “Effect: Dexterity increased by +1” for consort’s mask and similar armour. ([GameWith][19])
   * these are good text seeds; param can be used as a sanity check to ensure numbers are correct.
   in practice, you’ll likely combine them:
   * take the **human string** from wiki (nice English, consistent phrasing),
   * confirm / correct **numbers** using param values in smithbox.

3. **strip lore vs mechanics**

   * base description currently is lore + maybe vague effect text.
   * you want a clean split:
     * lore paragraph(s) only, then
     * blank line(s), then
     * “Passive Effect:” block(s) with numbers.
   * this can be done per item with an llm: give it:
     * original description,
     * the effect summary you want (e.g. “Increases Dexterity by +1”),
     * instructions: “rewrite description so that lore paragraphs contain no mechanical sentences; move all mechanical explanations into a formatted passive block like: `<font color="...">Passive Effect:</font> ...`”.

4. **compose final description string**

   something like:

   ```text
   [lore from original, cleaned]

   <font color="#C0B194">Passive Effect:</font>
   Increases <font color="#E0B985">Dexterity</font> by 1.
   ```

   you can choose whether to preserve font tags; the game’s text renderer supports `<font>` tags and mods commonly use them in FMGs. (your example already does; other mods similarly adjust colour using inline tags.) ([Nexus Mods][16])

5. **write back into FMG**

   * update the `<text id="2120">...</text>` entry in the appropriate `*Info.fmg` xml (or json).
   * repack FMG into `item*.msgbnd.dcx` via witchybnd/yabber. ([GitHub][7])
   * drop updated `msg/engus` folder into your mod’s directory (mod engine 2 setup, etc) and test.

the same pattern applies to spells, ashes of war, spirit ashes, etc — they just live in different param tables and different FMG groups (`GoodsInfo`, `ArtsCaption`, `GemInfo`, etc) which the mod’s changelog already name. ([Nexus Mods][1])

---

### 1.5 automation strategy by stage

now, how to automate each stage, assuming you have:

* smithbox gui,
* witchybnd (or yabber),
* a scripting environment (python/node/whatever) that your “codex agent” can use,
* and an llm capable of “read text + output new text”.

#### stage 0 – setup / exporting data

##### 0.1 unpack msgbnd → FMG xml

option 1 – witchybnd (recommended for automation):

* get witchybnd (github + nexus page). ([GitHub][7])
* copy `item.msgbnd.dcx`, `item_dlc01.msgbnd.dcx`, `item_dlc02.msgbnd.dcx` into the witchybnd folder.
* run witchybnd on each (drag‑and‑drop or cli): it will produce folders like `item-msgbnd-dcx\...` containing FMGs. mods merge `item_dlc02-msgbnd-dcx` exactly like this when editing DLC FMGs. ([DLCfun][20])
* run witchybnd again on each `.fmg` to produce `*.fmg.xml` (or `*.fmg.json` depending on configuration). multiple mods reference `.fmg.xml` editing workflows with yabber/witchybnd. ([Nexus Mods][21])

option 2 – smithbox only (nice for viewing, less ideal for bulk scripting):

* unpack the game using **UXM selective unpack** so the `msg` folder is present; mod authors note this is required for smithbox’s text editor to see text at all. ([Nexus Mods][14])
* create a smithbox project pointing at your mod (regulation + mod’s msg folder).
* in text editor → data, you can export FMG entries to merge files (json / fmgmerge); that format is scriptable but is more smithbox‑specific.

for heavy automation, i’d use witchybnd for the text and smithbox just as a viewer/param editor.

##### 0.2 export param data

* in smithbox param editor, select relevant tables and export to CSV:
  * `EquipParamAccessory` (talismans etc),
  * `EquipParamGoods` (consumables, spells, physick tears),
  * `EquipParamWeapon`,
  * `EquipParamProtector`,
  * `SpEffectParam` (for special effects).
* this “export CSV per param” workflow is exactly what many mods use — e.g. combine great runes / other param mods package CSVs for merging, with instructions to import via smithbox/DSMapStudio. ([Nexus Mods][21])

script‑side, you now have:

* `fmg_xml/` – multiple xml files with `<text id="...">` entries,
* `params/*.csv` – tables per param type.

#### stage 1 – build a master item list

goal: create a table like:

```text
item_id | category | in_game_name | fmg_name_file | fmg_name_id | fmg_info_file | fmg_info_id | base_description
```

**strategy:**

1. parse all `*Name.fmg.xml` files in `item*.msgbnd` for english:
   * e.g. `AccessoryName.fmg.xml`, `GoodsName.fmg.xml`, `WeaponName.fmg.xml`, `ProtectorName.fmg.xml`, `ArtsName.fmg.xml`, `GemName.fmg.xml`.
   * for each `<text id="N">Name</text>`, store (file, id, string).
2. parse corresponding `*Info.fmg.xml` and `*Caption.fmg.xml` to map description entries by id. examples:
   * great rune mods list edited `GoodsCaption.fmg` and `GoodsInfo.fmg` to change rune text. ([Nexus Mods][6])
   * talisman mods edit `AccessoryInfo.fmg` & `AccessoryCaption.fmg`. ([Nexus Mods][3])
3. optionally, join with param CSVs using known linkages:
   * `EquipParamAccessory` / `EquipParamGoods` often have fields for `nameId`, `infoId` or similar that match FMG ids (documented by yapped param editing guide: item parameters live in those tables and reference text via FMG ids). ([soulsmodding.wikidot.com][22])

for **dlc items**, simply doing this over `item_dlc01` and `item_dlc02` is enough to capture all new items + their vanilla descriptions.

#### stage 2 – fetch effect summaries

this is where the llm + scraping come in. two broad lanes:

##### 2A. param‑only (no external site dependence)

* for each item row in the relevant param table:
  * collect:
    * stat modifiers (e.g. fields pointing to `SpEffectParam` rows that change `Dex`, `Str`, etc),
    * fp/hp costs (for spells, skills, consumables),
    * damage types / multipliers (for spells / ashes of war using `AtkParam_Pc` / `Bullet` etc). ([Souls Modding][17])
* feed this param slice into an llm that understands the schema (or you pre‑interpret, then give it a cleaned description). sample llm prompt concept (for your local agent):

> given:
> – item category & name
> – relevant param rows (EquipParam*, SpEffectParam)
> generate 1–3 short plain‑English lines that summarize the item’s mechanical effects for the player, e.g. “Increases Dexterity by +1” or “Greatly increases stance damage but reduces your own poise by 20%.”

this keeps the data **exactly synced** with `regulation.bin` and doesn’t need any web scraping — just reading CSVs.

##### 2B. wiki‑assisted (what you originally imagined)

because my environment can’t successfully open fextralife pages (502’s ¯\_(ツ)_/¯), i’ll describe this in terms of the *pattern* other sites show, which you can adapt to fextralife locally:

* sites like **GameWith/Game8/Gamerant** have item or list pages with explicit “Effect” fields; e.g.
  * `Consort's Mask (Helm) – [Effect] Dexterity increased by +1` ([GameWith][19])
* fextralife’s “Equipment with Special Effects” page lists rows like: “Consort’s Mask – Head – Increases Dexterity (+1)” ([Elden Ring Wiki][18])

so the general plan:

1. for each **item name** in your master list:
   * construct its wiki url (or search query) and fetch the page html.
2. parse for effect strings. for fextralife or similar, these are usually:
   * in a dedicated “Effect” or “Notes & Tips” section;
   * bullet items beginning with verbs like “Increases”, “Raises”, “Boosts”, “Reduces”, “Grants”, etc.
3. filter down to the minimal line(s):
   * drop location/loot info, sell value, flavour tips, patch notes, etc;
   * keep only lines that describe persistent mechanics or important on‑use behaviour.
4. have an llm clean/normalize them into your preferred phrasing:
   * unify casing (“Dexterity”, “HP”, “FP”),
   * convert “+1” vs “+ 1” vs “+1%” to consistent forms,
   * optionally ensure they agree with param CSV values.

you can do this once to build a local **effect catalog**:

```json
{
  "Consort's Mask": {
    "slot": "Head",
    "effect_lines": [
      "Increases Dexterity by +1"
    ]
  },
  "Some DLC Talisman": {
    "slot": "Talisman",
    "effect_lines": [
      "Increases max HP by 10%",
      "Reduces damage taken from critical hits by 20%"
    ]
  },
  ...
}
```

for dlc items specifically, this may be **faster** than teaching an llm the entire param schema, as long as the wiki is kept relatively up to date.

realistically, your best pipeline is **hybrid**:

* first trust param numbers,
* then use wiki text as a “language template” that you adjust to param.

---

#### stage 3 – generate final descriptions via llm

for each item in your master list that needs work:

inputs to your agent per item:

* `orig_desc` – current in‑game description string from the relevant `*Info.fmg` (dlc: vanilla description; base game: maybe already a detailed one from Dziggy).
* `lore_only_hint` – optionally, the original vanilla description for base game items (from `elden-ring-data/msg` json, or from unmodded FMG backups). ([GitHub][23])
* `effect_lines` – 1..N effect strings from stage 2.
* `style_guide` – small instructions capturing Dziggy’s style (passive effect header, colour tags, no mechanics mixed into lore, etc).

agent task:

1. split `orig_desc` into:

   * lore fragments,
   * any existing mechanics sentences (“raises dexterity”, “greatly boosts …”).

2. discard the mechanics sentences; keep lore.

3. assemble a new string:

   ```text
   [lore paragraphs with standard punctuation / spacing]

   <font color="#C0B194">Passive Effect:</font>
   [effect lines, one per line, optionally with <font> for stats]
   ```

4. optional extra formatting:

   * highlight stats (`Dexterity`, `Strength`, etc) with `#E0B985` as in your example.
   * combine multiple effects with bullet‑ish pattern:

     ```text
     <font color="#C0B194">Passive Effects:</font>
     Increases <font ...>Strength</font> by 5.
     Reduces damage taken from critical hits by 20%.
     ```

agent output is the **final FMG text** for that item.

you then inject this into the `*Info.fmg.xml` entry for that id.

---

#### stage 4 – writing back and testing

##### 4.1 write back to FMG xml

script:

* load the target `*.fmg.xml`.
* find `<text id="TARGET_ID">...</text>`.
* replace the content with the llm’s new description, escaping any characters as needed.
* repeat for all items in batch.

##### 4.2 repack FMGs → msgbnd

* run witchybnd on the FMG xmls to turn them back into FMG binaries; several guides explain the reverse process (drag folder back onto yabber/witchybnd). ([Nexus Mods][8])
* ensure they’re placed back into `item.msgbnd.dcx`, `item_dlc01.msgbnd.dcx`, `item_dlc02.msgbnd.dcx` structure.

##### 4.3 integration with smithbox

optional but nice:

* create/update a smithbox project pointing to your **mod’s** regulation + msg folder.
* open text editor; ensure your updated FMGs are visible (mod authors note that unpacking the game’s `msg` folder is needed for smithbox to see text at all). ([Nexus Mods][14])
* use smithbox for:
  * quick item search,
  * visual sanity check of descriptions,
  * manual edits.

##### 4.4 in‑game testing

* run via mod engine 2 (standard approach for ER modding). mods altering msgbnd/params routinely use this layout. ([Nexus Mods][24])
* use a cheat‑table or item‑spawn mod (same type the original author cites as tools) to quickly acquire the items and check text/effects. ([Nexus Mods][1])

---

### 1.6 strategy for post‑1.09 base‑game changes

you also mentioned wanting to reflect balance changes introduced after the mod’s last content update. we can outline a way to **discover** those programmatically:

1. obtain an older regulation.bin from patch 1.09.x (or from Dziggy’s 1.3.3 package, which references specific param ids changed for that patch). ([Nexus Mods][1])
2. diff its param CSVs against current 1.12.x CSVs for relevant tables (`EquipParamAccessory`, `EquipParamGoods`, `EquipParamWeapon`, etc).
3. mark any rows where:
   * stat modifiers changed,
   * damage values changed,
   * spEffect links changed.
4. limit your “update descriptions” pass to that subset (plus dlc items).

that’s a bit more advanced, but doable once the basic pipeline exists.

---

[1]: https://www.nexusmods.com/eldenring/mods/1356 "Detailed Item Descriptions at Elden Ring Nexus - Mods and Community"
[2]: https://www.soulsmodding.com/doku.php?id=format%3Afmg&utm_source=chatgpt.com "FMG [?WikiName?"
[3]: https://www.nexusmods.com/eldenring/mods/4597?utm_source=chatgpt.com "Spirit Summon Overhaul - Elden Ring"
[4]: https://www.soulsmodding.com/doku.php?id=format%3Amain&utm_source=chatgpt.com "Formats [?WikiName?"
[5]: https://raw.githubusercontent.com/AsteriskAmpersand/Carian-Archive/main/Master.html?utm_source=chatgpt.com "https://raw.githubusercontent.com/AsteriskAmpersan..."
[6]: https://www.nexusmods.com/eldenring/mods/2869?utm_source=chatgpt.com "Great Rune Overhaul - Elden Ring"
[7]: https://github.com/ividyon/WitchyBND?utm_source=chatgpt.com "ividyon/WitchyBND: Unpacks/repacks FromSoftware ..."
[8]: https://www.nexusmods.com/eldenring/articles/115?utm_source=chatgpt.com "How to get the msgbnd.dcx files from game - Elden Ring"
[9]: https://www.nexusmods.com/eldenring/articles/36?utm_source=chatgpt.com "Each Param Change - Elden Ring"
[10]: https://www.soulsmodding.com/doku.php?id=bb-refmat%3Aparam%3Aequipparamgoods&utm_source=chatgpt.com "EquipParamGoods [?WikiName?"
[11]: https://www.nexusmods.com/eldenring/articles/396?utm_source=chatgpt.com "How These Spells Were Created at Elden Ring Nexus"
[12]: https://github.com/vawser/Smithbox?utm_source=chatgpt.com "Smithbox is a modding tool for Elden Ring, Armored Core ..."
[13]: https://www.nexusmods.com/eldenring/mods/5977?tab=posts&utm_source=chatgpt.com "Jorb's Greatest Runes - Elden Ring"
[14]: https://www.nexusmods.com/eldenring/mods/3821?tab=posts&utm_source=chatgpt.com "Call for Aid - Evolving Tarnished Summons - Nexus Mods"
[15]: https://www.nexusmods.com/eldenring/mods/5528?utm_source=chatgpt.com "MORTIS YOU DIED Replacement - Elden Ring"
[16]: https://www.nexusmods.com/eldenring/mods/1482?utm_source=chatgpt.com "Kairotox's Elden Ring Tweaks (KERT) (AKA MoreDew)"
[17]: https://soulsmodding.com/doku.php?id=ac6-refmat%3Aparam%3Amagic&utm_source=chatgpt.com "Magic [?WikiName?"
[18]: https://eldenring.wiki.fextralife.com/Equipment%2Bwith%2BSpecial%2BEffects?utm_source=chatgpt.com "Equipment with Special Effects | Elden Ring Wiki"
[19]: https://gamewith.net/elden-ring/article/show/33045?utm_source=chatgpt.com "Elden Ring | Best Armor & Equipment List"
[20]: https://dlcfun.com/es/elden-ring/koreiskii-modpak-clevers-moveset-modpack?utm_source=chatgpt.com "Paquete de modificaciones coreano Clever's Moveset Modpack"
[21]: https://www.nexusmods.com/eldenring/mods/1960?tab=docs&utm_source=chatgpt.com "Combine Great Runes at Elden Ring Nexus"
[22]: https://soulsmodding.wikidot.com/yapped-parameter-editing-items?utm_source=chatgpt.com "Yapped Parameter Editing - Items - Souls Modding Wiki"
[23]: https://github.com/elden-ring-data/msg "GitHub - elden-ring-data/msg: Elden Ring Data /msg folder"
[24]: https://www.nexusmods.com/eldenring/mods/3202?tab=description&utm_source=chatgpt.com "Stellar Meteoric ore blade - Elden Ring"
