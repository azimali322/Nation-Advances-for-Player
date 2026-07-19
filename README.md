# Handicap Advances for Player

A handicap/cheat mod for EU5 that lets you unlock and research other nations' unique advances alongside your own - choose specific advances by continent, region, or area, or unlock them all at once. Built on the [Community Mod Framework](https://steamcommunity.com/sharedfiles/filedetails/?id=3692202776).

- **Mod version:** 1.0
- **Supported game version:** 1.3.*
- **Mod id:** `handicap_advances_for_player` (script prefix `hafp_`, CMM mod id `hafp`)

## Features (phase 2 - CMM menu)

All controls live in the **Community Mod Menu** (CMM) under *Handicap Advances for Player*:

- **Continent tabs (Europe / Asia / Africa / America):** an *All of &lt;continent&gt;* toggle on top, then one group per region with an *All of &lt;region&gt;* toggle followed by individual **area** toggles. Area labels name the custom nations based there (e.g. *Bosnia - Bosnia, Hum, Travunija*). Selecting any group unlocks every custom advance of the nations in it; overlapping selections are harmless (an advance unlocks if *any* of its groups is on).
- **Cultures tab:** one toggle per culture and culture-group advance tree, grouped by the continent where the culture's pops live in 1337.
- **Religions & Governments tab:** one toggle per religion tree, per government tree, and the special trees (Colonial Nations, Cossacks Estate).
- **Settings tab:**
  - **Enabled** - master switch, off by default. While off the mod is invisible: every nation sees exactly its base-game advances. Turning it on applies your selections; your own nation's advances are never affected.
  - **Unlock All Custom Advances** - one toggle that mimics the original "All Advances Unlocked" mod (equivalent to selecting every continent/region/area, culture, religion, and government).
  - **Unlock by Era** - per-age toggles that make every gated advance of that age researchable.
  - **Research Scope** - whether the buttons below respect institution requirements (*Embraced institutions only* / *All advances*).
  - **Research buttons** - instantly research: all custom advances, all advances (including default trees), the current era, or all previous eras.

Every toggle and button has hover-over tooltip text; the advances themselves keep their normal vanilla tooltips in the advances screen.

## How it works

Every gated vanilla advance gets its availability rewritten (see [tools/generate_advances.py](tools/generate_advances.py)):

```
potential = {
	OR = {
		AND = {
			has_variable = hafp_enabled              # Settings > Enabled
			OR = {
				has_variable = hafp_all_advances_enabled   # Unlock All
				has_variable = hafp_g_age_<age>            # Unlock by Era
				has_variable = hafp_g_cont_<continent>     # geography toggles
				has_variable = hafp_g_reg_<region>
				has_variable = hafp_g_area_<area>
				has_variable = hafp_g_f_<file>             # culture/religion/gov toggles
			}
		}
		AND = { <original conditions> }              # base-game behavior
	}
}
```

Top-level `government =` gates are folded into the wrapped potential as `government_type` triggers. `allow` gates (institution requirements, e.g. the Meritocracy advance) are deliberately left untouched, so institution requirements behave exactly as in the base game — only the research buttons' *All advances* scope can step over them. Each CMM toggle syncs to its `hafp_*` country variable via `cmm_sync_bool_alias`, re-synced on every CMM callback.

Where each advance belongs is computed by [tools/build_groups.py](tools/build_groups.py) from the game files: nation tags map through their 1337 capital (formables through their formable-definition regions, a small manual table covers the rest); region/area/continent scope references are used directly; culture and language gated advances map to where those cultures' pops live in the 1337 setup.

## Generated files - do not edit by hand

| File | Generator |
| --- | --- |
| `in_game/common/advances/*` | `tools/generate_advances.py` |
| `in_game/common/scripted_effects/hafp_cmm_register.txt` | `tools/generate_cmm.py` |
| `in_game/common/scripted_effects/hafp_research_effects.txt` | `tools/generate_cmm.py` |
| `in_game/common/on_action/hafp_on_actions.txt` | `tools/generate_cmm.py` |
| `main_menu/localization/english/hafp_cmm_l_english.yml` | `tools/generate_cmm.py` |

Regenerate after every game patch:

```
python tools/build_groups.py
python tools/generate_advances.py
python tools/generate_cmm.py
```

Defaults assume a standard Steam install; pass the EU5 folder as `--game` / first argument otherwise.

## Folder layout (CMF mod format)

```
.metadata/metadata.json      mod metadata + CMF dependency
in_game/common/advances/     generated advance overrides (200 files, ~2,500 advances)
in_game/common/scripted_effects/
in_game/common/on_action/
main_menu/localization/english/
tools/                       generators + tools/data/groups.json mapping
REQUIREMENTS.md              full feature requirements / roadmap
TESTING.md                   in-game test plan
```

## Credits

- Mechanism based on the [All Advances Unlocked](https://steamcommunity.com/sharedfiles/filedetails/?id=3665391921) workshop mod.
- Built on the [Community Mod Framework](https://github.com/Europa-Universalis-5-Modding-Co-op/community-mod-framework) and its Community Mod Menu.
