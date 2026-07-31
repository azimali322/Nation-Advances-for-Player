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

## 7. Unique unit advances are opt-in (Settings)

- Settings toggle **Allow Unique Unit Advances**, **off by default**, acting on two layers:
  - **Unlock layer** — other nations' unit-granting custom advances stay locked even with *Unlock All Custom Advances* or whole continents selected.
  - **Research layer** — the research buttons skip *every* unique unit advance, **including the player's own nation's** (age VI Janissaries, regional ships, ...), so army/navy progression stays a deliberate choice.
- The player's own unit advances remain **normally researchable in the advances tree** whatever the toggle says — the mod never alters the base game's own-nation branch (requirement 4).
- Foreign advances that only give military **stat buffs** (infantry power, morale, sailors, ...) are never affected — only actual unit-roster grants are.
- The player's **own nation's** advances are unaffected (they flow through the base-game branch of the gate).
- Classification: `unlock_unit`, `unlock_levy`, or a `may_build_*_units` modifier on the advance (~141 of ~2,470 gated advances).
- History: originally an *exclusion* toggle covering any predominantly-military advance (2026-07-19), narrowed to unit grants only, then inverted to an opt-in default-off toggle after unlock-all handed out Janissaries and Bedouin cavalry unasked.

---

## 8. Keep base capabilities that unlocked advances would replace

- Some vanilla advances **replace** a base capability instead of adding to it. The Indian `samanta_advance` is the main case: vanilla hides vassalization (and Byzantine pronoia) behind `NOT = { has_advance = samanta_advance }`, because an Indian realm is meant to use the samanta system instead.
- When such an advance is obtained **through this mod** by a nation that would not qualify in the base game, the player must keep **both**: the base capability (vassals, pronoia) *and* the new one (samanta subject types).
- Nations that qualify natively (here: Indian culture group) keep vanilla behavior — they still trade vassals for samanta.
- Applies automatically, no setting.

## 9. Tall category (Misc tab)

- A **Playstyle** group in the Misc tab with a single **Tall Empire Advances** toggle that unlocks every custom advance in the world carrying a "tall" bonus, independently of the geography/culture/religion selections.
- Qualifying modifiers (444 advances as of 1.3):
  - development — `global_monthly_development`
  - population — `global_population_growth`, `global_population_capacity_modifier`
  - prosperity — `global_monthly_prosperity`
  - food economy — `global_monthly_food_modifier`, `global_food_capacity`, `global_food_decay`, `food_purchase_efficiency`, `food_consumption_modifier`, `global_pop_food_consumption`, `global_clergy_food_consumption`
  - raw materials / production — `global_raw_material_output`, `global_production_efficiency`, and every per-good `*_output_modifier`
  - pop promotion — `global_pop_promotion_speed_modifier`
  - cabinet seats (added 2026-07-19) — `government_size`. The game localizes this modifier as **"Cabinet Seats"**, so it contains neither "cabinet" nor "seat" and must be listed explicitly. Six custom advances grant seats: `colonial_assembly`, `geheimrat` (HAB), `zta_the_code_of_the_black_mountain` (SER), `grand_coordinators` (CHI), `cro_the_royal_council_of_croatia`, `ath_the_athenian_bureaucracy_advance`.
  - cabinet (added 2026-07-19) — any key containing `cabinet`: `country_cabinet_efficiency`, `set_cabinet_member_cost_modifier`, `replace_cabinet_member_cost_modifier`, `head_of_cabinet_promotion_cost_modifier`, `allow_female_cabinet`, `estate_power_from_cabinet`, `unlock_cabinet_action`
  - government reforms (added 2026-07-19) — any key containing `government_reform`: `unlock_government_reform`, `government_reform_slots`
  - crown power (added 2026-07-19) — any key containing `crown`: `global_crown_estate_power`
  - estate satisfaction equilibrium (added 2026-07-19) — any `*_target_satisfaction` key (the game's "target satisfaction" is the equilibrium value); satisfaction *recovery* keys are deliberately not included
- The per-good `*_output_modifier` family is included on the reading that "raw material productivity and bonuses" covers goods output; trim the list in `tools/generate_advances.py` (`TALL_KEYS` / `TALL_KEY_SUFFIXES`) if it should be narrower.

## Non-functional / setup requirements

- Mod format: Community Mod Framework (CMF) mod template/format, with CMF declared as a dependency in `.metadata/metadata.json`.
- Game version: **1.3**, mod version: **1.0**, name: **Handicap Advances for Player**.
- Advance overrides are regenerated from the local vanilla game files via `tools/generate_advances.py` so the mod re-baselines cleanly after game patches.

## Implementation notes / accepted adaptations

- Geography source: nations are placed by their **1337 capital** (formable nations by their formable-definition regions; a small manual table covers the few tags with neither). Confirmed by user 2026-07-19.
- Cultures are placed by where their pops live in the 1337 setup (language- and culture-group-gated advances are expanded to member cultures first).
- Because the selection UI spans four continent tabs, the "select all" control exists **once**, in the Settings tab (*Unlock All Custom Advances*), with per-continent *All of &lt;continent&gt;* toggles at the top of each continent tab. This satisfies the mirroring requirement (item 2) with a single shared setting instead of two synced buttons.
- Instant research uses the engine effect `research_advance = advance_type:<id>`, guarded per advance by the **Research Scope** dropdown (four options, all age limits stated explicitly rather than relying on engine triggers, so no scope can ever reach a future age):
  1. **All Advances** — the advance's own unlock gate only; ignores institutions *and* ages (future-age units can be obtained early).
  2. **All, No Future Ages** *(default)* — same, but never past the current age. Made the default 2026-07-19 after future-age own-nation units (age VI Janissaries, age IV–V ships) kept being reported as unlock bugs; the age filter and the foreign-unit filter are independent.
  3. **Embraced Institutions** — `has_advance_available` + institution requirements inherited through the `requires` chain + current age or earlier.
  4. **Current Age Institutions** — as 3, restricted to exactly the current age.
  
  `can_research_advance` is deliberately not used: it also demands every prerequisite already be researched, which skipped custom advances hanging off unresearched plain advances such as Classic Scholasticism.
- Advances gated by a top-level `government = X` key are wrapped using the trigger `government_type = government_type:X` (the bare key is an engine filter, not a trigger, and is silently ignored inside `potential` — the cause of the first-test visibility leak).

- Cascading selection (user enhancement, 2026-07-19): toggling a continent checks/unchecks every region and area beneath it, a region its areas, and each Cultures / Religions / Governments / Special group has a *Select All* parent. Cascade is downward-only and copies the parent's new value to all children.

- "Custom advance" definition (2026-07-19, round 4): for the research buttons, custom = any advance with a `potential` (or government) gate — the game's "Unique Advances" concept. This includes unique entries inside the generic trees (buildings, ships, reform laws, cabinet actions). Advances with no potential gate (always-available trees, institution-`allow`-gated defaults) are non-custom and stay locked behind normal research.
- All mod actions are recorded in CMF's Mod Action Log: toggle on/off, research-scope changes, and research button clicks.

## Changelog

- **2026-07-19** — Initial requirements captured (items 1–6). v1.0 implements the all-or-nothing unlock toggle (port of "All Advances Unlocked" into CMF format, re-baselined to 1.3).
- **2026-07-19 (phase 2)** — CMM menu implemented: continent/region/area toggles (items 1), Settings tab with Enabled master switch, unlock-all, era unlocks, research buttons with institution scope (items 2, 5, 6), tooltips (item 3), base-game invisibility when nothing is selected (item 4). Character-interaction toggle from v1.0 removed in favor of the CMM.
- **2026-07-19 (round 3)** — Cascading selection added (parent toggles check/uncheck their children; Select All parents for Cultures and category groups). Fixed "All advances" research scope: `has_advance_available` also enforces age/institution limits engine-side, so the all-scope branch now embeds the advance's own unlock gate instead, researching everything unlocked regardless of era or institutions.
