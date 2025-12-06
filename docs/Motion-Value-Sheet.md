# Motion-Value Sheet → Stats Block Mapping (Spec for Agents)

This report describes how to turn the motion-values / attack-data spreadsheet  
(e.g. “ER – Motion Values and Attack Data (App Ver. 1.16.1)”) into the **stats
section** used in our item descriptions.

The goal is *not* to reproduce exact in-game damage, but to:

- use the sheet’s numbers as **relative base values** for each skill
- tag those numbers with the **correct scaling stats**
- clearly distinguish **bullet arts** vs **weapon-hit arts**
- handle both **unique skills** and **Ash of War skills**.

The script you write should only read the spreadsheet + small bits of metadata,
and then output structured stats blocks (JSON or text) ready to drop into
`skill.json` / description templates.

---

## 1. Inputs and expected columns

The agent will be given:

- the motion-value / attack-data spreadsheet (as CSV/XLSX)
- a Google doc (or notes) that explains:
  - bullet hit formula
  - stat scaling for bullet arts (base_scaling, affinity multipliers, etc.)
  - any per-skill notes

At minimum, assume the sheet has **one row per skill-hit** with columns along
the lines of:

- `SkillID` / `AoWID` / `Name`  
- classification:
  - `Type` or `HitType` (e.g. bullet / weapon / hybrid)  
  - `Unique` vs `AshOfWar`  
- elemental base values (per hit):
  - `AtkPhys`, `AtkMag`, `AtkFire`, `AtkLtng`, `AtkHoly`  
- motion values (per hit):
  - `PhysMV`, `MagMV`, `FireMV`, `LtngMV`, `HolyMV`  
- (optionally) stance / poise / guard data:
  - `Stance`, `Poise`, `GuardBreakMV`, etc.  
- scaling metadata:
  - `OverwriteScaling` (e.g. Dex / Int / Fai / Dex+Fai)  
  - `Affinity` or `SubCategory` (e.g. “Dragon Cult Skill”, “Blood Art”)  
- hit labelling:
  - `HitIndex`, `Phase`, `Note` (e.g. “initial spin”, “follow-up #1”)

If the actual column names differ, do a one-time mapping at the top of your
script and use consistent internal names.

---

## 2. Skill categories

Every skill should be classified into one (or more) of:

1. **Bullet arts** (type-3 in the guide):  
   - damage comes from a projectile / shockwave / blood blade, not the weapon  
   - uses the **bullet formula**; ignores the weapon’s AR  
   - depends on:
     - weapon upgrade level  
     - 1–2 stats (by affinity)  
     - weapon affinity (affects scaling multipliers)

2. **Weapon-hit arts** (type-1):  
   - hitbox is the actual weapon  
   - motion values scale the weapon’s AR (we already have relative MVs in the sheet)

3. **Hybrid arts**:  
   - have both weapon-hit components and bullet components  
   - e.g. Magma Shower (weapon spins + magma pools)

Also distinguish:

- **Unique skills** (on special weapons only)  
- **Ashes of War** (transferable arts)

The classification will usually be a combination of:

- sheet’s `Type`/`SubCategory`  
- our pre-known classification list (we can maintain a small “known bullet arts”
  mapping if needed).

---

## 3. Target stats block style

We want **simple, per-hit lines** of the form:

### 3.1 Bullet components

For bullet hits:

- single-element, single-stat example:

  ```text
  Lightning damage: 50 (dexterity)
  ```

- dual-stat example:

  ```text
  Holy damage: 40 (faith + strength)
  ```

Where:

- the number (`50`, `40`) is the **base damage** from the sheet (e.g. `AtkLtng`,
  `AtkHoly`) for that bullet component.
- the scaling tag `(dexterity)` / `(faith + strength)` comes from
  `OverwriteScaling` and any affinity tag.

You do **not** apply the full bullet formula here; you just present the
base factor + stat tags. The bullet formula is *implicit*.

### 3.2 Weapon-hit components (motion values)

For weapon hits, we use motion values as **relative damage units**:

Example (Magma Shower):

```text
Slash damage (initial spin): 100
Slash damage (follow-up, first hit): 65
Slash damage (follow-up, second hit): 120
```

Where `100 / 65 / 120` are the `PhysMV` (or common MV) values for those hits.

If both physical and elemental MVs are identical per hit (as is often the case),
you can just pick one MV (e.g. physical) and label it by **damage type and phase**.

### 3.3 Stance / poise / secondary metrics

If stance / poise data is available per hit, add lines like:

```text
Stance damage (spin): 18
```

Use whatever stance value is associated with the key hit/phase. If there are
multiple, you can:

- show only the main one, or
- show multiple labelled lines as with motion values.

---

## 4. Mapping rules from sheet → stats lines

### 4.1 Bullet hits (type-3 skills, e.g. Blinkbolt)

For each bullet-type skill (or bullet component of a hybrid):

1. **Choose the primary element** from the `AtkXxx` columns:

   - if only one of `AtkPhys/Mag/Fire/Ltng/Holy` is non-zero, that’s the element.
   - if the docs say it’s multi-element, pick the dominant one or add lines per element.

2. **Take base damage**:

   ```text
   base_damage = AtkElement (e.g. AtkLtng)
   ```

3. **Resolve scaling stats**:

   - from `OverwriteScaling` and/or `SubCategory`:

     - `Dex`, `Str`, `Int`, `Fai`, `Arc`, or combinations
   - format as:

     - `(dexterity)`
     - `(faith + intelligence)` etc.

4. **Emit bullet line**:

   ```text
   <Element> damage: <base_damage> (<scaling_stat or stat list>)
   ```

Example for Blinkbolt (from the sheet):

```text
Lightning damage: 50 (dexterity)
```

You do **not** include the bullet formula in the text; you just encode the
base skill power and the stats that affect it.

### 4.2 Weapon hits (motion values)

For every weapon-hit row for a skill:

1. Identify **phase** and **hit role** from any of:

   - the sheet’s `Note` / `Phase` / `HitIndex` columns
   - a small hardcoded label map for tricky skills

2. For per-hit motion values, choose a representative MV:

   - if all `PhysMV/MagMV/...` are equal → just use that value.
   - if they differ, prefer:

     - `PhysMV` for physical slashes
     - or a per-element MV if we want to split them more finely.

3. Emit labelled lines:

   ```text
   Slash damage (initial spin): 100
   Slash damage (follow-up, first hit): 65
   Slash damage (follow-up, second hit): 120
   ```

Where the label in parentheses is derived from the phase/hit metadata.

### 4.3 Stance / poise

If stance-like columns exist:

- pick the relevant value(s) per hit or phase
- emit as:

  ```text
  Stance damage (spin): 18
  ```

If you only have one clear stance number per skill, it’s fine to show one
line for the primary hit.

---

## 5. Unique skills vs Ashes of War

### 5.1 Bullet scaling difference (engine side)

From community research:

- **Ash of War bullet arts** (infusible weapons):

  - base bullet scaling per stat:

    - single stat: ~0.25
    - dual stat (quality/cold): ~0.15 each
  - `affinity_scaling_multiplier` depends only on:

    - affinity
    - upgrade level
  - weapon **model** doesn’t matter; only affinity + upgrade.

- **Unique skills**:

  - often use the weapon’s own scaling as `base_scaling` for bullet hits.
  - may have different base damage and stat weights.

However, **we do not need to encode this formula in the text**. For both
unique and AoW bullet arts, the stats lines simply show:

```text
<Element> damage: <base_damage> (<scaling_stats>)
```

The actual numeric differences in `base_scaling` and multipliers are not visible
to the user and don’t need to be part of the stats block; the script just has to
pull the correct `base_damage` and scaling stat tags from the sheet/docs.

### 5.2 Script behaviour differences

Script behaviour should be very simple:

- **Unique skills**:

  - They’re already clearly flagged as unique in the flavour text (“Unique Skill: …”).
  - Use exactly the same mapping rules as above; just read their specific
    base damage and MVs from the sheet.

- **Ashes of War**:

  - Same mapping rules; just note that their bullet base damage and scaling stats
    are those used across all weapons that equip the AoW.
  - If we want to distinguish them programmatically, we can add a `kind` field:

    ```json
    "kind": "aow_bullet"
    ```

    or

    ```json
    "kind": "unique_bullet"
    ```

But the **output stats lines** for the user are formatted identically.

---

## 6. Suggested script output schema (for agents)

For each skill `id`, script should produce something like:

```jsonc
{
  "id": 1172,
  "name": "Magma Shower",
  "kind": "unique_hybrid",
  "stats": {
    "bullet": [
      {
        "element": "fire",
        "label": "magma",
        "base_damage": 30,
        "scales_with": ["faith"],       // example; actual stats from sheet/docs
        "line": "Base fire damage (magma): 30"
      }
    ],
    "weapon_hits": [
      {
        "label": "initial spin",
        "damage_type": "slash",
        "mv": 100,
        "line": "Slash damage (initial spin): 100"
      },
      {
        "label": "follow-up, first hit",
        "damage_type": "slash",
        "mv": 65,
        "line": "Slash damage (follow-up, first hit): 65"
      },
      {
        "label": "follow-up, second hit",
        "damage_type": "slash",
        "mv": 120,
        "line": "Slash damage (follow-up, second hit): 120"
      }
    ],
    "stance": [
      {
        "label": "spin",
        "value": 18,
        "line": "Stance damage (spin): 18"
      }
    ]
  }
}
```

Downstream, the description builder just concatenates the `"line"` fields into
the stats section.

Agents should focus on:

1. correctly parsing the sheet into per-skill bullet + weapon hit records,
2. mapping elemental base values and overwrite scaling into `line` strings for bullet hits,
3. mapping motion values into `line` strings for weapon hits,
4. adopting a consistent naming scheme for `label` so the text reads naturally.

---

## 7. Summary for the agent

- **You do not need any game code or live damage sampling.**
- Treat the motion-values spreadsheet as the authoritative per-skill base
  damage + MV table.
- For **bullet components**:

  - choose element from `AtkXxx` columns
  - base damage = that `AtkXxx`
  - scaling tags from `OverwriteScaling` / affinity metadata
  - emit `"Element damage: N (stat tags)"`.
- For **weapon components**:

  - use MV as the number
  - label phases clearly in the text
- Apply the same mapping to **unique** and **AoW** skills; uniqueness is just
  a tag, not a different text format.
- Output structured JSON or similar that includes both:

  - raw numbers and labels
  - prebuilt `line` strings for direct insertion into descriptions.
