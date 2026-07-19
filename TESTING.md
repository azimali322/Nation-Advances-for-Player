# Handicap Advances for Player — In-Game Test Plan (v1.0)

Version 1.0 ships the all-or-nothing unlock toggle (character interactions). Work through the checklist in order; note results next to each box.

## Setup

- [ ] The mod folder lives in `Documents/Paradox Interactive/Europa Universalis V/mod/Nation-Advances-for-Player` and the launcher lists **Handicap Advances for Player** version 1.0 for game version 1.3.
- [ ] Subscribe to / enable **Community Mod Framework** (the mod declares it as a dependency).
- [ ] Create a playset with both mods enabled (CMF first, then this mod) and launch the game.

## Smoke test (no toggle yet — mod should be invisible)

- [ ] Start a new game as **France**.
- [ ] Open the Advances screen: France's own unique advances (e.g. *French Tradition*, *Élan*) appear exactly as in the base game.
- [ ] Other nations' advances (e.g. English, Ottoman) are **not** visible/researchable.
- [ ] Check `Documents/Paradox Interactive/Europa Universalis V/logs/error.log` for new errors mentioning `advances`, `hafp`, or `character_interactions`. A clean log here is the main 1.3-compatibility check.

## Enable toggle

- [ ] On your own nation screen, find the character interaction **Unlock All Advances (Handicap Advances for Player)** and use it.
- [ ] Advances screen now shows other nations' unique advances as researchable (spot-check a few: English, Ottoman/`TUR`, a culture advance, a religion advance, a government advance for a government type you don't have).
- [ ] `monarchy_reform_traditions_advance` (Age of Traditions, unlocks the Autocracy reform) is researchable — this is the advance the original mod missed; verify it appears even for a non-monarchy country.
- [ ] Institution-gated advances (e.g. the New World tree) are researchable without the institution embraced (the mod also bypasses `allow` institution gates, matching the original mod).
- [ ] Start researching one foreign advance and confirm it completes and applies its modifier.
- [ ] AI countries do **not** get access (spot-check an AI neighbor via observe/tag-switch if you use debug tools, or just confirm nothing odd in AI research).

## Disable toggle

- [ ] Use **Remove Access to All Advances (Handicap Advances for Player)**.
- [ ] Newly-opened foreign advances are no longer researchable. (Note: Paradox notes advances do not become retroactively *visible*; some UI staleness right after toggling is acceptable — re-open the Advances screen.)
- [ ] Advances already researched keep their effects.

## Persistence

- [ ] With the toggle **enabled**, save, quit to menu, reload: foreign advances are still researchable (the `hafp_all_advances_enabled` variable persists in the save).
- [ ] With the toggle **disabled**, save and reload: behavior stays vanilla.

## Localization

- [ ] Both interactions show proper English names/descriptions, not raw `hafp_...` keys.

## Multiplayer / edge cases (optional)

- [ ] Hot-joining or MP: only the player who used the interaction gets the unlocks.
- [ ] Country switch (e.g. after forming a nation / tag switch): unlocks persist, since `has_or_had_tag` original conditions and the variable both live on the country.

## Known limitations in v1.0 (expected, not bugs)

- No per-continent/region/area selection yet — only the global toggle (see REQUIREMENTS.md items 1–6 for the roadmap).
- No CMM settings menu yet; the toggle is a character interaction, as in the original mod.
- Advances that were already *visible* stay visible after disabling the toggle until the game refreshes the advances view.

## Reporting

When something fails, note: country played, advance id (hover tooltips usually show it with debug mode `-debug_mode`), what you expected, what happened, and paste any related `error.log` lines. Add findings to a `TEST-RESULTS.md` or straight into GitHub issues.
