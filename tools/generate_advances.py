#!/usr/bin/env python3
"""Generate the mod's advances overrides from the vanilla EU5 game files.

For every advance in the vanilla `in_game/common/advances` folder this script
rewrites the availability gates so the player can opt in to researching any
nation's unique advances:

  * `potential = { X }`  becomes  `potential = { OR = { has_variable = <VAR> AND = { X } } }`
  * `allow = { X }`      becomes  `allow = { OR = { has_variable = <VAR> AND = { X } } }`
  * a top-level `government = <type>` gate is folded into the wrapped
    `potential` block (the engine treats the key as a hard filter, so it must
    be moved inside the OR for the unlock variable to bypass it)

Advances with none of those gates (and files containing only such advances)
are left untouched and are not shipped by the mod, keeping the override
footprint as small as possible.

This reproduces the mechanism of the "All Advances Unlocked" workshop mod
(id 3665391921) but regenerates everything from the local vanilla files, so
re-running the script after a game patch re-baselines the mod automatically.

Usage (defaults match a standard Steam install):
  python tools/generate_advances.py \
      --game "C:/Program Files (x86)/Steam/steamapps/common/Europa Universalis V" \
      --out  "in_game/common/advances"
"""

import argparse
import os
import re
import sys

UNLOCK_VARIABLE = "hafp_all_advances_enabled"

KEY_RE = re.compile(r"([A-Za-z0-9_.:]+)\s*=\s*(\{|\"[^\"]*\"|[^\s{}#]+)")


def strip_positions(text):
    """Return a bytearray mask: True where char is inside a comment or quote."""
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


def find_blocks(text, mask, start, end):
    """Yield (name, name_start, open_brace, close_brace) for `name = { ... }`
    blocks at brace-depth 0 within [start, end)."""
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


def find_scalar_keys(text, mask, start, end, key):
    """Yield (key_start, value_end) for scalar `key = value` at depth 0 in range."""
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


def wrap_gate(inner, extra_lines=None):
    """Build the wrapped gate body from the original inner content."""
    extra = ""
    if extra_lines:
        extra = "".join("\n\t\t\t\t%s" % line for line in extra_lines)
    inner = inner.strip("\r\n")
    inner = inner.strip() if inner.strip() else ""
    body = "\n\t\tOR = {\n\t\t\thas_variable = %s\n\t\t\tAND = {%s" % (
        UNLOCK_VARIABLE,
        extra,
    )
    if inner:
        for line in inner.splitlines():
            body += "\n\t\t\t\t" + line.strip()
    body += "\n\t\t\t}\n\t\t}\n\t"
    return body


def process_advance(block_text):
    """Rewrite one advance body (text between its outer braces).

    Returns (new_text, changed)."""
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

    edits = []  # (start, end, replacement)

    gov_lines = ["government = %s" % g[2] for g in gov_entries]

    if potential_span is not None:
        kstart, obrace, cbrace = potential_span
        inner = block_text[obrace + 1 : cbrace]
        edits.append((obrace + 1, cbrace, wrap_gate(inner, gov_lines)))
        # remove the original top-level government keys
        for gstart, gend, _ in gov_entries:
            edits.append((gstart, gend, ""))
    elif gov_entries:
        # no potential block: synthesize one in place of the first government key
        gstart, gend, _ = gov_entries[0]
        replacement = "potential = {%s}" % wrap_gate("", gov_lines)
        edits.append((gstart, gend, replacement))
        for extra_start, extra_end, _ in gov_entries[1:]:
            edits.append((extra_start, extra_end, ""))

    if allow_span is not None:
        kstart, obrace, cbrace = allow_span
        inner = block_text[obrace + 1 : cbrace]
        edits.append((obrace + 1, cbrace, wrap_gate(inner)))

    edits.sort(key=lambda e: e[0], reverse=True)
    new_text = block_text
    for start, end, repl in edits:
        new_text = new_text[:start] + repl + new_text[end:]
    return new_text, True


def process_file(text):
    """Rewrite a whole advances file. Returns (new_text, num_changed)."""
    mask = strip_positions(text)
    changed = 0
    pieces = []
    last = 0
    for name, kstart, obrace, cbrace in find_blocks(text, mask, 0, len(text)):
        body = text[obrace + 1 : cbrace]
        new_body, did = process_advance(body)
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
        default=os.path.join(os.path.dirname(__file__), "..", "in_game", "common", "advances"),
        help="Output folder for the generated overrides",
    )
    args = parser.parse_args()

    src = os.path.join(args.game, "game", "in_game", "common", "advances")
    if not os.path.isdir(src):
        sys.exit("Vanilla advances folder not found: %s" % src)
    os.makedirs(args.out, exist_ok=True)

    total_files = 0
    total_advances = 0
    skipped = []
    for fname in sorted(os.listdir(src)):
        if not fname.endswith(".txt"):
            continue
        with open(os.path.join(src, fname), "r", encoding="utf-8-sig") as fh:
            text = fh.read()
        new_text, changed = process_file(text)
        if changed == 0:
            skipped.append(fname)
            continue
        with open(os.path.join(args.out, fname), "w", encoding="utf-8-sig", newline="\n") as fh:
            fh.write(new_text)
        total_files += 1
        total_advances += changed
        print("  %-45s %3d advances unlocked" % (fname, changed))

    print()
    print("Wrote %d files, %d advances gated behind %s" % (total_files, total_advances, UNLOCK_VARIABLE))
    print("Skipped %d files with no availability gates: %s" % (len(skipped), ", ".join(skipped)))


if __name__ == "__main__":
    main()
