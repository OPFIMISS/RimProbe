import copy
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "verify_starmoon", Path(__file__).resolve().parents[1] / "scripts/verify-starmoon.py")
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class StarMoonVerificationTests(unittest.TestCase):
    def artifact(self, status="passed", checks=None):
        return {"status": status, "startup_error_candidates": 0, "runtime_error_candidates": 0,
                "suite": {"steps": [{"registered_test": {"checks": checks if checks is not None else [
                    {"name": "actual_effect", "passed": True}]}}]},
                "stop": {"profile": {"source_unchanged": True},
                         "background": {"foreground_violations": []}}}

    def test_positive_case_requires_actual_checks(self):
        self.assertTrue(VERIFIER.summarize_case("mechanics", self.artifact())["matches_expected"])
        self.assertFalse(VERIFIER.summarize_case("mechanics", self.artifact(checks=[]))["matches_expected"])

    def test_negative_case_requires_exact_deliberately_missing_effect(self):
        artifact = self.artifact("failed", [{"name": "deliberately_absent_marker", "passed": False}])
        self.assertTrue(VERIFIER.summarize_case("negative_control", artifact)["matches_expected"])
        artifact["suite"]["steps"][0]["registered_test"]["checks"].append(
            {"name": "unexpected_failure", "passed": False})
        self.assertFalse(VERIFIER.summarize_case("negative_control", artifact)["matches_expected"])

    def test_negative_case_does_not_accept_false_pass(self):
        self.assertFalse(VERIFIER.summarize_case("negative_control", self.artifact())["matches_expected"])

    def test_errors_config_drift_and_focus_violation_reject_validation(self):
        original = self.artifact()
        mutations = [("startup_error_candidates", 1), ("runtime_error_candidates", 1)]
        for field, value in mutations:
            artifact = copy.deepcopy(original)
            artifact[field] = value
            self.assertFalse(VERIFIER.summarize_case("mechanics", artifact)["matches_expected"])
        artifact = copy.deepcopy(original)
        artifact["stop"]["profile"]["source_unchanged"] = False
        self.assertFalse(VERIFIER.summarize_case("mechanics", artifact)["matches_expected"])
        artifact = copy.deepcopy(original)
        artifact["stop"]["background"]["foreground_violations"] = [{"code": "worker_in_foreground"}]
        self.assertFalse(VERIFIER.summarize_case("mechanics", artifact)["matches_expected"])

    def test_missing_cleanup_evidence_rejects_validation(self):
        artifact = self.artifact()
        del artifact["stop"]
        self.assertFalse(VERIFIER.summarize_case("mechanics", artifact)["matches_expected"])
