import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from rimprobe.errors import ProbeError
from rimprobe.plans import validate_plan, plan_catalog
from rimprobe.runner import TestRunner
from rimprobe.server import create_server


ROOT = Path(__file__).parents[1]


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / "examples/plans/ability-marker.json").read_text())

    def rejected(self, plan):
        with self.assertRaises(ProbeError) as context:
            validate_plan(plan)
        self.assertEqual(context.exception.code, "invalid_plan")

    def test_examples_normalize_idempotently_without_mutation(self):
        for path in (ROOT / "examples/plans").glob("*.json"):
            with self.subTest(path=path):
                original = json.loads(path.read_text())
                before = copy.deepcopy(original)
                normalized = validate_plan(original)
                self.assertEqual(normalized, validate_plan(normalized))
                self.assertEqual(original, before)
                normalized["steps"][0]["id"] = "changed"
                self.assertEqual(original, before)

    def test_strict_schema_numbers_and_budgets(self):
        for field, value in (("schema", True), ("schema", 2), ("max_ticks", True),
                             ("max_ticks", 59), ("timeout_seconds", 601), ("timeout_seconds", "180")):
            with self.subTest(field=field, value=value):
                self.rejected({**self.plan, field: value})
        for value in (float("nan"), float("inf"), True, "1"):
            changed = copy.deepcopy(self.plan)
            changed["steps"][-1]["value"] = value
            self.rejected(changed)

    def test_non_json_and_oversized_inputs_have_structured_errors(self):
        for value in (None, [], {"unexpected": object()}, {"large": "x" * 24577}):
            self.rejected(value)
        circular = {}
        circular["self"] = circular
        self.rejected(circular)

    def test_no_reflection_eval_or_extra_fields(self):
        for mutation in ({"op": "eval", "code": "return true"},
                         {"property": "health.hediffSet.Clear()"}, {"method": "SetExpectedResult"}):
            changed = copy.deepcopy(self.plan)
            changed["steps"][-1].update(mutation)
            self.rejected(changed)

    def test_registered_pack_keys_are_bounded_and_cannot_select_methods(self):
        plan = {"schema": 1, "intent": "Discover then run a reviewed compiled pack.",
                "steps": [{"id": "discover", "op": "query_tests"},
                          {"id": "test", "op": "registered_test", "key": "kiiro.mechanics"}]}
        normalized = validate_plan(plan)
        self.assertEqual(normalized["steps"][1]["key"], "kiiro.mechanics")
        for key in ("", "System.IO.File.Delete", "../mod", "kiiro.run()", "kiiro.run\n", "x" * 81):
            with self.subTest(key=key):
                bad = copy.deepcopy(plan)
                bad["steps"][1]["key"] = key
                self.rejected(bad)

    def test_ui_display_profile_is_explicit_and_bounded(self):
        self.assertEqual(validate_plan(self.plan)["display_profile"], "simulation")
        self.assertEqual(validate_plan({**self.plan, "display_profile": "ui"})["display_profile"], "ui")
        self.rejected({**self.plan, "display_profile": "user_desktop"})

    def test_fixture_cannot_inject_expected_effect_after_baseline_or_action(self):
        for op in ("measure", "cast", "assert", "wait"):
            changed = copy.deepcopy(self.plan)
            initial = {"measure": changed["steps"][4], "cast": changed["steps"][5],
                       "assert": dict(id="check", op="assert", target="actor", property="spawned", compare="eq", value=1),
                       "wait": dict(id="wait", op="wait", ticks=1)}[op]
            changed["steps"] = changed["steps"][:3] + [initial, dict(id="inject", op="fixture_hediff", actor="target", def_name="RimProbe_FixtureMarker")]
            self.rejected(changed)

    def test_discovery_does_not_close_fixture_phase(self):
        changed = copy.deepcopy(self.plan)
        changed["steps"].insert(0, dict(id="query", op="query_defs", def_type="AbilityDef"))
        changed["steps"].insert(1, dict(id="find", op="find_thing", bind="existing", def_name="Wall"))
        self.assertEqual(len(validate_plan(changed)["steps"]), 9)

    def test_forward_handles_duplicate_ids_and_rebinding_rejected(self):
        for field, value in (("target", "future"), ("actor", "targetItem")):
            changed = copy.deepcopy(self.plan)
            changed["steps"][5][field] = value
            self.rejected(changed)
        changed = copy.deepcopy(self.plan)
        changed["steps"][1]["bind"] = "actor"
        self.rejected(changed)
        changed = copy.deepcopy(self.plan)
        changed["steps"][1]["id"] = changed["steps"][0]["id"]
        self.rejected(changed)

    def test_existing_objects_cannot_be_ordered_as_fixture_pawns(self):
        changed = copy.deepcopy(self.plan)
        changed["steps"][0] = dict(id="find", op="find_thing", bind="actor", def_name="Human")
        self.rejected(changed)

    def test_baseline_must_be_prior_measure_not_object_or_later_value(self):
        for baseline in ("actor", "future", "target"):
            changed = copy.deepcopy(self.plan)
            changed["steps"][-1]["relative_to"] = baseline
            self.rejected(changed)
        changed = copy.deepcopy(self.plan)
        changed["steps"].insert(5, dict(changed["steps"][4], id="duplicate_measure"))
        self.rejected(changed)

    def test_named_and_distance_properties_enforce_parameters(self):
        for mutation in ({"def_name": None}, {"other": "actor"},
                         {"property": "hp"}, {"property": "pawn.distance_to", "def_name": None}):
            changed = copy.deepcopy(self.plan)
            changed["steps"][-1].update(mutation)
            self.rejected(changed)

    def test_wait_assert_hold_and_step_count_are_bounded(self):
        changed = copy.deepcopy(self.plan)
        changed["steps"][-1].update(ticks=100, hold_ticks=101)
        self.rejected(changed)
        changed = copy.deepcopy(self.plan)
        changed["steps"] = [dict(id="step" + str(index), op="wait", ticks=1) for index in range(25)]
        self.rejected(changed)

    def test_ability_job_wait_is_generic_and_requires_fixture_pawn(self):
        changed = copy.deepcopy(self.plan)
        changed["steps"].append(dict(id="cast_finished", op="wait_assert", target="actor",
                                     property="pawn.ability_casting", compare="eq", value=0, ticks=300))
        normalized = validate_plan(changed)
        self.assertEqual(normalized["steps"][-1]["property"], "pawn.ability_casting")
        self.assertIn("pawn.ability_casting", plan_catalog()["numeric_properties"])
        changed["steps"][-1]["def_name"] = "UnexpectedNamedAbility"
        self.rejected(changed)
        changed["steps"][-1].pop("def_name")
        changed["steps"].insert(0, dict(id="found", op="find_thing", bind="existing", def_name="Human"))
        changed["steps"][-1]["target"] = "existing"
        self.rejected(changed)

    def test_runner_rejects_invalid_plan_before_launch(self):
        controller = Mock()
        runner = TestRunner(controller)
        self.rejected({**self.plan, "schema": 2})
        with self.assertRaises(ProbeError):
            runner.run_plan({**self.plan, "schema": 2})
        controller.launch.assert_not_called()

    def test_runner_dispatches_normalized_plan_to_existing_owned_lifecycle(self):
        runner = TestRunner(Mock())
        runner.run_suite = Mock(return_value={"ok": True})
        result = runner.run_plan(self.plan, ["test.mod"])
        self.assertTrue(result["ok"])
        args = runner.run_suite.call_args.args
        self.assertEqual(args[:3], ("Scenario", None, ["test.mod"]))
        self.assertEqual(args[-1], validate_plan(self.plan))

    def test_sdk_publishes_discriminated_operations_and_baselines(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = asyncio.run(create_server(Path(directory), Path(directory) / "runs").list_tools())
        tool = next(tool for tool in tools if tool.name == "rimprobe_run_plan")
        schema = json.dumps(tool.input_schema)
        for name in ("discriminator", "spawn_pawn", "wait_assert", "relative_to", "additionalProperties", "bind_value"):
            self.assertIn(name, schema)
        catalog = plan_catalog()
        self.assertEqual(catalog["maximum_steps"], 24)
        self.assertIn("measure", catalog["discovery"])


if __name__ == "__main__":
    unittest.main()
