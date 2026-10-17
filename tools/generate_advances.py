#!/usr/bin/env python3
"""Generate the mod's advances overrides from the vanilla EU5 game files.

For every advance in the vanilla `in_game/common/advances` folder this script
rewrites the availability gates so the player can opt in to researching any
nation's unique advances, at several granularities driven by CMM settings
(see tools/build_groups.py for how advances are assigned to groups):

  potential = { X }   becomes

  potential = {
      OR = {
          AND = {
              has_variable = hafp_enabled              # mod master switch
              OR = {
                  has_variable = hafp_all_advances_enabled   # unlock everything
                  has_variable = hafp_g_age_<age>            # unlock whole era
                  has_variable = hafp_g_cont_<continent>     # geography toggles
                  has_variable = hafp_g_reg_<region>
                  has_variable = hafp_g_area_<area>
                  has_variable = hafp_g_f_<file>             # category toggles
              }
          }
          AND = { X }                                  # original conditions
      }
  }

  * a top-level `government = <type>` gate is folded into the wrapped
    `potential` (the engine treats the key as a hard filter otherwise).
  * `allow = { X }` gates (institution requirements) are left untouched so
    they behave exactly as in the base game.
  * generic vanilla trees only get the master + era variables.

Advances with none of those gates are left untouched; files with no changes
are not shipped. Run tools/build_groups.py first (it writes
tools/data/groups.json); re-run both after every game patch.

Usage (defaults match a standard Steam install):
  python tools/generate_advances.py [--game <EU5 folder>] [--out <folder>]
"""

import argparse
import json
import os
import re
import sys

MASTER_ENABLED = "hafp_enabled"
UNLOCK_ALL = "hafp_all_advances_enabled"
ALLOW_UNIT_UNLOCKS = "hafp_allow_unit_unlocks"

# An advance grants units if it unlocks a unit or levy outright, or enables
# building a unit family through a modifier (global_may_build_paik_units).
UNIT_UNLOCK_RE = re.compile(
    r"\bunlock_unit\s*=|\bunlock_levy\s*=|may_build_[a-z_]*units\s*=\s*yes")


# "Tall" advances: bonuses aimed at growing and governing what you already own -
# development, population, prosperity, the food economy, raw material / goods
# output, pop promotion, plus the cabinet, government reforms, crown power and
# estate satisfaction equilibrium. The full list is in REQUIREMENTS.md (item 9).
TALL_KEYS = {
    # development, population, prosperity
    "global_monthly_development",
    "global_population_growth",
    "global_migration_attraction",      # 1.4: pulls pops in = population growth
    "non_rural_migration_attraction",   # 1.4.1: "Towns and Cities Migration Attraction"
    "global_monthly_prosperity",
    # food economy
    "global_monthly_food_modifier",
    "food_purchase_efficiency",
    "food_consumption_modifier",
    "global_pop_food_consumption",
    "global_clergy_food_consumption",
    "expand_rgo_farming_cost_modifier",   # cheaper farmland = more food
    # raw materials / production
    "global_raw_material_output",
    "global_production_efficiency",
    "global_max_rgo_size_modifier",       # "Maximum RGO Size"
    "expand_rgo_mining_cost_modifier",
    "expand_rgo_gathering_cost_modifier",
    # pop promotion
    "global_pop_promotion_speed_modifier",
    # colonization and colonial migration (requested 1.4.1) - listed one by one
    # because a blanket "colonial" rule would also sweep in colonial-war costs,
    # colonial-federation politics and AI policy biases
    "colonial_migration_size",            # "Monthly Colonial Migration"
    "colonial_migration_size_modifier",
    "colonial_range",
    "colonial_range_modifier",
    "colonial_maintenance_efficiency",
    "create_colonial_charter_cost_modifier",
    "can_colonize",
    "can_create_colonial_charters",
    "can_invite_settlers",
    # cabinet seats - the game calls this modifier "Cabinet Seats", so it does
    # not contain "cabinet" and is not caught by TALL_KEY_SUBSTRINGS
    "government_size",
}
# per-good output (raw material bonuses, incl. masonry) and estate satisfaction
# equilibrium (the game's "target satisfaction")
TALL_KEY_SUFFIXES = ("_output_modifier", "_target_satisfaction")
# whole families: population capacity (flat and %), food storage (capacity and
# decay, flat and %), pop migration speed and character life expectancy
# (requested 1.4.1), the cabinet (members, efficiency, actions), government
# reforms (unlocks and slots), crown power, estate satisfaction recovery,
# literacy (max and monthly gain, overall and per pop type), research speed,
# and prosperity. Rural migration attraction stays out on purpose: it pulls
# pops to the countryside, away from towns and cities.
TALL_KEY_SUBSTRINGS = ("population_capacity", "food_capacity", "food_decay",
                       "migration_speed", "life_expectancy",
                       "cabinet", "government_reform", "crown",
                       "satisfaction_recovery", "literacy", "research",
                       "prosperity")

# Buildings: an advance also counts as tall when it unlocks a building that
# raises population capacity, food production or storage, migration
# attraction, development or prosperity (aqueducts, bunds, polders, ...).
# load_tall_buildings() derives that set from the game's building files; these
# are added regardless, because the user asked for them by name. (Oman's Falaj
# is deliberately absent: it is an event-only building, granted by an event
# chain rather than by any advance, so there is nothing for the toggle to
# unlock.)
TALL_BUILDINGS = {"bund", "calmecac", "incamisana", "polders", "terraces"}
TALL_BUILDING_KEY_RE = re.compile(
    r"\b(?:local|global)_[a-z_]*(?:population_capacity|monthly_food|food_capacity|"
    r"food_decay|migration_attraction|monthly_development|prosperity)[a-z_]*\s*=")
_tall_buildings = set(TALL_BUILDINGS)


# Matched by a family rule but not a modifier: research_cost sets the price of
# the advance it sits in (2.0 = twice as expensive), not the country's research.
TALL_EXCLUDED_KEYS = {"research_cost"}
_LOWER_IS_BETTER_RE = re.compile(r"decay|consumption|cost")


def is_tall_key(key):
    if key in TALL_EXCLUDED_KEYS:
        return False
    return (key in TALL_KEYS or key.endswith(TALL_KEY_SUFFIXES)
            or any(s in key for s in TALL_KEY_SUBSTRINGS))


def is_bonus(key, value):
    """Whether a modifier value helps the player.

    Town rights often trade a bonus for a penalty (Bohemian Royal Cities lowers
    nobles' satisfaction), so a tall modifier only counts when it is a bonus:
    named constants unless they are penalties, numbers above zero - or below
    zero for decay, consumption and cost modifiers, where lower is better."""
    value = value.strip('"')
    try:
        number = float(value)
    except ValueError:
        if value in ("yes", "no"):
            return value == "yes"
        return not re.search(r"penalty|malus", value)
    return number < 0 if _LOWER_IS_BETTER_RE.search(key) else number > 0


def load_tall_buildings(game):
    """Add every building whose definition carries a tall modifier."""
    folder = os.path.join(game, "game", "in_game", "common", "building_types")
    found = set()
    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            if not fname.endswith(".txt"):
                continue
            with open(os.path.join(folder, fname), encoding="utf-8-sig") as fh:
                text = fh.read()
            mask = strip_positions(text)
            for name, _k, obrace, cbrace in find_blocks(text, mask, 0, len(text)):
                if TALL_BUILDING_KEY_RE.search(text[obrace:cbrace]):
                    found.add(name)
    _tall_buildings.update(found)
    return found


def is_tall_advance(body, tall_buildings=None):
    """True if the advance carries any 'tall' economy/growth/governance modifier
    or unlocks a tall building."""
    buildings = _tall_buildings if tall_buildings is None else tall_buildings
    for line in body.splitlines():
        code = line.split("#")[0]
        m = re.match(r"\s*([a-z_0-9]+)\s*=\s*([^{\s]+)", code)
        if not m:
            continue
        if m.group(1) == "unlock_building":
            if m.group(2) in buildings:
                return True
        elif is_tall_key(m.group(1)) and is_bonus(m.group(1), m.group(2)):
            return True
    return False


def is_military_advance(fname, body):
    """True only for advances that grant army/navy UNITS.

    Deliberately narrow: advances that merely buff military stats (infantry
    power, morale, sailors, ...) are NOT affected - the toggle's purpose is to
    keep foreign unit rosters locked, not foreign military bonuses."""
    return bool(UNIT_UNLOCK_RE.search(body))

KEY_RE = re.compile(r"([A-Za-z0-9_.:]+)\s*=\s*(\{|\"[^\"]*\"|[^\s{}#]+)")

HERE = os.path.dirname(os.path.abspath(__file__))
GROUPS_PATH = os.path.join(HERE, "data", "groups.json")


def strip_positions(text):
    mask = [False] * len(text)
    in_comment = False
    in_quote = False
    for i, ch in enumerate(text):
        if in_comment:
            mask[i] = True
            if ch == "\n":
                in_comment = False
                mask[i] = False
        elif in_quote:
            mask[i] = True
            if ch == '"':
                in_quote = False
        elif ch == "#":
            in_comment = True
            mask[i] = True
        elif ch == '"':
            in_quote = True
            mask[i] = True
    return mask


def match_brace(text, mask, open_brace):
    depth = 0
    for i in range(open_brace, len(text)):
        if mask[i]:
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("Unbalanced braces at offset %d" % open_brace)


def find_blocks(text, mask, start, end):
    depth = 0
    i = start
    while i < end:
        if mask[i]:
            i += 1
            continue
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0:
            m = KEY_RE.match(text, i)
            if m and not mask[m.start(1)]:
                if m.group(2) == "{":
                    open_brace = m.end() - 1
                    close = match_brace(text, mask, open_brace)
                    yield m.group(1), m.start(), open_brace, close
                    i = close + 1
                    continue
                i = m.end()
                continue
        i += 1


def find_scalar_keys(text, mask, start, end, key):
    depth = 0
    i = start
    results = []
    while i < end:
        if mask[i]:
            i += 1
            continue
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0:
            m = KEY_RE.match(text, i)
            if m and not mask[m.start(1)]:
                if m.group(1) == key and m.group(2) != "{":
                    results.append((m.start(), m.end(), m.group(2)))
                if m.group(2) == "{":
                    close = match_brace(text, mask, m.end() - 1)
                    i = close + 1
                    continue
                i = m.end()
                continue
        i += 1
    return results


def split_dlc_checks(inner):
    """-> (top-level `has_dlc = X` lines, inner with them removed).

    DLC content in EU5 lives in the base files, locked by a top-level has_dlc
    check in its potential. Those checks must gate the mod's unlock branch as
    well, or Unlock All would hand paid DLC advances to players who do not own
    the DLC - so wrap_gate keeps them outside the OR."""
    mask = strip_positions(inner)
    found = find_scalar_keys(inner, mask, 0, len(inner), "has_dlc")
    lines = ["has_dlc = %s" % value for _s, _e, value in found]
    for start, end, _v in sorted(found, reverse=True):
        inner = inner[:start] + inner[end:]
    return lines, inner


def wrap_gate(inner, unlock_vars, extra_lines=None, military=False):
    """Build the wrapped gate body from the original inner content."""
    dlc_lines, inner = split_dlc_checks(inner)
    body = "".join("\n\t\t%s" % line for line in dlc_lines)
    body += "\n\t\tOR = {\n\t\t\tAND = {\n\t\t\t\thas_variable = %s" % MASTER_ENABLED
    if military:
        # unit-granting advances additionally require the opt-in toggle
        body += "\n\t\t\t\thas_variable = %s" % ALLOW_UNIT_UNLOCKS
    body += "\n\t\t\t\tOR = {"
    for var in unlock_vars:
        body += "\n\t\t\t\t\thas_variable = %s" % var
    body += "\n\t\t\t\t}\n\t\t\t}\n\t\t\tAND = {"
    if extra_lines:
        for line in extra_lines:
            body += "\n\t\t\t\t%s" % line
    inner = inner.strip()
    if inner:
        for line in inner.splitlines():
            body += "\n\t\t\t\t" + line.strip()
    body += "\n\t\t\t}\n\t\t}\n\t"
    return body


def process_advance(adv_id, block_text, unlock_vars, military=False):
    mask = strip_positions(block_text)

    gov_entries = find_scalar_keys(block_text, mask, 0, len(block_text), "government")
    potential_span = None
    for name, kstart, obrace, cbrace in find_blocks(block_text, mask, 0, len(block_text)):
        if name == "potential":
            potential_span = (kstart, obrace, cbrace)

    if not gov_entries and potential_span is None:
        return block_text, False

    edits = []
    # `government = X` is an engine FILTER KEY on advances, not a trigger; the
    # trigger equivalent (valid inside potential) is government_type.
    gov_lines = ["government_type = government_type:%s" % g[2] for g in gov_entries]

    if potential_span is not None:
        kstart, obrace, cbrace = potential_span
        inner = block_text[obrace + 1 : cbrace]
        edits.append((obrace + 1, cbrace,
                      wrap_gate(inner, unlock_vars, gov_lines, military)))
        for gstart, gend, _ in gov_entries:
            edits.append((gstart, gend, ""))
    elif gov_entries:
        gstart, gend, _ = gov_entries[0]
        replacement = "potential = {%s}" % wrap_gate("", unlock_vars, gov_lines, military)
        edits.append((gstart, gend, replacement))
        for extra_start, extra_end, _ in gov_entries[1:]:
            edits.append((extra_start, extra_end, ""))

    # NOTE: `allow` blocks are deliberately NOT wrapped. They carry institution
    # requirements (e.g. meritocracy_advance), which must behave exactly as in
    # the base game even for unlocked advances - only the research buttons'
    # "All advances" scope may step over them (research_advance forces).

    edits.sort(key=lambda e: e[0], reverse=True)
    new_text = block_text
    for start, end, repl in edits:
        new_text = new_text[:start] + repl + new_text[end:]
    return new_text, True


def unlock_vars_for(adv_id, body, file_entry, fname):
    """The list of has_variable unlocks for this advance, in a stable order."""
    unlock = [UNLOCK_ALL]
    age_m = re.search(r"\bage\s*=\s*(age_[a-z0-9_]+)", body)
    if age_m:
        unlock.append("hafp_g_age_%s" % age_m.group(1))
    if is_tall_advance(body):
        unlock.append("hafp_g_tall")
    if file_entry is None:
        return unlock  # generic vanilla tree: master + era only

    kind = file_entry["kind"]
    adv = file_entry["advances"].get(adv_id, {})
    if kind in ("nation", "special"):
        for c in adv.get("continents", []):
            unlock.append("hafp_g_cont_%s" % c)
        for r in adv.get("regions", []):
            unlock.append("hafp_g_reg_%s" % r)
        for a in adv.get("areas", []):
            unlock.append("hafp_g_area_%s" % a)
    if kind in ("culture", "culture_group", "religion", "government", "special"):
        unlock.append("hafp_g_f_%s" % fname[:-4])
    return unlock


def process_file(text, file_entry, fname):
    mask = strip_positions(text)
    changed = 0
    pieces = []
    last = 0
    military_count = 0
    for name, kstart, obrace, cbrace in find_blocks(text, mask, 0, len(text)):
        body = text[obrace + 1 : cbrace]
        unlock = unlock_vars_for(name, body, file_entry, fname)
        military = is_military_advance(fname, body)
        new_body, did = process_advance(name, body, unlock, military)
        pieces.append(text[last : obrace + 1])
        pieces.append(new_body)
        last = cbrace
        if did:
            changed += 1
            if military:
                military_count += 1
    pieces.append(text[last:])
    return "".join(pieces), changed, military_count


# ---------------------------------------------------------------------------
# Town rights
#
# Some town rights are locked to a nation, culture or region and carry tall
# bonuses - Byzantium's Imperial Breadbasket (population growth, food storage,
# prosperity), Castile's fueros, the British customals, ... They are not
# advances, so Unlock All and Tall make them available here instead. Only the
# WHO-YOU-ARE part of the potential is relaxed: DLC checks and progression
# requirements (an estate privilege's modifier:allow_*, government reforms,
# policies, HRE status, ...) stay required for everyone, and `allow` blocks are
# never touched. Town rights gated only by progression are left alone.
# ---------------------------------------------------------------------------

TOWN_RIGHT_UNLOCK_VARS = [UNLOCK_ALL, "hafp_g_tall"]
TOWN_RIGHT_KEEP_RE = re.compile(
    r"has_dlc|modifier:|has_reform|has_policy|has_advance|has_law|has_estate_privilege|"
    r"international_organization|special_status|situation")
TOWN_RIGHT_IDENTITY_RE = re.compile(
    r"\b(?:has_or_had_tag|tag|culture|culture_group|religion|religion_group|region|area|"
    r"continent|sub_continent|capital|language)\b")
_STATEMENT_KEY_RE = re.compile(r"[A-Za-z0-9_.:@$'\-]+")
_STATEMENT_OP_RE = re.compile(r"\s*(\?=|<=|>=|!=|=|<|>)\s*")


def top_level_statements(text):
    """Yield (start, end) spans of the depth-0 statements in a block body.

    A statement is `key OP value`, where OP may be `=`, `?=` or a comparison
    and value is a scalar, a quoted string or a {...} block. (KEY_RE and
    find_blocks only understand `=`, so `capital ?= { ... }` is invisible to
    them.)"""
    mask = strip_positions(text)
    i, n = 0, len(text)
    while i < n:
        if mask[i] or text[i].isspace():
            i += 1
            continue
        key = _STATEMENT_KEY_RE.match(text, i)
        if not key:
            i += 1
            continue
        start = i
        op = _STATEMENT_OP_RE.match(text, key.end())
        if not op:
            yield start, key.end()
            i = key.end()
            continue
        k = op.end()
        if k < n and text[k] == "{":
            end = match_brace(text, mask, k) + 1
        elif k < n and text[k] == '"':
            end = text.index('"', k + 1) + 1
        else:
            value = _STATEMENT_KEY_RE.match(text, k)
            end = value.end() if value else k
        yield start, end
        i = end


def is_tall_town_right(body):
    """True if any of the town right's modifier blocks carries a tall bonus,
    using the advance rules on the global equivalent of each local modifier."""
    mask = strip_positions(body)
    for name, _k, obrace, cbrace in find_blocks(body, mask, 0, len(body)):
        if not name.endswith("modifier"):
            continue
        for line in body[obrace + 1:cbrace].splitlines():
            m = re.match(r"\s*([a-z_0-9]+)\s*=\s*([^{\s]+)", line.split("#")[0])
            if not m:
                continue
            key = m.group(1)
            if ((is_tall_key(key) or is_tall_key(key.replace("local_", "global_", 1)))
                    and is_bonus(key, m.group(2))):
                return True
    return False


def split_town_right_potential(inner):
    """-> (statements to keep for everyone, who-you-are statements)."""
    keep, identity = [], []
    for start, end in top_level_statements(inner):
        statement = inner[start:end]
        if TOWN_RIGHT_KEEP_RE.search(statement):
            keep.append(statement)
        elif TOWN_RIGHT_IDENTITY_RE.search(statement):
            identity.append(statement)
        else:
            keep.append(statement)
    return keep, identity


def process_town_right(body):
    """Rewrite one town right body. Returns (new_body, changed)."""
    mask = strip_positions(body)
    potential = [(o, c) for name, _k, o, c in find_blocks(body, mask, 0, len(body))
                 if name == "potential"]
    if len(potential) != 1 or not is_tall_town_right(body):
        return body, False
    obrace, cbrace = potential[0]
    keep, identity = split_town_right_potential(body[obrace + 1:cbrace])
    if not identity:
        return body, False      # gated only by progression - not ours to relax
    new_inner = "".join("\n\t\t" + " ".join(s.split()) for s in keep)
    new_inner += wrap_gate("\n".join(identity), TOWN_RIGHT_UNLOCK_VARS)
    return body[:obrace + 1] + new_inner + body[cbrace:], True


def generate_town_rights(game, out_dir):
    """Write town_rights overrides. Returns (files written, rights unlocked)."""
    src = os.path.join(game, "game", "in_game", "common", "town_rights")
    if not os.path.isdir(src):
        return [], []
    os.makedirs(out_dir, exist_ok=True)
    vanilla_names = {f for f in os.listdir(src) if f.endswith(".txt")}
    written, unlocked = [], []
    for fname in sorted(vanilla_names):
        with open(os.path.join(src, fname), encoding="utf-8-sig") as fh:
            text = fh.read()
        mask = strip_positions(text)
        pieces, last, changed = [], 0, []
        for name, _k, obrace, cbrace in find_blocks(text, mask, 0, len(text)):
            new_body, did = process_town_right(text[obrace + 1:cbrace])
            if did:
                pieces += [text[last:obrace + 1], new_body]
                last = cbrace
                changed.append(name)
        if not changed:
            continue
        pieces.append(text[last:])
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8-sig", newline="\n") as fh:
            fh.write("".join(pieces))
        written.append(fname)
        unlocked += changed
    for fname in os.listdir(out_dir):          # stale or renamed overrides
        if fname.endswith(".txt") and fname not in written:
            os.remove(os.path.join(out_dir, fname))
    return written, unlocked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--game",
        default=r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V",
        help="EU5 install folder",
    )
    parser.add_argument(
        "--out",
        default=os.path.join(HERE, "..", "in_game", "common", "advances"),
        help="Output folder for the generated overrides",
    )
    args = parser.parse_args()

    src = os.path.join(args.game, "game", "in_game", "common", "advances")
    if not os.path.isdir(src):
        sys.exit("Vanilla advances folder not found: %s" % src)
    if not os.path.isfile(GROUPS_PATH):
        sys.exit("Missing %s - run tools/build_groups.py first" % GROUPS_PATH)
    with open(GROUPS_PATH, encoding="utf-8") as fh:
        groups = json.load(fh)
    os.makedirs(args.out, exist_ok=True)
    derived = load_tall_buildings(args.game)
    print("Tall buildings: %d derived from building files + %d named"
          % (len(derived), len(TALL_BUILDINGS)))

    # Drop any override whose filename no longer matches a vanilla file EXACTLY
    # (case-sensitive). Paradox renamed most country advance files between 1.3
    # and 1.4 (country_FRA.txt -> country_fra.txt); on Windows's case-insensitive
    # filesystem a plain regenerate would write into the old spelling and keep
    # shipping an override that no longer lines up with its vanilla file.
    vanilla_names = {f for f in os.listdir(src) if f.endswith(".txt")}
    renamed = []
    if os.path.isdir(args.out):
        for fname in sorted(os.listdir(args.out)):
            if fname.endswith(".txt") and fname not in vanilla_names:
                os.remove(os.path.join(args.out, fname))
                renamed.append(fname)

    total_files = 0
    total_advances = 0
    total_military = 0
    skipped = []
    for fname in sorted(os.listdir(src)):
        if not fname.endswith(".txt"):
            continue
        with open(os.path.join(src, fname), "r", encoding="utf-8-sig") as fh:
            text = fh.read()
        file_entry = groups["files"].get(fname)
        new_text, changed, military = process_file(text, file_entry, fname)
        if changed == 0:
            skipped.append(fname)
            continue
        with open(os.path.join(args.out, fname), "w", encoding="utf-8-sig", newline="\n") as fh:
            fh.write(new_text)
        total_files += 1
        total_advances += changed
        total_military += military
    # remove stale overrides for files the current run no longer modifies
    removed = []
    for fname in sorted(os.listdir(args.out)):
        if fname.endswith(".txt") and fname in skipped:
            os.remove(os.path.join(args.out, fname))
            removed.append(fname)
    print("Wrote %d files, %d advances gated (%d classified military)"
          % (total_files, total_advances, total_military))
    print("Skipped %d files with no availability gates: %s" % (len(skipped), ", ".join(skipped)))
    if removed:
        print("Removed %d stale overrides: %s" % (len(removed), ", ".join(removed)))
    if renamed:
        print("Removed %d overrides renamed/dropped by the game: %s"
              % (len(renamed), ", ".join(renamed)))
    # every shipped override must mirror a vanilla filename exactly
    bad = [f for f in os.listdir(args.out) if f.endswith(".txt") and f not in vanilla_names]
    if bad:
        sys.exit("Override filenames do not match vanilla exactly: %s" % ", ".join(bad))

    town_dir = os.path.join(os.path.dirname(os.path.normpath(args.out)), "town_rights")
    written, unlocked = generate_town_rights(args.game, town_dir)
    print("Town rights: %d unlocked by Tall/Unlock All in %d file(s): %s"
          % (len(unlocked), len(written), ", ".join(unlocked)))


if __name__ == "__main__":
    main()
