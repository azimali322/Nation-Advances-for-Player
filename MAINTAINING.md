# Maintaining Handicap Advances for Player

The recurring chores, organised by what just happened. Where possible the
tests remind you, so you do not have to remember any of this.

## You changed your local Python version

Edit `.python-version` to the new `major.minor` (for example `3.12`), then
commit and push. GitHub's Windows test job reads that file, so CI keeps
testing the Python you actually use.

You do not need to remember this: `python tools/test_generators.py` fails with
a message telling you to do it whenever your Python and the pin disagree.

## EU5 got a patch

1. Regenerate, in this order:

   ```
   python tools/build_groups.py
   python tools/generate_advances.py
   python tools/generate_exclusions.py
   python tools/generate_cmm.py
   ```

2. Read the generators' output for warnings: `UNMAPPED TAGS`,
   `FILE WITH NO GEOGRAPHY`, `CULTURE FILE WITHOUT HOME`, `UNCLASSIFIED`
   exclusion sites.
3. Verify - both must pass:

   ```
   python tools/verify_fidelity.py
   python tools/test_generators.py
   ```

4. If a test says an advance or nation "is gone", the patch renamed or removed
   it. Pick another advance with the same behaviour and update the test (or
   ask Claude to).
5. For a new game version, bump `supported_game_version` and the version tag
   in `.metadata/metadata.json` together (a test enforces it), and add a
   TESTING.md round for the in-game checks.

## The Community Mod Framework updated

Nothing to do while it stays on 2.x (our dependency is `2.*`). For a 3.x
release, update the dependency version and re-test the menu in game.

## You added or changed a menu feature

Run the tests - they fail if any setting, tab, group, button or dropdown
option is missing its text.

## You want to protect another nation you play

Add it to `PLAYER_PROFILES` in `tools/test_generators.py` (file, tag, home
region and area, a few of its tall advances, any own unique-unit advances), or
just tell Claude the nation. France and Khmer are already there.

## Newer Python releases

The Linux CI job pins the newest stable Python (3.14). Bump it occasionally in
`.github/workflows/tests.yml`; a failure there is an early warning, not a
problem with your setup.
