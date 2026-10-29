import copy
import json
from pathlib import Path
import tempfile
import unittest

from rimprobe.contracts import validate_contract
from rimprobe.inspection import inspect_mod
from rimprobe.errors import ProbeError
from rimprobe.profiles import plan_profile


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((Path(__file__).parents[1] / "examples" / "contracts" / "ability-marker.json").read_text())

    def test_contract_is_normalized_without_mutating_input(self):
        original = copy.deepcopy(self.contract)
        validated = validate_contract(self.contract)
        self.assertEqual(self.contract, original)
        self.assertEqual(validated["fixture"]["actor_hediffs"], [])

    def test_no_assertions_never_becomes_cast_success(self):
        self.contract["expect"] = []
        with self.assertRaises(ProbeError) as raised:
            validate_contract(self.contract)
        self.assertEqual(raised.exception.code, "missing_assertions")

    def test_unknown_observers_and_code_are_rejected(self):
        for mutation in ({"execute_csharp": "return true;"}, {"expect": [{"kind": "invent_success"}]}):
            with self.assertRaises(ProbeError):
                validate_contract({**self.contract, **mutation})

    def test_unknown_fixture_fields_are_rejected(self):
        self.contract["fixture"]["set_expected_result"] = True
        with self.assertRaises(ProbeError):
            validate_contract(self.contract)

    def test_malformed_enum_types_return_contract_errors(self):
        for value in ([], {}, True):
            with self.subTest(value=value):
                contract = {**self.contract, "expect": [{"kind": value}]}
                with self.assertRaises(ProbeError):
                    validate_contract(contract)
                contract = {**self.contract, "fixture": {"target": value}}
                with self.assertRaises(ProbeError):
                    validate_contract(contract)

    def test_cell_cannot_use_pawn_target_observers(self):
        self.contract["fixture"]["target"] = "cell"
        with self.assertRaises(ProbeError):
            validate_contract(self.contract)

    def test_budget_limits_are_validated_before_launch(self):
        for field, value in (("observe_ticks", 6000), ("timeout_seconds", 601), ("max_ticks", 1)):
            with self.assertRaises(ProbeError):
                validate_contract({**self.contract, field: value})

    def test_inspection_discovers_custom_defs_without_executing_them(self):
        result = inspect_mod(str(Path(__file__).parents[1] / "fixtures" / "AbilityContract"))
        candidate = next(item for item in result["candidates"] if item["def_name"] == "RimProbe_FixtureMark")
        self.assertEqual(candidate["declared_hediffs"], ["RimProbe_FixtureMarker"])
        self.assertTrue(candidate["contract_required"])

    def test_inspection_prunes_other_versions_and_build_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for directory in ("1.6/Defs", "1.7/Defs", "obj/Defs"):
                target = root / directory
                target.mkdir(parents=True)
                (target / "sample.xml").write_text("<Defs><AbilityDef><defName>Sample</defName></AbilityDef></Defs>")
            result = inspect_mod(str(root), "1.7")
            self.assertEqual(result["files_read"], 1)
            self.assertEqual(len(result["candidates"]), 1)
            self.assertIn("1.7", result["candidates"][0]["path"])


class ProfileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.source = Path(temporary.name) / "ModsConfig.xml"
        self.source.write_text("<ModsConfigData><activeMods><li>ludeon.rimworld</li><li>ludeon.rimworld.royalty</li><li>custom.ability</li><li>ludeon.rimworld.biotech</li></activeMods></ModsConfigData>", encoding="utf-8")

    def test_inherit_preserves_dlc_and_relative_order_without_source_write(self):
        original = self.source.read_bytes()
        profile = plan_profile("inherit", ["test.extra"], self.source)
        mods = profile["requested_mods"]
        self.assertEqual(mods, ["brrainz.harmony", "ludeon.rimworld", "ludeon.rimworld.royalty", "custom.ability", "ludeon.rimworld.biotech", "test.extra", "rimprobe.agent"])
        self.assertEqual(self.source.read_bytes(), original)
        self.assertFalse(profile["player_config_modified"])

    def test_missing_source_never_silently_selects_minimal(self):
        self.source.unlink()
        with self.assertRaises(ProbeError) as raised:
            plan_profile("inherit", [], self.source)
        self.assertEqual(raised.exception.code, "profile_source_missing")

    def test_minimal_requires_explicit_mode(self):
        self.assertEqual(plan_profile("minimal", [])["requested_mods"], ["brrainz.harmony", "ludeon.rimworld", "rimprobe.agent"])

    def test_duplicate_source_is_not_silently_reordered_or_fixed(self):
        self.source.write_text("<ModsConfigData><activeMods><li>ludeon.rimworld</li><li>ludeon.rimworld</li></activeMods></ModsConfigData>")
        with self.assertRaises(ProbeError):
            plan_profile("inherit", [], self.source)
