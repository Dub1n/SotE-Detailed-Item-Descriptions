## Colours

HEADER = "#C0B194"
GOLD = "#E0B985"
PHYSICAL = "#F395C4"
MAGIC = "#57DBCE"
FIRE = "#F48C25"
LIGHTNING = "#FFE033"
HOLY = "#F5EB89"
FROST = "#9DD7FB"
DEADLY POISON =
POISON = "#40BF40"
ROT = "#EF7676"
BLEED = "#C84343"
MADNESS_COLOR = "#EEAA2B"
SLEEP_COLOR = "#A698F4"
DEATH_COLOR = "#A17945"

## Buildups

<font color=\"#40BF40\">Poison:</font> Inflicts damage equal to 0.07% of <font color=\"#E0B985\">maximum HP</font> plus 7, every second for 90 seconds.

<font color=\"#40BF40\">Deadly Poison:</font> Inflicts damage equal to 0.14% of <font color=\"#E0B985\">maximum HP</font> plus 14, every second for 30 seconds.

<font color=\"#EF7676\">Scarlet Rot:</font> Inflicts damage equal to 0.33% of <font color=\"#E0B985\">maximum HP</font> plus 33, every second for 90 seconds.

<font color=\"#C84343\">Blood Loss:</font> Inflicts damage equal to 15% of <font color=\"#E0B985\">maximum HP</font> plus 100.
(hemorrhage is the same as blood loss; swap hemorrhage for blood loss if you come across it)

<font color=\"#9DD7FB\">Frostbite:</font> Inflicts damage equal to 10% of <font color=\"#E0B985\">maximum HP</font> plus 30, then increases <font color=\"#E0B985\">all damage received</font> by 20% for 30 seconds.

<font color=\"#A698F4\">Sleep:</font> Reduces FP by 30 then forces the enemy to sleep for 60 seconds, or until any damage is received, typically allowing for a critical attack.

<font color=\"#EEAA2B\">Madness:</font> Inflicts damage equal to 15% of <font color=\"#E0B985\">maximum HP</font> plus 100 and reduces FP equal to 10% of <font color=\"#E0B985\">maximum FP</font> plus 30. Only on Tarnished.

<font color=\"#A17945\">Death Blight:</font> Instant death. Only effective against Tarnished.

When combining buildup definitions, separate them with a blank line (`\n\n`)

Use `Deadly Poison` when the source inflicts the higher-damage, shorter-duration variant rather than regular `Poison`; check that it is actually referred to as Deadly Poison anywhere in the cache before labelling it as Deadly Poison.

## Resistances

<font color=\"#E0B985\">Immunity:</font> Resistance to <font color=\"#40BF40\">poison</font> and <font color=\"#EF7676\">scarlet rot</font>.

<font color=\"#E0B985\">Robustness:</font> Resistance to <font color=\"#C84343\">blood loss</font> and <font color=\"#9DD7FB\">frostbite</font>.

<font color=\"#E0B985\">Focus:</font> Resistance to <font color=\"#A698F4\">sleep</font> and <font color=\"#EEAA2B\">madness</font>."

<font color=\"#E0B985\">Vitality:</font> Resistance to <font color=\"#A17945\">death blight</font>

When combining multiple resistances, separate them with a newline, not a blank line, (`\n`)

## Damage Types

If a damage type scales with any stat(s), write it out in the stats block with:
  `<font color=\"{type colour}\">Base {Type} damage:</font> x (<font color=\"#E0B985\">{Stat}</font>)`
If a damage type doesn't scale with stats, write it out in the stats block with:
  `<font color=\"{type colour}\">{Type} damage</status colour>: x`
If the damage scales and is for a part of the attack/effect, add that part in brackets after "damage":
  `<font color=\"{type colour}\">Base {Type} damage ({part}):</font> x (<font color=\"#E0B985\">{Stat}</font>)`
If the damage doesn't scale and is for a part of the attack/effect, add that part in brackets after "damage":
  `<font color=\"{type colour}\">{Type} damage ({part}):</font> x`

## Status Accumulation

If a status buildup scales with any stats, write it out in the stats block with:
  `<font color=\"{status colour}\">Base {Status Name} accumulation</status colour>: x (<font color=\"#E0B985\">{Stat}</font>)`
  `<font color=\"{status colour}\">Base {Status Name} accumulation</status colour>: x (<font color=\"#E0B985\">{Stat}</font>, <font color=\"#E0B985\">{Stat 2}</font>)`
  etc.
If a status buildup doesn't scale with stats, write it out in the stats block with:
  `<font color=\"{status colour}\">{Status Name} accumulation</status colour>: x`
If a status buildup scales with any stats and is part of the attack/effect, write it out in the stats block with:
  `<font color=\"{status colour}\">Base {Status Name} accumulation ({part})</status colour>: x (<font color=\"#E0B985\">{Stat}</font>)`
If a status buildup doesn't scale with any stats and is part of the attack/effect, write it out in the stats block with:
  `<font color=\"{status colour}\">{Status Name} accumulation ({part})</status colour>: x`

## Notes

We are Capitalizing the names of the status buildups, including both words.
When there are multiple of either buildups or resistances, we need to order them in the order they are in here, both in the buildup stats block and in the definition block. This is less important in the descriptive block, but should be applied if it doesn't disrupt the flow of the text i.e. it is a simple rearrangement.
The definition block goes below the descriptive block and above the stats block (if there is a stats block)
When Fextralife shows a value scaling table or provides multiple values depending on the level of a given stat, write `Base` for that value and provide the stats that scale it after the number. Use the minimum value listed as the `Base` value.
If a value doesn't scale with any stats, do *not* write `Base` for that value, and do not note that it doesn't have scaling.
Do *not* include scaling details in the description block of the item's info, only with the stat name in brackets after the value that scales.
Do *not* include the damage or buildup values in the description block, only in the stat block. Exception: lasting buffs or one-off synergies that change the weapon/player after the skill/item is used (e.g. added elemental damage or buildup on the armament) belong in the description block, not the stat block.
If a weapon or entity, such as the player, gains a lasting effect from an item, that information goes in the description block using the appropriate Casing and coloring, with numbers where available. For instance, when a weapon gains a status buildup damage: `The armament retains its imbuement for 45 seconds, which adds 160 <font color=\"#FFE033\">lightning damage</font> and 80 <font color=\"#9DD7FB\">frostbite accumulation</font>`
If an item applies an effect to the player as a one-off, such as on-use or on-hit, that information goes in the description block, not in the stats block: `...but also 200 <font color=\"#40BF40\">poison accumulation</font> on yourself.`
When referring to status buildup in the description block, "buildup" is acceptable; in the stats block use "accumulation" with the capitalized status name and proper color.
Use "<font color=\"#C0B194\">Stance damage</font>" rather than "poise" numbers; if a value is listed as poise damage, rename it to stance damage rather than listing both.
If damage is dealt over a period of time, it is formatted as:
  `<font color={color}>[Base ]{Damage} per tick[ {part}]:</font> x[ (<font color=\"#E0B985\">{Stat}</font>)]`
  where parts in the `[square brackets]` are optional based on whether it is scaling and/or for part of the attack
  The duration and rate of the ticks is to be noted in the description block if available; there may be a standard "tick rate" in which case no rate is needed in the body, just the duration, and the amount per tick is noted in the stats block.
If a value scales with the weapon's stat scaling, that is formatted as: `... x (weapon <font color=\"#E0B985\">{Stat}</font> scaling)`
  For example, with the Poisonous Mist, the wiki says: "Both the poison buildup of the mist and on the armament can be affected by the Arcane stat if the weapon has Arcane scaling.", meaning that our description has `<font color=\"#40BF40\">Base poison accumulation per tick:</font> 120 (weapon <font color=\"#E0B985\">Arcane</font> scaling)`

## Values

For the Ice Lightning Sword, one user on Fextralife commented: "The scaling on the lightning strike attack (AtkParam_Pc id 30090011) seems to be bugged - it scales from Int and Fai, but Dragonscale Blade has 0 in both which results in no stat scaling. The ID is also sus because three other attacks of this ash have IDs of 300900110, 300900113 and 300900114 - it looks like the devs missed one digit and it should have been 300900111 instead."
  this might help show how we are to find the values for these attacks and scaling paramters if they aren't mentioned in the `fex_cache`/`fex_cache_filtered`.

## Examples

```json
  {
    "id": 330,
    "name": "Fetid Pot",
    "caption": "A cocktail of effluents is sealed inside. As the mixture ferments, toxins are produced alongside a putrid stench that seeps out once ripe.\n\nPush someone in a privy; expect to get dung on your hands.",
    "info": "Throw at an enemy to cause <font color=\"#40BF40\">poison accumulation</font> on target, but also 200 <font color=\"#40BF40\">poison accumulation</font> on yourself.\n\n<font color=\"#40BF40\">Poison:</font> Inflicts damage equal to 0.14% of <font color=\"#E0B985\">maximum HP</font> plus 12, every second for 30 seconds.\n\n<font color=\"#F395C4\">Base physical damage:</font> 1 (<font color=\"#E0B985\">Strength</font>)\n<font color=\"#40BF40\">Base poison accumulation:</font> 250"
  },
  {
    "id": 2000330,
    "name": "Hefty Fetid Pot",
    "caption": "Craftable item prepared using a capacious cracked pot.\nA heaping mass of effluents is sealed inside. As the mixture ferments, toxins are produced alongside a putrid stench that seeps out once ripe.\n\nPush someone in a privy; expect to get dung on your hands.",
    "info": "Throw to splatter enemies with <font color=\"#40BF40\">Deadly Poison</font> buildup while dealing strike impact.\nAlso inflict 200 <font color=\"#40BF40\">Deadly Poison</font> accumulation on yourself.\n\n<font color=\"#40BF40\">Deadly Poison:</font> Deals 0.14% of <font color=\"#E0B985\">maximum HP</font> plus 12 per second for 30 seconds (4.2% of <font color=\"#E0B985\">maximum HP</font> plus 360 total).\n\n<font color=\"#F395C4\">Base physical damage</font>: 105 (<font color=\"#E0B985\">Strength</font>)\n<font color=\"#C0B194\">Stance damage</font>: 5\n<font color=\"#40BF40\">Base Deadly Poison accumulation</font>: 500 (<font color=\"#E0B985\">Arcane</font>)"
  },
  {
    "id": 2000670,
    "name": "Hefty Rot Pot",
    "caption": "Craftable item prepared using a capacious cracked pot.\nA goodly amount of materials is sealed inside.\n\nRot is one of the divine elements of the outer gods, and eats away at life like a vicious plague.",
    "info": "Throw to apply <font color=\"#EF7676\">Scarlet Rot</font> to an enemy.\n\n<font color=\"#EF7676\">Scarlet Rot:</font> Inflicts damage equal to 0.33% of <font color=\"#E0B985\">maximum HP</font> plus 33, every second for 90 seconds.\n\n<font color=\"#F395C4\">Base physical damage</font>: 105 (<font color=\"#E0B985\">Strength</font>)\n<font color=\"#C0B194\">Stance damage</font>: 5\n<font color=\"#EF7676\">Scarlet Rot accumulation</font>: 400"
  },
  {
    "id": 1340,
    "name": "Dappled White Cured Meat",
    "category": "consumable_Tool_Multiplayer",
    "caption": "",
    "info": "Increases <font color=\"#E0B985\">immunity</font>, <font color=\"#E0B985\">robustness</font>, and <font color=\"#E0B985\">focus</font> by 75 for 120 seconds.\n\n<font color=\"#E0B985\">Immunity:</font> Resistance to <font color=\"#40BF40\">poison</font> and <font color=\"#EF7676\">scarlet rot</font>.\n<font color=\"#E0B985\">Robustness:</font> Resistance to <font color=\"#C84343\">blood loss</font> and <font color=\"#9DD7FB\">frostbite</font>.\n<font color=\"#E0B985\">Focus:</font> Resistance to <font color=\"#A698F4\">sleep</font> and <font color=\"#EEAA2B\">madness</font>."
  },
  {
    "id": 228,
    "name": "Poisonous Mist",
    "category": "skill",
    "caption": "<font color=\"#C0B194\">      Skill: Poisonous Mist</font>",
    "info": "Imbue the armament with poison and do a hortizontal slash to produce a poisonous cloud for 2 seconds. The armament remains imbued with poison for 40 seconds, adding 60 <font color=\"#40BF40\">poison accumulation</font> per attack (counts as a weapon buff).\n\n<font color=\"#40BF40\">Poison:</font> Inflicts damage equal to 0.1% of <font color=\"#E0B985\">maximum HP</font> plus 8, every second for 40 seconds.\n\n<font color=\"#C0B194\">Stance damage</font>: 12\n<font color=\"#40BF40\">Base poison accumulation per tick:</font> 120 (weapon <font color=\"#E0B985\">Arcane</font> scaling)"
  },
  {
    "id": 1043,
    "name": "Ice Lightning Sword",
    "category": "skill",
    "caption": "<font color=\"#C0B194\">      Unique Skill: Ice Lightning Sword</font>",
    "info": "Stomp as you raise the armament to imbue it with icy lightning, then slam it to the ground to conjure a bolt of icy lightning directly in front of you and a brief shockwave of lightning around you. The armament retains its imbuement for 45 seconds, which adds 160 <font color=\"#FFE033\">lightning damage</font> and 80 <font color=\"#9DD7FB\">frostbite accumulation</font>.\n\n<font color=\"#9DD7FB\">Frostbite:</font> Inflicts damage equal to 10% of <font color=\"#E0B985\">maximum HP</font> plus 30, then increases <font color=\"#E0B985\">all damage received</font> by 20% for 30 seconds.\n\n<font color=\"#FFE033\">Lightning damage (bolt):</font> 149\n<font color=\"#FFE033\">Lightning damage (shockwave):</font> 69\n<font color=\"#9DD7FB\">Frostbite accumulation (bolt and shockwave):</font> 70"
  },
  {
    "id": 5010,
    "name": "Explosive Ghostflame",
    "category": "consumable_Sorcery",
    "info": "Cause a large ghostflame explosion around you which will leave 5 ghostflame trails on the ground for 5 seconds.\n\n<font color=\"#9DD7FB\">Frostbite:</font> Inflicts damage equal to 10% of <font color=\"#E0B985\">maximum HP</font> plus 30, then increases <font color=\"#E0B985\">all damage received</font> by 20% for 30 seconds.\n\n<font color=\"#57DBCE\">Base magic damage (explosion):</font> 312 (<font color=\"#E0B985\">Dexterity</font>)\n<font color=\"#57DBCE\">Base magic damage (trail):</font> 60 (<font color=\"#E0B985\">Intelligence</font>)\n<font color=\"#9DD7FB\">Frostbite accumulation (explosion):</font> 130 (<font color=\"#E0B985\">Faith</font>)\n<font color=\"#9DD7FB\">Frostbite accumulation per tick (trail):</font> 38 (<font color=\"#E0B985\">Faith</font>)\n<font color=\"#E0B985\">Category:</font> Death"
  },
  {
    "id": 7240,
    "name": "Scarlet Aeonia",
    "category": "consumable_Incantation",
    "caption": "Technique of Malenia, the Goddess of Rot.\n\nEach time the scarlet flower blooms, Malenia's rot advances. It has bloomed twice already. With the third bloom, she will become a true goddess.",
    "info": "Incarnate a giant flower that blooms into an explosion of scarlet rot mist which lingers for 4 seconds.\n\n<font color=\"#EF7676\">Scarlet rot:</font> Inflicts damage equal to 0.33% of <font color=\"#E0B985\">maximum HP</font> plus 13, every second for 90 seconds.\n\n<font color=\"#F395C4\">Base physical damage (explosion):</font> 362\n<font color=\"#F395C4\">Base physical damage (mist):</font> 60\n<font color=\"#EF7676\">Base scarlet rot accumulation (explosion):</font> 150\n<font color=\"#EF7676\">Base scarlet rot accumulat    "id": 2000600,
    "id": 2000380,
    "id": 2000370,
    "id": 2000360,
    "id": 2000340,
ion (mist):</font> 50\n<font color=\"#E0B985\">Category:</font> Servants of Rot"
  },
```
