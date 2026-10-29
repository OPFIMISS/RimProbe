import asyncio
from pathlib import Path
import tempfile
import unittest

from rimprobe.server import create_server


class ServerTests(unittest.TestCase):
    def test_advanced_controls_are_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(Path(directory), Path(directory) / "runs", advanced_tools=True)
            tools = asyncio.run(server.list_tools())
            self.assertEqual(len(tools), 14)
            self.assertIn("rimprobe_get_state", {tool.name for tool in tools})

    def test_sdk_registers_expected_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(Path(directory), Path(directory) / "runs")
            tools = asyncio.run(server.list_tools())
            self.assertEqual({tool.name for tool in tools}, {
                "rimprobe_doctor", "rimprobe_capabilities", "rimprobe_run_suite",
                "rimprobe_get_run", "rimprobe_cancel_run", "rimprobe_get_artifact",
                "rimprobe_inspect_mod", "rimprobe_run_contract", "rimprobe_run_plan",
            })

    def test_contract_tool_exposes_effect_schema_for_small_models(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = asyncio.run(create_server(Path(directory), Path(directory) / "runs").list_tools())
            tool = next(tool for tool in tools if tool.name == "rimprobe_run_contract")
            schema = tool.input_schema
            encoded = str(schema)
            self.assertIn("hediff_added", encoded)
            self.assertIn("ability_cast", encoded)
            self.assertIn("additionalProperties", encoded)



if __name__ == "__main__":
    unittest.main()
