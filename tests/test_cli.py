import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CliTests(unittest.TestCase):
    def test_invalid_contract_json_is_structured_and_does_not_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = root / "bad.json"
            contract.write_text("{invalid")
            result = subprocess.run([sys.executable, "-m", "rimprobe", "--game", str(root / "missing-game"),
                                     "--runs", str(root / "runs"), "test-contract", "--contract", str(contract)],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stderr)["error"]["code"], "invalid_json")
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((root / "runs").exists())
