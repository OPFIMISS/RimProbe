import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


SPEC = importlib.util.spec_from_file_location(
    "verify_concurrent", Path(__file__).resolve().parents[1] / "scripts/verify-concurrent-mcp.py")
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class ConcurrentVerificationTests(unittest.TestCase):
    def test_process_audit_does_not_treat_own_live_process_as_query_failure(self):
        with patch.object(VERIFIER.subprocess, "run", return_value=Mock(returncode=0, stdout='[{"Id":123,"Started":"fixture"}]')) as query:
            self.assertEqual(VERIFIER.player_processes(), [{"Id": 123, "Started": "fixture"}])
            command = query.call_args.args[0][-1]
            self.assertIn("exit 0", command)
            self.assertNotIn("Stop-Process", command)
        with patch.object(VERIFIER.subprocess, "run", return_value=Mock(returncode=1, stdout='')):
            with self.assertRaises(RuntimeError):
                VERIFIER.player_processes()

    def test_endpoint_audit_requires_session_pid_protocol_and_valid_port(self):
        with tempfile.TemporaryDirectory() as temporary:
            launch = {"session_id": "owned-a", "pid": 123, "directory": temporary}
            valid = {"session_id": "owned-a", "pid": 123, "protocol": 1, "port": 32123}
            path = Path(temporary) / "bridge.json"
            path.write_text(json.dumps(valid), encoding="utf-8")
            self.assertEqual(VERIFIER.owned_endpoint(launch), valid)
            for update in ({"session_id": "foreign-b"}, {"pid": 456}, {"protocol": 2}, {"port": 0}, {"port": True}, {"port": 65536}):
                path.write_text(json.dumps(valid | update), encoding="utf-8")
                with self.subTest(update=update), self.assertRaises(RuntimeError):
                    VERIFIER.owned_endpoint(launch)
