# Skill Snapshot Report

This snapshot captures the current generated stats for selected skills after recent refactors.

## Included skills
- Carian Sovereignty
- Swift Slash
- Bubble Shower
- Revenger's Blade
- Moonlight Greatsword
- Barbaric Roar
- Ghostflame Call
- Shield Strike
- War Cry
- Aspects of the Crucible: Wings
- Bloody Slash

Source data: `work/skill_stats_from_sheet.json` (filtered into `dev/debug/skills_snapshot.json`).

## Observations
- **Weapon grouping**: Some entries still aggregate multiple weapon categories even when non-stance values differ (e.g., War Cry, Aspects of the Crucible: Wings). Stance ranges may therefore hide per-weapon differences.
- **Missing weapons**: Certain skills (e.g., Bloody Slash) do not list all compatible weapons in the generated output.
- **Stance ranges**: Merging logic currently computes stance ranges across grouped variants, but when non-stance lines differ inside a group, stance ranges can misrepresent the underlying per-weapon values.
- **Lacking FP padding**: Recent fixes restrict lacking brackets to attack parts that actually have lacking data; examples like Ghostflame Call show expected `[0]` padding, while Barbaric Roar heavy follow-ups now avoid zero-only lacking brackets.

These files are for reference only; no script changes were made as part of this snapshot.
