# Category Formatting Cheat Sheet

Notes from reviewing the modded source files in `descriptions-mod/` to help reformat the newer `work/responses/ready/` outputs so they slot in cleanly. Each section calls out what goes into `caption` vs `info`, the ordering of mechanical details, colour usage, and a template with placeholders.

## Stat Block Wording Consistency (apply everywhere)

- Damage/buildup lines nearly always start with **`Base …`**: `Base fire damage:`, `Base blood loss accumulation:`. Charged/alt parts sit in parentheses: `(charged)`, `(projectile)`, `(trail)`, `(1 tear)`, `(2 tears)`.
- Status formula headers use only the status name + colon inside the tag, never “Base”: `<font color="#9DD7FB">Frostbite:</font> …`.
- `Category:` is always gold, capitalized, and on its own line at the end of the block.
- Colons live **inside** the `<font>` tag; numbers stay uncoloured after the tag.
- Ordering is consistent: uncharged → charged, primary damage → secondary damage, then buildup, then category.
- **Do NOT create “Base … damage negation” lines.** Damage-negation buffs stay as sentences in the behaviour block: `Increase <font color="#F395C4">physical damage negation</font> by 35% for 70 seconds.`
- **Buff phrasing stays in prose** (e.g., Terra Magica: “increasing the magic damage inflicted … by 35%”) rather than Base-label lines for buffs.
- When in doubt, open the matching `descriptions-mod/*.json` for the category and mirror nearby entries.

## Global Style (from mod author’s wiki notes)

- **Exact numbers everywhere**: effect descriptions should expose base damage, buildup, buff %s, durations, hit counts—anything actionable.
- **Accuracy first**: keep values authoritative; avoid hedging or vague phrases.
- **Lore untouched**: lore/physical description text stays as-is and is kept separate from mechanics.
- **Mechanical clarity**: spell out what the item does, how strong it is, and how long it lasts; keep that in the `info` block after a clean break from lore.
- **Room for detail**: longer mechanical sections are expected (menus were adjusted to fit), so prefer explicit, multi-line stat blocks over compressed prose.
- **When to omit numbers (weapon skills edge case)**: Physical-hit damage for many weapon skills can scale irregularly by weapon type. Use the caption to decide:
  - Captions with `Skill:` (no `Unique`) are shared across many weapons → omit exact physical-hit damage numbers for the melee portion; still include numbers for projectiles, buffs/debuffs, and status buildup.
  - Captions with `Unique Skill:` apply to a single weapon → safe to include exact damage numbers if available.
  Add numbers only where they stay accurate across weapon types to avoid misleading data.
- **Fill gaps with source data**: If an item should have numbers/mechanics but they’re missing, pull them from `work/fex_cache_filtered/` first. If the filtered JSON lacks needed details/context, consult the corresponding HTML in `work/fex_cache/`. If neither has the numbers, leave the field absent rather than guessing.

## Common wording (use these over synonyms)

- Use **“Increases …”** (not “Raises/Boosts”) for buffs; **“Reduces …”** for reductions; **“Negates …”** when fully nullifying.
- Use **“Causes … accumulation”** or **“Inflicts … accumulation”** for status buildup (avoid “builds up”).
- Use **“Restores …”** for HP/FP/stamina returns; **“Recovers”** is avoided in the mod text.
- Use **“Adds … damage”** for buffed damage values on weapons/skills; avoid “Grants” or “Gives”.
- Use **“Allows you to …” / “Enables …”** for key item functions; avoid “Lets you …”.
- Use **“Online multiplayer item.”** as the standard opener for multiplayer tools.
- Extra mechanics not present in the mod should follow the mod’s existing patterns:
  - **Stance damage**: treat like other numeric lines; add a coloured Base line: `<font color="#C0B194">Base stance damage:</font> <value>` and place it alongside other Base damage lines.
  - **Parry immunity / horseback / input locks**: fold into the behaviour paragraph using the same wording style as existing notes (“Cannot be used on horseback.” / “Can be cast on horseback.”). Keep them sentence-level, not headers.
  - **Other reliable numerics** (e.g., poise damage, guard boost effects): use a Base line with the most relevant colour, keeping colon-inside-tag format.

## Incantations (`consumable_Incantation.json`)

- **Caption**: lore only, often two paragraphs separated by a blank line. No mechanics or numbers.
- **Info order**: single concise behaviour sentence (what the cast does), optional casting notes (charging/repeat/horseback) in the same block, blank line, optional status formula block (e.g., Death blight, Frostbite), blank line, stat lines, `Category` last.
- **Stat lines**: one per component; coloured label with the colon inside the tag (e.g., `<font color="#F48C25">Base fire damage:</font> 288`). Keep uncharged → charged ordering, then buildup/auxiliary lines, then category.
- **Category line**: always present, coloured gold: `<font color="#E0B985">Category:</font> Fire Monk`.
- **Colours inside text**: status/damage keywords are coloured when mentioned inside sentences (poison, scarlet rot, etc.).

Example:

```json
{
  "id": <id>,
  "name": "<Incantation Name>",
  "caption": "Lore sentence one.\n\nLore sentence two.",
  "info": "Plain behaviour sentence describing the cast. Include charging/repeat/horseback notes here.\n\n<font color=\"#9DD7FB\">Frostbite:</font> Inflicts damage equal to 10% of <font color=\"#E0B985\">maximum HP</font> plus 30, then increases <font color=\"#E0B985\">all damage received</font> by 20% for 30 seconds.\n\n<font color=\"#57DBCE\">Base magic damage:</font> <value>\n<font color=\"#57DBCE\">Base magic damage (charged):</font> <value>\n<font color=\"#9DD7FB\">Base frostbite accumulation:</font> <value>\n<font color=\"#E0B985\">Category:</font> <Family label>"
}
```

## Sorceries (`consumable_Sorcery.json`)

- **Caption**: lore-only, same two-paragraph style as incantations.
- **Info order**: behaviour sentence(s) first, blank line, optional status formula block (used for frostbite/death blight/blood loss definitions), blank line, stat lines, category last.
- **Stat lines**: coloured labels per damage/buildup component; keep multiple components separated (e.g., explosion vs trail). Colon stays inside the `<font>` tag.
- **Category line**: always coloured gold and last.
- **Casting notes**: horseback/repeat/while in motion sit in the first paragraph, not in stat lines.

Example:

```json
{
  "id": <id>,
  "name": "<Sorcery Name>",
  "caption": "Lore sentence one.\n\nLore sentence two.",
  "info": "Behaviour sentence (what the cast does and any charge/repeat/horseback allowances).\n\n<font color=\"#C84343\">Blood loss:</font> Inflicts damage equal to 15% of <font color=\"#E0B985\">maximum HP</font> plus 100.\n\n<font color=\"#57DBCE\">Base magic damage (projectile):</font> <value>\n<font color=\"#57DBCE\">Base magic damage (explosion):</font> <value>\n<font color=\"#C84343\">Base blood loss accumulation:</font> <value>\n<font color=\"#E0B985\">Category:</font> <Family label(s)>"
}
```

## Key Items (`consumable_Key_Item.json`)

- **Caption**: lore-only; short items may be one line, longer ones use two paragraphs.
- **Info**: pure usage/behaviour text. Multi-step instructions are split with blank lines. No colour tags, stat blocks, or category lines.
- **Tone**: straightforward “Allows/Breaks/Grants” phrasing; avoid numbers unless intrinsic (e.g., “2 keys”).

Example:

```json
{
  "id": <id>,
  "name": "<Key Item>",
  "caption": "Lore line or two.\n\nOptional second lore paragraph.",
  "info": "Direct usage sentence.\n\nFollow-up context or consequences, if any."
}
```

## Physick Tears (`consumable_Physick_Tear.json`)

- **Info opening**: always starts with `Needs to be mixed in the Flask of Wondrous Physick to use.` as its own line.
- **Spacing**: mixing line, blank line, effect description. Add another blank line before any numeric stat lines.
- **Effects**: describe the buff/debuff window plainly (duration, magnitude). Use colour tags on stat names within the text (`<font color="#E0B985">maximum HP</font>` etc.).
- **Stat lines**: used when there are base damage variants (e.g., Ruptured Tear). Labels coloured; colon inside the tag.
- **No category line**.

Example with a stat block:

```json
{
  "id": <id>,
  "name": "<Tear Name>",
  "caption": "Lore sentence about the tear's origin.",
  "info": "Needs to be mixed in the Flask of Wondrous Physick to use.\n\nEffect sentence(s) with duration/magnitude.\n\n<font color=\"#F5EB89\">Base holy damage (1 tear):</font> <value>\n<font color=\"#F5EB89\">Base holy damage (2 tears):</font> <value>"
}
```

## Multiplayer & Tools (`consumable_Tool_Multiplayer.json`)

There are clear subtypes; keep their distinct openings and endings.

- **Summon/invasion/hunter tools**: `caption` contains lore (or a lone dash when none). `info` starts with `Online multiplayer item.` on its own line, then a blank line, then the action/objective sentence(s). No stat block or category.
- **Throwables/craftables (Cracked/Ritual Pots, darts, etc.)**: `info` begins with a single-line action (`Throw at an enemy to inflict <font color="#F48C25">fire damage</font>.`), blank line, optional status definition block, blank line, stat lines (coloured labels with colons inside), blank line, craftability line (`Craftable item using a Cracked Pot.` or `Craftable item.`). Keep any self-inflicted effects in the action sentence.
- **Support trinkets (warming stone, glowstones, HP/FP flasks)**: caption often carries the flavour and sometimes a short mechanic sentence; `info` is minimal (`Craftable item.` or replenishment instructions). If mechanics live in the caption in the source, leave them there and keep `info` terse.
- **Stat lines**: only when damage/buildup numbers exist; same coloured-label format as spells.

Summoning tool template:

```json
{
  "id": <id>,
  "name": "<Tool Name>",
  "caption": "Lore sentence one.\nLore sentence two (no blank line for these short entries).",
  "info": "Online multiplayer item.\n\nCreates a summon sign for cooperative multiplayer. Arrive as a cooperator with the objective of defeating the area boss of the world to which you were summoned."
}
```

Throwable craftable template:

```json
{
  "id": <id>,
  "name": "<Pot/Dart Name>",
  "caption": "Flavour about contents/origin.\n\nOptional second lore line.",
  "info": "Throw at an enemy to disperse a mist that causes <font color=\"#A698F4">sleep accumulation</font> 5 times per second.\n\n<font color=\"#A698F4\">Sleep:</font> Reduces FP by 30 then forces sleep for 60 seconds or until damage is taken.\n\n<font color=\"#F395C4\">Base physical damage:</font> <value>\n<font color=\"#A698F4\">Base sleep accumulation:</font> <value>\n\nCraftable item using a Cracked Pot."
}
```

## Skills (`skill.json`)

- **Caption**: purely the labelled header, colour-tagged, with leading spaces preserved. Normal skills use `Skill:`, special ones use `Unique Skill:`. Example: `<font color="#C0B194">      Skill: Lion's Claw</font>`.
- **Info order**: action description first (can include follow-up inputs), blank line, optional status formula block (e.g., Blood loss explanation), blank line, optional stat lines (coloured labels), with no category line in `info`. Values are integers (unless multipliers); colons sit inside the font tags.
- **Stat lines**: per damage component (projectile, shockwave, etc.) or buildup; use the damage-appropriate colour code.
- **Body/self-damage notes**: sit in the main paragraph (e.g., self-HP cost) before the blank line and stat block.

Example:

```json
{
  "id": <id>,
  "name": "<Skill Name>",
  "category": "skill",
  "caption": "<font color=\"#C0B194\">      Unique Skill: <Skill Name></font>",
  "info": "Concise action description and any follow-up inputs. Include self-costs and buff windows here.\n\n<font color=\"#C84343\">Blood loss:</font> Inflicts damage equal to 15% of <font color=\"#E0B985">maximum HP</font> plus 100.\n\n<font color=\"#F48C25\">Base fire damage (projectile):</font> <value>\n<font color=\"#F48C25\">Base fire damage (wave):</font> <value>"
}
```

## Talismans (`talisman.json`)

- **Caption**: lore only, usually two short paragraphs. Never include mechanics here.
- **Info**: one concise mechanical sentence. Multi-effect talismans list all bonuses in a single sentence with commas; penalties append with “but increases all damage received by X%.” No headers.
- **Resist definitions**: when boosting derived defenses (Immunity/Focus/Robustness/Vitality), add a second paragraph defining the term: `<font color="#E0B985">Robustness:</font> Resistance to <font color="#C84343">blood loss</font> and <font color="#9DD7FB">frostbite</font>.`
- **No category/passive-effect lines.** Stats in sentences get coloured (`<font color="#E0B985">maximum HP</font>`), but there are no standalone stat blocks.
- **Self-activating/conditional effects**: still single sentences (“Negates all fall damage.”, “Increases all damage inflicted by 10% while HP is at maximum.”).

Example:

```json
{
  "id": <id>,
  "name": "<Talisman>",
  "caption": "Lore line one.\n\nLore line two.",
  "info": "Increases <font color=\"#E0B985">maximum HP</font> by 6%.\n\n<font color=\"#E0B985">Vitality:</font> Resistance to <font color=\"#A17945">death blight</font>."
}
```

## Quick differences vs `work/responses/ready/`

- Category labels for spells should be coloured and sit on their own line at the end; ready outputs often leave them uncoloured or inline.
- Stat labels keep the colon inside the `<font>` tag; ready data sometimes colours only the label text and leaves the colon/plain text outside.
- Behaviour paragraphs are short and mechanical with numbers pulled into the stat block; ready entries sometimes mix numeric values into the opening sentences.
- Ensure the standard opening lines stay intact (`Online multiplayer item.`, `Needs to be mixed...`) and that craftable throwables end with their `Craftable item...` line after a blank spacer.
