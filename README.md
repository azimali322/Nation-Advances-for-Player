# Handicap Advances for Player

A handicap/cheat mod for EU5 that lets you unlock and research other nations' unique advances alongside your own - choose specific advances by continent, region, or area, or unlock them all at once. Built on the [Community Mod Framework](https://steamcommunity.com/sharedfiles/filedetails/?id=3692202776).

- **Mod version:** 1.0
- **Supported game version:** 1.3.*
- **Mod id:** `handicap_advances_for_player` (script prefix `hafp_`)

## Current state (v1.0)

Version 1.0 is a clean, re-baselined port of the ["All Advances Unlocked"](https://steamcommunity.com/sharedfiles/filedetails/?id=3665391921) workshop mod into the Community Mod Framework (CMF) mod format:

- Every unique advance (nation, culture, culture group, religion, government, regional, and other special trees — 2,491 advances across 200 files) has its availability gate wrapped so that setting the country variable `hafp_all_advances_enabled` makes it researchable by the player.
- Two character interactions on your own nation toggle the variable: **Unlock All Advances** and **Remove Access to All Advances**.
- All advance overrides are **generated from the local vanilla 1.3 game files** by [tools/generate_advances.py](tools/generate_advances.py), not hand-copied, so the mod stays accurate to the current patch. (This also fixed an advance the original mod missed: `monarchy_reform_traditions_advance`.)

The selectable continent/region/area toggle menu, CMM settings tab, and research buttons described in [REQUIREMENTS.md](REQUIREMENTS.md) are the roadmap for upcoming versions.

## How it works

For each advance, the vanilla availability gates are rewritten:

```
potential = { <original conditions> }
```

becomes

```
potential = {
	OR = {
		has_variable = hafp_all_advances_enabled
		AND = { <original conditions> }
	}
}
```

The same wrap is applied to `allow = { ... }` gates (e.g. institution requirements), and top-level `government = <type>` gates are folded into the wrapped `potential` so the unlock variable can bypass them. Advances with no gates are untouched and not shipped.

## Regenerating after a game patch

```
python tools/generate_advances.py
```

Defaults assume a standard Steam install; pass `--game "<EU5 install folder>"` otherwise. The script rewrites `in_game/common/advances/` from the vanilla files.

## Folder layout (CMF mod format)

```
.metadata/metadata.json      mod metadata + CMF dependency
in_game/common/advances/     generated advance overrides
in_game/common/character_interactions/
main_menu/localization/english/
tools/generate_advances.py   generator script
REQUIREMENTS.md              full feature requirements / roadmap
TESTING.md                   in-game test plan
```

## Credits

- Mechanism based on the [All Advances Unlocked](https://steamcommunity.com/sharedfiles/filedetails/?id=3665391921) workshop mod.
- Built for the [Community Mod Framework](https://github.com/Europa-Universalis-5-Modding-Co-op/community-mod-framework).
