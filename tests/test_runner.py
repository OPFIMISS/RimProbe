import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from rimprobe.errors import ProbeError
from rimprobe.runner import TestRunner, scan_log_files


class RunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        (self.directory / "process.log").write_text("INFO ready\n", encoding="utf-8")
        self.controller = Mock()
        self.controller.session = None
        def launch(**kwargs):
            self.controller.session = object()
            return {"directory": str(self.directory), "session_id": "fixture-session"}
        def stop():
            self.controller.session = None
            return {"ok": True, "owned_process_exit_verified": True}
        self.controller.launch.side_effect = launch
        self.controller.stop.side_effect = stop
        self.controller.status.return_value = {"map_ready": True}
        self.controller.start_building_suite.side_effect = lambda parameters: {"suite": {
            "run_id": parameters["run_id"], "status": "passed", "stage": "construction", "message": "fixture",
            "events": ["bounded detail"], "checks": [{"name": "construction", "status": "passed"}]}}
        self.runner = TestRunner(self.controller)
        self.addCleanup(self.runner.shutdown)

    def completed(self):
        launched = self.runner.run_suite()
        self.runner._thread.join(5)
        self.assertFalse(self.runner._thread.is_alive())
        return self.runner.get_run(launched["run_id"])

    def test_autonomous_run_records_results_and_reclaims_owned_process(self):
        result = self.completed()
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["cleanup_complete"])
        self.assertTrue(result["controller_finished"])
        self.assertTrue(result["owned_process_exit_verified"])
        self.assertEqual(result["cleanup_status"], "succeeded")
        self.assertNotIn("events", result["suite"])
        artifact = self.runner.get_artifact(result["run_id"], "report.json")
        self.assertEqual(artifact["suite"]["events"], ["bounded detail"])
        self.controller.stop.assert_called_once()

    def test_startup_only_does_not_request_quicktest_or_a_functional_suite(self):
        self.controller.status.return_value = {"phase": "entry", "long_event_pending": False, "map_ready": False, "mod_set_matches": True}
        launched = self.runner.run_startup()
        self.runner._thread.join(5)
        result = self.runner.get_run(launched["run_id"])
        self.assertTrue(result["controller_finished"])
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["outcomes"]["functional"], "not_applicable")
        self.assertFalse(self.controller.launch.call_args.kwargs["quicktest"])
        self.controller.start_contract.assert_not_called()
        self.controller.start_building_suite.assert_not_called()
        self.controller.stop.assert_called_once()

    def test_startup_errors_remain_visible_without_functional_claim(self):
        self.controller.status.return_value = {"phase": "entry", "long_event_pending": False, "map_ready": False}
        (self.directory / "process.log").write_text("ERROR Def failed\n")
        launched = self.runner.run_startup()
        self.runner._thread.join(5)
        result = self.runner.get_run(launched["run_id"])
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["outcomes"]["functional"], "not_applicable")
        self.assertEqual(result["startup_error_candidates"], 1)

    def test_stop_faults_end_controller_without_claiming_process_exit_and_allow_retry(self):
        successful_stop = self.controller.stop.side_effect
        for fault in (PermissionError("denied"), subprocess.TimeoutExpired("owned", 10), RuntimeError("unexpected stop failure")):
            with self.subTest(fault=type(fault).__name__):
                self.controller.stop.side_effect = fault
                result = self.completed()
                self.assertTrue(result["controller_finished"])
                self.assertTrue(result["cleanup_complete"])
                self.assertFalse(result["owned_process_exit_verified"])
                self.assertEqual(result["cleanup_status"], "failed")
                self.assertEqual(result["status"], "failed")
                self.assertIn("cleanup_error", result)
                self.assertEqual(self.runner.get_artifact(result["run_id"], "report.json")["cleanup_status"], "failed")
                with self.assertRaises(ProbeError) as raised:
                    self.runner.run_suite()
                self.assertEqual(raised.exception.code, "cleanup_pending")
                self.controller.stop.side_effect = successful_stop
                self.assertTrue(self.runner.cancel_run(result["run_id"])["cleanup_retry_requested"])
                self.runner._thread.join(5)
                recovered = self.runner.get_run(result["run_id"])
                self.assertTrue(recovered["owned_process_exit_verified"])
                self.assertEqual(recovered["cleanup_status"], "succeeded")
                self.assertEqual(recovered["status"], "failed")

    def test_missing_explicit_exit_evidence_never_claims_success(self):
        def stop():
            self.controller.session = None
            return {"ok": True}
        self.controller.stop.side_effect = stop
        result = self.completed()
        self.assertEqual(result["cleanup_status"], "failed")
        self.assertFalse(result["owned_process_exit_verified"])
        self.assertEqual(result["status"], "failed")

    def test_startup_errors_do_not_become_false_pass(self):
        (self.directory / "process.log").write_text("ERROR preexisting installation issue\n", encoding="utf-8")
        result = self.completed()
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["suite"]["status"], "passed")
        self.assertEqual(result["startup_error_candidates"], 1)

    def test_diagnostic_checks_cannot_override_mod_order_mismatch(self):
        original = self.controller.start_building_suite.side_effect
        self.controller.start_building_suite.side_effect = lambda parameters: {
            **original(parameters), "mod_set_matches": False}
        result = self.completed()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["suite"]["status"], "passed")
        self.assertIn("Diagnostic run only", result["message"])
        self.controller.stop.assert_called_once()

    def test_user_accepted_duplicate_mod_scan_noise_does_not_veto_pass(self):
        (self.directory / "process.log").write_text("ERROR Tried loading mod with the same packageId multiple times: sample.mod. Ignoring the duplicates.\n")
        result = self.completed()
        self.assertEqual(result["status"], "passed")
        startup = self.runner.get_artifact(result["run_id"], "startup.json")
        self.assertEqual(startup["ignored_error_count"], 1)

    def test_contract_uses_different_action_dispatch(self):
        contract = json.loads((Path(__file__).parents[1] / "examples" / "contracts" / "ability-marker.json").read_text())
        self.controller.start_contract.side_effect = self.controller.start_building_suite.side_effect
        launched = self.runner.run_contract(contract)
        self.runner._thread.join(5)
        self.assertEqual(self.runner.get_run(launched["run_id"])["status"], "passed")
        self.controller.start_contract.assert_called_once()
        self.controller.start_building_suite.assert_not_called()

    def test_runtime_errors_veto_passing_recipe(self):
        original = self.controller.start_building_suite.side_effect
        def start(parameters):
            with (self.directory / "process.log").open("a") as stream:
                stream.write("ERROR construction exception\n")
            return original(parameters)
        self.controller.start_building_suite.side_effect = start
        self.assertEqual(self.completed()["status"], "failed")

    def test_red_journal_overflow_prevents_false_pass(self):
        original = self.controller.start_building_suite.side_effect
        def start(parameters):
            result = original(parameters)
            result.update(red_error_sequence=100, red_errors=[])
            return result
        self.controller.start_building_suite.side_effect = start
        result = self.completed()
        self.assertEqual(result["status"], "inconclusive")
        self.assertTrue(self.runner.get_artifact(result["run_id"], "diagnostics.json")["agent_coverage_incomplete"])

    def test_new_red_journal_vetoes_pass_without_file_error(self):
        original = self.controller.start_building_suite.side_effect
        def start(parameters):
            result = original(parameters)
            result.update(red_error_sequence=1, red_errors=[{"sequence": 1, "text": "fixture new red"}])
            return result
        self.controller.start_building_suite.side_effect = start
        self.assertEqual(self.completed()["status"], "failed")

    def test_new_red_is_retained_after_disappearing_from_latest_snapshot(self):
        original = self.controller.start_building_suite.side_effect
        final = None
        def start(parameters):
            nonlocal final
            final = original(parameters)
            final.update(red_error_sequence=1, red_errors=[])
            return {"suite": {**final["suite"], "status": "running"}, "red_error_sequence": 1,
                    "red_errors": [{"sequence": 1, "text": "earlier action error"}]}
        self.controller.start_building_suite.side_effect = start
        self.controller.status.side_effect = lambda: final or {"map_ready": True}
        self.assertEqual(self.completed()["status"], "failed")

    def test_log_read_failure_does_not_skip_process_cleanup(self):
        self.controller.logs.side_effect = OSError("fixture log access failure")
        result = self.completed()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["cleanup_status"], "succeeded")
        self.assertTrue(result["owned_process_exit_verified"])
        self.assertIn("collection_error", result)
        self.assertNotIn("cleanup_error", result)
        self.controller.stop.assert_called_once()

    def test_late_foreground_violation_vetoes_result(self):
        def stop():
            self.controller.session = None
            return {"ok": True, "owned_process_exit_verified": True, "background": {"foreground_violations": [{"code": "fixture"}]}}
        self.controller.stop.side_effect = stop
        self.assertEqual(self.completed()["status"], "failed")

    def test_missing_logs_make_result_inconclusive(self):
        (self.directory / "process.log").unlink()
        self.assertEqual(self.completed()["status"], "inconclusive")

    def test_mod_set_mismatch_prevents_mutations_and_still_stops_worker(self):
        self.controller.status.side_effect = ProbeError("mod_set_mismatch", "fixture drift")
        result = self.completed()
        self.assertEqual(result["status"], "blocked")
        self.controller.start_building_suite.assert_not_called()
        self.controller.stop.assert_called_once()
        startup = json.loads((self.directory / "startup.json").read_text())
        self.assertEqual(startup["sources"], ["process.log"])

    def test_artifact_paths_are_allowlisted(self):
        result = self.completed()
        with self.assertRaises(ProbeError) as raised:
            self.runner.get_artifact(result["run_id"], "../secret")
        self.assertEqual(raised.exception.code, "invalid_artifact")

    def test_cancel_during_startup_never_starts_suite(self):
        self.controller.status.return_value = {"map_ready": False}
        launched = self.runner.run_suite()
        self.runner.cancel_run(launched["run_id"])
        self.runner._thread.join(5)
        self.assertEqual(self.runner.get_run(launched["run_id"])["status"], "cancelled")
        self.controller.start_building_suite.assert_not_called()

    def test_cancelled_agent_report_replaces_stale_running_suite(self):
        original = self.controller.start_building_suite.side_effect
        def start(parameters):
            state = original(parameters)
            self.controller.cancel_suite.return_value = {"suite": {**state["suite"], "status": "cancelled"}}
            self.runner._cancel.set()
            return {"suite": {**state["suite"], "status": "running"}}
        self.controller.start_building_suite.side_effect = start
        result = self.completed()
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["suite"]["status"], "cancelled")
        self.controller.stop.assert_called_once()

    def test_invalid_names_and_budgets_never_launch(self):
        for arguments in ({"def_name": "../x"}, {"stuff_name": "x;execute()"}, {"timeout_seconds": 601}, {"max_ticks": 0}):
            with self.assertRaises(ProbeError):
                self.runner.run_suite(**arguments)
        self.controller.launch.assert_not_called()

    def test_supply_delay_is_forwarded_without_direct_material_injection(self):
        launched = self.runner.run_suite(supply_delay_ticks=180)
        self.runner._thread.join(5)
        self.assertTrue(self.runner.get_run(launched["run_id"])["cleanup_complete"])
        self.assertEqual(self.controller.start_building_suite.call_args.args[0]["supply_delay_ticks"], 180)

    def test_bounded_wait_returns_early_after_complete_cleanup(self):
        original = self.controller.start_building_suite.side_effect
        def start(parameters):
            import time
            time.sleep(0.05)
            return original(parameters)
        self.controller.start_building_suite.side_effect = start
        launched = self.runner.run_suite()
        report = self.runner.get_run(launched["run_id"], wait_seconds=1)
        self.assertTrue(report["cleanup_complete"])
        self.assertEqual(report["status"], "passed")
        self.controller.stop.assert_called_once()

    def test_invalid_wait_does_not_start_game(self):
        for wait in (-1, 16, True, 0.5, "10"):
            with self.assertRaises(ProbeError) as error:
                self.runner.get_run("unknown", wait_seconds=wait)
            self.assertEqual(error.exception.code, "invalid_wait")
        self.controller.launch.assert_not_called()

    def test_log_scan_is_bounded_and_scoped(self):
        (self.directory / "process.log").write_text("WARN old\nERROR known\n", encoding="utf-8")
        startup = scan_log_files(self.directory)
        self.assertEqual(startup["error_count"], 1)
        with (self.directory / "process.log").open("a") as stream:
            stream.write("INFO later\n")
        self.assertEqual(scan_log_files(self.directory, startup["offsets"])["error_count"], 0)

    def test_unsupported_functionality_never_passes(self):
        original = self.controller.start_building_suite.side_effect
        def start(parameters):
            state = original(parameters)
            state["suite"]["status"] = "unsupported"
            return state
        self.controller.start_building_suite.side_effect = start
        self.assertEqual(self.completed()["status"], "unsupported")
