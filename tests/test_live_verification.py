import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "verify_live_mcp", Path(__file__).resolve().parents[1] / "scripts/verify-live-mcp.py")
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class LiveVerificationTests(unittest.TestCase):
    def test_failed_final_audit_retracts_completion_and_preserves_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence.json"
            evidence = {"cases": [{"name": "expected_failure", "status": "failed"}], "full_acceptance": False,
                        "artifact_audit": {"ok": True}}
            with patch.object(VERIFIER, "audit_evidence", side_effect=RuntimeError("startup error")):
                with self.assertRaisesRegex(RuntimeError, "startup error"):
                    VERIFIER.finalize_evidence(evidence, output, Path(directory), None)
            stored = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(stored["verification_complete"])
            self.assertEqual(stored["cases"], evidence["cases"])
            self.assertEqual(stored["audit_error"], "startup error")
            self.assertNotIn("artifact_audit", stored)

    def test_completed_evidence_includes_successful_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence.json"
            with patch.object(VERIFIER, "audit_evidence", return_value={"ok": True}) as audit:
                VERIFIER.finalize_evidence({"cases": []}, output, Path(directory), None)
                audit.assert_called_once_with(output, Path(directory), None)
            stored = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(stored["verification_complete"])
            self.assertEqual(stored["artifact_audit"], {"ok": True})

    def test_startup_gate_accepts_clean_coverage(self):
        VERIFIER.validate_startup_evidence(
            {"error_count": 0, "scan_truncated": False, "sources": ["process.log"]})

    def test_startup_gate_rejects_errors_and_missing_coverage_even_for_controls(self):
        clean = {"error_count": 0, "scan_truncated": False, "sources": ["process.log"]}
        for mutation in ({"error_count": 1}, {"error_count": False},
                         {"scan_truncated": True}, {"sources": []}):
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                VERIFIER.validate_startup_evidence({**clean, **mutation})
        with self.assertRaises(RuntimeError):
            VERIFIER.validate_startup_evidence({})


if __name__ == "__main__":
    unittest.main()
