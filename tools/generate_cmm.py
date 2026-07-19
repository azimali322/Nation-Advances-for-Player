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
    # Collect every advance in the game                                  #
    # ------------------------------------------------------------------ #
    # advance -> {age, insts (own), requires, custom, gate (mod potential)}
    adv_dir = os.path.join(game, "game", "in_game", "common", "advances")
    advs = {}
    order = []
    for fname in sorted(os.listdir(adv_dir)):
        if not fname.endswith(".txt") or fname in ("readme.txt", "_advances_template.txt"):
            continue
        text = open(os.path.join(adv_dir, fname), encoding="utf-8-sig").read()
        is_custom = fname in files
        for adv_id, body in split_advances(text):
            if adv_id in advs:
                continue
            order.append(adv_id)
            age_m = re.search(r"\bage\s*=\s*(age_[a-z0-9_]+)", body)
            advs[adv_id] = {
                "age": age_m.group(1) if age_m else None,
                "insts": set(re.findall(
                    r"has_embraced_institution\s*=\s*institution:([a-z0-9_]+)", body)),
                "requires": re.findall(r"\brequires\s*=\s*([A-Za-z0-9_.]+)", body),
                "custom": is_custom,
            }

    # Institution requirements inherited through the requires chains: the
    # advance tree's institution branches gate only their ROOT advance, so
    # every descendant inherits its ancestors' has_embraced_institution
    # requirements (e.g. everything chained under the Meritocracy root
    # requires the meritocracy institution).
    def inst_closure(adv_id, _stack=None):
        info = advs.get(adv_id)
        if info is None:
            return set()
        if "inst_all" in info:
            return info["inst_all"]
        stack = _stack if _stack is not None else set()
        if adv_id in stack:
            return info["insts"]
        stack.add(adv_id)
        out = set(info["insts"])
        for req in info["requires"]:
            out |= inst_closure(req, stack)
        stack.discard(adv_id)
        info["inst_all"] = out
        return out

    for adv_id in order:
        inst_closure(adv_id)

    # The availability gate the mod generated for each gated advance (its
    # rewritten `potential` body). The "All advances" research scope embeds it
    # so buttons research everything the player has unlocked, regardless of
    # age or institutions (has_advance_available/can_research_advance both
    # enforce those engine-side).
    from generate_advances import strip_positions, find_blocks
    gates = {}
    mod_adv_dir = os.path.join(ROOT, "in_game", "common", "advances")
    for fname in os.listdir(mod_adv_dir):
        if not fname.endswith(".txt"):
            continue
        text = open(os.path.join(mod_adv_dir, fname), encoding="utf-8-sig").read()
        mask = strip_positions(text)
        for name, kstart, obrace, cbrace in find_blocks(text, mask, 0, len(text)):
            if name not in advs or name in gates:
                continue
            body = text[obrace + 1 : cbrace]
            bmask = strip_positions(body)
            for bname, bk, bo, bc in find_blocks(body, bmask, 0, len(body)):
                if bname == "potential":
                    gates[name] = [ln.strip() for ln in
                                   body[bo + 1 : bc].strip().splitlines() if ln.strip()]
                    break

    # "Custom" for the research buttons = any advance with a (rewritten)
    # potential gate. This matches the game's Unique Advances concept and
    # includes the potential-gated entries inside the generic trees (unique
    # buildings, ships, reform laws, cabinet actions...). Advances with no
    # potential - the plain always-available trees - stay non-custom, so
    # Research All Custom Advances leaves them locked behind normal research.
    for adv_id in order:
        advs[adv_id]["custom"] = adv_id in gates

    def topo_sort(ids):
        """Order ids so prerequisites come before dependents (stable)."""
        idset = set(ids)
        deps = {i: [r for r in advs[i]["requires"] if r in idset] for i in ids}
        done = set()
        out = []

        def visit(i, stack):
            if i in done or i in stack:
                return
            stack.add(i)
            for r in deps[i]:
                visit(r, stack)
            stack.discard(i)
            done.add(i)
            out.append(i)

        for i in ids:
            visit(i, set())
        return out

    # ------------------------------------------------------------------ #
    # Settings inventory                                                 #
    # ------------------------------------------------------------------ #
    # (setting_id, tab, group, alias) - alias None for pure "select all"
    # parent toggles that only cascade to their children
    toggles = []
    # parent setting id -> [child setting ids]; toggling the parent copies its
    # value onto every child through the cmf_on_callback hook
    parents = {}
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
                   "Unlock every custom nation advance on %s. Toggling this "
                   "also checks or unchecks every region and area below." % cname)

        cont_regions = sorted((r for r, v in regions.items() if v["continent"] == cont),
                              key=lambda r: regions[r]["name"])
        cont_children = []
        for reg in cont_regions:
            rname = regions[reg]["name"]
            gid = "reg_%s" % reg
            loc["%s__%s__%s_name" % (MOD_ID, tab, gid)] = rname
            reg_areas = sorted((a for a, v in areas.items() if v["region"] == reg),
                               key=lambda a: areas[a]["name"])
            n_nations = sorted({t for a in reg_areas for t in areas[a]["tag_names"]})
            add_toggle(gid, tab, gid, "hafp_g_reg_%s" % reg,
                       "All of %s" % rname,
                       "Unlock every custom nation advance in the %s region%s. "
                       "Toggling this also checks or unchecks its areas." % (
                           rname,
                           " (%s)" % esc(", ".join(n_nations)) if n_nations else ""))
            area_ids = []
            for a in reg_areas:
                v = areas[a]
                label = v["name"]
                nations = esc(", ".join(v["tag_names"]))
                add_toggle("area_%s" % a, tab, gid, "hafp_g_area_%s" % a,
                           "%s%s" % (label, " - %s" % nations if nations else ""),
                           "Unlock the custom advances of nations based in %s%s." % (
                               label, " (%s)" % nations if nations else ""))
                area_ids.append("area_%s" % a)
            parents[gid] = area_ids
            cont_children.append(gid)
            cont_children.extend(area_ids)
        parents["cont_%s" % cont] = cont_children

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
        add_toggle("cul_all_%s" % cont, tab, gid, None,
                   "Select All - %s" % gname,
                   "Check or uncheck every culture toggle in this group.")
        parents["cul_all_%s" % cont] = [
            "f_%s" % f[:-4] for f in cultures_by_cont[cont]]
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
        add_toggle("all_%s" % gid, tab, gid, None,
                   "Select All %s" % gname,
                   "Check or uncheck every toggle in this group.")
        parents["all_%s" % gid] = [
            "f_%s" % f[:-4] for f, e in sorted(files.items()) if e["kind"] == kind]
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
        "Only instantly research advances of ages you have reached whose "
        "institution requirements - including those inherited from their "
        "prerequisite tree - you have embraced.")
    loc["%s__research_scope_option_2_name" % MOD_ID] = "All advances"
    loc["%s__research_scope_option_2_desc" % MOD_ID] = (
        "Instantly research advances regardless of age or embraced "
        "institutions.")
    loc["%s__research_scope_option_3_name" % MOD_ID] = (
        "Embraced institutions, current age only")
    loc["%s__research_scope_option_3_desc" % MOD_ID] = (
        "Like Embraced institutions only, but restricted to advances of the "
        "age the game is currently in.")

    buttons = [
        ("research_custom", "Research All Custom Advances",
         "Instantly research every unique advance available to you - nation, "
         "culture, religion, government, and the unique entries of the "
         "building/ship/reform trees - your own plus any you unlocked in the "
         "other tabs. Plain always-available advances stay unresearched."),
        ("research_all", "Research All Advances",
         "Instantly research every advance available to you, including the "
         "default trees."),
        ("research_current_era", "Research Current Era",
         "Instantly research every available advance of the age your game is "
         "currently in."),
        ("research_previous_eras", "Research Previous Eras",
         "Instantly research every available advance of the ages before the "
         "current one."),
    ]
    for bid, bname, bdesc in buttons:
        loc["%s__%s_name" % (MOD_ID, bid)] = bname
        loc["%s__%s_desc" % (MOD_ID, bid)] = bdesc
        loc["%s__%s_text" % (MOD_ID, bid)] = bname
        loc["%s_log_%s" % (MOD_ID, bid)] = "clicked %s (Handicap Advances)" % bname

    # Mod Action Log phrasing (entries render as: [actor] [arg1] [action] [arg2])
    loc["%s_log_turned_on" % MOD_ID] = "turned ON"
    loc["%s_log_turned_off" % MOD_ID] = "turned OFF"
    loc["%s_log_changed" % MOD_ID] = "changed"
    loc["%s_log_suffix" % MOD_ID] = "(Handicap Advances)"

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
    reg.append("\t\toption_count = 3")
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
        if alias:
            reg.append("\tcmm_sync_bool_alias = { setting = %s__%s alias = %s }"
                       % (MOD_ID, setting_id, alias))
    reg.append("}")
    reg.append("")
    reg.append("# Toggling a parent (continent / region / select-all) copies its new")
    reg.append("# value onto every child toggle, then aliases are re-synced.")
    reg.append("hafp_handle_callback = {")
    for parent, children in parents.items():
        reg.append("\tif = {")
        reg.append("\t\tlimit = { var:cmf_callback = flag:%s__%s }" % (MOD_ID, parent))
        reg.append("\t\tif = {")
        reg.append('\t\t\tlimit = { "variable_map(cmm|flag:%s__%s)" >= 1 }' % (MOD_ID, parent))
        for child in children:
            reg.append("\t\t\tadd_to_variable_map = { name = cmm key = flag:%s__%s value = 1 }"
                       % (MOD_ID, child))
        reg.append("\t\t}")
        reg.append("\t\telse = {")
        for child in children:
            reg.append("\t\t\tadd_to_variable_map = { name = cmm key = flag:%s__%s value = 0 }"
                       % (MOD_ID, child))
        reg.append("\t\t}")
        reg.append("\t}")
    reg.append("\thafp_sync_aliases = yes")
    reg.append("\t# Record every toggle/scope change in the CMF Mod Action Log")
    for setting_id, tab, group, alias in toggles:
        reg.append("\tif = {")
        reg.append("\t\tlimit = { var:cmf_callback = flag:%s__%s }" % (MOD_ID, setting_id))
        reg.append("\t\tif = {")
        reg.append('\t\t\tlimit = { "variable_map(cmm|flag:%s__%s)" >= 1 }' % (MOD_ID, setting_id))
        reg.append("\t\t\tcmf_log_with_args = { action = %s_log_turned_on arg1 = %s__%s_name arg2 = %s_log_suffix }"
                   % (MOD_ID, MOD_ID, setting_id, MOD_ID))
        reg.append("\t\t}")
        reg.append("\t\telse = {")
        reg.append("\t\t\tcmf_log_with_args = { action = %s_log_turned_off arg1 = %s__%s_name arg2 = %s_log_suffix }"
                   % (MOD_ID, MOD_ID, setting_id, MOD_ID))
        reg.append("\t\t}")
        reg.append("\t}")
    reg.append("\tif = {")
    reg.append("\t\tlimit = { var:cmf_callback = flag:%s__research_scope }" % MOD_ID)
    reg.append("\t\tcmf_log_with_args = { action = %s_log_changed arg1 = %s__research_scope_name arg2 = %s_log_suffix }"
               % (MOD_ID, MOD_ID, MOD_ID))
    reg.append("\t}")
    for bid, _, _ in buttons:
        reg.append("\tif = {")
        reg.append("\t\tlimit = { var:cmf_callback = flag:%s__%s }" % (MOD_ID, bid))
        reg.append("\t\thafp_%s = yes" % bid)
        reg.append("\t\tcmf_log = { action = %s_log_%s }" % (MOD_ID, bid))
        reg.append("\t}")
    reg.append("}")

    # ------------------------------------------------------------------ #
    # Emit research effects                                              #
    # ------------------------------------------------------------------ #
    def research_block(adv_id, indent="\t"):
        # Scope paths through the limit (dropdown values checked exactly):
        #  * 2 "All advances": force-research anything the player has unlocked
        #    (the advance's rewritten potential: own nation OR mod toggles),
        #    ignoring institutions and age.
        #  * 1 "Embraced institutions only" / 3 "... current age only":
        #    has_advance_available (unlocked + reached age + own institution
        #    requirement) PLUS the institution requirements inherited from
        #    prerequisite roots; option 3 additionally requires the advance to
        #    belong to the age the game is currently in. Deliberately NOT
        #    can_research_advance: that also demands every prerequisite be
        #    researched, which skipped custom advances hanging off unresearched
        #    plain advances (e.g. Classic Scholasticism, which stays locked).
        info = advs[adv_id]
        scope = '"variable_map(cmm|flag:%s__research_scope)"' % MOD_ID
        lines = ["%sif = {" % indent,
                 "%s\tlimit = {" % indent,
                 "%s\t\tNOT = { has_advance = %s }" % (indent, adv_id),
                 "%s\t\tOR = {" % indent,
                 "%s\t\t\tAND = {" % indent,
                 "%s\t\t\t\t%s = 2" % (indent, scope)]
        for gl in gates.get(adv_id, ()):
            lines.append("%s\t\t\t\t%s" % (indent, gl))
        lines += ["%s\t\t\t}" % indent,
                  "%s\t\t\tAND = {" % indent,
                  "%s\t\t\t\thas_advance_available = %s" % (indent, adv_id)]
        for inst in sorted(info.get("inst_all") or ()):
            lines.append("%s\t\t\t\thas_embraced_institution = institution:%s"
                         % (indent, inst))
        lines += ["%s\t\t\t\tOR = {" % indent,
                  "%s\t\t\t\t\t%s = 1" % (indent, scope)]
        if info["age"]:
            lines += ["%s\t\t\t\t\tAND = {" % indent,
                      "%s\t\t\t\t\t\t%s = 3" % (indent, scope),
                      "%s\t\t\t\t\t\tcurrent_age = %s" % (indent, info["age"]),
                      "%s\t\t\t\t\t}" % indent]
        else:
            lines.append("%s\t\t\t\t\t%s = 3" % (indent, scope))
        lines += ["%s\t\t\t\t}" % indent,
                  "%s\t\t\t}" % indent,
                  "%s\t\t}" % indent,
                  "%s\t}" % indent,
                  "%s\tresearch_advance = advance_type:%s" % (indent, adv_id),
                  "%s}" % indent]
        return lines

    res = ["﻿# Generated by tools/generate_cmm.py - do not edit by hand.",
           "# Root scope: country (the player clicking the CMM button)."]

    # each advance's research block is emitted exactly once, in either the
    # generic or custom half of its age effect; composite effects call these
    by_age = defaultdict(list)
    no_age = []
    for adv_id in order:
        if advs[adv_id]["age"]:
            by_age[advs[adv_id]["age"]].append(adv_id)
        else:
            no_age.append(adv_id)

    for age_id, _ in AGES:
        for half, is_custom in (("generic", False), ("custom", True)):
            res.append("")
            res.append("hafp_research_%s_%s = {" % (age_id, half))
            half_ids = [a for a in by_age.get(age_id, [])
                        if advs[a]["custom"] == is_custom]
            for adv_id in topo_sort(half_ids):
                res.extend(research_block(adv_id))
            res.append("}")
        res.append("")
        res.append("hafp_research_%s = {" % age_id)
        res.append("\thafp_research_%s_generic = yes" % age_id)
        res.append("\thafp_research_%s_custom = yes" % age_id)
        res.append("}")

    for half, is_custom in (("generic", False), ("custom", True)):
        res.append("")
        res.append("hafp_research_no_age_%s = {" % half)
        half_ids = [a for a in no_age if advs[a]["custom"] == is_custom]
        for adv_id in topo_sort(half_ids):
            res.extend(research_block(adv_id))
        res.append("}")
    res.append("")
    res.append("hafp_research_no_age = {")
    res.append("\thafp_research_no_age_generic = yes")
    res.append("\thafp_research_no_age_custom = yes")
    res.append("}")

    res.append("")
    res.append("hafp_research_custom = {")
    for age_id, _ in AGES:
        res.append("\thafp_research_%s_custom = yes" % age_id)
    res.append("\thafp_research_no_age_custom = yes")
    res.append("}")

    res.append("")
    res.append("hafp_research_all = {")
    for age_id, _ in AGES:
        res.append("\thafp_research_%s = yes" % age_id)
    res.append("\thafp_research_no_age = yes")
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
    print("advances known: %d (%d custom)" % (
        len(advs), sum(1 for a in advs.values() if a["custom"])))


if __name__ == "__main__":
    main()
