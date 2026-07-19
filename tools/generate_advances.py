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

  * `allow = { X }` gates get the same wrap (so institution requirements are
    bypassed for unlocked advances, matching the original mod's behavior).
  * a top-level `government = <type>` gate is folded into the wrapped
    `potential` (the engine treats the key as a hard filter otherwise).
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


def wrap_gate(inner, unlock_vars, extra_lines=None):
    """Build the wrapped gate body from the original inner content."""
    body = "\n\t\tOR = {\n\t\t\tAND = {\n\t\t\t\thas_variable = %s\n\t\t\t\tOR = {" % MASTER_ENABLED
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


def process_advance(adv_id, block_text, unlock_vars):
    mask = strip_positions(block_text)

    gov_entries = find_scalar_keys(block_text, mask, 0, len(block_text), "government")
    potential_span = None
    allow_span = None
    for name, kstart, obrace, cbrace in find_blocks(block_text, mask, 0, len(block_text)):
        if name == "potential":
            potential_span = (kstart, obrace, cbrace)
        elif name == "allow":
            allow_span = (kstart, obrace, cbrace)

    if not gov_entries and potential_span is None and allow_span is None:
        return block_text, False

    edits = []
    gov_lines = ["government = %s" % g[2] for g in gov_entries]

    if potential_span is not None:
        kstart, obrace, cbrace = potential_span
        inner = block_text[obrace + 1 : cbrace]
        edits.append((obrace + 1, cbrace, wrap_gate(inner, unlock_vars, gov_lines)))
        for gstart, gend, _ in gov_entries:
            edits.append((gstart, gend, ""))
    elif gov_entries:
        gstart, gend, _ = gov_entries[0]
        replacement = "potential = {%s}" % wrap_gate("", unlock_vars, gov_lines)
        edits.append((gstart, gend, replacement))
        for extra_start, extra_end, _ in gov_entries[1:]:
            edits.append((extra_start, extra_end, ""))

    if allow_span is not None:
        kstart, obrace, cbrace = allow_span
        inner = block_text[obrace + 1 : cbrace]
        edits.append((obrace + 1, cbrace, wrap_gate(inner, unlock_vars)))

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
    for name, kstart, obrace, cbrace in find_blocks(text, mask, 0, len(text)):
        body = text[obrace + 1 : cbrace]
        unlock = unlock_vars_for(name, body, file_entry, fname)
        new_body, did = process_advance(name, body, unlock)
        pieces.append(text[last : obrace + 1])
        pieces.append(new_body)
        last = cbrace
        if did:
            changed += 1
    pieces.append(text[last:])
    return "".join(pieces), changed


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

    total_files = 0
    total_advances = 0
    skipped = []
    for fname in sorted(os.listdir(src)):
        if not fname.endswith(".txt"):
            continue
        with open(os.path.join(src, fname), "r", encoding="utf-8-sig") as fh:
            text = fh.read()
        file_entry = groups["files"].get(fname)
        new_text, changed = process_file(text, file_entry, fname)
        if changed == 0:
            skipped.append(fname)
            continue
        with open(os.path.join(args.out, fname), "w", encoding="utf-8-sig", newline="\n") as fh:
            fh.write(new_text)
        total_files += 1
        total_advances += changed
    print("Wrote %d files, %d advances gated" % (total_files, total_advances))
    print("Skipped %d files with no availability gates: %s" % (len(skipped), ", ".join(skipped)))


if __name__ == "__main__":
    main()
