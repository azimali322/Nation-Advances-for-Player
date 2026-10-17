#!/usr/bin/env python3
"""Unit tests for the Handicap Advances generators.

Run:  python tools/test_generators.py          (stdlib unittest, no deps)

Covers the parsing and classification logic that the EU5 1.4 migration
touched, plus an integration pass over the generated output.
"""

import collections
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import build_groups as bg
import generate_advances as ga
import generate_exclusions as gx

VANILLA_ADVANCES = os.path.join(bg.GAME_DEFAULT, "game", "in_game", "common", "advances")
SHIPPED_ADVANCES = os.path.join(ROOT, "in_game", "common", "advances")
REGISTER = os.path.join(ROOT, "in_game", "common", "scripted_effects", "hafp_cmm_register.txt")
RESEARCH = os.path.join(ROOT, "in_game", "common", "scripted_effects", "hafp_research_effects.txt")
LOCALIZATION = os.path.join(ROOT, "main_menu", "localization", "english", "hafp_cmm_l_english.yml")
METADATA = os.path.join(ROOT, ".metadata", "metadata.json")


def read_text(path):
    with open(path, encoding="utf-8-sig") as fh:
        return fh.read()


def braces_balanced(text):
    depth = 0
    for line in text.splitlines():
        stripped = "".join(line.split("#")[0].split('"')[::2])
        depth += stripped.count("{") - stripped.count("}")
    return depth == 0


class TestStripNegated(unittest.TestCase):
    """1.4's Panama canal is gated NOT = { continent = continent:oceania }.

    Reading that as a positive reference filed the advance under the one
    continent that cannot have it, and produced a phantom Oceania tab."""

    def test_removes_not_block(self):
        body = "potential = { NOT = { continent = continent:oceania } }"
        self.assertNotIn("oceania", bg.strip_negated(body))

    def test_removes_nor_block(self):
        body = "potential = { NOR = { region = region:italy_region } }"
        self.assertNotIn("italy_region", bg.strip_negated(body))

    def test_keeps_positive_references(self):
        body = "potential = { continent = continent:europe }"
        self.assertIn("europe", bg.strip_negated(body))

    def test_keeps_positive_sibling_of_negated(self):
        body = ("potential = { continent = continent:europe\n"
                "  NOT = { continent = continent:oceania } }")
        out = bg.strip_negated(body)
        self.assertIn("europe", out)
        self.assertNotIn("oceania", out)

    def test_handles_nested_braces_inside_not(self):
        body = ("NOT = { culture = { has_culture_group = culture_group:italian_group } }\n"
                "region = region:france_region")
        out = bg.strip_negated(body)
        self.assertNotIn("italian_group", out)
        self.assertIn("france_region", out)

    def test_does_not_match_inside_identifier(self):
        body = "CANNOT = { region = region:italy_region }"
        self.assertIn("italy_region", bg.strip_negated(body))

    def test_unterminated_block_does_not_crash(self):
        bg.strip_negated("NOT = { continent = continent:oceania")


class TestSetupPath(unittest.TestCase):
    """1.4 moved start data from setup/start/ to setup/1337/ and setup/1658/."""

    def _tree(self, tmp, subdir):
        d = os.path.join(tmp, "game", "main_menu", "setup", subdir)
        os.makedirs(d)
        open(os.path.join(d, "10_countries.txt"), "w").close()

    def test_prefers_1337_over_legacy_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp, "1337")
            self._tree(tmp, "start")
            got = bg.setup_path(tmp, "10_countries.txt")
            self.assertIn(os.sep + "1337" + os.sep, got)

    def test_falls_back_to_legacy_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp, "start")
            got = bg.setup_path(tmp, "10_countries.txt")
            self.assertIn(os.sep + "start" + os.sep, got)

    def test_exits_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertRaises(SystemExit, bg.setup_path, tmp, "10_countries.txt")


class TestLoadCapitals(unittest.TestCase):
    """~360 pop-type nations (Tuareg, Guanche) declare no capital at all."""

    FIXTURE = (
        "country_setup = {\n"
        "\tFRA = {\n"
        "\t\tcapital = paris\n"
        "\t\town_control_core = { amiens }\n"
        "\t}\n"
        "\tAHG = {\n"
        "\t\ttype = pop\n"
        "\t\tadd_pops_from_locations = {\n"
        "\t\t\tabalessa\n"
        "\t\t}\n"
        "\t}\n"
        "\tXXX = {\n"
        "\t\town_control_core = { somewhere elsewhere }\n"
        "\t}\n"
        "\tCOM = {\n"
        "\t\t# capital = commented_out\n"
        "\t\tadd_pops_from_locations = { realplace }\n"
        "\t}\n"
        "}\n"
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = os.path.join(self.tmp.name, "game", "main_menu", "setup", "1337")
        os.makedirs(d)
        with open(os.path.join(d, "10_countries.txt"), "w", encoding="utf-8") as fh:
            fh.write(self.FIXTURE)
        self.caps = bg.load_capitals(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_declared_capital_wins(self):
        self.assertEqual(self.caps["FRA"], "paris")

    def test_pop_nation_falls_back_to_seed_location(self):
        self.assertEqual(self.caps["AHG"], "abalessa")

    def test_falls_back_to_own_control_core(self):
        self.assertEqual(self.caps["XXX"], "somewhere")

    def test_commented_capital_is_ignored(self):
        self.assertEqual(self.caps["COM"], "realplace")


class TestLoadFormables(unittest.TestCase):
    """The Tuareg formable lists bare locations instead of regions/areas."""

    FIXTURE = (
        "TRG_f = {\n"
        "\tname = TRG\n"
        "\ttag = TRG\n"
        "\tlocations = {\n"
        "\t\tagadez abalessa\n"
        "\t}\n"
        "}\n"
        "SCA_f = {\n"
        "\ttag = SCA\n"
        "\tregions = { scandinavian_region }\n"
        "\tareas = { iceland_area }\n"
        "}\n"
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = os.path.join(self.tmp.name, "game", "in_game", "common", "formable_countries")
        os.makedirs(d)
        with open(os.path.join(d, "00_formable_countries.txt"), "w", encoding="utf-8") as fh:
            fh.write(self.FIXTURE)
        self.formables = bg.load_formables(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_locations_are_collected(self):
        self.assertIn("agadez", self.formables["TRG"]["locations"])

    def test_regions_and_areas_still_parsed(self):
        self.assertIn("scandinavian_region", self.formables["SCA"]["regions"])
        self.assertIn("iceland_area", self.formables["SCA"]["areas"])


class TestSplitAdvances(unittest.TestCase):
    def test_finds_indented_and_commented_blocks(self):
        text = ("# a comment with braces { }\n"
                "alpha = {\n\tage = age_1_traditions\n}\n"
                "\tbeta = {\n\t\tage = age_2_renaissance\n\t}\n")
        got = dict(bg.split_advances(text))
        self.assertEqual(sorted(got), ["alpha", "beta"])


class TestTallClassifier(unittest.TestCase):
    def test_each_family_matches(self):
        cases = {
            "development": "global_monthly_development = 0.1",
            "population": "global_population_growth = 0.1",
            "migration (new in 1.4)": "global_migration_attraction = 0.1",
            "prosperity": "global_monthly_prosperity = 0.1",
            "non-rural prosperity (new in 1.4)": "global_non_rural_monthly_prosperity = 0.1",
            "food": "global_monthly_food_modifier = 0.1",
            "food purchase": "food_purchase_efficiency = 0.1",
            "masonry output": "global_masonry_output_modifier = 0.1",
            "new 1.4 good": "global_steel_output_modifier = 0.1",
            "raw material": "global_raw_material_output = 0.1",
            "pop promotion": "global_pop_promotion_speed_modifier = 0.1",
            "cabinet seats": "government_size = 1",
            "cabinet efficiency": "country_cabinet_efficiency = 0.1",
            "government reform": "unlock_government_reform = autocracy",
            "crown power": "global_crown_estate_power = 0.1",
            "satisfaction equilibrium": "nobles_estate_target_satisfaction = 0.1",
            "satisfaction recovery": "nobles_estate_satisfaction_recovery = 0.1",
            "literacy": "global_max_literacy = 5",
            "research": "research_speed_modifier = 0.1",
            "tall building": "unlock_building = polders",
        }
        for label, body in cases.items():
            self.assertTrue(ga.is_tall_advance(body),
                            "%s should classify as tall: %s" % (label, body))

    def test_non_tall_examples(self):
        for body in ("land_morale_modifier = 0.2",
                     "unlock_unit = a_renaissance_janissaries",
                     "diplomatic_reputation = 1",
                     "unlock_building = kalari"):
            self.assertFalse(ga.is_tall_advance(body), "should not be tall: %s" % body)

    def test_commented_modifier_does_not_count(self):
        self.assertFalse(ga.is_tall_advance("# global_monthly_development = 0.1"))


class TestUnitClassifier(unittest.TestCase):
    def test_unit_grants(self):
        for body in ("unlock_unit = n_galleass",
                     "unlock_levy = levy_mailed_knights",
                     "global_may_build_paik_units = yes"):
            self.assertTrue(ga.is_military_advance("x.txt", body), body)

    def test_military_buffs_are_not_unit_grants(self):
        for body in ("land_morale_modifier = 0.2",
                     "army_light_infantry_power = 0.1",
                     "navy_tradition_from_battle = 0.5"):
            self.assertFalse(ga.is_military_advance("x.txt", body), body)


class TestGateGeneration(unittest.TestCase):
    def test_government_key_becomes_government_type_trigger(self):
        body = "\n\tage = age_1_traditions\n\tgovernment = monarchy\n"
        out, changed = ga.process_advance("x", body, [ga.UNLOCK_ALL])
        self.assertTrue(changed)
        self.assertIn("government_type = government_type:monarchy", out)
        self.assertNotIn("\tgovernment = monarchy", out)
        self.assertTrue(braces_balanced("x = {" + out + "}"))

    def test_allow_block_is_left_untouched(self):
        body = ("\n\tage = age_1_traditions\n"
                "\tpotential = { has_or_had_tag = FRA }\n"
                "\tallow = { has_embraced_institution = institution:meritocracy }\n")
        out, _ = ga.process_advance("x", body, [ga.UNLOCK_ALL])
        allow = out[out.index("allow = {"):]
        self.assertNotIn("hafp_", allow)

    def test_unit_advance_requires_opt_in_toggle(self):
        body = "\n\tpotential = { has_or_had_tag = TUR }\n\tunlock_unit = a_janissaries\n"
        out, _ = ga.process_advance("x", body, [ga.UNLOCK_ALL], military=True)
        self.assertIn("has_variable = " + ga.ALLOW_UNIT_UNLOCKS, out)

    def test_non_unit_advance_has_no_opt_in_toggle(self):
        body = "\n\tpotential = { has_or_had_tag = TUR }\n"
        out, _ = ga.process_advance("x", body, [ga.UNLOCK_ALL], military=False)
        self.assertNotIn(ga.ALLOW_UNIT_UNLOCKS, out)

    def test_original_conditions_survive_in_their_own_branch(self):
        body = "\n\tpotential = { has_or_had_tag = FRA }\n"
        out, _ = ga.process_advance("x", body, [ga.UNLOCK_ALL])
        self.assertIn("has_or_had_tag = FRA", out)
        self.assertIn("has_variable = " + ga.MASTER_ENABLED, out)

    def test_ungated_advance_is_untouched(self):
        body = "\n\tage = age_1_traditions\n\tglobal_max_literacy = 5\n"
        out, changed = ga.process_advance("x", body, [ga.UNLOCK_ALL])
        self.assertFalse(changed)
        self.assertEqual(out, body)

    def test_tall_advance_gets_tall_unlock_variable(self):
        body = "\n\tpotential = { has_or_had_tag = FRA }\n\tglobal_monthly_development = 0.1\n"
        got = ga.unlock_vars_for("x", body, None, "country_fra.txt")
        self.assertIn("hafp_g_tall", got)

    def test_non_tall_advance_has_no_tall_variable(self):
        body = "\n\tpotential = { has_or_had_tag = FRA }\n\tland_morale_modifier = 0.2\n"
        got = ga.unlock_vars_for("x", body, None, "country_fra.txt")
        self.assertNotIn("hafp_g_tall", got)


class TestExclusionRelax(unittest.TestCase):
    def test_relaxes_and_stays_balanced(self):
        text = ("vassal = {\n\tvisible = {\n"
                "\t\tNOT = { has_advance = samanta_advance }\n\t}\n}\n")
        pots = {"samanta_advance":
                "culture = { has_culture_group = culture_group:indian_group }"}
        out, count = gx.relax(text, ["samanta_advance"], pots)
        self.assertEqual(count, 1)
        self.assertIn("indian_group", out)
        self.assertIn("NOT = { has_advance = samanta_advance }", out)
        self.assertTrue(braces_balanced(out))

    def test_unknown_advance_is_left_alone(self):
        text = "\t\tNOT = { has_advance = other_advance }\n"
        out, count = gx.relax(text, ["samanta_advance"], {})
        self.assertEqual(count, 0)
        self.assertEqual(out, text)


class TestGeneratedOutput(unittest.TestCase):
    """Integration checks over the committed output."""

    ADV = os.path.join(ROOT, "in_game", "common", "advances")

    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(cls.ADV):
            raise unittest.SkipTest("generated advances not present")

    def test_all_generated_files_have_balanced_braces(self):
        for fname in os.listdir(self.ADV):
            with open(os.path.join(self.ADV, fname), encoding="utf-8-sig") as fh:
                self.assertTrue(braces_balanced(fh.read()), "unbalanced: %s" % fname)

    def test_filenames_match_vanilla_case_sensitively(self):
        if not os.path.isdir(VANILLA_ADVANCES):
            self.skipTest("game files not available")
        names = {f for f in os.listdir(VANILLA_ADVANCES) if f.endswith(".txt")}
        bad = [f for f in os.listdir(self.ADV) if f not in names]
        self.assertEqual(bad, [], "overrides whose filenames do not match vanilla exactly")

    def test_every_gate_variable_has_a_toggle_and_vice_versa(self):
        reg_path = os.path.join(ROOT, "in_game", "common", "scripted_effects",
                                "hafp_cmm_register.txt")
        if not os.path.isfile(reg_path):
            self.skipTest("register file not generated")
        with open(reg_path, encoding="utf-8-sig") as fh:
            reg = fh.read()
        aliases = set(re.findall(r"alias = (hafp_[a-z0-9_]+)", reg))
        gate_vars = set()
        towns = os.path.join(ROOT, "in_game", "common", "town_rights")
        for folder in (self.ADV, towns):
            if not os.path.isdir(folder):
                continue
            for fname in os.listdir(folder):
                with open(os.path.join(folder, fname), encoding="utf-8-sig") as fh:
                    text = fh.read()
                gate_vars.update(re.findall(r"has_variable = (hafp_[a-z0-9_]+)", text))
        self.assertEqual(gate_vars - aliases, set(), "gate variables with no CMM toggle")
        self.assertEqual(aliases - gate_vars, set(), "toggles that gate nothing")

    def test_institution_allow_gates_are_never_wrapped(self):
        from generate_advances import strip_positions, find_blocks
        for fname in os.listdir(self.ADV):
            with open(os.path.join(self.ADV, fname), encoding="utf-8-sig") as fh:
                text = fh.read()
            mask = strip_positions(text)
            for _n, _k, obrace, cbrace in find_blocks(text, mask, 0, len(text)):
                body = text[obrace + 1:cbrace]
                bmask = strip_positions(body)
                for bname, _bk, bo, bc in find_blocks(body, bmask, 0, len(body)):
                    if bname == "allow":
                        self.assertNotIn("hafp_", body[bo:bc],
                                         "allow gate wrapped in %s" % fname)


class TestGroupingSanity(unittest.TestCase):
    """Guards on how advances are filed into the menu's categories."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(HERE, "data", "groups.json")
        if not os.path.isfile(path):
            raise unittest.SkipTest("groups.json not built")
        with open(path, encoding="utf-8") as fh:
            cls.groups = json.load(fh)

    def test_manual_tag_overrides_name_real_regions(self):
        """Catches typos and regions renamed by a game patch."""
        if not os.path.isdir(bg.GAME_DEFAULT):
            self.skipTest("game files not available")
        _l, _a, region_info, _s, _c = bg.load_hierarchy(bg.GAME_DEFAULT)
        for tag, region in bg.MANUAL_TAG_REGIONS.items():
            self.assertIn(region, region_info, "%s maps to unknown region %s" % (tag, region))

    def test_no_nation_file_sprawls_across_continents(self):
        """A formable's region list is what you must CONQUER to form it, not
        where the nation sits - ROM once filed Byzantine advances under Britain,
        Iberia and Egypt. Files that legitimately span continents are listed."""
        legitimate = {"canal_advances.txt", "region_asia.txt"}
        for fname, entry in self.groups["files"].items():
            if entry["kind"] != "nation" or fname in legitimate:
                continue
            conts = {c for a in entry["advances"].values() for c in a["continents"]}
            self.assertLessEqual(len(conts), 2,
                                 "%s spans %s" % (fname, sorted(conts)))

    def test_geography_toggles_exist_for_every_nation_advance(self):
        """Nation and special advances are the ones whose areas/regions/
        continents become toggles (see unlock_vars_for), so every reference
        they carry must be present in the inventory the menu is built from.
        Culture/religion/government files toggle by file, not by geography,
        so their scraped references are deliberately not in the inventory."""
        areas, regions, conts = (set(self.groups["areas"]), set(self.groups["regions"]),
                                 set(self.groups["continents"]))
        missing = []
        for fname, entry in self.groups["files"].items():
            if entry["kind"] not in ("nation", "special"):
                continue
            for adv_id, a in entry["advances"].items():
                missing += ["%s: area %s" % (adv_id, x) for x in a["areas"] if x not in areas]
                missing += ["%s: region %s" % (adv_id, x) for x in a["regions"] if x not in regions]
                missing += ["%s: continent %s" % (adv_id, x) for x in a["continents"] if x not in conts]
        self.assertEqual(missing[:10], [], "geography with no toggle: %d" % len(missing))

    def test_culture_files_have_a_home_continent(self):
        missing = [f for f, e in self.groups["files"].items()
                   if e["kind"] in ("culture", "culture_group") and not e.get("home_continent")]
        self.assertEqual(missing, [], "culture files with no home continent")


class TestVanillaFidelity(unittest.TestCase):
    """With no toggle set, the mod must reproduce vanilla exactly.

    verify_fidelity.py compares every overridden advance token-by-token against
    the installed game; these tests run it on the real output and prove it
    actually fails when the output drifts from vanilla."""

    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(os.path.join(bg.GAME_DEFAULT, "game")):
            raise unittest.SkipTest("game files not available")
        import verify_fidelity
        cls.vf = verify_fidelity

    def _mutated(self, mutate):
        import shutil
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(ROOT, "in_game"), os.path.join(tmp, "in_game"))
            mutate(tmp)
            self.vf.ROOT = tmp
            problems, _ = self.vf.run(bg.GAME_DEFAULT)
        finally:
            self.vf.ROOT = ROOT
            shutil.rmtree(tmp, ignore_errors=True)
        return problems

    def _edit(self, tmp, rel, old, new):
        path = os.path.join(tmp, "in_game", "common", rel)
        with open(path, encoding="utf-8-sig") as fh:
            text = fh.read()
        self.assertIn(old, text)
        with open(path, "w", encoding="utf-8-sig") as fh:
            fh.write(text.replace(old, new, 1))

    def test_shipped_mod_matches_vanilla(self):
        problems, stats = self.vf.run(bg.GAME_DEFAULT)
        self.assertEqual(problems, [])
        self.assertEqual(stats["vanilla advances"], stats["effective advances"])

    def test_detects_changed_modifier(self):
        self.assertTrue(self._mutated(lambda t: self._edit(
            t, os.path.join("advances", "country_fra.txt"),
            "diplomatic_capacity = 1", "diplomatic_capacity = 9")))

    def test_detects_altered_vanilla_condition(self):
        self.assertTrue(self._mutated(lambda t: self._edit(
            t, os.path.join("advances", "country_fra.txt"),
            "has_or_had_tag = FRA", "has_or_had_tag = ENG")))

    def test_detects_stray_condition_in_mod_branch(self):
        self.assertTrue(self._mutated(lambda t: self._edit(
            t, os.path.join("advances", "country_fra.txt"),
            "has_variable = hafp_all_advances_enabled",
            "has_variable = hafp_all_advances_enabled always = yes")))

    def test_detects_dlc_check_left_out_of_the_unlock_branch(self):
        """The pre-1.4.1 bug: has_dlc only in the vanilla branch, so Unlock All
        granted DLC advances to players without the DLC."""
        self.assertTrue(self._mutated(lambda t: self._edit(
            t, os.path.join("advances", "religion_hellenism.txt"),
            '\t\thas_dlc = "d008_fate_of_the_phoenix"\n\t\tOR = {', "\t\tOR = {")))

    def test_detects_dropped_town_right_requirement(self):
        self.assertTrue(self._mutated(lambda t: self._edit(
            t, os.path.join("town_rights", "10_country_specific.txt"),
            "\t\tmodifier:allow_ville_franche_town_rights = yes\n", "")))

    def test_detects_subject_type_drift(self):
        self.assertTrue(self._mutated(lambda t: self._edit(
            t, os.path.join("subject_types", "vassal.txt"), "level = 2", "level = 3")))


class TestShippedFiles(unittest.TestCase):
    """Repository hygiene that must hold for every future version of the mod."""

    def test_every_paradox_file_has_a_utf8_bom(self):
        """EU5 expects .txt script and .yml localization files to begin with a
        UTF-8 byte order mark."""
        missing = []
        for top in ("in_game", "main_menu"):
            for dirpath, _dirs, files in os.walk(os.path.join(ROOT, top)):
                for fname in files:
                    if fname.endswith((".txt", ".yml")):
                        path = os.path.join(dirpath, fname)
                        with open(path, "rb") as fh:
                            if fh.read(3) != b"\xef\xbb\xbf":
                                missing.append(os.path.relpath(path, ROOT))
        self.assertEqual(missing, [], "files without a UTF-8 BOM")

    def test_metadata_is_valid(self):
        with open(METADATA, encoding="utf-8-sig") as fh:
            meta = json.load(fh)
        for key in ("name", "id", "version", "supported_game_version",
                    "short_description", "tags", "relationships"):
            self.assertIn(key, meta)
        m = re.match(r"^(\d+\.\d+)\.\*$", meta["supported_game_version"])
        self.assertIsNotNone(m, "supported_game_version should look like 1.4.*")
        self.assertIn(m.group(1), meta["tags"],
                      "the version tag must match supported_game_version - bump both together")
        deps = [r for r in meta["relationships"] if r.get("id") == "community_mod_framework"]
        self.assertEqual(len(deps), 1, "the Community Mod Framework dependency is missing")
        self.assertEqual(deps[0].get("rel_type"), "dependency")

    def test_mod_id_never_changes(self):
        """Changing the id orphans every player's saved settings and Workshop
        subscription, so it is pinned on purpose."""
        with open(METADATA, encoding="utf-8-sig") as fh:
            self.assertEqual(json.load(fh)["id"], "handicap_advances_for_player")


def _field(body, name):
    m = re.search(r"\b%s = (\w+)" % name, body)
    return m.group(1) if m else None


class TestMenuLocalization(unittest.TestCase):
    """Every element of the Community Mod Menu needs localization; a missing
    key shows the player a raw identifier such as hafp__area_x_name."""

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(REGISTER):
            raise unittest.SkipTest("register file not generated")
        cls.reg = read_text(REGISTER)
        cls.keys = set(re.findall(r"^ ([A-Za-z0-9_]+):", read_text(LOCALIZATION), re.M))
        cls.regs = []
        for kind, body in re.findall(r"cmm_register_(\w+?)_setting = \{(.*?)\n\t\}", cls.reg, re.S):
            cls.regs.append({"kind": kind, "id": _field(body, "setting_id"),
                             "tab": _field(body, "tab_id"), "group": _field(body, "group_id"),
                             "options": _field(body, "option_count"),
                             "default": _field(body, "default_index")})

    def _missing(self, wanted):
        return sorted(k for k in set(wanted) if k not in self.keys)

    def test_registrations_were_parsed(self):
        kinds = {r["kind"] for r in self.regs}
        self.assertTrue({"bool", "dropdown", "button"} <= kinds,
                        "registration parsing broke - found only %s" % sorted(kinds))

    def test_mod_has_a_name_and_description(self):
        self.assertEqual(self._missing(["hafp_name", "hafp_desc"]), [])

    def test_every_setting_has_a_name_and_description(self):
        wanted = []
        for r in self.regs:
            wanted += ["hafp__%s_name" % r["id"], "hafp__%s_desc" % r["id"]]
        self.assertEqual(self._missing(wanted), [])

    def test_every_tab_and_group_has_a_name(self):
        wanted = []
        for r in self.regs:
            wanted += ["hafp__%s_name" % r["tab"], "hafp__%s__%s_name" % (r["tab"], r["group"])]
        self.assertEqual(self._missing(wanted), [])

    def test_every_button_has_label_text(self):
        self.assertEqual(self._missing(["hafp__%s_text" % r["id"]
                                        for r in self.regs if r["kind"] == "button"]), [])

    def test_every_dropdown_option_has_a_name_and_a_valid_default(self):
        for r in (r for r in self.regs if r["kind"] == "dropdown"):
            count, default = int(r["options"]), int(r["default"])
            self.assertTrue(1 <= default <= count, "%s default out of range" % r["id"])
            self.assertEqual(self._missing(["hafp__%s_option_%d_name" % (r["id"], i)
                                            for i in range(1, count + 1)]), [])

    def test_every_action_log_key_is_localized(self):
        used = re.findall(r"(?:action|arg1|arg2) = (hafp[A-Za-z0-9_]+)", self.reg)
        self.assertTrue(used, "no Mod Action Log entries found")
        self.assertEqual(self._missing(used), [])

    def test_cascades_only_target_registered_settings(self):
        """Parent toggles (continent, region, Select All) write into children."""
        targets = set(re.findall(r"key = flag:hafp__(\w+) value", self.reg))
        self.assertTrue(targets, "no cascades found")
        self.assertEqual(sorted(targets - {r["id"] for r in self.regs}), [])


class TestResearchEffects(unittest.TestCase):
    """The instant-research buttons (hafp_research_effects.txt)."""

    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(RESEARCH):
            raise unittest.SkipTest("research effects not generated")
        cls.text = read_text(RESEARCH)
        cls.ids = re.findall(r"research_advance = advance_type:([A-Za-z0-9_.]+)", cls.text)
        cls.blocks = dict(re.findall(
            r"\tif = \{\n\t\tlimit = \{\n\t\t\tNOT = \{ has_advance = ([A-Za-z0-9_.]+) \}(.*?)research_advance",
            cls.text, re.S))
        cls.gated, cls.units = set(), set()
        for fname in os.listdir(SHIPPED_ADVANCES):
            text = read_text(os.path.join(SHIPPED_ADVANCES, fname))
            mask = ga.strip_positions(text)
            for name, _k, o, c in ga.find_blocks(text, mask, 0, len(text)):
                body = text[o:c]
                if "has_variable = " + ga.MASTER_ENABLED in body:
                    cls.gated.add(name)
                    if ga.is_military_advance(fname, body):
                        cls.units.add(name)

    def test_each_advance_has_exactly_one_research_block(self):
        dup = sorted(i for i, n in collections.Counter(self.ids).items() if n > 1)
        self.assertEqual(dup, [], "advances with more than one research block")

    def test_every_gated_advance_is_researchable(self):
        self.assertEqual(sorted(self.gated - set(self.ids)), [])

    def test_unique_unit_advances_need_the_opt_in_toggle(self):
        """Requirement 7, research layer: the buttons never grant a unique unit -
        the player's own included - unless Allow Unique Unit Advances is on.

        The check must sit at the TOP of the limit. The block also embeds the
        advance's gate, whose mod branch repeats the toggle, but that copy only
        covers foreign units: the player's own unit advance passes the gate
        through its vanilla branch and would still be researched."""
        self.assertTrue(self.units, "no unit-granting advances found - parsing broke?")
        top = re.compile(r"\s*has_variable = %s\n" % ga.ALLOW_UNIT_UNLOCKS)
        lacking = sorted(u for u in self.units if not top.match(self.blocks.get(u, "")))
        self.assertEqual(lacking, [])

    def test_scope_checks_match_the_dropdown(self):
        """Adding or reordering Research Scope options must be mirrored in the
        effects; a mismatch silently changes what a button researches."""
        block = re.search(r"setting_id = research_scope(.*?)\n\t\}", read_text(REGISTER), re.S)
        count = int(_field(block.group(1), "option_count"))
        used = set(int(v) for v in re.findall(r'research_scope\)" = (\d+)', self.text))
        self.assertEqual(used, set(range(1, count + 1)))


class TestUserRequirements(unittest.TestCase):
    """Behaviours the user explicitly asked for (REQUIREMENTS.md), pinned to
    real advances in the shipped output.

    If a game patch renames or removes one of these advances, the test fails
    with 'golden example ... is gone'. Pick another advance that shows the same
    behaviour and update the entry here - the behaviour is what matters."""

    def advance(self, fname, adv_id):
        path = os.path.join(SHIPPED_ADVANCES, fname)
        if os.path.isfile(path):
            text = read_text(path)
            mask = ga.strip_positions(text)
            for name, _k, o, c in ga.find_blocks(text, mask, 0, len(text)):
                if name == adv_id:
                    return text[o:c]
        self.fail("golden example %s in %s is gone - a game patch probably renamed or "
                  "removed it; pick another advance with the same behaviour" % (adv_id, fname))

    def assertGate(self, fname, adv_id, has=(), lacks=()):
        """`has` needles must appear as whole tokens (hafp_g_tall must not be
        satisfied by hafp_g_tallX); `lacks` needles must not appear at all."""
        body = self.advance(fname, adv_id)
        for needle in has:
            self.assertRegex(body, re.escape(needle) + r"(?![A-Za-z0-9_])",
                             "%s should contain %r" % (adv_id, needle))
        for needle in lacks:
            self.assertNotIn(needle, body, "%s should not contain %r" % (adv_id, needle))

    def test_req1_nations_filed_by_continent_region_and_area(self):
        self.assertGate("country_fra.txt", "french_tradition",
                        has=("hafp_g_cont_europe", "hafp_g_reg_france_region",
                             "hafp_g_area_ile_de_france_area"))

    def test_req4_own_nation_keeps_its_vanilla_condition(self):
        self.assertGate("country_fra.txt", "french_tradition", has=("has_or_had_tag = FRA",))

    def test_req7_foreign_unique_units_are_opt_in(self):
        self.assertGate("country_tur.txt", "a_revolutions_janissaries_advance",
                        has=("has_variable = hafp_allow_unit_unlocks", "has_or_had_tag = TUR"))
        self.assertGate("culture_arabian.txt", "a_bedouin_cavalry_advance",
                        has=("has_variable = hafp_allow_unit_unlocks",))

    def test_req7_military_buffs_are_not_treated_as_units(self):
        self.assertGate("country_fra.txt", "elan", lacks=("hafp_allow_unit_unlocks",))

    def test_req8_vassals_kept_alongside_samanta(self):
        text = read_text(os.path.join(ROOT, "in_game", "common", "subject_types", "vassal.txt"))
        self.assertIn("samanta_advance", text)
        self.assertIn("culture_group:indian_group", text)

    def test_req9_tall_examples(self):
        for fname, adv in (("culture_netherlands.txt", "polders_advance"),   # tall building
                           ("country_hab.txt", "geheimrat"),                # cabinet seats
                           ("country_vij.txt", "vij_the_bunds")):           # tall building
            self.assertGate(fname, adv, has=("hafp_g_tall",))
        self.assertGate("country_fra.txt", "french_tradition", lacks=("hafp_g_tall",))

    def test_government_key_is_folded_as_a_trigger(self):
        self.assertGate("government_monarchy.txt", "noble_knights",
                        has=("government_type = government_type:monarchy",),
                        lacks=("\tgovernment = monarchy",))

    def test_institution_requirements_are_untouched(self):
        self.assertGate("0_age_of_traditions.txt", "meritocracy_advance",
                        has=("has_embraced_institution = institution:meritocracy",),
                        lacks=("hafp_",))

    def test_negated_geography_is_not_read_as_membership(self):
        """1.4: the Panama canal is gated NOT = { continent = continent:oceania }."""
        self.assertGate("canal_advances.txt", "panama_canal_advance",
                        lacks=("hafp_g_cont_oceania",))

    def test_formable_conquest_territory_is_not_home_geography(self):
        """The Roman Empire's formable spans Britain to Egypt; its Byzantine
        advances belong in the Balkans and Anatolia."""
        text = read_text(os.path.join(SHIPPED_ADVANCES, "D008_byzantine_unlocks.txt"))
        self.assertIn("hafp_g_reg_balkan_region", text)
        self.assertNotIn("hafp_g_cont_africa", text)

    def test_req9_141_additions(self):
        for fname, adv in (("0_age_of_traditions.txt", "aqueduct_system"),     # tall building
                           ("country_ITA.txt", "ita_attractive_migration"),    # towns & cities migration
                           ("country_alg.txt", "zab_zibane_palmery"),          # farmland expansion
                           ("country_HUN.txt", "hun_curtailed_peasantry"),     # max RGO size
                           ("country_pol.txt", "granary_of_europe"),           # food production
                           ("country_ser.txt", "hum_the_ponor_storage_system")):  # food storage
            self.assertGate(fname, adv, has=("hafp_g_tall",))

    def test_req9_colonization_migration_speed_life_expectancy(self):
        for fname, adv in (("country_grl.txt", "grl_western_outpost"),        # colonial migration
                           ("country_KON.txt", "kon_european_contact"),       # colonial range
                           ("country_maj.txt", "maj_island_colonies"),        # colonial charter cost
                           ("country_bra.txt", "edict_of_potsdam"),           # migration speed
                           ("country_bos.txt", "bos_bosnian_ljekaruse")):     # life expectancy
            self.assertGate(fname, adv, has=("hafp_g_tall",))

    def test_req9_false_positives_are_not_tall(self):
        self.assertGate("country_son.txt", "sharia", lacks=("hafp_g_tall",))      # penalty only
        self.assertGate("0_age_of_traditions.txt", "state_administration_advance",
                        lacks=("hafp_g_tall",))                                    # research_cost

    def test_req9_roman_town_rights_unlocked_by_tall(self):
        path = os.path.join(ROOT, "in_game", "common", "town_rights", "byzantine_greek_roman.txt")
        if not os.path.isfile(path):
            self.fail("byzantine_greek_roman.txt town rights are gone - a patch renamed them")
        text = read_text(path)
        mask = ga.strip_positions(text)
        rights = {n: text[o:c + 1] for n, _k, o, c in ga.find_blocks(text, mask, 0, len(text))}
        for name in ("imperial_breadbasket_rights", "scholai_literacy_rights",
                     "constantinopolitan_silk_monopoly_rights", "municipia_privilegia"):
            self.assertIn(name, rights, "town right %s is gone" % name)
            kept, or_block = potential_parts(rights[name])
            self.assertTrue(has_token(or_block, "has_variable = hafp_g_tall"), name)
        kept, or_block = potential_parts(rights["municipia_privilegia"])
        self.assertIn("has_dlc", kept, "Municipia must still require Fate of the Phoenix")

    def test_dlc_advances_require_the_dlc(self):
        kept, or_block = potential_parts(self.advance("religion_hellenism.txt",
                                                     "epic_poetry_advance"))
        self.assertIn('has_dlc = "d008_fate_of_the_phoenix"', kept)
        self.assertNotIn("has_dlc", or_block)

    def test_pop_nations_are_placed_by_seed_location(self):
        """1.4: Kel Ahaggar declares no capital and is seeded at Abalessa."""
        self.assertGate("country_tle.txt", "ahg_hoggar_massif",
                        has=("hafp_g_reg_maghreb_region",))


def shipped_advances(fname):
    """Advance id -> body for one shipped override file ({} if absent)."""
    path = os.path.join(SHIPPED_ADVANCES, fname)
    if not os.path.isfile(path):
        return {}
    text = read_text(path)
    mask = ga.strip_positions(text)
    return {name: text[o:c] for name, _k, o, c in ga.find_blocks(text, mask, 0, len(text))}


def has_token(body, needle):
    return re.search(re.escape(needle) + r"(?![A-Za-z0-9_])", body) is not None


class TestUnlockAll(unittest.TestCase):
    """The user plays with Unlock All Custom Advances switched on."""

    def _gated(self):
        for fname in os.listdir(SHIPPED_ADVANCES):
            for adv_id, body in shipped_advances(fname).items():
                if has_token(body, "has_variable = " + ga.MASTER_ENABLED):
                    yield fname, adv_id, body

    def test_unlock_all_reaches_every_custom_advance(self):
        missing = [adv for _f, adv, body in self._gated()
                   if not has_token(body, "has_variable = " + ga.UNLOCK_ALL)]
        self.assertEqual(missing, [], "custom advances Unlock All cannot reach")

    def test_unique_units_stay_opt_in_even_with_unlock_all(self):
        """Requirement 7, unlock layer: Unlock All must not hand out foreign
        unique units unless Allow Unique Unit Advances is also on."""
        lacking = [adv for f, adv, body in self._gated()
                   if ga.is_military_advance(f, body)
                   and not has_token(body, "has_variable = " + ga.ALLOW_UNIT_UNLOCKS)]
        self.assertEqual(lacking, [], "unit advances that Unlock All alone would grant")


# Nations the user actually plays - tall, with Unlock All Custom Advances on.
# To protect another nation, add an entry here (see MAINTAINING.md).
PLAYER_PROFILES = {
    "France": {"file": "country_fra.txt", "tag": "FRA",
               "region": "france_region", "area": "ile_de_france_area",
               "tall": ("estates_general", "the_philosophes"),
               "own_units": ()},
    "Khmer": {"file": "country_khm.txt", "tag": "KHM",
              "region": "indochina_region", "area": "lower_mekong_area",
              "tall": ("khm_foreign_production_skills", "khm_invest_in_irrigation"),
              "own_units": ("khm_ballista_elephants",)},
}


class TestPlayerProfiles(unittest.TestCase):
    """What must keep working for the nations in PLAYER_PROFILES.

    A failure saying a nation or advance 'is gone' means a game patch renamed
    or removed it - update the profile rather than the generators."""

    def _advances(self, nation, profile):
        advs = shipped_advances(profile["file"])
        if not advs:
            self.fail("%s: %s is gone - a game patch renamed or removed it; "
                      "update PLAYER_PROFILES" % (nation, profile["file"]))
        return advs

    def _advance(self, nation, profile, adv_id):
        body = self._advances(nation, profile).get(adv_id)
        if body is None:
            self.fail("%s: advance %s is gone - pick another example and update "
                      "PLAYER_PROFILES" % (nation, adv_id))
        return body

    def test_own_advances_keep_their_vanilla_condition(self):
        """Requirement 4: the nation always sees its own tree, mod on or off."""
        for nation, p in PLAYER_PROFILES.items():
            with self.subTest(nation=nation):
                lost = [a for a, body in self._advances(nation, p).items()
                        if not has_token(body, "has_or_had_tag = " + p["tag"])]
                self.assertEqual(lost, [])

    def test_own_advances_are_filed_under_home_region_and_area(self):
        """Requirement 1: selecting the home region or area unlocks the tree."""
        for nation, p in PLAYER_PROFILES.items():
            with self.subTest(nation=nation):
                for adv_id, body in self._advances(nation, p).items():
                    for var in ("hafp_g_reg_" + p["region"], "hafp_g_area_" + p["area"]):
                        self.assertTrue(has_token(body, "has_variable = " + var),
                                        "%s/%s is not filed under %s" % (nation, adv_id, var))

    def test_tall_advances_are_classified_tall(self):
        """Requirement 9."""
        for nation, p in PLAYER_PROFILES.items():
            for adv_id in p["tall"]:
                with self.subTest(nation=nation, advance=adv_id):
                    self.assertTrue(has_token(self._advance(nation, p, adv_id),
                                              "has_variable = hafp_g_tall"))

    def test_own_unique_units_are_left_to_the_player(self):
        """Requirement 7: the nation can still research its own unique units by
        hand (vanilla branch kept), but no research button grants them unless
        Allow Unique Unit Advances is on."""
        research = read_text(RESEARCH)
        for nation, p in PLAYER_PROFILES.items():
            for adv_id in p["own_units"]:
                with self.subTest(nation=nation, advance=adv_id):
                    self.assertTrue(has_token(self._advance(nation, p, adv_id),
                                              "has_or_had_tag = " + p["tag"]))
                    m = re.search(r"NOT = \{ has_advance = %s \}\n\s*has_variable = %s\n"
                                  % (re.escape(adv_id), ga.ALLOW_UNIT_UNLOCKS), research)
                    self.assertIsNotNone(m, "%s's research block lacks the opt-in" % adv_id)


class TestTallRules141(unittest.TestCase):
    """Tall additions for 1.4.1: towns & cities migration, food production and
    storage, RGO capacity, tall buildings - and the false positives removed."""

    def test_new_families_are_tall(self):
        for body in ("non_rural_migration_attraction = 0.1",      # towns & cities migration
                     "expand_rgo_farming_cost_modifier = -0.1",   # cheaper farmland
                     "global_max_rgo_size_modifier = 0.1",
                     "expand_rgo_mining_cost_modifier = -0.1",
                     "expand_rgo_gathering_cost_modifier = -0.1",
                     "global_food_capacity_modifier = 0.1",       # food storage %
                     "global_food_decay = -0.005",                # food storage
                     "global_population_capacity_modifier = 0.1"):
            self.assertTrue(ga.is_tall_advance(body), body)

    def test_research_cost_is_not_a_research_bonus(self):
        """research_cost prices the advance it sits in (2.0 = twice as dear)."""
        self.assertFalse(ga.is_tall_advance("research_cost = 2.0"))
        self.assertTrue(ga.is_tall_advance("research_speed_modifier = 0.1"))

    def test_penalties_do_not_count(self):
        for body in ("dhimmi_estate_target_satisfaction = medium_permanent_target_satisfaction_penalty",
                     "global_food_decay = 0.01",                  # more spoilage
                     "expand_rgo_farming_cost_modifier = 0.1",    # dearer farmland
                     "global_monthly_development = -0.1"):
            self.assertFalse(ga.is_tall_advance(body), body)

    def test_colonization_migration_speed_and_life_expectancy_are_tall(self):
        """Requested for 1.4.1."""
        for body in ("colonial_migration_size_modifier = 0.25",   # Monthly Colonial Migration
                     "colonial_migration_size = 1",
                     "colonial_range_modifier = 0.2",
                     "colonial_maintenance_efficiency = 0.2",
                     "create_colonial_charter_cost_modifier = -0.1",
                     "can_colonize = yes",
                     "global_migration_speed_modifier = 0.1",     # Pop Migration Speed
                     "global_life_expectancy = 3"):               # Character Life Expectancy
            self.assertTrue(ga.is_tall_advance(body), body)

    def test_deliberately_excluded(self):
        for body in ("rural_migration_attraction = 0.1",          # countryside, not towns - agreed
                     "exploration_mission_speed = 0.1",           # exploration, not colonization
                     "aid_colonial_war_cost_modifier = -0.1",     # war, not colonization
                     "join_colonial_federation_cost_modifier = -0.1"):
            self.assertFalse(ga.is_tall_advance(body), body)

    def test_is_bonus_polarity(self):
        self.assertTrue(ga.is_bonus("global_monthly_food_modifier", "monthly_food_productivity_severe_bonus"))
        self.assertFalse(ga.is_bonus("nobles_estate_target_satisfaction", "small_privilege_target_satisfaction_penalty"))
        self.assertTrue(ga.is_bonus("global_pop_food_consumption", "-0.05"))
        self.assertFalse(ga.is_bonus("global_pop_food_consumption", "0.05"))
        self.assertTrue(ga.is_bonus("allow_female_cabinet", "yes"))

    def test_unlocking_a_tall_building_makes_an_advance_tall(self):
        body = "potential = { has_or_had_tag = X }\n\tunlock_building = aqueduct_system\n"
        self.assertTrue(ga.is_tall_advance(body, {"aqueduct_system"}))
        self.assertFalse(ga.is_tall_advance(body, set()))
        self.assertFalse(ga.is_tall_advance("# unlock_building = aqueduct_system", {"aqueduct_system"}))

    def test_building_rule_reads_building_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "game", "in_game", "common", "building_types")
            os.makedirs(d)
            with open(os.path.join(d, "test.txt"), "w", encoding="utf-8") as fh:
                fh.write("granary = {\n\tmodifier = { local_food_capacity = 100 }\n}\n"
                         "barracks = {\n\tmodifier = { local_manpower = 1 }\n}\n"
                         "housing = {\n\tmodifier = { local_population_capacity = 0.5 }\n}\n")
            saved = set(ga._tall_buildings)
            try:
                found = ga.load_tall_buildings(tmp)
            finally:
                ga._tall_buildings.clear()
                ga._tall_buildings.update(saved)
        self.assertEqual(found, {"granary", "housing"})


def potential_parts(text):
    """-> (text outside the OR, OR block text) of the first potential block
    found at any depth in `text` (an advance, a town right, or a fragment)."""
    mask = ga.strip_positions(text)
    for m in re.finditer(r"\bpotential\s*=\s*\{", text):
        if mask[m.start()]:
            continue                                   # inside a comment
        o = m.end() - 1
        inner = text[o + 1:ga.match_brace(text, mask, o)]
        imask = ga.strip_positions(inner)
        for iname, ik, _io, ic in ga.find_blocks(inner, imask, 0, len(inner)):
            if iname == "OR":
                return inner[:ik] + inner[ic + 1:], inner[ik:ic + 1]
        return inner, ""
    return "", ""


class TestDlcOwnership(unittest.TestCase):
    """DLC content lives in the base files behind has_dlc checks. The mod must
    never unlock it for players who do not own the DLC."""

    def test_wrap_gate_keeps_dlc_check_outside_the_unlock_branch(self):
        body = ('\n\tpotential = {\n\t\thas_dlc = "d008_fate_of_the_phoenix"\n'
                '\t\treligion = religion:hellenism_religion\n\t}\n')
        out, changed = ga.process_advance("x", body, [ga.UNLOCK_ALL])
        self.assertTrue(changed)
        kept, or_block = potential_parts("x = {" + out + "}")
        self.assertIn("has_dlc", kept)
        self.assertNotIn("has_dlc", or_block)
        self.assertIn("religion = religion:hellenism_religion", or_block)
        self.assertTrue(braces_balanced("x = {" + out + "}"))

    def test_every_shipped_dlc_gate_applies_to_both_branches(self):
        checked = 0
        for sub in ("advances", "town_rights"):
            folder = os.path.join(ROOT, "in_game", "common", sub)
            if not os.path.isdir(folder):
                continue
            for fname in os.listdir(folder):
                text = read_text(os.path.join(folder, fname))
                mask = ga.strip_positions(text)
                for name, _k, o, c in ga.find_blocks(text, mask, 0, len(text)):
                    body = text[o:c + 1]
                    kept, or_block = potential_parts(body)
                    if "has_dlc" in kept + or_block:
                        checked += 1
                        self.assertNotIn("has_dlc", or_block,
                                         "%s/%s unlocks DLC content without the DLC" % (fname, name))
        self.assertGreater(checked, 0, "no DLC-gated content found - parsing broke?")


class TestTownRights(unittest.TestCase):
    """Nation/culture-locked town rights with tall bonuses, unlocked by Tall."""

    def tr(self, potential, modifiers="local_monthly_food_modifier = 0.1"):
        return ("\n\tlocation_modifier = {\n\t\t%s\n\t}\n\tpotential = {\n\t\t%s\n\t}\n"
                "\tallow = { }\n" % (modifiers, potential))

    def test_statement_splitter_understands_question_equals(self):
        text = "capital ?= { region = region:x }\nmodifier:allow_y = yes\nvalue >= 0.5"
        got = [text[s:e] for s, e in ga.top_level_statements(text)]
        self.assertEqual(got, ["capital ?= { region = region:x }", "modifier:allow_y = yes",
                               "value >= 0.5"])

    def test_identity_gate_is_unlocked(self):
        out, changed = ga.process_town_right(self.tr("OR = { has_or_had_tag = BYZ has_or_had_tag = ROM }"))
        self.assertTrue(changed)
        kept, or_block = potential_parts("x = {" + out + "}")
        self.assertIn("hafp_g_tall", or_block)
        self.assertIn("has_or_had_tag = BYZ", or_block)
        self.assertNotIn("hafp_g_reg_", out, "town rights only respond to Tall and Unlock All")

    def test_progression_gate_is_left_alone(self):
        body = self.tr("has_reform = government_reform:agrarian_community")
        self.assertEqual(ga.process_town_right(body), (body, False))

    def test_mixed_gate_keeps_the_progression_part_for_everyone(self):
        out, changed = ga.process_town_right(self.tr(
            "culture = { has_culture_group = culture_group:french_group }\n"
            "\t\tmodifier:allow_ville_franche_town_rights = yes"))
        self.assertTrue(changed)
        kept, or_block = potential_parts("x = {" + out + "}")
        self.assertIn("modifier:allow_ville_franche_town_rights = yes", kept)
        self.assertIn("french_group", or_block)

    def test_dlc_gate_is_kept_for_everyone(self):
        out, _ = ga.process_town_right(self.tr('has_dlc = "d008_fate_of_the_phoenix"\n'
                                               "\t\thas_or_had_tag = BYZ"))
        kept, or_block = potential_parts("x = {" + out + "}")
        self.assertIn("has_dlc", kept)
        self.assertNotIn("has_dlc", or_block)

    def test_non_tall_and_penalty_only_rights_are_left_alone(self):
        for mods in ("local_nobles_estate_power = -0.5",
                     "nobles_estate_target_satisfaction = small_privilege_target_satisfaction_penalty"):
            body = self.tr("has_or_had_tag = BOH", mods)
            self.assertEqual(ga.process_town_right(body), (body, False), mods)

    def test_shipped_town_rights_only_respond_to_tall_and_unlock_all(self):
        folder = os.path.join(ROOT, "in_game", "common", "town_rights")
        if not os.path.isdir(folder):
            self.skipTest("no town rights shipped")
        used = set()
        for fname in os.listdir(folder):
            used.update(re.findall(r"has_variable = (hafp_[a-z0-9_]+)",
                                   read_text(os.path.join(folder, fname))))
        self.assertEqual(used, {ga.MASTER_ENABLED, ga.UNLOCK_ALL, "hafp_g_tall"})


class TestCoreTenets(unittest.TestCase):
    """The promises the mod makes whatever else changes - all runnable without
    the game, so GitHub checks them on every push.

    1. Installing it changes nothing until the player opts in: every toggle is
       off by default and every unlock path needs the Enabled master switch.
    2. The player's own nation keeps its vanilla tree (TestPlayerProfiles and
       test_req4 below), and institution gates are never bypassed
       (test_institution_allow_gates_are_never_wrapped).
    3. Unique units, future ages and DLC content each need an explicit choice:
       units the Allow Unique Unit Advances toggle (TestResearchEffects,
       TestUnlockAll), future ages a research scope that says so (below), and
       DLC ownership (TestDlcOwnership)."""

    def setUp(self):
        if not os.path.isfile(REGISTER):
            self.skipTest("register file not generated")
        self.reg = read_text(REGISTER)

    def test_every_toggle_defaults_to_off(self):
        bools = re.findall(r"cmm_register_bool_setting = \{(.*?)\n\t\}", self.reg, re.S)
        self.assertGreater(len(bools), 300, "toggle parsing broke")
        on = [_field(b, "setting_id") for b in bools if _field(b, "default_value") != "0"]
        self.assertEqual(on, [], "toggles that would change the game on first load")

    def test_research_scope_defaults_to_no_future_ages(self):
        block = re.search(r"setting_id = research_scope(.*?)\n\t\}", self.reg, re.S).group(1)
        default = _field(block, "default_index")
        self.assertEqual(default, "2")
        names = set(re.findall(r'^ hafp__research_scope_option_%s_name: "(.*)"' % default,
                               read_text(LOCALIZATION), re.M))
        self.assertEqual(names, {"All, No Future Ages"})

    def test_every_unlock_path_needs_the_master_switch(self):
        """Each rewritten gate is OR { AND {unlock branch} AND {vanilla} }; the
        unlock branch must open with has_variable = hafp_enabled."""
        checked = 0
        for sub in ("advances", "town_rights"):
            folder = os.path.join(ROOT, "in_game", "common", sub)
            if not os.path.isdir(folder):
                continue
            for fname in os.listdir(folder):
                text = read_text(os.path.join(folder, fname))
                mask = ga.strip_positions(text)
                for name, _k, o, c in ga.find_blocks(text, mask, 0, len(text)):
                    _kept, or_block = potential_parts(text[o:c + 1])
                    if "hafp_" not in or_block:
                        continue
                    checked += 1
                    first = re.search(r"OR = \{\s*AND = \{\s*(\S+ = \S+)", or_block)
                    self.assertIsNotNone(first, "%s/%s: unexpected gate shape" % (fname, name))
                    self.assertEqual(first.group(1), "has_variable = " + ga.MASTER_ENABLED,
                                     "%s/%s: unlock branch skips the master switch" % (fname, name))
        self.assertGreater(checked, 2800, "gate parsing broke")

    def test_research_only_reaches_future_ages_under_all_advances(self):
        """Scopes 2-4 state their age limit explicitly in every block of an
        age's research effect; only scope 1 (All Advances) may skip ahead."""
        text = read_text(RESEARCH)
        effects = re.findall(r"^hafp_research_(age_\d_[a-z]+)_(?:generic|custom) = \{\n(.*?)\n\}",
                             text, re.M | re.S)
        self.assertEqual(len(effects), 12, "expected generic + custom effects for six ages")
        blocks = 0
        for age, body in effects:
            # prefix a newline so the effect's first block is split off too
            for block in re.split(r"\n\tif = \{", "\n" + body)[1:]:
                blocks += 1
                adv = re.search(r"has_advance = (\S+) \}", block).group(1)
                self.assertGreaterEqual(block.count("current_age_or_later = { age = %s }" % age), 2,
                                        "%s: a scope can research it before %s" % (adv, age))
                self.assertIn("current_age = %s" % age, block,
                              "%s: Current Age Institutions is not limited to %s" % (adv, age))
        self.assertGreater(blocks, 3000)


class TestDevelopmentEnvironment(unittest.TestCase):
    def test_local_python_matches_the_ci_pin(self):
        """GitHub's Windows test job runs the Python named in .python-version, so
        CI tests what you actually use. Upgrade Python locally and this fails,
        telling you exactly what to change - nothing to remember."""
        if os.environ.get("GITHUB_ACTIONS") == "true":
            self.skipTest("only meaningful on the machine that runs the generators")
        pin = read_text(os.path.join(ROOT, ".python-version")).strip()
        local = "%d.%d" % sys.version_info[:2]
        self.assertEqual(".".join(pin.split(".")[:2]), local,
                         "You are running Python %s but .python-version pins %s. Change "
                         ".python-version to %s, then commit and push - GitHub's Windows "
                         "test job reads it. See MAINTAINING.md." % (local, pin, local))


if __name__ == "__main__":
    unittest.main(verbosity=2)
