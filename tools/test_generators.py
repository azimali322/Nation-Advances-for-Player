#!/usr/bin/env python3
"""Unit tests for the Handicap Advances generators.

Run:  python tools/test_generators.py          (stdlib unittest, no deps)

Covers the parsing and classification logic that the EU5 1.4 migration
touched, plus an integration pass over the generated output.
"""

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

VANILLA_ADVANCES = os.path.join(
    ga.__dict__.get("HERE") and r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V" or "",
    "game", "in_game", "common", "advances")


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
        for fname in os.listdir(self.ADV):
            with open(os.path.join(self.ADV, fname), encoding="utf-8-sig") as fh:
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

    def test_detects_subject_type_drift(self):
        self.assertTrue(self._mutated(lambda t: self._edit(
            t, os.path.join("subject_types", "vassal.txt"), "level = 2", "level = 3")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
