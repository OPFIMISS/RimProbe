import asyncio
import copy
import json
import importlib.util
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock

from rimprobe.baselines import compare_sessions
from rimprobe.errors import ProbeError
from rimprobe.plans import validate_plan
from rimprobe.runner import TestRunner, outcome_layers
from rimprobe.server import create_server


def plan(steps):
    return {"schema": 1, "intent": "Observe real interaction effects", "steps": steps}


class InteractionTests(unittest.TestCase):
    def test_live_matrix_plans_are_valid_and_negative_case_grants_its_actual_ability(self):
        path = Path(__file__).parents[1] / "scripts/verify-interactions.py"
        spec = importlib.util.spec_from_file_location("verify_interactions", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, payload in module.cases():
            with self.subTest(name=name):
                normalized = validate_plan(payload)
                grants = {step["def_name"] for step in normalized["steps"] if step["op"] == "grant_ability"}
                commands = {step["def_name"] for step in normalized["steps"] if step["op"] == "begin_ability"}
                self.assertTrue(commands <= grants)

    def test_choice_aliases_are_separate_and_require_prior_enumeration(self):
        steps = [{"id": "actor", "op": "spawn_pawn", "bind": "actor"},
                 {"id": "discover", "op": "enumerate_choices", "target": "actor", "bind_choice": "landing", "x": 10, "z": 12},
                 {"id": "select", "op": "select_choice", "choice": "landing"}]
        self.assertEqual(validate_plan(plan(steps))["steps"][-1]["choice"], "landing")
        for bad in ("actor", "future"):
            with self.assertRaises(ProbeError):
                validate_plan(plan(steps[:-1] + [dict(steps[-1], choice=bad)]))
        with self.assertRaises(ProbeError):
            validate_plan(plan(steps + [dict(steps[1], id="rebind")]))

    def test_candidate_selectors_are_bounded_and_not_labels_methods_or_indices(self):
        base = {"id": "choices", "op": "enumerate_choices", "x": 10, "z": 12}
        for change in ({"z": None}, {"limit": 9}, {"offset": -1}, {"index": 0}, {"label": "确定"}, {"method": "Activate"}, {"x": True}):
            with self.subTest(change=change), self.assertRaises(ProbeError):
                validate_plan(plan([{**base, **change}]))

    def test_barriers_require_real_actor_when_needed_and_wall_clock_bounds(self):
        fixture = {"id": "actor", "op": "spawn_pawn", "bind": "actor"}
        barrier = {"id": "ready", "op": "wait_until", "condition": "ability_job_finished", "actor": "actor", "cancel_if": "actor_unavailable"}
        self.assertEqual(validate_plan(plan([fixture, barrier]))["steps"][1]["stable_frames"], 3)
        for change in ({"actor": None}, {"stable_frames": 1}, {"timeout_seconds": 0}, {"condition": "IsTargeting"}, {"cancel_if": "run C#"}):
            with self.subTest(change=change), self.assertRaises(ProbeError):
                validate_plan(plan([fixture, {**barrier, **change}]))

    def test_begin_ability_closes_fixture_phase_and_cannot_order_found_pawn(self):
        begin = {"id": "begin", "op": "begin_ability", "actor": "actor", "def_name": "AnyAbility"}
        with self.assertRaises(ProbeError):
            validate_plan(plan([{"id": "found", "op": "find_thing", "bind": "actor", "def_name": "Human"}, begin]))
        with self.assertRaises(ProbeError):
            validate_plan(plan([{"id": "pawn", "op": "spawn_pawn", "bind": "actor"}, begin,
                                {"id": "inject", "op": "fixture_hediff", "actor": "actor", "def_name": "Marker"}]))

    def test_cross_map_observers_are_typed_independent_assertions(self):
        for prop in ("map.id", "map.tile_id", "map.layer_id", "position.x", "position.z", "pawn.job_active"):
            normalized = validate_plan(plan([{"id": "pawn", "op": "spawn_pawn", "bind": "actor"},
                {"id": "before", "op": "measure", "target": "actor", "property": prop, "bind_value": "before"},
                {"id": "check", "op": "wait_assert", "target": "actor", "property": prop, "relative_to": "before", "compare": "eq", "value": 0, "hold_ticks": 5}]))
            self.assertEqual(normalized["steps"][-1]["property"], prop)

    def test_live_operations_reject_missing_or_foreign_runs_before_game_access(self):
        controller = Mock()
        runner = TestRunner(controller)
        with self.assertRaises(ProbeError):
            runner.interact("foreign", "inspect_interaction")
        controller.interact.assert_not_called()
        for query in ({"interaction": "../path"}, {"method": "Apply"}, {"x": 1}, {"limit": True}):
            with self.assertRaises(ProbeError):
                runner.interact("foreign", "enumerate_choices", query)
        with self.assertRaises(ProbeError):
            runner.interact("foreign", "select_choice", {"choice": "a" * 32})

    def test_live_calls_are_bounded_and_evidence_is_kept_out_of_compact_poll(self):
        controller = Mock()
        runner = TestRunner(controller)
        with tempfile.TemporaryDirectory() as directory:
            runner._directory = Path(directory)
            runner._thread = Mock(is_alive=Mock(return_value=True))
            runner._record = {"run_id": "owned", "session_id": "a" * 32, "status": "running", "suite_name": "scenario", "artifacts": ["report.json"],
                "suite": {"status": "running", "steps": [{"status": "passed"}] * 24}}
            controller.interact.return_value = {"interaction": {"kind": "world_target", "handle": "b" * 32}}
            for _ in range(64):
                runner.interact("owned", "inspect_interaction")
            with self.assertRaises(ProbeError) as error:
                runner.interact("owned", "inspect_interaction")
            self.assertEqual(error.exception.code, "interaction_budget")
            compact = runner.get_run("owned")
            self.assertNotIn("interaction_events", compact)
            self.assertNotIn("steps", compact["suite"])
            self.assertEqual(compact["check_counts"]["passed"], 24)
            self.assertEqual(len(runner.get_run("owned", detail=True)["interaction_events"]), 64)
            self.assertGreater(len(json.dumps(runner.get_run("owned", detail=True))), len(json.dumps(compact)) * 2)

    def test_outcomes_preserve_business_pass_and_strict_overall_failure(self):
        layers = outcome_layers({"status": "failed", "suite": {"status": "passed"}, "startup_error_candidates": 3,
                                 "runtime_error_candidates": 0, "cleanup_status": "failed"})
        self.assertEqual(layers["functional"], "passed")
        self.assertEqual(layers["overall"], "failed")
        self.assertEqual(layers["startup"], "error_candidates")
        self.assertEqual(layers["runtime"], "no_candidates_observed")

    def test_installed_sdk_exposes_typed_interaction_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = asyncio.run(create_server(Path(directory), Path(directory)).list_tools())
        tool = next(tool for tool in tools if tool.name == "rimprobe_enumerate_choices")
        encoded = json.dumps(tool.input_schema)
        for key in ("map_id", "thing_id", "interaction", "additionalProperties", "maximum"):
            self.assertIn(key, encoded)


class BaselineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.ids = ["a" * 32, "b" * 32]
        for session_id in self.ids:
            folder = self.root / session_id
            folder.mkdir()
            self.write(session_id, "run.json", {"session_id": session_id, "game": {"version": "1.7", "sha256": "game"},
                "active_mods": ["core", "target"], "agent_sha256": "agent", "display_profile": {"purpose": "simulation"},
                "profile": {"mode": "inherit", "source_sha256": "same"}})
            self.write(session_id, "startup.json", {"sources": ["process.log"], "scan_truncated": False,
                "error_candidates": [{"line": "ERROR shared candidate"}]})

    def write(self, session_id, name, value):
        (self.root / session_id / name).write_text(json.dumps(value), encoding="utf-8")

    def test_independent_shared_candidates_do_not_modify_or_upgrade_outcomes(self):
        before = {path: path.read_bytes() for path in self.root.rglob("*.json")}
        report = compare_sessions(self.root, *self.ids)
        self.assertTrue(report["environment_fields_match"])
        self.assertEqual(len(report["shared_error_candidates"]), 1)
        self.assertFalse(report["outcomes_modified"])
        self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob("*.json")})

    def test_environment_mismatch_and_incomplete_coverage_remain_visible(self):
        manifest = json.loads((self.root / self.ids[1] / "run.json").read_text())
        manifest["active_mods"].reverse()
        self.write(self.ids[1], "run.json", manifest)
        self.write(self.ids[1], "startup.json", {"sources": ["process.log"], "scan_truncated": True,
            "error_candidates": [{"line": "ERROR shared candidate"}, {"line": "ERROR new candidate"}]})
        result = compare_sessions(self.root, *self.ids)
        self.assertFalse(result["environment_fields_match"])
        self.assertFalse(result["coverage_complete"])
        self.assertEqual(len(result["candidate_only_errors"]), 1)

    def test_only_log_clock_prefix_is_normalized_and_launch_mode_is_compared(self):
        for session_id, clock in zip(self.ids, ("12:00:00", "13:11:12")):
            self.write(session_id, "startup.json", {"sources": ["process.log"], "scan_truncated": False,
                "error_candidates": [{"line": clock + " ERROR shared candidate"}]})
        manifest = json.loads((self.root / self.ids[1] / "run.json").read_text())
        manifest["arguments"] = ["game.exe", "-quicktest"]
        self.write(self.ids[1], "run.json", manifest)
        result = compare_sessions(self.root, *self.ids)
        self.assertEqual(len(result["shared_error_candidates"]), 1)
        self.assertIn("quicktest", result["environment_mismatches"])

    def test_same_run_traversal_and_manifest_mismatch_are_rejected(self):
        for left, right in ((self.ids[0], self.ids[0]), ("../outside", self.ids[1])):
            with self.assertRaises(ProbeError):
                compare_sessions(self.root, left, right)
        self.write(self.ids[0], "run.json", {"session_id": self.ids[1]})
        with self.assertRaises(ProbeError):
            compare_sessions(self.root, *self.ids)


if __name__ == "__main__":
    unittest.main()
