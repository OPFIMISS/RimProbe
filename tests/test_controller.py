import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as xml

from rimprobe.controller import Controller, install_agent, validate_game
from rimprobe.errors import ProbeError


class ControllerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / "Game with spaces"
        self.game.mkdir()
        for name in ("RimWorld.exe", "Assembly-CSharp.dll", "UnityStubs.dll"):
            (self.game / name).write_bytes(b"offline-fixture-not-a-game")
        (self.game / "Version.txt").write_text("1.7.4985 rev1269", encoding="utf-8")
        assemblies = self.game / "Mods" / "RimProbe" / "1.7" / "Assemblies"
        assemblies.mkdir(parents=True)
        (assemblies / "RimProbe.Agent.dll").write_bytes(b"agent-fixture")
        self.controller = Controller(self.game, self.root / "runs")
        self.process = Mock(pid=12345, returncode=0)
        self.process.poll.return_value = None
        self.process.wait.return_value = 0
        self.popen = patch("rimprobe.controller.subprocess.Popen", return_value=self.process).start()
        self.addCleanup(patch.stopall)
        worker = patch("rimprobe.controller.BackgroundWorker").start().return_value
        self.popen = worker.spawn
        self.popen.return_value = self.process
        worker.evidence.return_value = {"foreground_violations": [], "mode": "mock"}

    def launch(self):
        self.controller.launch(profile_mode="minimal")
        return self.controller.session

    def descriptor(self, session, **updates):
        descriptor = {"protocol": 1, "session_id": session.session_id, "pid": self.process.pid, "port": 32123}
        descriptor.update(updates)
        (session.directory / "bridge.json").write_text(json.dumps(descriptor), encoding="utf-8")

    def test_doctor_validates_version(self):
        self.assertEqual(validate_game(self.game)["version"], "1.7.4985 rev1269")
        (self.game / "Version.txt").write_text("1.5.0", encoding="utf-8")
        with self.assertRaises(ProbeError) as raised:
            validate_game(self.game)
        self.assertEqual(raised.exception.code, "unsupported_version")

    def test_launch_isolates_config_and_keeps_token_out_of_manifest(self):
        session = self.launch()
        arguments, options = self.popen.call_args
        self.assertNotIn("shell", options)
        self.assertIn(f"-savedatafolder={session.directory / 'profile'}", arguments[0])
        self.assertIn("-NoFileLog", arguments[0])
        self.assertEqual(options["env"]["RIMPROBE_TOKEN"], session.token)
        manifest = (session.directory / "run.json").read_text(encoding="utf-8")
        self.assertNotIn(session.token, manifest)
        config = xml.parse(session.directory / "profile" / "Config" / "ModsConfig.xml")
        self.assertEqual([item.text for item in config.findall("activeMods/li")],
                         ["brrainz.harmony", "ludeon.rimworld", "rimprobe.agent"])
        self.assertFalse((self.game / "Config").exists())

    def test_ui_uses_audited_larger_disposable_display_profile(self):
        self.controller.launch(profile_mode="minimal", ui_profile=True)
        session = self.controller.session
        prefs = xml.parse(session.directory / "profile/Config/Prefs.xml")
        self.assertEqual(prefs.findtext("screenWidth"), "1600")
        self.assertEqual(prefs.findtext("screenHeight"), "1000")
        self.assertEqual(session.manifest["display_profile"]["purpose"], "ui")
        self.assertFalse((self.game / "Config").exists())

    def test_cannot_launch_over_owned_session(self):
        self.launch()
        with self.assertRaises(ProbeError) as raised:
            self.controller.launch()
        self.assertEqual(raised.exception.code, "session_exists")

    def test_process_exit_is_distinct_from_bridge_not_ready(self):
        self.launch()
        with self.assertRaises(ProbeError) as raised:
            self.controller.status()
        self.assertEqual(raised.exception.code, "bridge_not_ready")
        self.process.poll.return_value = 9
        with self.assertRaises(ProbeError) as raised:
            self.controller.status()
        self.assertEqual(raised.exception.code, "process_exited")

    def test_rejects_endpoint_from_other_process(self):
        session = self.launch()
        self.descriptor(session, pid=99)
        with self.assertRaises(ProbeError) as raised:
            self.controller.status()
        self.assertEqual(raised.exception.code, "bridge_mismatch")

    def test_live_state_uses_authenticated_transport(self):
        session = self.launch()
        self.descriptor(session)
        with patch("rimprobe.controller.request", return_value={"map_ready": True, "game_version": "1.7.4985 rev1269", "loaded_mods": session.manifest["active_mods"]}) as transport:
            self.assertTrue(self.controller.status()["map_ready"])
        transport.assert_called_once_with(32123, session.session_id, session.token, "get_state", timeout=5)

    def test_known_expansions_prevent_automatic_dlc_activation(self):
        about = self.game / "Data" / "Royalty" / "About" / "About.xml"
        about.parent.mkdir(parents=True)
        about.write_text("<ModMetaData><packageId>Ludeon.RimWorld.Royalty</packageId></ModMetaData>", encoding="utf-8")
        session = self.launch()
        config = xml.parse(session.directory / "profile" / "Config" / "ModsConfig.xml")
        self.assertEqual([item.text for item in config.findall("knownExpansions/li")], ["ludeon.rimworld.royalty"])
        self.assertNotIn("ludeon.rimworld.royalty", session.manifest["active_mods"])

    def test_effective_mod_drift_fails_closed_and_preserves_evidence(self):
        session = self.launch()
        self.descriptor(session)
        with patch("rimprobe.controller.request", return_value={"game_version": "1.7.4985", "loaded_mods": [*session.manifest["active_mods"], "unexpected.mod"]}):
            with self.assertRaises(ProbeError) as raised:
                self.controller.status()
        self.assertEqual(raised.exception.code, "mod_set_mismatch")
        self.assertFalse(json.loads((session.directory / "mod-set.json").read_text())["matches"])

    def test_wait_rejects_invalid_timeout(self):
        for timeout in (0, -1, 601, float("nan"), float("inf")):
            with self.assertRaises(ProbeError):
                self.controller.wait_ready(timeout)

    def prepare_16(self):
        (self.game / "Version.txt").write_text("1.6.4871 rev590", encoding="utf-8")
        (self.game / "RimWorldWin64.exe").write_bytes(b"fixture")
        managed = self.game / "RimWorldWin64_Data" / "Managed"
        managed.mkdir(parents=True)
        (managed / "Assembly-CSharp.dll").write_bytes(b"1.6-game-fixture")
        (managed / "UnityEngine.CoreModule.dll").write_bytes(b"unity-fixture")
        assemblies = self.game / "Mods" / "RimProbe" / "1.6" / "Assemblies"
        assemblies.mkdir(parents=True)
        (assemblies / "RimProbe.Agent.dll").write_bytes(b"1.6-agent-fixture")

    def test_16_detection_uses_unity_managed_layout(self):
        self.prepare_16()
        game = validate_game(self.game)
        self.assertEqual(game["mod_version"], "1.6")
        self.assertEqual(game["runtime"], "unity-mono-net472")
        self.assertTrue(game["executable"].endswith("RimWorldWin64.exe"))

    def test_16_launch_uses_unity_logfile_argument(self):
        self.prepare_16()
        session = self.launch()
        arguments = self.popen.call_args.args[0]
        self.assertIn("-logFile", arguments)
        self.assertIn(str(session.directory / "Player.log"), arguments)
        self.assertNotIn("-NoFileLog", arguments)
        self.assertEqual(session.manifest["game"]["mod_version"], "1.6")

    def test_rejects_agent_reporting_other_game_version(self):
        session = self.launch()
        self.descriptor(session)
        with patch("rimprobe.controller.request", return_value={"game_version": "1.6.4871"}):
            with self.assertRaises(ProbeError) as raised:
                self.controller.status()
        self.assertEqual(raised.exception.code, "game_version_mismatch")

    def test_diagnostic_mismatch_records_both_orders_without_changing_profile(self):
        session = self.launch()
        self.descriptor(session)
        actual = ["ludeon.rimworld"]
        response = {"game_version": "1.7.4985", "loaded_mods": actual, "map_ready": True}
        with patch("rimprobe.controller.request", return_value=response):
            with self.assertRaises(ProbeError) as raised:
                self.controller.status()
            self.assertEqual(raised.exception.code, "mod_set_mismatch")
            self.controller.diagnostic_mod_mismatch = True
            self.assertFalse(self.controller.status()["mod_set_matches"])
        audit = json.loads((session.directory / "mod-set.json").read_text())
        self.assertEqual(audit["effective"], actual)
        self.assertEqual(audit["requested"], session.manifest["active_mods"])
        self.assertFalse(audit["matches"])

    def test_wait_timeout_is_failure(self):
        self.launch()
        with self.assertRaises(ProbeError) as raised:
            self.controller.wait_ready(0.01)
        self.assertEqual(raised.exception.code, "ready_timeout")

    def test_readiness_distinguishes_agent_from_map(self):
        with patch.object(self.controller, "status", return_value={"map_ready": False, "phase": "entry"}):
            self.assertTrue(self.controller.wait_ready(0.1, require_map=False)["ok"])
            with self.assertRaises(ProbeError):
                self.controller.wait_ready(0.01, require_map=True)

    def test_log_tail_is_bounded_and_scoped(self):
        session = self.launch()
        (session.directory / "process.log").write_text("old\nwarning\nlatest\n", encoding="utf-8")
        (self.root / "Player.log").write_text("not-this-session", encoding="utf-8")
        result = self.controller.logs(limit=2)
        self.assertEqual(result["sources"][0]["tail"], ["warning", "latest"])
        self.assertNotIn("not-this-session", json.dumps(result))

    def test_stop_uses_owned_handle(self):
        session = self.launch()
        result = self.controller.stop()
        self.process.terminate.assert_called_once()
        self.assertIsNone(self.controller.session)
        self.assertEqual(result["session_id"], session.session_id)
        self.assertTrue((session.directory / "stop.json").is_file())
        self.assertTrue(result["owned_process_exit_verified"])
        self.assertEqual(result["exit_code"], self.process.wait.return_value)

    def test_stop_cannot_drop_session_after_unverified_wait_or_exit_timeout(self):
        session = self.launch()
        self.process.wait.return_value = None
        with self.assertRaises(ProbeError) as raised:
            self.controller.stop()
        self.assertEqual(raised.exception.code, "process_exit_unverified")
        self.assertIs(self.controller.session, session)
        self.process.wait.side_effect = subprocess.TimeoutExpired("owned", 10)
        with self.assertRaises(subprocess.TimeoutExpired):
            self.controller.stop()
        self.assertIs(self.controller.session, session)

    def test_stop_kills_only_after_termination_timeout(self):
        self.launch()
        self.process.wait.side_effect = [subprocess.TimeoutExpired("owned", 10), 0]
        self.assertTrue(self.controller.stop()["forced"])
        self.process.kill.assert_called_once()

    def test_inherited_source_integrity_is_checked_without_restoring_it(self):
        source = self.root / "player-mods.xml"
        source.write_text("<ModsConfigData><activeMods><li>ludeon.rimworld</li></activeMods></ModsConfigData>")
        self.controller.mods_config = source
        self.controller.launch()
        source.write_text("concurrently changed by player")
        result = self.controller.stop()
        self.assertFalse(result["profile"]["source_unchanged"])
        self.assertEqual(source.read_text(), "concurrently changed by player")

    def test_install_refuses_existing_directory(self):
        source = self.root / "source"
        (source / "About").mkdir(parents=True)
        (source / "1.7" / "Assemblies").mkdir(parents=True)
        (source / "1.7" / "Assemblies" / "RimProbe.Agent.dll").write_bytes(b"agent")
        (source / "About" / "About.xml").write_text(
            "<ModMetaData><packageId>rimprobe.agent</packageId></ModMetaData>", encoding="utf-8")
        with self.assertRaises(ProbeError) as raised:
            install_agent(self.game, source)
        self.assertEqual(raised.exception.code, "install_exists")

    def test_owned_installer_adopts_identical_updates_and_preserves_backup_outside_mod_library(self):
        source = self.root / "agent-source"
        (source / "About").mkdir(parents=True)
        about = "<ModMetaData><packageId>rimprobe.agent</packageId></ModMetaData>"
        (source / "About" / "About.xml").write_text(about, encoding="utf-8")
        assembly = source / "1.7" / "Assemblies" / "RimProbe.Agent.dll"
        assembly.parent.mkdir(parents=True)
        assembly.write_bytes(b"agent-fixture")
        installed = self.game / "Mods" / "RimProbe"
        (installed / "About").mkdir()
        (installed / "About" / "About.xml").write_text(about, encoding="utf-8")
        self.assertEqual(install_agent(self.game, source, True)["action"], "adopted_identical")
        assembly.write_bytes(b"new-version")
        result = install_agent(self.game, source, True)
        self.assertEqual(result["action"], "updated")
        backup = Path(result["backup_path"])
        self.assertNotIn("Mods", backup.relative_to(self.game).parts)
        self.assertEqual((backup / "1.7" / "Assemblies" / "RimProbe.Agent.dll").read_bytes(), b"agent-fixture")
        (installed / "user-file.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(ProbeError) as raised:
            install_agent(self.game, source, True)
        self.assertEqual(raised.exception.code, "modified_install")
        self.assertEqual((installed / "user-file.txt").read_text(), "keep")

    def test_locked_install_is_preserved_and_temporary_staging_is_reclaimed(self):
        source = self.root / "agent-source"
        (source / "About").mkdir(parents=True)
        (source / "About/About.xml").write_text("<ModMetaData><packageId>rimprobe.agent</packageId></ModMetaData>")
        (source / "1.7/Assemblies").mkdir(parents=True)
        (source / "1.7/Assemblies/RimProbe.Agent.dll").write_bytes(b"agent-fixture")
        installed = self.game / "Mods/RimProbe"
        (installed / "About").mkdir()
        (installed / "About/About.xml").write_bytes((source / "About/About.xml").read_bytes())
        install_agent(self.game, source, True)
        before = {path.relative_to(installed): path.read_bytes() for path in installed.rglob("*") if path.is_file()}
        (source / "1.7/Assemblies/RimProbe.Agent.dll").write_bytes(b"new-agent")
        with patch.object(Path, "rename", side_effect=PermissionError("game is using DLL")):
            with self.assertRaises(PermissionError):
                install_agent(self.game, source, True)
        self.assertEqual(before, {path.relative_to(installed): path.read_bytes() for path in installed.rglob("*") if path.is_file()})
        self.assertEqual(list(self.game.glob(".RimProbe-stage-*")), [])


if __name__ == "__main__":
    unittest.main()
