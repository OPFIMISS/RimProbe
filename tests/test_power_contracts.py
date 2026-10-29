import copy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from pydantic import TypeAdapter, ValidationError

from rimprobe.contracts import validate_contract
from rimprobe.errors import ProbeError
from rimprobe.inspection import inspect_mod
from rimprobe.runner import TestRunner, capabilities
from rimprobe.schema import BehaviorContractInput


class PowerContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parents[1]
        self.contract = json.loads((self.root / "examples/contracts/building-power.json").read_text())

    def test_normalization_is_idempotent_and_non_mutating(self):
        before = copy.deepcopy(self.contract)
        normalized = validate_contract(self.contract)
        self.assertEqual(before, self.contract)
        self.assertEqual(normalized, validate_contract(normalized))
        self.assertIsNone(normalized["fixture"]["stuff_name"])

    def test_sdk_union_roundtrip_and_discriminated_observers(self):
        adapter = TypeAdapter(BehaviorContractInput)
        normalized = adapter.validate_python(self.contract).model_dump(exclude_unset=True, by_alias=True)
        self.assertEqual(validate_contract(normalized)["recipe"], "building_power")
        invalid = dict(self.contract, expect=[{"kind": "power_net_registered", "minimum_watts": 1}])
        with self.assertRaises(ValidationError):
            adapter.validate_python(invalid)

    def test_output_threshold_must_be_finite_positive_number(self):
        for value in (True, False, 0, -1, float("nan"), float("inf"), 10000001, "90", None):
            with self.subTest(value=value), self.assertRaises(ProbeError):
                validate_contract(dict(self.contract, expect=[{"kind": "power_output_at_least", "minimum_watts": value}, {"kind": "power_net_registered"}]))

    def test_both_distinct_assertions_are_required(self):
        for expected in ([], self.contract["expect"][:1], [self.contract["expect"][0]] * 2, [{"kind": "power_net_registered"}] * 2):
            with self.subTest(expected=expected), self.assertRaises(ProbeError):
                validate_contract(dict(self.contract, expect=expected))

    def test_ignored_or_executable_fields_are_rejected(self):
        for expected in ([{"kind": "eval", "code": "x"}, {"kind": "power_net_registered"}], [{"kind": "power_output_at_least", "minimum_watts": 90, "when": "eventually"}, {"kind": "power_net_registered"}]):
            with self.assertRaises(ProbeError):
                validate_contract(dict(self.contract, expect=expected))
        for fixture in ({"force_power": True}, {"fuel": 99}, {"construction_skill": True}, {"construction_skill": -1}, {"construction_skill": 21}, {"settle_ticks": 0}, {"settle_ticks": True}, {"stuff_name": "../invalid"}):
            with self.subTest(fixture=fixture), self.assertRaises(ProbeError):
                validate_contract(dict(self.contract, fixture=fixture))

    def test_tick_budgets_leave_room_for_normal_construction(self):
        for options in ({"observe_ticks": 1}, {"observe_ticks": True}, {"max_ticks": 240}, {"timeout_seconds": 601}):
            with self.subTest(options=options), self.assertRaises(ProbeError):
                validate_contract(dict(self.contract, **options))

    def test_malformed_assertions_are_contract_errors(self):
        for assertion in (None, [], "power", {"kind": []}, {"kind": "power_output_at_least"}):
            with self.subTest(assertion=assertion), self.assertRaises(ProbeError):
                validate_contract(dict(self.contract, expect=[assertion, {"kind": "power_net_registered"}]))

    def test_stuff_passes_to_existing_runner(self):
        runner = TestRunner(Mock())
        contract = dict(self.contract, fixture={"stuff_name": "Steel"})
        with patch.object(runner, "run_suite", return_value={"ok": True}) as run:
            runner.run_contract(contract)
        self.assertEqual(run.call_args.args[1], "Steel")
        self.assertEqual(run.call_args.args[6]["recipe"], "building_power")

    def test_invalid_contract_never_launches(self):
        controller = Mock()
        with self.assertRaises(ProbeError):
            TestRunner(controller).run_contract(dict(self.contract, expect=[]))
        controller.launch.assert_not_called()

    def test_inspector_and_capabilities_expose_non_whitelisted_defs(self):
        result = inspect_mod(str(self.root / "fixtures/AbilityContract"))
        candidate = next(entry for entry in result["candidates"] if entry["def_name"] == "RimProbe_FixturePower")
        self.assertEqual(candidate["declared_power_comps"], ["CompPowerPlant"])
        self.assertIn("building_power", {entry["name"] for entry in capabilities()["suites"]})
