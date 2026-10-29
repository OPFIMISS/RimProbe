import copy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock
from pydantic import TypeAdapter, ValidationError
from rimprobe.contracts import validate_contract
from rimprobe.errors import ProbeError
from rimprobe.inspection import inspect_mod
from rimprobe.runner import TestRunner, capabilities
from rimprobe.schema import BehaviorContractInput


class ExtendedContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parents[1]
        self.item = json.loads((self.root / "examples/contracts/item-marker.json").read_text())
        self.ui = json.loads((self.root / "examples/contracts/ui-info-card.json").read_text())

    def test_sdk_union_preserves_recipe_and_alias(self):
        adapter = TypeAdapter(BehaviorContractInput)
        for contract in (self.item, self.ui):
            result = adapter.validate_python(contract).model_dump(exclude_unset=True, by_alias=True)
            self.assertEqual(validate_contract(result)["recipe"], contract["recipe"])
        with self.assertRaises(ValidationError):
            adapter.validate_python(dict(self.ui, recipe="eval"))

    def test_normalization_preserves_input(self):
        for contract in (self.item, self.ui):
            before = copy.deepcopy(contract)
            validate_contract(contract)
            self.assertEqual(before, contract)

    def test_normalization_is_idempotent_and_ui_has_no_ignored_tick_fields(self):
        for contract in (self.item, self.ui):
            normalized = validate_contract(contract)
            self.assertEqual(normalized, validate_contract(normalized))
        ui = copy.deepcopy(self.ui)
        ui.pop("timeout_seconds", None)
        normalized = validate_contract(ui)
        self.assertEqual(normalized["timeout_seconds"], 30)
        self.assertNotIn("observe_ticks", normalized)
        self.assertNotIn("max_ticks", normalized)

    def test_item_actor_only_and_exact_hediff(self):
        for assertion in ({"kind": "hediff_added"}, {"kind": "item_consumed", "subject": "target"}, {"kind": "item_consumed", "def_name": "Injected"}, {"kind": "cooldown_started"}):
            with self.subTest(assertion=assertion), self.assertRaises(ProbeError):
                validate_contract(dict(self.item, expect=[assertion]))

    def test_initial_food_is_bounded_and_finite(self):
        for fraction in (True, -1, 0, 1, float("nan"), float("inf"), "0.25"):
            with self.subTest(fraction=fraction), self.assertRaises(ProbeError):
                validate_contract(dict(self.item, fixture={"initial_food_fraction": fraction}))

    def test_ui_requires_distinct_lifecycle_checks(self):
        for checks in ([], self.ui["expect"][:3], [self.ui["expect"][0]] * 4):
            with self.subTest(checks=checks), self.assertRaises(ProbeError):
                validate_contract(dict(self.ui, expect=checks))

    def test_ui_rejects_ignored_tick_budgets(self):
        for field in ("observe_ticks", "max_ticks"):
            with self.assertRaises(ProbeError):
                validate_contract(dict(self.ui, **{field: 1000}))

    def test_ui_hold_uses_bounded_wall_clock(self):
        for hold in (False, 0, 11, float("nan"), float("inf")):
            with self.subTest(hold=hold), self.assertRaises(ProbeError):
                validate_contract(dict(self.ui, fixture={"hold_seconds": hold}))

    def test_executable_and_cross_fixture_fields_rejected(self):
        for contract in (self.item, self.ui):
            for fixture in ({"execute": "return true"}, {"set_expected_result": True}):
                with self.assertRaises(ProbeError):
                    validate_contract(dict(contract, fixture=fixture))

    def test_invalid_delay_is_rejected_before_launch(self):
        controller = Mock()
        runner = TestRunner(controller)
        for delay in (-1, 3601, True, "180", 60):
            with self.subTest(delay=delay), self.assertRaises(ProbeError):
                runner.run_suite(max_ticks=60, supply_delay_ticks=delay)
        controller.launch.assert_not_called()

    def test_inspector_exposes_lexical_ingestion(self):
        result = inspect_mod(str(self.root / "fixtures/AbilityContract"))
        target = next(entry for entry in result["candidates"] if entry["def_name"] == "RimProbe_FixtureMeal")
        self.assertTrue(target["declared_ingestible"])
        self.assertIn("IngestionOutcomeDoer_GiveHediff", target["declared_ingestion_outcomes"])

    def test_capabilities_describe_registered_routes(self):
        suites = {entry["name"] for entry in capabilities()["suites"]}
        self.assertTrue({"building_construction", "ability_cast", "item_ingest", "ui_info_card"} <= suites)
