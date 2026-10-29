import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rimprobe.errors import ProbeError
from rimprobe.evidence import audit_evidence


class EvidenceAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.build = self.root / "build"
        agent = self.build / "1.7/Assemblies/RimProbe.Agent.dll"
        agent.parent.mkdir(parents=True)
        agent.write_bytes(b"offline-test-fixture-not-a-game-assembly")
        self.directory = self.root / ("a" * 32)
        self.directory.mkdir()
        self.path = self.root / "regression.json"
        stopped = {"requested_mods": ["ludeon.rimworld", "rimprobe.agent"],
                   "background": {"foreground_samples": 3, "foreground_violations": []}}
        report = {"status": "failed", "suite": {"status": "failed", "checks": []}, "stop": stopped,
                  "session_id": self.directory.name, "profile": {"source_unchanged": True},
                  "loaded_mods": [{"package_id": name} for name in stopped["requested_mods"]]}
        summary = dict(report, cleanup_complete=True, directory=str(self.directory))
        self.evidence = {"verification_complete": True, "player_config_unchanged": True,
                         "player_config_before": {"ModsConfig": "original"}, "player_config_after": {"ModsConfig": "original"},
                         "cases": [{"name": "expected_negative", "checks_validated": True, "report": summary}]}
        self.write("report.json", dict(report, suite=dict(report["suite"], events=["details omitted from compact get_run"])))
        self.write("run.json", {"session_id": self.directory.name, "game": {"mod_version": "1.7"},
                                "agent_sha256": hashlib.sha256(agent.read_bytes()).hexdigest(), "active_mods": stopped["requested_mods"]})
        self.write("stop.json", stopped)
        self.write("startup.json", {"error_count": 0, "scan_truncated": False})
        self.write("diagnostics.json", {"error_count": 0, "agent_new_red_errors": [], "agent_coverage_incomplete": False, "scan_truncated": False})
        self.save()

    def write(self, name, value):
        (self.directory / name).write_text(json.dumps(value), encoding="utf-8")

    def save(self):
        self.path.write_text(json.dumps(self.evidence), encoding="utf-8")

    def test_finished_thread_with_unverified_process_cannot_pass_audit(self):
        summary = self.evidence["cases"][0]["report"]
        summary.update(controller_finished=True, cleanup_status="failed", owned_process_exit_verified=False)
        self.save()
        with self.assertRaises(ProbeError) as raised:
            audit_evidence(self.path, self.build)
        self.assertIn("cleanup was not verified", str(raised.exception))

    def test_new_cleanup_claim_requires_stored_exit_evidence(self):
        summary = self.evidence["cases"][0]["report"]
        summary.update(controller_finished=True, cleanup_status="succeeded", owned_process_exit_verified=True)
        self.save()
        with self.assertRaises(ProbeError) as raised:
            audit_evidence(self.path, self.build)
        self.assertIn("Stored process exit evidence", str(raised.exception))
        report = json.loads((self.directory / "report.json").read_text())
        report.update(cleanup_status="succeeded", owned_process_exit_verified=True)
        stopped = report["stop"]
        stopped.update(owned_process_exit_verified=True, exit_code=0)
        summary["stop"] = stopped
        self.write("report.json", report)
        self.write("stop.json", stopped)
        self.save()
        self.assertTrue(audit_evidence(self.path, self.build)["ok"])

    def test_expected_negative_can_have_valid_evidence_without_becoming_passed(self):
        result = audit_evidence(self.path, self.build)
        self.assertTrue(result["ok"])
        self.assertEqual(result["cases"][0]["status"], "failed")
        self.assertFalse(result["full_acceptance"])

    def test_rejects_runtime_red_even_when_cached_negative_looks_expected(self):
        self.write("diagnostics.json", {"error_count": 0, "agent_new_red_errors": [{"text": "new failure"}], "agent_coverage_incomplete": False, "scan_truncated": False})
        with self.assertRaises(ProbeError):
            audit_evidence(self.path, self.build)

    def test_rejects_incomplete_or_outside_or_repeated_case(self):
        before = copy.deepcopy(self.evidence)
        for mutation in ("incomplete", "outside", "duplicate"):
            self.evidence = copy.deepcopy(before)
            if mutation == "incomplete":
                self.evidence["verification_complete"] = False
            elif mutation == "outside":
                self.evidence["cases"][0]["report"]["directory"] = str(self.root.parent / ("b" * 32))
            else:
                self.evidence["cases"] *= 2
            self.save()
            with self.subTest(mutation=mutation), self.assertRaises(ProbeError):
                audit_evidence(self.path, self.build)

    def test_rejects_selected_build_drift(self):
        (self.build / "1.7/Assemblies/RimProbe.Agent.dll").write_bytes(b"changed")
        with self.assertRaises(ProbeError):
            audit_evidence(self.path, self.build)

    def test_missing_diagnostics_allowed_only_for_explicit_cancelled_result(self):
        (self.directory / "diagnostics.json").unlink()
        with self.assertRaises(ProbeError):
            audit_evidence(self.path, self.build)
        self.evidence["cases"][0]["report"]["status"] = "cancelled"
        report = self.evidence["cases"][0]["report"].copy()
        self.write("report.json", report)
        self.save()
        result = audit_evidence(self.path, self.build)
        self.assertEqual(result["cases"][0]["runtime_diagnostics"], "not collected on cancellation")
