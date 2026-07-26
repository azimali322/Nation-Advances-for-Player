#!/usr/bin/env python3
"""Relax vanilla "having advance X removes capability Y" exclusions.

A few vanilla advances deliberately REPLACE a base capability rather than add
to it. The clearest case is the Indian samanta system: `subject_types/vassal.txt`
hides vassalization behind `NOT = { has_advance = samanta_advance }`, because an
Indian realm is meant to use samanta / maha samanta / pradhana maha samanta
instead of vassals. The same exclusion also hides Byzantine pronoia.

That is correct for a natively Indian nation, but this mod can hand
`samanta_advance` to anyone - and a Tunisian or French player who unlocks it
then silently loses the ability to vassalize. This script rewrites those
exclusions so they only apply to nations that qualify for the advance in the
BASE GAME:

    NOT = { has_advance = samanta_advance }

becomes

    OR = {
        NOT = { has_advance = samanta_advance }
        NOT = { AND = { <the advance's vanilla potential> } }
    }

i.e. "you only lose this capability if you have the advance AND you are the
kind of nation vanilla intended to have it". Nations that unlocked the advance
through this mod keep both the base capability and the new one. Behavior is
unchanged without the mod, since vanilla's own potential already prevents those
nations from ever holding the advance.

Only the sites in RELAX_SITES are rewritten. `NOT = { has_advance = X }` inside
a `hidden = { ... }` block is the opposite pattern - a normal "you need this
advance" requirement - and must be left alone; those are listed in
IGNORED_SITES. Any other candidate site found in the game files is reported so
it can be classified after a patch.

Run after generate_advances.py:
  python tools/generate_exclusions.py [--game <EU5 folder>]
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from generate_advances import strip_positions, find_blocks  # noqa: E402

GAME_DEFAULT = r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V"

# Exclusions to relax: path under in_game/common -> advances to relax there.
RELAX_SITES = {
    os.path.join("subject_types", "vassal.txt"): ["samanta_advance"],
    os.path.join("subject_types", "D008_pronoia.txt"): ["samanta_advance"],
}

# Candidate sites deliberately left untouched.
IGNORED_SITES = {
    os.path.join("unit_abilities", "promote_to_farari.txt"):
        "inside hidden = {} - requires the advance, does not remove anything",
    os.path.join("unit_abilities", "march_to_sound_of_guns.txt"):
        "inside hidden = {} - requires the advance, does not remove anything",
    os.path.join("scripted_effects", "situation_effects.txt"):
        "effect guard - grants the advance if missing, removes nothing",
}

EXCLUSION_RE = re.compile(r"NOT\s*=\s*\{\s*has_advance\s*=\s*([A-Za-z0-9_.]+)\s*\}")


def advance_potentials(game):
    """advance id -> vanilla potential body (stripped), for gated advances."""
    adv_dir = os.path.join(game, "game", "in_game", "common", "advances")
    potentials = {}
    for fname in sorted(os.listdir(adv_dir)):
        if not fname.endswith(".txt"):
            continue
        text = open(os.path.join(adv_dir, fname), encoding="utf-8-sig").read()
        mask = strip_positions(text)
        for name, kstart, obrace, cbrace in find_blocks(text, mask, 0, len(text)):
            if name in potentials:
                continue
            body = text[obrace + 1 : cbrace]
            bmask = strip_positions(body)
            for bname, bk, bo, bc in find_blocks(body, bmask, 0, len(body)):
                if bname == "potential":
                    inner = body[bo + 1 : bc].strip()
                    if inner:
                        potentials[name] = inner
                    break
    return potentials


def relax(text, advances, potentials):
    """Rewrite the configured exclusions in one file. Returns (text, count)."""
    count = 0

    def sub(match):
        nonlocal count
        adv = match.group(1)
        if adv not in advances or adv not in potentials:
            return match.group(0)
        line_start = text.rfind("\n", 0, match.start()) + 1
        indent = re.match(r"[ \t]*", text[line_start : match.start()]).group(0)
        if text[line_start : match.start()].strip():
            indent += "\t"
        body = "\n".join(indent + "\t\t\t" + ln.strip()
                         for ln in potentials[adv].splitlines() if ln.strip())
        count += 1
        return (
            "OR = {\n"
            "%s\t%s\n"
            "%s\t# Handicap Advances for Player: only nations that qualify for this\n"
            "%s\t# advance in the base game lose this capability to it. Nations that\n"
            "%s\t# unlocked it through the mod keep both.\n"
            "%s\tNOT = {\n"
            "%s\t\tAND = {\n"
            "%s\n"
            "%s\t\t}\n"
            "%s\t}\n"
            "%s}" % (indent, match.group(0), indent, indent, indent,
                     indent, indent, body, indent, indent, indent)
        )

    return EXCLUSION_RE.sub(sub, text), count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", default=GAME_DEFAULT, help="EU5 install folder")
    args = parser.parse_args()

    common = os.path.join(args.game, "game", "in_game", "common")
    if not os.path.isdir(common):
        sys.exit("Vanilla common folder not found: %s" % common)
    potentials = advance_potentials(args.game)

    total = 0
    for relpath, advances in sorted(RELAX_SITES.items()):
        src = os.path.join(common, relpath)
        if not os.path.isfile(src):
            print("  MISSING in game files, skipped: %s" % relpath)
            continue
        text = open(src, encoding="utf-8-sig").read()
        new_text, count = relax(text, advances, potentials)
        if count == 0:
            print("  no exclusion found (vanilla changed?): %s" % relpath)
            continue
        dst = os.path.join(ROOT, "in_game", "common", relpath)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8-sig", newline="\n") as fh:
            fh.write(new_text)
        total += count
        print("  %-40s %d exclusion(s) relaxed" % (relpath, count))

    print("Relaxed %d exclusion(s) in %d file(s)" % (total, len(RELAX_SITES)))

    # Report any candidate site that is neither handled nor classified.
    unknown = []
    for dirpath, _dirs, fnames in os.walk(common):
        for fname in fnames:
            if not fname.endswith(".txt"):
                continue
            full = os.path.join(dirpath, fname)
            relpath = os.path.relpath(full, common)
            if relpath in RELAX_SITES or relpath in IGNORED_SITES:
                continue
            if relpath.startswith("advances" + os.sep):
                continue
            try:
                text = open(full, encoding="utf-8-sig").read()
            except (OSError, UnicodeDecodeError):
                continue
            for m in EXCLUSION_RE.finditer(text):
                adv = m.group(1)
                if adv in potentials:  # gated advance the mod can hand out
                    unknown.append((relpath, adv))
    if unknown:
        print("\nUNCLASSIFIED exclusion sites (gated advance removes a capability?):")
        for relpath, adv in sorted(set(unknown)):
            print("   %s: %s" % (relpath, adv))
        print("Add each to RELAX_SITES or IGNORED_SITES in tools/generate_exclusions.py")
    else:
        print("No unclassified exclusion sites.")


if __name__ == "__main__":
    main()
