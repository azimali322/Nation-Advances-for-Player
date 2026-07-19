# Handicap Advances for Player — In-Game Test Plan (phase 2, CMM menu)

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
