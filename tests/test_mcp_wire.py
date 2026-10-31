import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest

from mcp.types import LATEST_PROTOCOL_VERSION


class McpWireTests(unittest.TestCase):
    def test_independent_jsonrpc_client_without_sdk_client_or_game(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
            with (root / "stderr.log").open("w", encoding="utf-8") as errors:
                process = subprocess.Popen([sys.executable, "-m", "rimprobe", "--game", str(root / "not-installed"),
                                            "--runs", str(root / "runs"), "serve"],
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                                           text=True, encoding="utf-8", env=environment)
                messages = queue.Queue()

                def receive():
                    for line in process.stdout:
                        try:
                            messages.put(json.loads(line))
                        except json.JSONDecodeError:
                            messages.put({"invalid_stdout": line})
                    messages.put({"closed": True})

                thread = threading.Thread(target=receive, daemon=True)
                thread.start()

                def send(method, params, request_id=None):
                    request = {"jsonrpc": "2.0", "method": method, "params": params}
                    if request_id is not None:
                        request["id"] = request_id
                    process.stdin.write(json.dumps(request) + "\n")
                    process.stdin.flush()
                    if request_id is None:
                        return None
                    for attempt in range(20):
                        response = messages.get(timeout=15)
                        self.assertNotIn("invalid_stdout", response)
                        self.assertNotIn("closed", response)
                        if response.get("id") == request_id:
                            return response
                    self.fail("No correlated JSON-RPC response")

                try:
                    initialized = send("initialize", {"protocolVersion": LATEST_PROTOCOL_VERSION, "capabilities": {},
                                                      "clientInfo": {"name": "RimProbe-independent-wire-test", "version": "1"}}, 1)
                    self.assertEqual(initialized["result"]["serverInfo"]["name"], "RimProbe")
                    send("notifications/initialized", {})
                    listed = send("tools/list", {}, 2)["result"]["tools"]
                    self.assertEqual(len(listed), 15)
                    target = next(tool for tool in listed if tool["name"] == "rimprobe_run_contract")
                    encoded = json.dumps(target["inputSchema"])
                    for recipe in ("ability_cast", "item_ingest", "ui_info_card", "building_power"):
                        self.assertIn(recipe, encoded)
                    result = send("tools/call", {"name": "rimprobe_capabilities", "arguments": {}}, 3)
                    capabilities = json.loads(next(item["text"] for item in result["result"]["content"] if item["type"] == "text"))
                    self.assertEqual(capabilities["versions"], ["1.6", "1.7"])
                    self.assertIn("minimal_all_installed_dlc", capabilities["profile_modes"])
                    self.assertIn("minimal_all_installed_dlc", encoded)
                    invalid = send("tools/call", {"name": "rimprobe_run_contract", "arguments": {
                        "contract": {"schema": 1, "recipe": "execute_csharp"}}}, 4)
                    self.assertTrue(invalid["result"]["isError"])
                    generic = next(tool for tool in listed if tool["name"] == "rimprobe_run_plan")
                    self.assertIn("relative_to", json.dumps(generic["inputSchema"]))
                    invalid_plan = send("tools/call", {"name": "rimprobe_run_plan", "arguments": {
                        "plan": {"schema": True, "intent": "invalid schema", "steps": [{"id": "wait", "op": "wait", "ticks": 1}]}}}, 5)
                    self.assertTrue(invalid_plan["result"]["isError"])
                    invalid_alias = send("tools/call", {"name": "rimprobe_run_plan", "arguments": {
                        "plan": {"schema": 1, "intent": "invalid forward alias", "steps": [{"id": "inspect", "op": "inspect", "target": "future"}]}}}, 6)
                    alias_error = json.loads(next(item["text"] for item in invalid_alias["result"]["content"] if item["type"] == "text"))
                    self.assertEqual(alias_error["error"]["code"], "invalid_plan")
                    self.assertFalse((root / "runs").exists())
                finally:
                    process.stdin.close()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    process.stdout.close()
                    thread.join(timeout=2)
                self.assertEqual(process.returncode, 0, (root / "stderr.log").read_text(encoding="utf-8"))
