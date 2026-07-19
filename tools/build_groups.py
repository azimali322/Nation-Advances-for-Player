#!/usr/bin/env python3
"""Build the advance-group mapping (tools/data/groups.json) from vanilla files.

For every advance in the vanilla advances folder this script determines which
selection groups it belongs to:

  * nation advances (has_or_had_tag gates): capital location of the tag at the
    1337 start -> area -> region -> continent (map_data/definitions.txt).
    Formable nations absent in 1337 fall back to their formable definition's
    regions/areas, then to a manual table.
  * advances gated on region:/area:/continent: scopes use those directly
    (continent refs may be sub-continents; they resolve to the parent continent
    plus all regions inside the sub-continent).
  * advances gated on cultures with no other geography fall back to where those
    cultures' pops live in 1337 (06_pops.txt), at region level.
  * culture / culture-group files: one toggle per file, grouped under the
    continent where the culture's pops predominantly live.
  * religion / government files: one toggle per file, flat categories.
  * special files with no usable geography (colonial_nations, estate_cossacks):
    one toggle per file in a Special category.
  * generic vanilla trees (0_*, 1_*, ..., diplomacy, ctype_*): master-only.

Output: tools/data/groups.json, consumed by generate_advances.py and
generate_cmm.py.
"""

import json
import os
import re
import sys
from collections import defaultdict

GAME_DEFAULT = r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V"

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "data", "groups.json")

GENERIC_FILES = {
    "0_age_of_absolutism.txt", "0_age_of_discovery.txt", "0_age_of_reformation.txt",
    "0_age_of_renaissance.txt", "0_age_of_revolutions.txt", "0_age_of_traditions.txt",
    "1_building_unlocks.txt", "2_army_unlocks.txt", "2_ship_unlocks.txt",
    "3_cabinet_actions_unlocks.txt", "3_character_interaction_unlocks.txt",
    "3_fort_level.txt", "3_production_method_unlocks.txt", "3_reform_unlocks.txt",
    "3_road_unlocks.txt", "3_supply_limit.txt", "4_choices_adm.txt",
    "4_choices_dip.txt", "4_choices_mil.txt", "ctype_army.txt",
    "ctype_buildings.txt", "ctype_location.txt", "diplomacy_unlocks.txt",
    "new_world.txt", "readme.txt", "_advances_template.txt",
}

# Manual fallbacks: tag -> region id, applied when neither the 1337 setup nor
# formable definitions place the tag. Verified against definitions at build time.
MANUAL_TAG_REGIONS = {
    "HIN": "hindustan_region",   # Hindustan (formable)
    "MLC": "indochina_region",   # Malacca (formable, Malay peninsula)
    "AYU": "indochina_region",   # Ayutthaya (formable)
    "ASK": "japan_region",       # Ashikaga (formable)
    "MLK": "caucasus_region",    # appears in Armenian culture advances
    "MTP": "italy_region",       # appears in Tuscan culture advances
}

SPECIAL_FILES = {
    "colonial_nations.txt": "Colonial nation advances",
    "estate_cossacks.txt": "Cossacks estate advances",
}

# Culture files gated on scripted triggers or unresolvable refs:
# file -> (home continent, home region or None).
MANUAL_FILE_HOMES = {
    "culture_nomadic.txt": ("asia", None),  # is_former_or_current_nomadic_steppe_culture
    "culture_cham.txt": ("asia", "indochina_region"),  # Champa (cham_language)
}


def strip_comments(text):
    return re.sub(r"#[^\n]*", "", text)


def tokenize(text):
    return re.findall(r"\{|\}|=|[^\s{}=]+", strip_comments(text))


def parse_nested(tokens, i=0):
    result = {}
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok == "}":
            return result, i + 1
        if i + 1 < n and tokens[i + 1] == "=":
            if i + 2 < n and tokens[i + 2] == "{":
                sub, i = parse_nested(tokens, i + 3)
                result.setdefault(tok, []).append(sub)
            else:
                result.setdefault(tok, []).append(tokens[i + 2] if i + 2 < n else None)
                i += 3
                continue
        else:
            result.setdefault(tok, []).append(None)
            i += 1
            continue
    return result, i


def parse_file_nested(path):
    with open(path, encoding="utf-8-sig") as fh:
        tree, _ = parse_nested(tokenize(fh.read()), 0)
    return tree


def load_hierarchy(game):
    path = os.path.join(game, "game", "in_game", "map_data", "definitions.txt")
    tree = parse_file_nested(path)

    loc_to_area = {}
    area_info = {}      # area -> (region, continent)
    region_info = {}    # region -> continent
    subcont_info = {}   # subcontinent -> (continent, [regions])
    continents = set()
    for continent, subs in tree.items():
        continents.add(continent)
        for sub in subs:
            if not isinstance(sub, dict):
                continue
            for subcont, regions in sub.items():
                sub_regions = []
                for regs in regions:
                    if not isinstance(regs, dict):
                        continue
                    for region, areas in regs.items():
                        region_info[region] = continent
                        sub_regions.append(region)
                        for ars in areas:
                            if not isinstance(ars, dict):
                                continue
                            for area, provinces in ars.items():
                                area_info[area] = (region, continent)
                                for provs in provinces:
                                    if not isinstance(provs, dict):
                                        continue
                                    for prov, locs in provs.items():
                                        for entry in locs:
                                            if isinstance(entry, dict):
                                                for loc in entry:
                                                    loc_to_area[loc] = area
                subcont_info[subcont] = (continent, sub_regions)
    return loc_to_area, area_info, region_info, subcont_info, continents


def load_capitals(game):
    path = os.path.join(game, "game", "main_menu", "setup", "start", "10_countries.txt")
    text = strip_comments(open(path, encoding="utf-8-sig").read())
    capitals = {}
    current = None
    for m in re.finditer(r"^\t([A-Z0-9]{3}) = \{|^\t\tcapital = ([a-z0-9_]+)", text, re.M):
        if m.group(1):
            current = m.group(1)
        elif current and current not in capitals:
            capitals[current] = m.group(2)
    return capitals


def load_formables(game):
    path = os.path.join(game, "game", "in_game", "common", "formable_countries",
                        "00_formable_countries.txt")
    tree = parse_file_nested(path)
    formables = {}
    for fid, entries in tree.items():
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            tags = entry.get("tag")
            if not tags:
                continue
            tag = tags[0]
            regions, areas = [], []
            for blk in entry.get("regions", []):
                if isinstance(blk, dict):
                    regions.extend(blk.keys())
            for blk in entry.get("areas", []):
                if isinstance(blk, dict):
                    areas.extend(blk.keys())
            info = formables.setdefault(tag, {"regions": [], "areas": []})
            info["regions"].extend(r for r in regions if r not in info["regions"])
            info["areas"].extend(a for a in areas if a not in info["areas"])
    return formables


def load_culture_groups(game):
    """culture -> [groups], group -> [cultures], language -> [cultures]."""
    cdir = os.path.join(game, "game", "in_game", "common", "cultures")
    culture_to_groups = {}
    group_to_cultures = defaultdict(list)
    language_to_cultures = defaultdict(list)
    for fname in os.listdir(cdir):
        if not fname.endswith(".txt"):
            continue
        tree = parse_file_nested(os.path.join(cdir, fname))
        for cid, entries in tree.items():
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                groups = []
                for blk in entry.get("culture_groups", []):
                    if isinstance(blk, dict):
                        groups.extend(blk.keys())
                if groups:
                    culture_to_groups[cid] = groups
                    for g in groups:
                        group_to_cultures[g].append(cid)
                for lang in entry.get("language", []):
                    if isinstance(lang, str):
                        language_to_cultures[lang].append(cid)
    return culture_to_groups, dict(group_to_cultures), dict(language_to_cultures)


def load_pops_culture_areas(game, loc_to_area):
    path = os.path.join(game, "game", "main_menu", "setup", "start", "06_pops.txt")
    culture_area = defaultdict(lambda: defaultdict(float))
    current_area = None
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.split("#")[0]
            m = re.match(r"^\s*([a-z0-9_]+)\s*=\s*\{", line)
            if m and "define_pop" not in line:
                current_area = loc_to_area.get(m.group(1))
                continue
            pm = re.search(r"size\s*=\s*([0-9.]+)\s+culture\s*=\s*([a-z0-9_]+)", line)
            if pm and current_area:
                culture_area[pm.group(2)][current_area] += float(pm.group(1))
    return culture_area


def load_loc_names(game):
    names = {}
    loc_dir = os.path.join(game, "game", "main_menu", "localization", "english")
    if not os.path.isdir(loc_dir):
        return names
    for fname in os.listdir(loc_dir):
        if not re.search(r"(area|region|continent|country_names|culture|religion|government)"
                         r".*_l_english\.yml$", fname):
            continue
        for line in open(os.path.join(loc_dir, fname), encoding="utf-8-sig"):
            m = re.match(r'\s*([A-Za-z0-9_]+):\d*\s+"(.*?)"', line)
            if m:
                names.setdefault(m.group(1), m.group(2))
    return names


def humanize(ident):
    ident = re.sub(r"_(area|region|province|group|culture)$", "", ident)
    return ident.replace("_", " ").title()


def split_advances(text):
    """Yield (advance_id, body) for depth-0 blocks; tolerates indented ids."""
    text = strip_comments(text)
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0:
            m = re.compile(r"([A-Za-z0-9_.]+)\s*=\s*\{").match(text, i)
            if m:
                d = 0
                for j in range(m.end() - 1, n):
                    if text[j] == "{":
                        d += 1
                    elif text[j] == "}":
                        d -= 1
                        if d == 0:
                            yield m.group(1), text[m.end() : j]
                            i = j
                            break
        i += 1


def main():
    game = sys.argv[1] if len(sys.argv) > 1 else GAME_DEFAULT
    adv_dir = os.path.join(game, "game", "in_game", "common", "advances")

    loc_to_area, area_info, region_info, subcont_info, continents = load_hierarchy(game)
    capitals = load_capitals(game)
    formables = load_formables(game)
    culture_to_groups, group_to_cultures, language_to_cultures = load_culture_groups(game)
    culture_areas = load_pops_culture_areas(game, loc_to_area)
    loc_names = load_loc_names(game)

    unmapped_tags = set()

    def tag_geo(tag):
        cap = capitals.get(tag)
        if cap and cap in loc_to_area:
            area = loc_to_area[cap]
            region, continent = area_info[area]
            return [area], [region], [continent]
        f = formables.get(tag)
        if f:
            regions = [r for r in f["regions"] if r in region_info]
            areas = [a for a in f["areas"] if a in area_info]
            for a in areas:
                if area_info[a][0] not in regions:
                    regions.append(area_info[a][0])
            conts = sorted({region_info[r] for r in regions})
            if regions:
                return areas, regions, conts
        if tag in MANUAL_TAG_REGIONS:
            region = MANUAL_TAG_REGIONS[tag]
            return [], [region], [region_info[region]]
        return None

    def expand_cultures(cultures, groups, languages=()):
        out = set(cultures)
        for g in groups:
            out.update(group_to_cultures.get(g, []))
        for lang in languages:
            out.update(language_to_cultures.get(lang, []))
        return out

    def culture_geo(cultures):
        """Dominant continent, region, and per-area sizes for a culture set."""
        cont_totals = defaultdict(float)
        region_totals = defaultdict(float)
        for c in cultures:
            for area, size in culture_areas.get(c, {}).items():
                region, continent = area_info[area]
                cont_totals[continent] += size
                region_totals[region] += size
        if not cont_totals:
            return None, None
        continent = max(cont_totals, key=cont_totals.get)
        region = max((r for r in region_totals if region_info[r] == continent),
                     key=region_totals.get, default=None)
        return continent, region

    files = {}
    for fname in sorted(os.listdir(adv_dir)):
        if not fname.endswith(".txt") or fname in GENERIC_FILES:
            continue
        text = open(os.path.join(adv_dir, fname), encoding="utf-8-sig").read()
        entry = {"kind": None, "advances": {}}

        if fname.startswith("culture_group_"):
            entry["kind"] = "culture_group"
        elif fname.startswith("culture_"):
            entry["kind"] = "culture"
        elif fname.startswith("religion_"):
            entry["kind"] = "religion"
        elif fname.startswith("government_"):
            entry["kind"] = "government"
        elif fname in SPECIAL_FILES:
            entry["kind"] = "special"
        else:
            entry["kind"] = "nation"

        all_cultures, all_groups, all_languages = set(), set(), set()
        for adv_id, body in split_advances(text):
            adv = {}
            age_m = re.search(r"\bage\s*=\s*(age_[a-z0-9_]+)", body)
            adv["age"] = age_m.group(1) if age_m else None
            inst_m = re.search(r"has_embraced_institution\s*=\s*institution:([a-z0-9_]+)", body)
            adv["institution"] = inst_m.group(1) if inst_m else None

            tags = sorted(set(re.findall(r"has_or_had_tag\s*=\s*([A-Za-z0-9]{3})", body)))
            adv["tags"] = tags
            areas, regions, conts = set(), set(), set()
            for tag in tags:
                geo = tag_geo(tag)
                if geo is None:
                    unmapped_tags.add((fname, tag))
                    continue
                a, r, c = geo
                areas.update(a)
                regions.update(r)
                conts.update(c)
            for rid in re.findall(r"region:([a-z0-9_]+)", body):
                if rid in region_info:
                    regions.add(rid)
                    conts.add(region_info[rid])
            for aid in re.findall(r"area:([a-z0-9_]+)", body):
                if aid in area_info:
                    areas.add(aid)
                    regions.add(area_info[aid][0])
                    conts.add(area_info[aid][1])
            for cid in re.findall(r"continent:([a-z0-9_]+)", body):
                if cid in continents:
                    conts.add(cid)
                elif cid in subcont_info:
                    parent, sub_regions = subcont_info[cid]
                    conts.add(parent)
                    regions.update(sub_regions)

            cults = set(re.findall(r"culture\s*=\s*culture:([a-z0-9_]+)", body))
            cults.update(re.findall(r"contains_culture\s*=\s*culture:([a-z0-9_]+)", body))
            grps = set(re.findall(r"culture_group:([a-z0-9_]+)", body))
            langs = set(re.findall(r"language:([a-z0-9_]+)", body))
            all_cultures.update(cults)
            all_groups.update(grps)
            all_languages.update(langs)

            # culture-gated nation/special advances with no other geography:
            # place them where the culture's pops live (region level)
            if entry["kind"] in ("nation", "special") and not conts and (cults or grps or langs):
                continent, region = culture_geo(expand_cultures(cults, grps, langs))
                if continent:
                    conts.add(continent)
                    if region:
                        regions.add(region)

            adv["areas"] = sorted(areas)
            adv["regions"] = sorted(regions)
            adv["continents"] = sorted(conts)
            entry["advances"][adv_id] = adv

        if entry["kind"] in ("culture", "culture_group"):
            continent, region = culture_geo(
                expand_cultures(all_cultures, all_groups, all_languages))
            if not continent:
                # fall back to explicit area/region refs, then the manual table
                for adv in entry["advances"].values():
                    if adv["continents"]:
                        continent = adv["continents"][0]
                        region = adv["regions"][0] if adv["regions"] else None
                        break
            if not continent and fname in MANUAL_FILE_HOMES:
                continent, region = MANUAL_FILE_HOMES[fname]
            entry["cultures"] = sorted(all_cultures | all_groups | all_languages)
            entry["home_continent"] = continent
            entry["home_region"] = region

        # nation/special advances that could not be placed individually inherit
        # the union of the rest of their file (they toggle with their file-mates)
        if entry["kind"] in ("nation", "special"):
            u_areas, u_regions, u_conts = set(), set(), set()
            for adv in entry["advances"].values():
                u_areas.update(adv["areas"])
                u_regions.update(adv["regions"])
                u_conts.update(adv["continents"])
            for adv in entry["advances"].values():
                if not adv["continents"] and u_conts:
                    adv["areas"] = sorted(u_areas)
                    adv["regions"] = sorted(u_regions)
                    adv["continents"] = sorted(u_conts)
                    adv["inherited"] = True

        files[fname] = entry

    # Aggregate the group inventory actually used by nation/special advances
    used_areas, used_regions, used_continents = {}, {}, {}
    for fname, entry in files.items():
        if entry["kind"] not in ("nation", "special"):
            continue
        for adv in entry["advances"].values():
            for a in adv["areas"]:
                r, c = area_info[a]
                used_areas.setdefault(a, {"region": r, "continent": c,
                                          "name": loc_names.get(a, humanize(a)),
                                          "tags": set()})
                used_areas[a]["tags"].update(adv["tags"])
            for r in adv["regions"]:
                used_regions.setdefault(r, {"continent": region_info[r],
                                            "name": loc_names.get(r, humanize(r))})
            for c in adv["continents"]:
                used_continents.setdefault(c, {"name": loc_names.get(c, humanize(c))})
    for a in used_areas.values():
        a["tags"] = sorted(a["tags"])
        a["tag_names"] = [loc_names.get(t, t) for t in a["tags"]]

    data = {
        "files": files,
        "areas": used_areas,
        "regions": used_regions,
        "continents": used_continents,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)

    print("continents used:", sorted(used_continents))
    print("regions used: %d, areas used: %d" % (len(used_regions), len(used_areas)))
    kinds = defaultdict(int)
    for e in files.values():
        kinds[e["kind"]] += 1
    print("file kinds:", dict(kinds))
    if unmapped_tags:
        print("UNMAPPED TAGS (%d):" % len(unmapped_tags))
        for fname, tag in sorted(unmapped_tags):
            print("   %s: %s" % (fname, tag))
    for f, e in files.items():
        if e["kind"] in ("nation", "special"):
            missing = [a for a, adv in e["advances"].items() if not adv["continents"]]
            if len(missing) == len(e["advances"]):
                print("FILE WITH NO GEOGRAPHY:", f)
            elif missing:
                print("PARTIAL GEOGRAPHY: %s (%d/%d advances unplaced)"
                      % (f, len(missing), len(e["advances"])))
        if e["kind"] in ("culture", "culture_group") and not e.get("home_continent"):
            print("CULTURE FILE WITHOUT HOME:", f, e.get("cultures"))


if __name__ == "__main__":
    main()
