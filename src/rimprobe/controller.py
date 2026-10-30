import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import time
import uuid
import xml.etree.ElementTree as xml
from dataclasses import dataclass
from datetime import datetime, timezone

from .errors import ProbeError
from .background import BackgroundWorker, NativeProcess
from .protocol import PROTOCOL_VERSION, request
from .profiles import plan_profile

AGENT_PACKAGE_ID = "rimprobe.agent"
BASE_MODS = ("brrainz.harmony", "ludeon.rimworld", AGENT_PACKAGE_ID)


def installed_expansions(game_path: Path) -> list[str]:
    expansions = []
    for about in sorted((game_path / "Data").glob("*/About/About.xml")):
        try:
            package_id = (xml.parse(about).getroot().findtext("packageId") or "").strip().lower()
        except (OSError, xml.ParseError) as error:
            raise ProbeError("invalid_expansion_metadata", f"{about}: {error}") from error
        if package_id.startswith("ludeon.rimworld."):
            expansions.append(package_id)
    return sorted(set(expansions))


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def validate_game(game_path: Path) -> dict:
    game_path = game_path.resolve()
    if not (game_path / "Version.txt").is_file():
        raise ProbeError("unsupported_install", "Missing Version.txt; provide a complete RimWorld installation.")
    version = (game_path / "Version.txt").read_text(encoding="utf-8-sig").strip()
    if version.startswith("1.6."):
        mod_version = "1.6"
        executable = game_path / "RimWorldWin64.exe"
        managed = game_path / "RimWorldWin64_Data" / "Managed"
        engine = managed / "UnityEngine.CoreModule.dll"
        runtime = "unity-mono-net472"
    elif version.startswith("1.7."):
        mod_version = "1.7"
        executable = game_path / "RimWorld.exe"
        managed = game_path
        engine = managed / "UnityStubs.dll"
        runtime = "waylith-net10"
    else:
        raise ProbeError("unsupported_version", f"Expected RimWorld 1.6 or 1.7; found {version!r}.")
    assembly = managed / "Assembly-CSharp.dll"
    for path in (executable, assembly, engine):
        if not path.is_file():
            raise ProbeError("unsupported_install", f"Missing {path}; a DLL snapshot is not a runnable game installation.")
    return {
        "game_path": str(game_path),
        "version": version,
        "mod_version": mod_version,
        "runtime": runtime,
        "executable": str(executable),
        "assembly_sha256": fingerprint(assembly),
        "engine_assembly_sha256": fingerprint(engine),
    }


def install_agent(game_path: Path, mod_source: Path, update_owned: bool = False) -> dict:
    game = validate_game(game_path)
    mod_source = mod_source.resolve()
    if not (mod_source / game["mod_version"] / "Assemblies" / "RimProbe.Agent.dll").is_file():
        raise ProbeError("agent_not_built", f"Build the {game['mod_version']} Agent before installation.")
    try:
        metadata = xml.parse(mod_source / "About" / "About.xml").getroot()
    except (OSError, xml.ParseError) as error:
        raise ProbeError("invalid_agent", str(error)) from error
    if metadata.findtext("packageId") != AGENT_PACKAGE_ID:
        raise ProbeError("invalid_agent", "Source Mod packageId does not match RimProbe.")
    destination = Path(game["game_path"]) / "Mods" / "RimProbe"
    def inventory(directory):
        files = {}
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise ProbeError("unsafe_install", "Agent directory must not contain symlinks.")
            if path.is_file() and path.name != ".rimprobe-install.json":
                files[path.relative_to(directory).as_posix()] = fingerprint(path)
        return files
    source_files = inventory(mod_source)
    if destination.exists():
        if not update_owned:
            raise ProbeError("install_exists", f"Refusing to overwrite {destination}; use --update-owned for a verified RimProbe installation.")
        ownership = destination / ".rimprobe-install.json"
        current = inventory(destination)
        if not ownership.is_file():
            if current != source_files:
                raise ProbeError("unowned_install", "Existing installation is not identical; refusing to adopt or overwrite it.")
            atomic_json(ownership, {"files": current})
            return {"ok": True, "installed_path": str(destination), "action": "adopted_identical"}
        try:
            recorded = json.loads(ownership.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ProbeError("invalid_install_manifest", str(error)) from error
        if recorded.get("files") != current:
            raise ProbeError("modified_install", "Installed Agent files changed or contain unknown files; refusing update.")
        if current == source_files:
            return {"ok": True, "installed_path": str(destination), "action": "unchanged"}
        staging = Path(game["game_path"]) / (".RimProbe-stage-" + uuid.uuid4().hex)
        backup = Path(game["game_path"]) / "RimProbeBackups" / uuid.uuid4().hex
        backup.parent.mkdir(exist_ok=True)
        shutil.copytree(mod_source, staging)
        atomic_json(staging / ".rimprobe-install.json", {"files": source_files})
        try:
            destination.rename(backup)
        except OSError:
            # This directory was just created by this call and has not been exposed as an install.
            shutil.rmtree(staging)
            raise
        try:
            staging.rename(destination)
        except OSError:
            backup.rename(destination)
            raise
        return {"ok": True, "installed_path": str(destination), "action": "updated", "backup_path": str(backup)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(mod_source, destination)
    atomic_json(destination / ".rimprobe-install.json", {"files": source_files})
    return {"ok": True, "installed_path": str(destination)}


@dataclass
class Session:
    session_id: str
    token: str
    directory: Path
    process: NativeProcess
    manifest: dict
    worker: BackgroundWorker


class Controller:
    def __init__(self, game_path: Path, runs_path: Path, mods_config: Path | None = None, diagnostic_mod_mismatch: bool = False):
        self.game_path = game_path.resolve()
        self.runs_path = runs_path.resolve()
        self.session: Session | None = None
        self.mods_config = mods_config
        self.diagnostic_mod_mismatch = diagnostic_mod_mismatch
        self._lock = threading.RLock()

    def _session(self) -> Session:
        if self.session is None:
            raise ProbeError("no_session", "No game session is owned by this controller.")
        return self.session

    def launch(self, quicktest: bool = True, extra_mods: list[str] | None = None, profile_mode: str = "inherit", ui_profile: bool = False) -> dict:
        with self._lock:
            if self.session is not None:
                raise ProbeError("session_exists", "Stop the previous session before launching another.")
            game = validate_game(self.game_path)
            installed = self.game_path / "Mods" / "RimProbe"
            agent_assembly = installed / game["mod_version"] / "Assemblies" / "RimProbe.Agent.dll"
            if not agent_assembly.is_file():
                raise ProbeError("agent_not_installed", "Install the built Agent into the game's Mods/RimProbe directory.")
            if extra_mods is not None and not isinstance(extra_mods, list):
                raise ProbeError("invalid_mods", "extra_mods must be an ordered list of packageIds.")
            extra_mods = list(extra_mods or [])
            if any(not isinstance(item, str) or not item.strip() for item in extra_mods):
                raise ProbeError("invalid_mods", "Each additional Mod must have a nonempty packageId.")
            profile_plan = plan_profile(profile_mode, extra_mods, self.mods_config)
            mods = profile_plan["requested_mods"]
            session_id = uuid.uuid4().hex
            directory = self.runs_path / session_id
            directory.mkdir(parents=True, exist_ok=False)
            profile = directory / "profile"
            config_directory = profile / "Config"
            config_directory.mkdir(parents=True)
            config = xml.Element("ModsConfigData")
            xml.SubElement(config, "version").text = game["version"].split()[0]
            active = xml.SubElement(config, "activeMods")
            for package_id in mods:
                xml.SubElement(active, "li").text = package_id
            known_expansions = installed_expansions(self.game_path)
            known = xml.SubElement(config, "knownExpansions")
            for package_id in known_expansions:
                xml.SubElement(known, "li").text = package_id
            xml.ElementTree(config).write(config_directory / "ModsConfig.xml", encoding="utf-8", xml_declaration=True)
            preferences = xml.Element("PrefsData")
            for key, value in {"runInBackground": "True", "pauseOnLoad": "False", "fullscreen": "False",
                               "screenWidth": "1600" if ui_profile else "1280", "screenHeight": "1000" if ui_profile else "800", "uiScale": "1", "volumeMaster": "0",
                               "volumeGame": "0", "volumeMusic": "0", "volumeAmbient": "0", "volumeUI": "0"}.items():
                xml.SubElement(preferences, key).text = value
            xml.ElementTree(preferences).write(config_directory / "Prefs.xml", encoding="utf-8", xml_declaration=True)
            arguments = [game["executable"], f"-savedatafolder={profile}"]
            if game["mod_version"] == "1.6":
                arguments.extend(["-logFile", str(directory / "Player.log")])
            else:
                arguments.extend(["-NoFileLog", "-NoCrashDialog"])
            if quicktest:
                arguments.append("-quicktest")
            token = secrets.token_hex(32)
            environment = os.environ.copy()
            environment.update({
                "RIMPROBE_SESSION_DIR": str(directory),
                "RIMPROBE_SESSION_ID": session_id,
                "RIMPROBE_TOKEN": token,
            })
            manifest = {
                "session_id": session_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "game": game,
                "active_mods": mods,
                "profile": profile_plan,
                "known_expansions": known_expansions,
                "agent_sha256": fingerprint(agent_assembly),
                "arguments": arguments,
                "quicktest_is_deterministic": False,
                "diagnostic_mod_mismatch": self.diagnostic_mod_mismatch,
                "display_profile": {"width": 1600 if ui_profile else 1280, "height": 1000 if ui_profile else 800, "ui_scale": 1, "purpose": "ui" if ui_profile else "simulation"},
            }
            atomic_json(directory / "run.json", manifest)
            atomic_json(directory / "profile-plan.json", profile_plan)
            worker = BackgroundWorker(session_id)
            manifest["background"] = worker.evidence()
            process = None
            try:
                with (directory / "process.log").open("wb") as output:
                    process = worker.spawn(arguments, cwd=self.game_path, env=environment, output=output)
            except (OSError, ProbeError) as error:
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
                worker.close()
                atomic_json(directory / "launch-error.json", {"error": str(error)})
                if isinstance(error, ProbeError):
                    raise
                raise ProbeError("launch_failed", str(error)) from error
            manifest["pid"] = process.pid
            self.session = Session(session_id, token, directory, process, manifest, worker)
            atomic_json(directory / "run.json", manifest)
            return {"ok": True, "session_id": session_id, "pid": process.pid, "directory": str(directory)}

    def status(self, timeout: float = 5) -> dict:
        return self._snapshot("get_state", timeout)

    def start_building_suite(self, parameters: dict) -> dict:
        with self._lock:
            state = self.status()
            if not state.get("map_ready"):
                raise ProbeError("map_not_ready", "Wait for a playable map before starting a suite.")
            return self._snapshot("start_building_suite", 5, parameters)

    def cancel_suite(self) -> dict:
        return self._snapshot("cancel_suite", 5)

    def interact(self, command: str, run_id: str, query: dict) -> dict:
        if command not in {"inspect_interaction", "enumerate_choices", "select_choice", "cancel_interaction"}:
            raise ProbeError("unsupported", "Unknown typed interaction command.")
        return self._snapshot(command, 5, {"run_id": run_id, "interaction": query})

    def start_contract(self, parameters: dict) -> dict:
        with self._lock:
            if not self.status().get("map_ready"):
                raise ProbeError("map_not_ready", "Wait for a playable map before starting a contract.")
            return self._snapshot("start_contract", 5, parameters)

    def _snapshot(self, command: str, timeout: float, parameters: dict | None = None) -> dict:
        with self._lock:
            session = self._session()
            if session.worker.evidence()["foreground_violations"]:
                raise ProbeError("background_violation", "Owned test worker appeared in the foreground; stop the session.")
            exit_code = session.process.poll()
            if exit_code is not None:
                raise ProbeError("process_exited", f"Owned game process exited with code {exit_code}; inspect this run's logs.")
            descriptor_path = session.directory / "bridge.json"
            if not descriptor_path.is_file():
                raise ProbeError("bridge_not_ready", "Agent has not published its endpoint yet.")
            try:
                descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
                if not isinstance(descriptor, dict):
                    raise ValueError("Descriptor must be an object.")
                if (
                    descriptor.get("session_id") != session.session_id
                    or descriptor.get("pid") != session.process.pid
                    or descriptor.get("protocol") != PROTOCOL_VERSION
                ):
                    raise ProbeError("bridge_mismatch", "Endpoint belongs to a different process/session/protocol.")
                port = descriptor.get("port")
                if type(port) is not int or not 1 <= port <= 65535:
                    raise ValueError("Invalid endpoint port.")
            except (OSError, UnicodeError, ValueError) as error:
                raise ProbeError("invalid_descriptor", str(error)) from error
            arguments = {} if parameters is None else {"parameters": parameters}
            state = request(port, session.session_id, session.token, command, timeout=timeout, **arguments)
            if not str(state.get("game_version", "")).startswith(session.manifest["game"]["mod_version"] + "."):
                raise ProbeError("game_version_mismatch", "Agent responded with a different or missing game version.")
            atomic_json(session.directory / "state.json", state)
            loaded = state.get("loaded_mods")
            effective = [item.lower() for item in loaded] if isinstance(loaded, list) and all(isinstance(item, str) for item in loaded) else None
            comparison = {"requested": session.manifest["active_mods"], "effective": effective,
                          "matches": effective == session.manifest["active_mods"]}
            atomic_json(session.directory / "mod-set.json", comparison)
            atomic_json(session.directory / "loaded-mods.json", {"session_id": session.session_id,
                        "profile": session.manifest["profile"], "requested": comparison["requested"],
                        "loaded": [{"order": index + 1, "package_id": package_id} for index, package_id in enumerate(effective or [])],
                        "matches": comparison["matches"]})
            state["mod_set_matches"] = comparison["matches"]
            if not comparison["matches"] and not self.diagnostic_mod_mismatch:
                raise ProbeError("mod_set_mismatch", "Loaded Mod order differs from the requested profile; inspect mod-set.json. No functional test may proceed.")
            return state

    def wait_ready(self, timeout: float = 180, require_map: bool = True) -> dict:
        if not math.isfinite(timeout) or not 0 < timeout <= 600:
            raise ProbeError("invalid_timeout", "Timeout must be finite, greater than zero and at most 600 seconds.")
        deadline = time.monotonic() + timeout
        last_error: dict | None = None
        while time.monotonic() < deadline:
            try:
                state = self.status(timeout=min(5, max(0.001, deadline - time.monotonic())))
                if not require_map or state.get("map_ready") is True:
                    return {"ok": True, "state": state}
                last_error = {"code": "map_not_ready", "message": str(state.get("phase"))}
            except ProbeError as error:
                if error.code not in {"bridge_not_ready", "bridge_unreachable", "main_thread_timeout"}:
                    raise
                last_error = error.as_dict()["error"]
            time.sleep(min(0.25, max(0, deadline - time.monotonic())))
        raise ProbeError("ready_timeout", f"Game did not become ready; last observation: {last_error}")

    def logs(self, limit: int = 100) -> dict:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ProbeError("invalid_limit", "Log limit must be between 1 and 500 lines per source.")
        with self._lock:
            session = self._session()
            candidates = [session.directory / "process.log", session.directory / "agent.log", session.directory / "Player.log"]
            profile = session.directory / "profile"
            candidates.extend(profile.rglob("*.log"))
            candidates.extend(profile.rglob("Player*.txt"))
            sources = []
            for path in sorted(set(candidates)):
                if not path.is_file():
                    continue
                with path.open("rb") as source:
                    source.seek(0, 2)
                    size = source.tell()
                    offset = max(0, size - 262144)
                    source.seek(offset)
                    raw = source.read(262144)
                if offset:
                    raw = raw.partition(b"\n")[2]
                lines = raw.decode("utf-8", errors="replace").splitlines()
                sources.append({
                    "path": str(path.relative_to(session.directory)),
                    "tail": lines[-limit:],
                    "scan_truncated": bool(offset),
                })
            result = {"ok": True, "session_id": session.session_id, "sources": sources,
                      "note": "Raw bounded log tails; absence of matching text is not a functional pass."}
            atomic_json(session.directory / "logs.json", result)
            return result

    def stop(self) -> dict:
        with self._lock:
            session = self._session()
            process = session.process
            forced = False
            exit_code = process.poll()
            if exit_code is None:
                process.terminate()
                try:
                    exit_code = process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    forced = True
                    process.kill()
                    exit_code = process.wait(timeout=10)
            if type(exit_code) is not int:
                raise ProbeError("process_exit_unverified", "Owned process wait returned no verified exit code; session retained for controlled cleanup retry.")
            result = {"ok": True, "session_id": session.session_id,
                      "requested_mods": session.manifest["active_mods"], "profile": session.manifest["profile"],
                      "exit_code": exit_code, "forced": forced, "owned_process_exit_verified": True,
                      "background": session.worker.evidence(),
                      "note": "Process termination, not a save-and-quit operation; test profile only."}
            loaded_path = session.directory / "loaded-mods.json"
            result["loaded_mods"] = json.loads(loaded_path.read_text(encoding="utf-8"))["loaded"] if loaded_path.is_file() else None
            session.worker.close()
            profile = result["profile"]
            if profile.get("source"):
                try:
                    source = Path(profile["source"])
                    profile["source_sha256_after"] = hashlib.sha256(source.read_bytes()).hexdigest()
                    profile["source_unchanged"] = profile["source_sha256_after"] == profile["source_sha256"]
                except OSError as error:
                    profile["source_unchanged"] = None
                    profile["integrity_error"] = str(error)
            atomic_json(session.directory / "stop.json", result)
            self.session = None
            return result
