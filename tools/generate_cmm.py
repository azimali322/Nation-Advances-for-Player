#!/usr/bin/env python3
"""Generate the CMM menu wiring for Handicap Advances for Player.

Reads tools/data/groups.json (from build_groups.py) plus the vanilla advances
files and writes:

  in_game/common/on_action/hafp_on_actions.txt
  in_game/common/scripted_effects/hafp_cmm_register.txt
  in_game/common/scripted_effects/hafp_research_effects.txt
  main_menu/localization/english/hafp_cmm_l_english.yml

Menu layout (mod_id `hafp`):
  * one tab per continent (Europe / Asia / Africa / America): a continent
    toggle on top, then one group per region with the region toggle followed
    by its area toggles (labels name the nations in each area)
  * Cultures tab: culture and culture-group toggles grouped by home continent
  * Categories tab: religion, government, and special toggles
  * Settings tab: Enabled master switch, Unlock-all toggle, per-era unlock
    toggles, research scope dropdown, and research buttons

Every toggle syncs (cmm_sync_bool_alias) to the country variable the advance
gates check (see generate_advances.py).

Run order after a game patch:
  python tools/build_groups.py && python tools/generate_advances.py && python tools/generate_cmm.py
"""

import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
GROUPS_PATH = os.path.join(HERE, "data", "groups.json")
GAME_DEFAULT = r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V"

sys.path.insert(0, HERE)
from build_groups import split_advances  # noqa: E402

MOD_ID = "hafp"

AGES = [
    ("age_1_traditions", "Age of Traditions"),
    ("age_2_renaissance", "Age of Renaissance"),
    ("age_3_discovery", "Age of Discovery"),
    ("age_4_reformation", "Age of Reformation"),
    ("age_5_absolutism", "Age of Absolutism"),
    ("age_6_revolutions", "Age of Revolutions"),
]

CONTINENT_ORDER = ["europe", "asia", "africa", "america", "oceania"]

GENERIC_FILES = None  # populated from build_groups


def esc(s):
    return s.replace('"', "'")


def humanize(ident):
    ident = re.sub(r"^(culture_group_|culture_|religion_|government_)", "", ident)
    ident = re.sub(r"_(area|region|province|group|culture)$", "", ident)
    return ident.replace("_", " ").title()


def main():
    game = sys.argv[1] if len(sys.argv) > 1 else GAME_DEFAULT
    with open(GROUPS_PATH, encoding="utf-8") as fh:
        groups = json.load(fh)

    from build_groups import GENERIC_FILES as generic_files

    files = groups["files"]
    areas = groups["areas"]
    regions = groups["regions"]
    continents = groups["continents"]

    # ------------------------------------------------------------------ #
    # Collect every advance in the game (id, age, institution, custom?)  #
    # ------------------------------------------------------------------ #
    adv_dir = os.path.join(game, "game", "in_game", "common", "advances")
    all_advances = []  # (adv_id, age, institution, is_custom)
    seen = set()
    for fname in sorted(os.listdir(adv_dir)):
        if not fname.endswith(".txt") or fname in ("readme.txt", "_advances_template.txt"):
            continue
        text = open(os.path.join(adv_dir, fname), encoding="utf-8-sig").read()
        is_custom = fname in files
        for adv_id, body in split_advances(text):
            if adv_id in seen:
                continue
            seen.add(adv_id)
            age_m = re.search(r"\bage\s*=\s*(age_[a-z0-9_]+)", body)
            inst_m = re.search(r"has_embraced_institution\s*=\s*institution:([a-z0-9_]+)", body)
            all_advances.append((adv_id, age_m.group(1) if age_m else None,
                                 inst_m.group(1) if inst_m else None, is_custom))

    # ------------------------------------------------------------------ #
    # Settings inventory                                                 #
    # ------------------------------------------------------------------ #
    # (setting_id, tab, group, alias, name, desc)
    toggles = []
    loc = {}

    def add_toggle(setting_id, tab, group, alias, name, desc):
        toggles.append((setting_id, tab, group, alias))
        loc["%s__%s_name" % (MOD_ID, setting_id)] = name
        loc["%s__%s_desc" % (MOD_ID, setting_id)] = desc

    loc["%s_name" % MOD_ID] = "Handicap Advances for Player"
    loc["%s_desc" % MOD_ID] = (
        "Unlock and research other nations' unique advances alongside your own. "
        "Pick continents, regions, or areas, individual cultures, religions and "
        "governments - or unlock everything at once from the Settings tab.")

    # --- continent tabs -------------------------------------------------
    conts_used = [c for c in CONTINENT_ORDER if c in continents]
    for cont in conts_used:
        cname = continents[cont]["name"]
        tab = cont
        loc["%s__%s_name" % (MOD_ID, tab)] = cname
        loc["%s__%s_desc" % (MOD_ID, tab)] = (
            "Unlock nation advances from %s by continent, region, or area." % cname)
        loc["%s__%s__all_name" % (MOD_ID, tab)] = "Entire Continent"
        add_toggle("cont_%s" % cont, tab, "all", "hafp_g_cont_%s" % cont,
                   "All of %s" % cname,
                   "Unlock every custom nation advance on %s, regardless of the "
                   "region and area toggles below." % cname)

        cont_regions = sorted((r for r, v in regions.items() if v["continent"] == cont),
                              key=lambda r: regions[r]["name"])
        for reg in cont_regions:
            rname = regions[reg]["name"]
            gid = "reg_%s" % reg
            loc["%s__%s__%s_name" % (MOD_ID, tab, gid)] = rname
            reg_areas = sorted((a for a, v in areas.items() if v["region"] == reg),
                               key=lambda a: areas[a]["name"])
            n_nations = sorted({t for a in reg_areas for t in areas[a]["tag_names"]})
            add_toggle(gid, tab, gid, "hafp_g_reg_%s" % reg,
                       "All of %s" % rname,
                       "Unlock every custom nation advance in the %s region%s." % (
                           rname,
                           " (%s)" % esc(", ".join(n_nations)) if n_nations else ""))
            for a in reg_areas:
                v = areas[a]
                label = v["name"]
                nations = esc(", ".join(v["tag_names"]))
                add_toggle("area_%s" % a, tab, gid, "hafp_g_area_%s" % a,
                           "%s%s" % (label, " - %s" % nations if nations else ""),
                           "Unlock the custom advances of nations based in %s%s." % (
                               label, " (%s)" % nations if nations else ""))

    # --- cultures tab ---------------------------------------------------
    tab = "cultures"
    loc["%s__%s_name" % (MOD_ID, tab)] = "Cultures"
    loc["%s__%s_desc" % (MOD_ID, tab)] = (
        "Unlock culture and culture-group advances, organized by where the "
        "culture lives.")
    cultures_by_cont = defaultdict(list)
    for fname, entry in sorted(files.items()):
        if entry["kind"] not in ("culture", "culture_group"):
            continue
        cont = entry.get("home_continent") or "other"
        cultures_by_cont[cont].append(fname)
    for cont in CONTINENT_ORDER + ["other"]:
        if cont not in cultures_by_cont:
            continue
        gid = "cul_%s" % cont
        gname = continents[cont]["name"] if cont in continents else (
            humanize(cont) if cont != "other" else "Other")
        loc["%s__%s__%s_name" % (MOD_ID, tab, gid)] = gname
        for fname in cultures_by_cont[cont]:
            entry = files[fname]
            stem = fname[:-4]
            base = humanize(stem)
            is_group = entry["kind"] == "culture_group"
            name = "%s%s" % (base, " (Culture Group)" if is_group else "")
            n = len(entry["advances"])
            region = entry.get("home_region")
            where = regions[region]["name"] if region in regions else (
                continents[cont]["name"] if cont in continents else "the world")
            add_toggle("f_%s" % stem, tab, gid, "hafp_g_f_%s" % stem, name,
                       "Unlock the %d %s advances (%s)." % (
                           n, "culture-group" if is_group else "culture", where))

    # --- categories tab -------------------------------------------------
    tab = "categories"
    loc["%s__%s_name" % (MOD_ID, tab)] = "Religions & Governments"
    loc["%s__%s_desc" % (MOD_ID, tab)] = (
        "Unlock religion, government, and special advance trees.")
    for gid, kind, gname in (("religions", "religion", "Religions"),
                             ("governments", "government", "Governments"),
                             ("special", "special", "Special")):
        loc["%s__%s__%s_name" % (MOD_ID, tab, gid)] = gname
        for fname, entry in sorted(files.items()):
            if entry["kind"] != kind:
                continue
            stem = fname[:-4]
            name = humanize(stem)
            if kind == "special":
                name = {"colonial_nations": "Colonial Nations",
                        "estate_cossacks": "Cossacks Estate"}.get(stem, name)
            add_toggle("f_%s" % stem, tab, gid, "hafp_g_f_%s" % stem, name,
                       "Unlock the %d advances of this tree." % len(entry["advances"]))

    # --- settings tab ---------------------------------------------------
    tab = "settings"
    loc["%s__%s_name" % (MOD_ID, tab)] = "Settings"
    loc["%s__%s_desc" % (MOD_ID, tab)] = "Master switches and research shortcuts."
    loc["%s__%s__master_name" % (MOD_ID, tab)] = "Master"
    loc["%s__%s__era_unlock_name" % (MOD_ID, tab)] = "Unlock by Era"
    loc["%s__%s__research_name" % (MOD_ID, tab)] = "Instant Research"

    add_toggle("enabled", tab, "master", "hafp_enabled",
               "Enabled",
               "Master switch for the whole mod. While off, every advance "
               "behaves exactly as in the base game no matter what is selected "
               "in the other tabs. Turn on to apply your selections; your own "
               "nation's advances are always unaffected.")
    add_toggle("unlock_all", tab, "master", "hafp_all_advances_enabled",
               "Unlock All Custom Advances",
               "Unlock every nation, culture, religion, and government advance "
               "in the game for research - the same as selecting every "
               "continent, region, and area. Overrides the individual toggles "
               "in the other tabs (they stay as you set them).")

    for age_id, age_name in AGES:
        add_toggle("age_%s" % age_id, tab, "era_unlock",
                   "hafp_g_age_%s" % age_id,
                   "Unlock %s" % age_name,
                   "Make every gated advance of the %s researchable, for all "
                   "nations, cultures, religions, and governments." % age_name)

    # dropdown + buttons (registered separately from bool toggles)
    loc["%s__research_scope_name" % MOD_ID] = "Research Scope"
    loc["%s__research_scope_desc" % MOD_ID] = (
        "Whether the research buttons below respect institution requirements.")
    loc["%s__research_scope_option_1_name" % MOD_ID] = "Embraced institutions only"
    loc["%s__research_scope_option_1_desc" % MOD_ID] = (
        "Only instantly research advances whose institution requirements your "
        "country already meets.")
    loc["%s__research_scope_option_2_name" % MOD_ID] = "All advances"
    loc["%s__research_scope_option_2_desc" % MOD_ID] = (
        "Instantly research advances regardless of embraced institutions.")

    buttons = [
        ("research_custom", "Research All Custom Advances",
         "Instantly research every custom (nation, culture, religion, "
         "government) advance. Default game advances stay unresearched."),
        ("research_all", "Research All Advances",
         "Instantly research every advance in the game, including the default "
         "trees."),
        ("research_current_era", "Research Current Era",
         "Instantly research every advance of the age your game is currently "
         "in."),
        ("research_previous_eras", "Research Previous Eras",
         "Instantly research every advance of the ages before the current "
         "one."),
    ]
    for bid, bname, bdesc in buttons:
        loc["%s__%s_name" % (MOD_ID, bid)] = bname
        loc["%s__%s_desc" % (MOD_ID, bid)] = bdesc
        loc["%s__%s_text" % (MOD_ID, bid)] = bname

    # ------------------------------------------------------------------ #
    # Emit scripted effects: registration + alias sync + callback        #
    # ------------------------------------------------------------------ #
    reg = ["﻿# Generated by tools/generate_cmm.py - do not edit by hand.",
           "# Root scope: country.",
           "hafp_register_mod = {"]
    for setting_id, tab, group, alias in toggles:
        reg.append("\tcmm_register_bool_setting = {")
        reg.append("\t\tmod_id = %s" % MOD_ID)
        reg.append("\t\tsetting_id = %s" % setting_id)
        reg.append("\t\ttab_id = %s" % tab)
        reg.append("\t\tgroup_id = %s" % group)
        reg.append("\t\tdefault_value = 0")
        reg.append("\t}")
    reg.append("\tcmm_register_dropdown_setting = {")
    reg.append("\t\tmod_id = %s" % MOD_ID)
    reg.append("\t\tsetting_id = research_scope")
    reg.append("\t\ttab_id = settings")
    reg.append("\t\tgroup_id = research")
    reg.append("\t\tdefault_index = 1")
    reg.append("\t\toption_count = 2")
    reg.append("\t}")
    for bid, _, _ in buttons:
        reg.append("\tcmm_register_button_setting = {")
        reg.append("\t\tmod_id = %s" % MOD_ID)
        reg.append("\t\tsetting_id = %s" % bid)
        reg.append("\t\ttab_id = settings")
        reg.append("\t\tgroup_id = research")
        reg.append("\t}")
    reg.append("\thafp_sync_aliases = yes")
    reg.append("}")
    reg.append("")
    reg.append("hafp_sync_aliases = {")
    for setting_id, tab, group, alias in toggles:
        reg.append("\tcmm_sync_bool_alias = { setting = %s__%s alias = %s }"
                   % (MOD_ID, setting_id, alias))
    reg.append("}")
    reg.append("")
    reg.append("hafp_handle_callback = {")
    reg.append("\thafp_sync_aliases = yes")
    for bid, _, _ in buttons:
        reg.append("\tif = {")
        reg.append("\t\tlimit = { var:cmf_callback = flag:%s__%s }" % (MOD_ID, bid))
        reg.append("\t\thafp_%s = yes" % bid)
        reg.append("\t}")
    reg.append("}")

    # ------------------------------------------------------------------ #
    # Emit research effects                                              #
    # ------------------------------------------------------------------ #
    def research_block(adv_id, institution, indent="\t"):
        lines = ["%sif = {" % indent,
                 "%s\tlimit = {" % indent,
                 "%s\t\tNOT = { has_advance = %s }" % (indent, adv_id)]
        if institution:
            lines.append("%s\t\tOR = {" % indent)
            lines.append('%s\t\t\t"variable_map(cmm|flag:%s__research_scope)" >= 2'
                         % (indent, MOD_ID))
            lines.append("%s\t\t\thas_embraced_institution = institution:%s"
                         % (indent, institution))
            lines.append("%s\t\t}" % indent)
        lines.append("%s\t}" % indent)
        lines.append("%s\tresearch_advance = advance_type:%s" % (indent, adv_id))
        lines.append("%s}" % indent)
        return lines

    res = ["﻿# Generated by tools/generate_cmm.py - do not edit by hand.",
           "# Root scope: country (the player clicking the CMM button)."]

    by_age = defaultdict(list)
    for adv_id, age, inst, is_custom in all_advances:
        if age:
            by_age[age].append((adv_id, inst))
    for age_id, _ in AGES:
        res.append("")
        res.append("hafp_research_%s = {" % age_id)
        for adv_id, inst in by_age.get(age_id, []):
            res.extend(research_block(adv_id, inst))
        res.append("}")

    res.append("")
    res.append("hafp_research_custom = {")
    for adv_id, age, inst, is_custom in all_advances:
        if is_custom:
            res.extend(research_block(adv_id, inst))
    res.append("}")

    res.append("")
    res.append("hafp_research_all = {")
    for age_id, _ in AGES:
        res.append("\thafp_research_%s = yes" % age_id)
    ageless = [(a, i) for a, age, i, _ in all_advances if not age]
    for adv_id, inst in ageless:
        res.extend(research_block(adv_id, inst))
    res.append("}")

    res.append("")
    res.append("hafp_research_current_era = {")
    for age_id, _ in AGES:
        res.append("\tif = {")
        res.append("\t\tlimit = { current_age = %s }" % age_id)
        res.append("\t\thafp_research_%s = yes" % age_id)
        res.append("\t}")
    res.append("}")

    res.append("")
    res.append("hafp_research_previous_eras = {")
    for idx, (age_id, _) in enumerate(AGES):
        if idx == 0:
            continue
        res.append("\tif = {")
        res.append("\t\tlimit = { current_age = %s }" % age_id)
        for prev_id, _ in AGES[:idx]:
            res.append("\t\thafp_research_%s = yes" % prev_id)
        res.append("\t}")
    res.append("}")

    # ------------------------------------------------------------------ #
    # Emit on_actions                                                    #
    # ------------------------------------------------------------------ #
    on_actions = """﻿# Generated by tools/generate_cmm.py - do not edit by hand.
# Hook into CMF shared registration and callback on_actions.
cmf_on_mod_registration = {
\ton_actions = {
\t\thafp_on_register_mod
\t}
}

hafp_on_register_mod = {
\teffect = {
\t\thafp_register_mod = yes
\t}
}

cmf_on_callback = {
\ton_actions = {
\t\thafp_on_callback
\t}
}

hafp_on_callback = {
\teffect = {
\t\thafp_handle_callback = yes
\t}
}
"""

    # ------------------------------------------------------------------ #
    # Write files                                                        #
    # ------------------------------------------------------------------ #
    def write(relpath, content):
        path = os.path.join(ROOT, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        print("wrote %s (%d lines)" % (relpath, content.count("\n")))

    write("in_game/common/scripted_effects/hafp_cmm_register.txt", "\n".join(reg) + "\n")
    write("in_game/common/scripted_effects/hafp_research_effects.txt", "\n".join(res) + "\n")
    write("in_game/common/on_action/hafp_on_actions.txt", on_actions)

    loc_lines = ["﻿l_english:"]
    for key in loc:
        loc_lines.append(' %s: "%s"' % (key, loc[key]))
    write("main_menu/localization/english/hafp_cmm_l_english.yml", "\n".join(loc_lines) + "\n")

    print("settings: %d toggles + 1 dropdown + %d buttons" % (len(toggles), len(buttons)))
    print("advances known: %d (%d custom)" % (len(all_advances),
                                              sum(1 for a in all_advances if a[3])))


if __name__ == "__main__":
    main()
