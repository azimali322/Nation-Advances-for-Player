# Handicap Advances for Player — Requirements

Living document. Update this file as new requirements are added.

**Premise:** a handicap/cheat mod to help players. The player can select all or some of the custom (unique) advances they would like to play with, alongside the advances of the nation they are already playing. Instead of only giving *all* advances to the player (which it can also do), the player can custom-select the specific custom advances they want from a certain continent, region, or area — covering all the custom nations in that continent/region/area. The base "all advances" behavior stays available as a single toggle.

---

## 1. Selectable custom advances by continent / region / area

- All custom nation advances must be individually toggleable/selectable for the player.
- Organization hierarchy: **Continent → Region → Area**, with each custom nation's advances assigned by where that nation sits in the world.
  - First map each custom advance to its country/nation (from the advance files' `has_or_had_tag` gates).
  - Then place the nation geographically using the game files (or the EU5 wiki if needed).
- Additional standalone categories (selectable individually, outside the geography tree):
  - **Culture advances** and **culture group advances** — organized by where the culture exists in the game world.
  - **Government advances** and **religion advances** — no region/area organization needed.
- Selecting/toggling a continent, region, or area enables/disables all the custom advances under it for the player.
- **Overlaps:** a nation/advance may appear under more than one continent/region/area. Keep duplicate instances under each, but an advance already unlocked via one selection stays unlocked; selecting a second group containing the same advance must not double-apply it.
- A **Select All** button at the top enables research of all the custom advances at once.

## 2. Settings tab

A second tab called **Settings** containing:

- **Unlock all advances** toggle (top): unlocks all continents/regions/areas for the player — mimics the original "all advances" mod behavior. This button and the "Select All" button in the selection tab mirror each other: toggling one dictates the state of the other. This is the default format.
- **Research all custom advances** button: instantly researches all the *custom-only* advances for the player. Default game advances stay un-researched (the player still researches those normally).
- **Research all advances** button (below the previous): instantly researches *all* advances for the player, including default advances.
- Each research button has an option to apply to:
  - only advances available within the player's **embraced institutions**, or
  - **all** advances regardless of embraced institutions.
- **Enabled** setting (off by default): master switch for the mod.
  - When turned on, it detects the country/nation the player is playing and mirrors the advances the player already has — i.e. behavior is unchanged from the base game until the player selects advances outside the ones their nation gets by default.
  - Only when the player selects advances beyond their defaults do additional custom advances unlock.
  - When "all advances" is selected, all custom advances in the game become researchable by the player.

## 3. Hover tooltips

- Custom nation advances must have hover-over text (tooltips).

## 4. Base / current-nation preset

- A "base/current nation" version/preset: when selected, the player's current nation, culture, culture group, and religion advances are pre-selected, matching exactly what they would see in the base game — including the default advances every nation gets.

## 5. Era research buttons (Settings)

- A button that researches all advances for the **era the game is currently in**.
- A button that researches all advances for the **era(s) before** the current one.

## 6. Era unlock option (Settings)

- A settings option to **unlock** (make researchable, not auto-research) all advances in a **specific era**.

---

## Non-functional / setup requirements

- Mod format: Community Mod Framework (CMF) mod template/format, with CMF declared as a dependency in `.metadata/metadata.json`.
- Game version: **1.3**, mod version: **1.0**, name: **Handicap Advances for Player**.
- Advance overrides are regenerated from the local vanilla game files via `tools/generate_advances.py` so the mod re-baselines cleanly after game patches.

## Implementation notes / accepted adaptations

- Geography source: nations are placed by their **1337 capital** (formable nations by their formable-definition regions; a small manual table covers the few tags with neither). Confirmed by user 2026-07-19.
- Cultures are placed by where their pops live in the 1337 setup (language- and culture-group-gated advances are expanded to member cultures first).
- Because the selection UI spans four continent tabs, the "select all" control exists **once**, in the Settings tab (*Unlock All Custom Advances*), with per-continent *All of &lt;continent&gt;* toggles at the top of each continent tab. This satisfies the mirroring requirement (item 2) with a single shared setting instead of two synced buttons.
- Instant research uses the engine effect `research_advance = advance_type:<id>`; the institution option is implemented per-advance from the vanilla `has_embraced_institution` requirements.

## Changelog

- **2026-07-19** — Initial requirements captured (items 1–6). v1.0 implements the all-or-nothing unlock toggle (port of "All Advances Unlocked" into CMF format, re-baselined to 1.3).
- **2026-07-19 (phase 2)** — CMM menu implemented: continent/region/area toggles (items 1), Settings tab with Enabled master switch, unlock-all, era unlocks, research buttons with institution scope (items 2, 5, 6), tooltips (item 3), base-game invisibility when nothing is selected (item 4). Character-interaction toggle from v1.0 removed in favor of the CMM.
