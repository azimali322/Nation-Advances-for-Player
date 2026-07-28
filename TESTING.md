# Handicap Advances for Player — In-Game Test Plan (phase 2, CMM menu)

## Round 14 checks (research buttons skip ALL unique unit advances)

- [ ] As the Ottomans with *Allow Unique Unit Advances* **off** (default) and anything unlocked, at **any** age and under **any** research scope: *Research All Custom Advances* grants **no** unique units at all — no Janissaries or Akıncılar (your own), no Galiot/Galleass/Baghlah, no foreign uniques. Non-military custom advances still research normally.
- [ ] Your own unit advances are **still visible and researchable by hand** in the advances tree, at normal cost — the mod must not remove them (base game unchanged).
- [ ] Generic base units are unaffected: Footmen, Archers, Cog, War Galley etc. still come from the ordinary trees and from *Research All Advances*.
- [ ] Turn the toggle **on**: the buttons now grant unique units again (foreign ones too, for the groups you selected).
- [ ] Setting name changed to *Allow Unique Unit Advances* but its id did not, so an existing save keeps your previous choice.

## Round 13 checks (default scope is now era-safe)

The **Research Scope default changed to *All, No Future Ages*** (was *All Advances*). Existing saves keep their stored pick — set it manually once.

- [ ] As the Ottomans in Age of Traditions, scope *All, No Future Ages*, *Allow Foreign Unit Unlocks* off, All of Asia selected, *Research All Custom Advances*: the army list shows **no** Janissary Columns (age VI) or Akıncılar (age III), and the navy list shows **no** Galiot/Galleass (age IV) or Baghlah (age V) — only age-I units such as Footmen, Archers, Armored Horsemen, Cog.
- [ ] Those units appear normally as you advance into their ages, and re-clicking the button in a later age researches the ones that have become current.
- [ ] Foreign units (Bedouin cavalry etc.) stay absent in every age while the allow toggle is off — confirming the two filters are independent.
- [ ] Switching the scope back to *All Advances* reproduces the old behavior (future-age own-nation units early), confirming it is a scope choice and not a leak.

## Round 12 checks (foreign unit unlocks are now opt-in)

The setting was renamed, so existing saves start it at its new default (**off**) — no manual step needed.

- [ ] Settings > Master shows **Allow Foreign Unit Unlocks**, off by default (the old *Exclude Foreign Unit Unlocks* is gone).
- [ ] As the Ottomans with Asia + Europe selected **and** *Unlock All Custom Advances* on: *Research All Custom Advances* grants **no** foreign unique units — no Bedouin cavalry, no foreign unique ships, no foreign unique regiments. Foreign civilian and military-bonus advances still unlock/research normally.
- [ ] Your **own** unique units are unaffected — as the Ottomans the Janissary line still behaves exactly as vanilla.
- [ ] Turn **Allow Foreign Unit Unlocks** on: foreign unit advances become unlockable/researchable again for the groups you have selected.
- [ ] Newly covered: Bengali `bng_bengali_paik` (grants paik units via a `may_build` modifier rather than `unlock_unit`) is now treated as a unit grant.

## Round 11 checks (era leakage — future-age units)

The Research Scope dropdown now has **four** options; existing saves store the scope by number, so **re-pick it once** after updating.

- [ ] Scope **All, No Future Ages** (new, option 2) + *Research All Custom Advances* in Age of Traditions: **no** Age of Reformation ships (galleass, war galley) or any other future-age advance is researched; everything from your current age and earlier still is, institutions ignored.
- [ ] Scope **All Advances** (option 1, the default) still deliberately researches future-age advances — that is what it is for. If you never want that, use option 2.
- [ ] Scopes **Embraced Institutions** / **Current Age Institutions** also never research future-age advances (they now carry an explicit age check instead of relying on the engine's availability trigger).
- [ ] After researching under option 2, check the navy build list: only ships of your current age and earlier are buildable.

## Round 10 checks (vassalization kept alongside Indian samanta)

- [ ] As a **non-Indian** nation (e.g. Tunis) that has unlocked/researched `samanta_advance` through the mod: the **Vassalize** diplomatic action is available again, **and** the samanta / maha samanta / pradhana maha samanta subject types are also available.
- [ ] Same check for **pronoia** (Byzantine, Fate of the Phoenix): still offerable after gaining samanta through the mod.
- [ ] As an **Indian-culture** nation researching samanta normally: vanilla behavior is unchanged — vassals (and pronoia) are replaced by the samanta system.
- [ ] Without the mod's advances unlocked, nothing about vassalization changes for anyone.
- [ ] `error.log` clean of anything mentioning `vassal`, `samanta`, `pronoia`, or `subject_types`.

## Round 9 checks (Exclude toggle narrowed to unit unlocks)

- [ ] The Settings toggle is now labeled **Exclude Foreign Unit Unlocks**. With it ON and everything unlocked: foreign advances that unlock **units or levies** (ship unlocks like Dhow/Genoese Galley, levy unlocks like Noble Knights/Mailed Knights, unique regiment advances) stay locked.
- [ ] Foreign advances that only give military **buffs** now unlock normally with it on — e.g. Élan (land morale), Gendarmes (heavy cavalry power — a buff, not a unit), infantry/sailor power advances.
- [ ] Note: if you already force-researched military advances in your Tunisia save before this change (via *All advances* scope), those stay researched — the toggle only controls what is *unlockable/researchable*, it never un-researches. Test on a fresh save or before clicking research buttons.

## Round 8 checks (institution `allow` gates no longer bypassed)

- [ ] With *Unlock All Custom Advances* on, the **Meritocracy advance** (and other institution-gated defaults: Legalism/Feudalism roots, Banking, New World tree, ...) is **not** researchable until its institution is actually embraced — identical to vanilla. Previously the unlock toggles bypassed these `allow` gates.
- [ ] After embracing an institution normally in-game, its gated advances become researchable as usual.
- [ ] *Research All Advances* under **All advances** scope still force-researches institution-gated advances (the effect steps over `allow`); under the embraced scopes it does not.
- [ ] The mod no longer overrides three vanilla files at all (0_age_of_absolutism / discovery / revolutions had only `allow` gates); confirm no errors and that those ages' advances behave vanilla.

## Round 7 checks (new feature: Exclude Foreign Military Advances)

- [ ] Settings > Master > **Exclude Foreign Military Advances** exists (off by default), with tooltip.
- [ ] With it ON and e.g. *All of Europe* selected (or Unlock All): foreign military advances (Élan, Gendarmes, Cataphracts, the unique ship/army unlocks like Dhow or Genoese Galley) are **not** researchable; foreign civilian advances (French Tradition, Estates General, religious/economic trees) still are.
- [ ] Your **own nation's** military advances remain exactly as in the base game while the toggle is on.
- [ ] Research buttons skip the excluded military advances under every scope; toggling it off makes them unlockable/researchable again.
- [ ] Borderline classification spot-checks welcome: an advance is "military" if it's in the army/ship unlock trees, unlocks units/levies, or has mostly military-stat modifiers (e.g. French Heritage counts as military because its only effect is nobles levy size). Report any that feel wrongly classified either way.

## Round 6 checks (from fifth test pass)

- [ ] **Unembraced institution branches stay unresearched.** As Tunis (Feudalism embraced, Meritocracy not), *Research All Custom Advances* under *Embraced institutions only* no longer researches custom advances chained under the Meritocracy root (e.g. the Mamluk `barid` tree requires the Meritocracy advance) — institution requirements are now inherited through the whole prerequisite chain. After embracing Meritocracy, the same click researches them.
- [ ] **New third scope option** — *Embraced institutions, current age only*: like option 1 but restricted to advances of the age the game is currently in (in Age of Traditions they're equivalent; the difference shows from Age 2 onward, where option 3 skips earlier-age advances).
- [ ] The institutions themselves are never embraced/spawned by any button (the mod cannot do that — verify Meritocracy's embrace status is untouched by all buttons).

## Round 5 checks (from fourth test pass)

- [ ] **Embraced scope no longer skips children of unresearched plain advances.** With *Unlock All Custom Advances* on and scope = *Embraced institutions only*, *Research All Custom Advances* now also researches the customs hanging off Classic Scholasticism (Genghisid Legacy, Pōchtēcayōtl, Byzantine Historiography, Legacy of Saint George, Buddhist Syncretism, Onmyōdō, Colonial Traditions, Master Masons, Genoese Galley, ...). Classic Scholasticism itself stays unresearched — plain advances remain locked behind normal research.
- [ ] Verify the scope still filters correctly: nothing from unreached ages or unembraced institutions researches under *Embraced institutions only*. (The embraced branch now uses `has_advance_available` instead of `can_research_advance`; if anything from a future era slips through, report it — the fallback is an explicit institution check.)

## Round 4 checks (from third test pass)

- [ ] **Research All Custom Advances now covers unique advances in the generic trees.** With *Unlock All Custom Advances* on, the button also researches the potential-gated entries of the building/ship/reform/cabinet trees (the leftovers from last round: Confucian School, Cathedral, Fortress Church, Lieutenancy, Order Headquarters, Republic/Tribal/Divine reform laws, Trade Caravans, Aqueduct System, Dhow, etc.). The Unique Advances counter should reach its maximum after clicking under *All advances* scope.
- [ ] **Plain always-available advances stay unresearched** by that button (e.g. Horsemen, generic adm/dip/mil choices, institution-gated defaults like the New World tree) — they still need normal research (or the explicit Research All / era buttons).
- [ ] **Mod Action Log** (Mod Menu > General > Session > Mod Action Log): every toggle change ("<Setting> turned ON/OFF (Handicap Advances)"), Research Scope changes, and each research button click are logged with your country as actor.

## Round 3 checks (from second test pass)

- [ ] **Cascading selection.** Toggling *All of Balkans* checks every area under it; unchecking it unchecks them. *All of Europe* checks/unchecks every region and area in the Europe tab. New *Select All* toggles at the top of each Cultures group and of Religions / Governments / Special do the same for their group. (Cascade is downward only: unchecking a single area does not untick its region — and note the region toggle alone still unlocks the whole region while checked.)
- [ ] **"All advances" scope now bypasses ages/institutions.** With *Unlock All Custom Advances* on and scope = *All advances*, *Research All Custom Advances* researches custom advances from **all** eras and institutions, including unembraced/future ones. With scope = *Embraced institutions only* the behavior confirmed working last round is unchanged.
- [ ] With scope = *All advances* but **nothing unlocked**, the research buttons still only touch advances available to you (your own nation's full tree across all eras, plus default trees for the all/era buttons).

## Round 2 regression checks (bugfixes from first test pass)

Fixes to verify first, from the 2026-07-19 test report:

- [ ] **Steppe/government advances no longer visible with the mod off.** As France with *Enabled* unchecked, the Age of Traditions tree shows **no** Kurultai / Yams of the Great Khān / Steppe Slave Raiding / Caravanserai / Beyond the Sun (these were leaking from the `government = X` gate fold; now a proper `government_type` trigger). Monarchy advances (Noble Knights, Serfs) still show — France is a monarchy, that's vanilla.
- [ ] **Research buttons respect your unlocks.** With *Enabled* on but nothing selected, *Research All Custom Advances* researches only advances you could see (your own nation's tree). Foreign customs research only after you toggle their group on.
- [ ] **Embraced-institutions scope works.** With scope = *Embraced institutions only*, the research buttons use the game's own research rule (`can_research_advance`): nothing from unreached ages, nothing whose institutions you haven't embraced, and prerequisite chains complete in one click in order. With scope = *All advances*, everything **visible to you** force-researches regardless of institutions/age.
- [ ] Watch `error.log` again for anything mentioning `hafp`, `government_type`, `has_advance_available`, or `can_research_advance`.

Phase 2 replaces the character-interaction toggle with a full Community Mod Menu (CMM) integration. Work through the checklist in order; note results next to each box.

## Setup

- [ ] Playset contains **Community Mod Framework** (2.x) *above* **Handicap Advances for Player**; both enabled; launcher shows game version 1.3.
- [ ] Start a new game as **France**.
- [ ] Check `Documents/Paradox Interactive/Europa Universalis V/logs/error.log` for new errors mentioning `hafp`, `advances`, `cmm`, or `on_action`. **This is the most important check** — with ~300 generated settings and ~34k lines of research effects, script typos would show up here.

## Menu appears

- [ ] Open the CMM (Community Mod Menu) — *Handicap Advances for Player* is listed.
- [ ] Tabs present: **Europe, Asia, Africa, America, Cultures, Religions & Governments, Settings**.
- [ ] Europe tab: "Entire Continent" group with *All of Europe*, then one group per region (Balkans, France, Italy, ...) each with *All of &lt;region&gt;* plus area toggles labeled with nation names (e.g. *Bosnia - Bosnia, Hum, Travunija*).
- [ ] Hover a few toggles — tooltips describe what each unlocks.

## Mod disabled by default (base-game invisibility)

- [ ] Settings tab: **Enabled** is off by default.
- [ ] With Enabled off, toggle *All of Europe* on: advances screen shows **no change** (no foreign advances) — the master switch gates everything.
- [ ] France's own advances (French Tradition, Élan) appear exactly as in the base game.

## Area / region / continent toggles

- [ ] Turn **Enabled** on. With no other toggles: still no foreign advances (base/current-nation preset).
- [ ] Toggle the **area** containing England (British Isles region → its area shows "England"): English advances become researchable for France; other nations' do not.
- [ ] Toggle it off, toggle **All of Balkans** (region): Serbian/Bosnian/Byzantine advances appear; English ones do not.
- [ ] Toggle **All of Europe** (continent): everything European appears, including areas whose individual toggles are off.
- [ ] Overlap check: turn on both a region and one of its areas — no errors, advances unlock once; turning the area off while the region stays on keeps them unlocked (OR semantics).

## Cultures / Religions & Governments

- [ ] Cultures tab: toggle *Venetian* — Venetian culture advances become researchable.
- [ ] Religions & Governments tab: toggle *Orthodox* — Orthodox advances appear for Catholic France; toggle *Republic* — republic advances appear for a monarchy.

## Settings tab

- [ ] **Unlock All Custom Advances**: every custom tree becomes researchable (equivalent to all toggles on). Turn off: only individually-selected groups remain.
- [ ] **Unlock by Era**: with everything else off, *Unlock Age of Renaissance* makes gated age-2 advances researchable (all nations), other ages unaffected.
- [ ] **Research Scope** = *Embraced institutions only*, click **Research All Custom Advances**: custom advances instantly researched, except ones needing institutions you lack; default trees untouched.
- [ ] Scope = *All advances*, click again: the institution-gated ones research too.
- [ ] **Research Current Era**: every advance of the current age (including default trees) researches instantly.
- [ ] **Research Previous Eras** (best tested with a later-age save or after advancing an age): all earlier-age advances research.
- [ ] **Research All Advances**: everything researches.

## Persistence & multiplayer basics

- [ ] Set a few toggles, save, reload: selections and unlocked advances persist.
- [ ] Turn **Enabled** off after unlocking: foreign advances stop being researchable; already-researched ones keep their effects.
- [ ] (Optional, MP) Second player's selections are independent (settings are per-country).

## AI safety

- [ ] AI countries never gain access: variables are only set through the CMM UI, which only the player uses. Spot-check via observe/tag-switch that an AI neighbor shows vanilla advances only.

## Known limitations (expected, not bugs)

- Advances do not become retroactively *visible* mid-session in some UI states — re-open the Advances screen after toggling.
- An advance already researched stays researched when its group is toggled off (by design).
- Area granularity follows each nation's 1337 capital (formables use their formable-definition regions), so a nation's area may differ from where its later conquests lie.

## Reporting

When something fails, note: country played, the toggle/button used, the advance id involved, expected vs. actual, and paste related `error.log` lines. Keep results in a `TEST-RESULTS.md` or GitHub issues.
