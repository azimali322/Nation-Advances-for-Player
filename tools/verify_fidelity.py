#!/usr/bin/env python3
"""Prove the mod reproduces vanilla exactly whenever no toggle is set.

Compares every shipped override against the installed game's files:

  * Effective advance set - vanilla files we do not override plus our
    overrides - must contain exactly vanilla's advances, each in its vanilla
    file and in vanilla's definition order, with no duplicates.
  * Per advance, everything outside `potential` and the top-level `government`
    key must be token-identical to vanilla (comments and whitespace ignored,
    order significant). Advances vanilla does not gate must be identical in
    full.
  * The rewritten potential must be exactly
        OR = { AND = { <only hafp_ variables> } AND = { <vanilla conditions> } }
    where <vanilla conditions> is vanilla's potential with any top-level
    `government = X` folded in as `government_type = government_type:X`.
    With every hafp_ variable unset the first branch is false, so the advance
    is available to precisely the nations vanilla allows.
  * subject_types overrides must equal vanilla except for the relaxed
    `NOT = { has_advance = X }` sites (see generate_exclusions.py).
  * No other shipped file may collide with a vanilla path.

Run:  python tools/verify_fidelity.py [--game <EU5 folder>]
Exits non-zero if anything differs. Also exercised by test_generators.py.
"""

import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import build_groups as bg          # noqa: E402
import generate_advances as ga     # noqa: E402
import generate_exclusions as gx   # noqa: E402

SKIP = ("readme.txt", "_advances_template.txt")
EXPECTED_COLLISION_DIRS = (
    os.path.join("in_game", "common", "advances"),
    os.path.join("in_game", "common", "subject_types"),
)


def toks(text):
    return bg.tokenize(text)


def read(path):
    with open(path, encoding="utf-8-sig") as fh:
        return fh.read()


def advances_of(text):
    """Ordered (id, body) pairs using the generator's own block finder."""
    mask = ga.strip_positions(text)
    return [(name, text[o + 1:c]) for name, _k, o, c in ga.find_blocks(text, mask, 0, len(text))]


def split_gate(body):
    """-> (last potential inner or None, government values, rest, #potentials)."""
    mask = ga.strip_positions(body)
    pots = [(k, o, c) for name, k, o, c in ga.find_blocks(body, mask, 0, len(body))
            if name == "potential"]
    govs = ga.find_scalar_keys(body, mask, 0, len(body), "government")
    spans = sorted([(k, c + 1) for k, _o, c in pots] + [(s, e) for s, e, _v in govs])
    rest, last = [], 0
    for s, e in spans:
        rest.append(body[last:s])
        last = e
    rest.append(body[last:])
    inner = body[pots[-1][1] + 1:pots[-1][2]] if pots else None
    return inner, [g[2] for g in govs], "".join(rest), len(pots)


def branches(potential_inner):
    """Expect OR = { AND = {mod} AND = {orig} }; return (mod, orig) or None."""
    mask = ga.strip_positions(potential_inner)
    top = list(ga.find_blocks(potential_inner, mask, 0, len(potential_inner)))
    if len(top) != 1 or top[0][0] != "OR":
        return None
    or_inner = potential_inner[top[0][2] + 1:top[0][3]]
    omask = ga.strip_positions(or_inner)
    parts = list(ga.find_blocks(or_inner, omask, 0, len(or_inner)))
    if len(parts) != 2 or parts[0][0] != "AND" or parts[1][0] != "AND":
        return None
    get = lambda b: or_inner[b[2] + 1:b[3]]
    return get(parts[0]), get(parts[1])


def check_advance(fname, adv_id, van_body, mod_body):
    problems = []
    v_inner, v_govs, v_rest, v_npot = split_gate(van_body)
    if v_npot > 1:
        problems.append("%s/%s: vanilla has %d potential blocks (only the last is wrapped)"
                        % (fname, adv_id, v_npot))
    if len(v_govs) > 1:
        problems.append("%s/%s: vanilla has %d government keys (folding ANDs them)"
                        % (fname, adv_id, len(v_govs)))

    if v_inner is None and not v_govs:
        if toks(van_body) != toks(mod_body):
            problems.append("%s/%s: ungated advance differs from vanilla" % (fname, adv_id))
        return problems

    m_inner, m_govs, m_rest, _n = split_gate(mod_body)
    if m_govs:
        problems.append("%s/%s: top-level government key not folded" % (fname, adv_id))
    if toks(v_rest) != toks(m_rest):
        problems.append("%s/%s: content outside the gate differs from vanilla" % (fname, adv_id))
    if m_inner is None:
        problems.append("%s/%s: gated in vanilla but no potential in mod" % (fname, adv_id))
        return problems

    split = branches(m_inner)
    if split is None:
        problems.append("%s/%s: potential is not OR { AND{mod} AND{orig} }" % (fname, adv_id))
        return problems
    mod_branch, orig_branch = split

    mt = toks(mod_branch)
    allowed = {"has_variable", "=", "{", "}", "OR"}
    stray = [t for t in mt if t not in allowed and not t.startswith("hafp_")]
    if stray or mt[:3] != ["has_variable", "=", ga.MASTER_ENABLED]:
        problems.append("%s/%s: mod branch has unexpected content %s" % (fname, adv_id, stray[:4]))

    expected = []
    for g in v_govs:
        expected += ["government_type", "=", "government_type:%s" % g]
    expected += toks(v_inner or "")
    if toks(orig_branch) != expected:
        problems.append("%s/%s: vanilla conditions not preserved in the original branch"
                        % (fname, adv_id))
    return problems


def check_advances(game):
    van_dir = os.path.join(game, "game", "in_game", "common", "advances")
    mod_dir = os.path.join(ROOT, "in_game", "common", "advances")
    problems, stats = [], collections.Counter()
    van_files = sorted(f for f in os.listdir(van_dir) if f.endswith(".txt") and f not in SKIP)
    mod_files = set(os.listdir(mod_dir))

    for f in sorted(mod_files):
        if f not in van_files:
            problems.append("%s: shipped override has no vanilla counterpart" % f)

    effective = collections.defaultdict(list)
    vanilla = collections.defaultdict(list)
    for f in van_files:
        van = advances_of(read(os.path.join(van_dir, f)))
        for adv_id, _b in van:
            vanilla[adv_id].append(f)
        if f not in mod_files:
            for adv_id, _b in van:
                effective[adv_id].append(f)
            continue
        mod = advances_of(read(os.path.join(mod_dir, f)))
        for adv_id, _b in mod:
            effective[adv_id].append(f)
        if [a for a, _ in van] != [a for a, _ in mod]:
            problems.append("%s: advance ids/order differ from vanilla" % f)
            continue
        for (adv_id, vb), (_m, mb) in zip(van, mod):
            stats["advances compared"] += 1
            v_inner, v_govs, _r, _n = split_gate(vb)
            stats["gated" if (v_inner is not None or v_govs) else "ungated"] += 1
            problems += check_advance(f, adv_id, vb, mb)

    missing = sorted(set(vanilla) - set(effective))
    extra = sorted(set(effective) - set(vanilla))
    dups = sorted(a for a, fs in effective.items() if len(fs) > 1)
    moved = sorted(a for a in vanilla if vanilla[a] != effective.get(a))
    if missing:
        problems.append("effective set is missing %d vanilla advances: %s" % (len(missing), missing[:5]))
    if extra:
        problems.append("effective set has %d advances vanilla lacks: %s" % (len(extra), extra[:5]))
    if dups:
        problems.append("%d advances defined twice: %s" % (len(dups), dups[:5]))
    if moved:
        problems.append("%d advances moved file: %s" % (len(moved), moved[:5]))
    stats["vanilla advances"] = len(vanilla)
    stats["effective advances"] = len(effective)
    return problems, stats


def check_subject_types(game):
    problems = []
    potentials = gx.advance_potentials(game)
    for rel, advs in gx.RELAX_SITES.items():
        mod_path = os.path.join(ROOT, "in_game", "common", rel)
        van_path = os.path.join(game, "game", "in_game", "common", rel)
        if not os.path.isfile(mod_path):
            continue
        expected = []
        vt = toks(read(van_path))
        i = 0
        while i < len(vt):
            window = vt[i:i + 7]
            if (len(window) == 7 and window[:6] == ["NOT", "=", "{", "has_advance", "=", window[5]]
                    and window[6] == "}" and window[5] in advs and window[5] in potentials):
                expected += (["OR", "=", "{"] + window + ["NOT", "=", "{", "AND", "=", "{"]
                             + toks(potentials[window[5]]) + ["}", "}", "}"])
                i += 7
            else:
                expected.append(vt[i])
                i += 1
        if toks(read(mod_path)) != expected:
            problems.append("%s: differs from vanilla beyond the relaxed exclusions" % rel)
    return problems


def check_collisions(game):
    problems = []
    for top in ("in_game", "main_menu"):
        base = os.path.join(ROOT, top)
        for dp, _dirs, fns in os.walk(base):
            for fn in fns:
                rel = os.path.relpath(os.path.join(dp, fn), ROOT)
                if os.path.exists(os.path.join(game, "game", rel)):
                    if not rel.startswith(EXPECTED_COLLISION_DIRS):
                        problems.append("%s: unintentionally overrides a vanilla file" % rel)
    return problems


def run(game):
    problems, stats = check_advances(game)
    problems += check_subject_types(game)
    problems += check_collisions(game)
    return problems, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", default=bg.GAME_DEFAULT, help="EU5 install folder")
    args = parser.parse_args()
    problems, stats = run(args.game)
    for k in ("vanilla advances", "effective advances", "advances compared", "gated", "ungated"):
        print("%-20s %d" % (k, stats.get(k, 0)))
    if problems:
        print("\n%d FIDELITY PROBLEM(S):" % len(problems))
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print("\nOK - with no toggle set, every advance matches vanilla exactly.")


if __name__ == "__main__":
    main()
