import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpStdioTests(unittest.IsolatedAsyncioTestCase):
    async def verify_version(self, version: str):
        with tempfile.TemporaryDirectory() as temporary:
            game = Path(temporary) / "game"
            game.mkdir()
            (game / "Version.txt").write_text(version + ".0 offline-fixture", encoding="utf-8")
            managed = game if version == "1.7" else game / "RimWorldWin64_Data" / "Managed"
            managed.mkdir(parents=True, exist_ok=True)
            (managed / "Assembly-CSharp.dll").write_bytes(b"offline-fixture")
            (managed / ("UnityStubs.dll" if version == "1.7" else "UnityEngine.CoreModule.dll")).write_bytes(b"fixture")
            (game / ("RimWorld.exe" if version == "1.7" else "RimWorldWin64.exe")).write_bytes(b"not-executable")
            environment = os.environ.copy()
            source = str(Path(__file__).resolve().parents[1] / "src")
            environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "rimprobe", "--game", str(game), "--runs", str(Path(temporary) / "runs"), "serve"],
                env=environment,
            )
            async with stdio_client(parameters) as streams:
                async with ClientSession(*streams, read_timeout_seconds=15) as session:
                    initialized = await session.initialize()
                    self.assertEqual(initialized.server_info.name, "RimProbe")
                    listed = await session.list_tools()
                    self.assertEqual(len(listed.tools), 9)
                    doctor = await session.call_tool("rimprobe_doctor", {})
                    content = json.loads(next(item.text for item in doctor.content if item.type == "text"))
                    self.assertEqual(content["mod_version"], version)
                    result = await session.call_tool("rimprobe_get_run", {"run_id": "unknown"})
                    content = json.loads(next(item.text for item in result.content if item.type == "text"))
                    self.assertFalse(content["ok"])
                    self.assertEqual(content["error"]["code"], "unknown_run")
                    invalid = await session.call_tool("rimprobe_run_contract", {"contract": {"schema": 1, "recipe": "execute_csharp"}})
                    self.assertTrue(invalid.is_error)
            self.assertFalse((Path(temporary) / "runs").exists())

    async def test_stdio_16_without_starting_game(self):
        await self.verify_version("1.6")

    async def test_stdio_17_without_starting_game(self):
        await self.verify_version("1.7")
