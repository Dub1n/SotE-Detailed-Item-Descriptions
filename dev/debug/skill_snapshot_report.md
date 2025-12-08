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

- **Ordering fixed, grouping regressed**: 1h/2h ordering is now stable in the generated blocks, but merging was tightened to avoid stance reordering. This leaves multiple per-weapon blocks instead of the snapshot’s grouped outputs (e.g., War Cry and Barbaric Roar now emit many per-weapon blocks; snapshot expected a smaller set).
- **Weapon coverage drift**: War Cry, Barbaric Roar, and Aspects of the Crucible: Wings show both missing and extra blocks relative to the snapshot due to over-splitting by weapon and lack of stance-range merging. Shield Strike also shows extra aggregated blocks vs. the per-shield splits in the snapshot.
- **Value mismatch**: Bloody Slash still diverges on the flat damage line (current 345 vs. snapshot 322 for the base entry); stance/lacking lines match.
- **Snapshot diff status (current run)**: Differences remain for War Cry (missing 4, extra 10 blocks), Barbaric Roar (missing 5, extra 12), Aspects of the Crucible: Wings (missing 3, extra 7), Bloody Slash (1 content diff), Shield Strike (missing 1, extra 2), and Revenger’s Blade (1 reorder-only).
- **Lacking FP padding**: Still correct after prior fixes (Ghostflame Call remains clean).

These files are for reference only; no script changes were made as part of this snapshot.
