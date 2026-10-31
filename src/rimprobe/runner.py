import copy
import json
from pathlib import Path
import re
import threading
import time
import uuid

from .controller import Controller, atomic_json
from .errors import ProbeError
from .contracts import validate_contract
from .plans import validate_plan, plan_catalog, InteractionQueryInput


def capabilities() -> dict:
    return {
        "plans": plan_catalog(),
        "interaction_protocol": "Four typed live tools cooperate only with an active scenario explicitly yielding at wait_until interaction_closed; opaque handles, 64 live calls/run. See docs/interactions.md.",
        "startup_only": "rimprobe_run_startup loads to the main menu without quicktest; functional=not_applicable. Deferred resources still need a feature test.",
        "protocol": 1, "versions": ["1.6", "1.7"], "background": "Windows private desktop, no desktop input",
        "suites": [{"name": "building_construction", "arguments": ["def_name", "stuff_name", "extra_mods", "supply_delay_ticks"],
                    "steps": ["startup log scan", "normal placement", "blueprint", "real hauling", "real construction"],
                    "function_adapters": {"Wall": "structural assertions only"}},
                   {"name": "building_power", "entry": "run_contract", "steps": ["normal placement, hauling and construction", "settle actual Comp ticks", "sample real output and network"],
                    "assertions": ["power_output_at_least", "power_net_registered"], "scope": "Generation output only; no fuel provision, power consumer or production assertions"},
                   {"name": "ability_cast", "entry": "run_contract", "steps": ["generate fixture Pawns", "grant AbilityDef", "normal cast job", "assert declared observable effect deltas"],
                    "assertions": ["hediff_added", "hediff_removed", "injury_increased", "cooldown_started", "stunned", "downed"]},
                   {"name": "item_ingest", "entry": "run_contract", "steps": ["generate fixture Pawn", "normal Ingest job", "observe exact item consumption", "assert source-derived effects"],
                    "assertions": ["item_consumed", "nutrition_increased", "hediff_added", "hediff_removed"]},
                   {"name": "ui_info_card", "entry": "run_contract", "assertions": ["window_opened", "window_drawn", "window_in_bounds", "window_closed"],
                    "scope": "Real information-card Stats repaint; not pixel correctness or input hit-testing"}],
        "profile": "inherit enabled Mods/DLC/order by default; only the disposable copy receives additions; loaded-mods.json audits actual order",
        "profile_modes": {"inherit": "Default: preserve enabled player Mods/DLC and relative order; read-only source.",
                          "minimal": "Harmony + Core + Agent + explicit extra_mods; no DLC automatically enabled.",
                          "minimal_all_installed_dlc": "Independent test instance: Harmony + Core + all installed DLC + Agent + explicit extra_mods. Does not read the player's Mod list. Missing Agent precedes added test packs; extra_mods must include required dependencies in order."},
        "process_isolation": "Never attach to or stop a player instance. Each Controller owns one independent game process, private desktop, profile and authenticated endpoint. Separate MCP servers may coexist; cancellation stops only that server's owned run. Not a resource/performance isolation guarantee.",
        "outcomes": ["passed", "failed", "blocked", "unsupported", "inconclusive", "cancelled"],
        "workflow": "inspect_mod + actual source + capabilities.plans -> run_plan or recipe -> get_run(wait_seconds=10) until controller_finished; require cleanup_status=succeeded and owned_process_exit_verified=true. cleanup_complete is a legacy attempt-finished alias. If cleanup failed with a retained owned session, cancel_run retries cleanup; query evidence with get_artifact.",
        "limitations": ["1.6 live game not verified", "Semantic interactions are not UI pixels/input/hit-testing", "quicktest world is not deterministic",
                        "World choices enumerate existing WorldObjects/MapParents, not arbitrary tiles; source/verb Targeter chains, Caravan, bills and custom frameworks remain unsupported", "Read-only baseline comparison never attributes or suppresses errors; complete Mod/asset provenance is missing", "Observable stable-frame readiness does not prove renderer rebuild completion"],
    }


def scan_log_files(directory: Path, start_offsets: dict | None = None) -> dict:
    sources = []
    offsets = {}
    errors = []
    ignored = []
    warnings = []
    truncated = False
    for name in ("process.log", "Player.log", "agent.log"):
        path = directory / name
        if not path.is_file():
            continue
        start = (start_offsets or {}).get(name, 0)
        size = path.stat().st_size
        offsets[name] = size
        if start > size:
            truncated = True
            start = 0
        if size - start > 2097152:
            truncated = True
            start = size - 2097152
        with path.open("rb") as source:
            source.seek(start)
            raw = source.read(2097152)
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if re.search(r"\bERROR\b|\b(?:[A-Za-z]+Exception):|Failed to find|Could not resolve cross-reference", line):
                entry = {"source": name, "line": line[:1200],
                         "context": [entry[:500] for entry in lines[max(0, index - 1):index + 8]]}
                if re.search(r"Tried loading mod with the same packageId multiple times:", line):
                    entry["rule"] = "user_accepted_duplicate_package_id"
                    ignored.append(entry)
                else:
                    errors.append(entry)
            elif re.search(r"(?:^|\s)WARN(?:ING)?(?:\s|:)", line, re.IGNORECASE):
                warnings.append({"source": name, "line": line[:500]})
        sources.append(name)
    return {"error_candidates": errors[:40], "error_count": len(errors), "warning_count": len(warnings),
            "ignored_errors": ignored[:40], "ignored_error_count": len(ignored), "total_error_count": len(errors) + len(ignored),
            "warning_examples": warnings[:5], "scan_truncated": truncated, "offsets": offsets, "sources": sources,
            "policy": "Only duplicate-packageId scan noise is accepted; other startup errors and new action errors remain visible.",
            "attribution": "Unattributed log candidates, not proof of target Mod fault; no-errors does not prove correctness."}


def outcome_layers(record: dict) -> dict:
    def log_status(key):
        count = record.get(key)
        return "not_observed" if count is None else "error_candidates" if count else "no_candidates_observed"
    return {"functional": record.get("suite", {}).get("status", "not_observed"),
            "startup": log_status("startup_error_candidates"), "runtime": log_status("runtime_error_candidates"),
            "cleanup": record.get("cleanup_status", "pending"), "overall": record["status"],
            "note": "Independent dimensions; no-candidates is not proof of correctness. Overall remains strict."}


class TestRunner:
    def __init__(self, controller: Controller):
        self.controller = controller
        self._lock = threading.RLock()
        self._thread = None
        self._cancel = threading.Event()
        self._record = None
        self._directory = None

    def run_suite(self, def_name: str = "Wall", stuff_name: str | None = None,
                  extra_mods: list[str] | None = None, timeout_seconds: int = 180, max_ticks: int = 60000,
                  profile_mode: str = "inherit", contract: dict | None = None, supply_delay_ticks: int = 0) -> dict:
        if not isinstance(def_name, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,128}", def_name):
            raise ProbeError("invalid_def", "def_name must be a bounded Def identifier.")
        if stuff_name is not None and (not isinstance(stuff_name, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,128}", stuff_name)):
            raise ProbeError("invalid_stuff", "stuff_name must be a bounded Def identifier.")
        if type(timeout_seconds) is not int or not 5 <= timeout_seconds <= 600 or type(max_ticks) is not int or not 60 <= max_ticks <= 120000:
            raise ProbeError("invalid_budget", "timeout_seconds: 5..600; max_ticks: 60..120000.")
        with self._lock:
            if type(supply_delay_ticks) is not int or not 0 <= supply_delay_ticks <= 3600 or supply_delay_ticks >= max_ticks:
                raise ProbeError("invalid_supply_delay", "supply_delay_ticks must be 0..3600 and less than max_ticks.")
            if self._thread is not None and self._thread.is_alive():
                raise ProbeError("run_active", "Wait for or cancel the current test run.")
            if self.controller.session is not None:
                raise ProbeError("cleanup_pending", "Previous owned session remains; retry cleanup with cancel_run before starting another run.")
            launch_args = {"extra_mods": extra_mods, "profile_mode": profile_mode,
                           "ui_profile": contract is not None and (contract["recipe"] == "ui_info_card" or contract.get("display_profile") == "ui")}
            if contract is not None and contract["recipe"] == "startup":
                launch_args["quicktest"] = False
            launched = self.controller.launch(**launch_args)
            run_id = uuid.uuid4().hex
            self._directory = Path(launched["directory"])
            self._cancel = threading.Event()
            self._record = {"run_id": run_id, "session_id": launched["session_id"], "status": "running", "stage": "startup",
                            "cleanup_status": "pending", "owned_process_exit_verified": False,
                            "suite_name": contract["recipe"] if contract else "building_construction", "def_name": def_name, "stuff_name": stuff_name,
                            "profile_mode": profile_mode, "directory": str(self._directory),
                            "artifacts": ["report.json", "startup.json", "diagnostics.json", "stop.json", "mod-set.json", "logs.json", "loaded-mods.json", "profile-plan.json", "contract.json"]}
            self._save()
            parameters = {"run_id": run_id, "def_name": def_name, "stuff_name": stuff_name,
                          "timeout_seconds": timeout_seconds, "max_ticks": max_ticks, "supply_delay_ticks": supply_delay_ticks}
            if contract is not None:
                parameters["contract"] = contract
                atomic_json(self._directory / "contract.json", contract)
            self._thread = threading.Thread(target=self._execute, args=(parameters,), name="RimProbe.Suite", daemon=True)
            self._thread.start()
            return {"ok": True, "run_id": run_id, "status": "running", "poll_after_seconds": 2}

    def run_plan(self, plan: dict, extra_mods: list[str] | None = None, profile_mode: str = "inherit") -> dict:
        validated = validate_plan(plan)
        return self.run_suite("Scenario", None, extra_mods, validated["timeout_seconds"], validated["max_ticks"], profile_mode, validated)

    def run_startup(self, extra_mods: list[str] | None = None, profile_mode: str = "inherit", timeout_seconds: int = 180) -> dict:
        return self.run_suite("Startup", None, extra_mods, timeout_seconds, 60, profile_mode,
                              {"recipe": "startup", "timeout_seconds": timeout_seconds, "max_ticks": 60,
                               "scope": "Def/resource initialization and main-menu readiness only; no generated test map or functional pass."})

    def run_contract(self, contract: dict, extra_mods: list[str] | None = None, profile_mode: str = "inherit") -> dict:
        validated = validate_contract(contract)
        return self.run_suite(validated["def_name"], validated["fixture"].get("stuff_name"), extra_mods, validated["timeout_seconds"],
                              validated.get("max_ticks", 6000), profile_mode, validated)

    def _save(self):
        self._record["outcomes"] = outcome_layers(self._record)
        atomic_json(self._directory / "report.json", self._record)

    def _update(self, **values):
        with self._lock:
            self._record.update(values)
            self._save()

    def _execute(self, parameters):
        try:
            startup_only = parameters.get("contract", {}).get("recipe") == "startup"
            deadline = time.monotonic() + (parameters["timeout_seconds"] if startup_only else 180)
            while not self._cancel.is_set():
                try:
                    state = self.controller.status()
                    if state.get("map_ready") or startup_only and state.get("phase") == "entry" and state.get("long_event_pending") is False:
                        break
                except ProbeError as error:
                    if error.code not in {"bridge_not_ready", "bridge_unreachable", "main_thread_timeout"}:
                        raise
                if time.monotonic() >= deadline:
                    raise ProbeError("startup_timeout", "Startup readiness not reached within its budget.")
                self._cancel.wait(0.5)
            if self._cancel.is_set():
                self._update(status="cancelled", stage="startup")
                return
            startup = scan_log_files(self._directory)
            atomic_json(self._directory / "startup.json", startup)
            if startup_only:
                status = "passed" if not startup["error_count"] and not startup["scan_truncated"] and startup["sources"] else "inconclusive"
                if state.get("mod_set_matches") is False:
                    status = "blocked"
                self._update(status=status,
                             stage="completed", startup_error_candidates=startup["error_count"],
                             suite={"status": "not_applicable", "stage": "startup", "scope": "Startup loading only; functional behavior not tested."},
                             message="Startup-only log/Def loading check; no test map requested, no functional conclusion.")
                return
            self._update(stage="construction", startup_error_candidates=startup["error_count"])
            red_checkpoint = state.get("red_error_sequence", 0)
            red_seen = red_checkpoint
            red_entries = {}
            red_incomplete = False
            state = self.controller.start_contract(parameters) if "contract" in parameters else self.controller.start_building_suite(parameters)
            deadline = time.monotonic() + parameters["timeout_seconds"] + 10
            while not self._cancel.is_set():
                sequence = state.get("red_error_sequence", red_seen)
                entries = state.get("red_errors", [])
                observed = {entry["sequence"]: entry for entry in entries if entry.get("sequence", 0) > red_seen}
                red_incomplete |= sequence < red_seen or sequence - red_seen > len(observed)
                red_seen = max(sequence, red_seen)
                for entry_sequence, entry in observed.items():
                    if "Tried loading mod with the same packageId multiple times:" not in entry.get("text", ""):
                        if len(red_entries) < 64:
                            red_entries[entry_sequence] = entry
                        else:
                            red_incomplete = True
                suite = state.get("suite")
                if not isinstance(suite, dict) or suite.get("run_id") != parameters["run_id"]:
                    raise ProbeError("suite_mismatch", "Agent returned no matching suite report.")
                self._update(suite=suite, stage=suite["stage"])
                if suite["status"] != "running":
                    diagnostics = scan_log_files(self._directory, startup["offsets"])
                    new_red = list(red_entries.values())
                    diagnostics["agent_new_red_errors"] = new_red
                    diagnostics["agent_checkpoint"] = red_checkpoint
                    diagnostics["agent_final_sequence"] = state.get("red_error_sequence", red_checkpoint)
                    diagnostics["agent_coverage_incomplete"] = red_incomplete
                    atomic_json(self._directory / "diagnostics.json", diagnostics)
                    outcome = suite["status"]
                    message = suite["message"]
                    if state.get("mod_set_matches") is False:
                        outcome = "blocked"
                        message = "Diagnostic run only: actual Mod/DLC order differs from the requested profile. " + message
                    if diagnostics["error_count"] or new_red:
                        outcome = "failed" if outcome == "passed" else outcome
                        message = "Runtime error candidates detected; inspect diagnostics.json. " + message
                    elif outcome == "passed" and (red_incomplete or startup["error_count"] or startup["scan_truncated"] or diagnostics["scan_truncated"] or not startup["sources"]):
                        outcome = "inconclusive"
                        message = "Recipe checks passed, but startup errors or incomplete log coverage prevent an overall pass. Inspect startup.json."
                    self._update(status=outcome, stage="completed", message=message,
                                 log_coverage="bounded heuristic scan; no baseline attribution",
                                 runtime_error_candidates=diagnostics["error_count"])
                    return
                if time.monotonic() >= deadline:
                    raise ProbeError("suite_timeout", "Controller wall-clock budget exceeded.")
                self._cancel.wait(0.5)
                if not self._cancel.is_set():
                    state = self.controller.status()
            cancelled = self.controller.cancel_suite()
            cancelled_suite = cancelled.get("suite") if isinstance(cancelled, dict) else None
            if isinstance(cancelled_suite, dict) and cancelled_suite.get("run_id") == parameters["run_id"]:
                self._update(suite=cancelled_suite)
            self._update(status="cancelled", stage="completed", message="Cancellation requested; owned worker cleanup follows.")
        except (ProbeError, OSError) as error:
            detail = error.as_dict()["error"] if isinstance(error, ProbeError) else {"code": "filesystem_error", "message": str(error)}
            self._update(status="blocked", stage="error", error=detail)
        except Exception as error:
            self._update(status="failed", stage="error", error={"code": "runner_error", "message": str(error)})
        finally:
            try:
                if self.controller.session is not None:
                    try:
                        startup_path = self._directory / "startup.json"
                        if not startup_path.exists():
                            startup = scan_log_files(self._directory)
                            atomic_json(startup_path, startup)
                            self._update(startup_error_candidates=startup["error_count"])
                        self.controller.logs()
                    except Exception as error:
                        self._update(status="failed", collection_error=str(error)[:2000])
                    finally:
                        self._stop_owned()
            except Exception as error:
                self._update(status="failed", cleanup_error=str(error)[:2000])
                if self._record.get("cleanup_status") != "succeeded":
                    self._update(cleanup_status="failed")

    def _stop_owned(self):
        self._update(cleanup_status="running")
        stopped = self.controller.stop()
        verified = stopped.get("ok") is True and stopped.get("owned_process_exit_verified") is True
        self._update(stop=stopped, loaded_mods=stopped.get("loaded_mods"), profile=stopped.get("profile"),
                     owned_process_exit_verified=verified, cleanup_status="succeeded" if verified else "failed")
        if not verified:
            self._update(status="failed", cleanup_error="Owned process exit was not verified by stop evidence.")
        if stopped.get("background", {}).get("foreground_violations"):
            self._update(status="failed", message="Background isolation violation detected during cleanup.")

    def _retry_cleanup(self):
        try:
            self._stop_owned()
        except Exception as error:
            self._update(status="failed", cleanup_status="failed", cleanup_error=str(error)[:2000])

    def get_run(self, run_id: str, wait_seconds: int = 0, detail: bool = False) -> dict:
        if type(detail) is not bool:
            raise ProbeError("invalid_detail", "detail must be a boolean.")
        if type(wait_seconds) is not int or not 0 <= wait_seconds <= 15:
            raise ProbeError("invalid_wait", "wait_seconds must be an integer 0..15; zero returns immediately.")
        with self._lock:
            if self._record is None or run_id != self._record["run_id"]:
                raise ProbeError("unknown_run", "No matching run owned by this MCP instance.")
            worker = self._thread
        if wait_seconds and worker is not None:
            worker.join(timeout=wait_seconds)
        with self._lock:
            if self._record is None or run_id != self._record["run_id"]:
                raise ProbeError("unknown_run", "No matching run owned by this MCP instance.")
            record = copy.deepcopy(self._record)
            if "suite" in record:
                record["suite"].pop("events", None)
            record["controller_finished"] = self._thread is not None and not self._thread.is_alive()
            record["cleanup_complete"] = record["controller_finished"]
            record["cleanup_complete_semantics"] = "cleanup attempt finished; success requires cleanup_status=succeeded and owned_process_exit_verified=true"
            record["outcomes"] = outcome_layers(record)
            if not detail:
                suite = record.get("suite", {})
                if suite.get("interaction") is not None:
                    record["interaction"] = suite["interaction"]
                steps = suite.get("steps", [])
                checks = suite.get("checks", [])
                record["check_counts"] = {"steps": len(steps), "checks": len(checks),
                    "passed": sum(step.get("status") == "passed" for step in steps) + sum(check.get("status") == "passed" for check in checks)}
                primary = suite.get("primary_failure") or {}
                record["error_summary"] = {"startup_candidates": record.get("startup_error_candidates"), "runtime_candidates": record.get("runtime_error_candidates"),
                    "primary_failure": {key: primary[key] for key in ("type", "message", "step_id", "test_key", "lifecycle_phase", "failure_domain") if key in primary},
                    "cleanup_failure_count": len(suite.get("cleanup_failures", []))}
                for key in ("stop", "profile", "loaded_mods", "interaction_events"):
                    record.pop(key, None)
                if "suite" in record:
                    record["suite"] = {key: suite[key] for key in ("status", "stage", "message", "scope") if key in suite}
                record["detail_available"] = "rimprobe_get_run(detail=true) or rimprobe_get_artifact(report.json)"
            return record

    def cancel_run(self, run_id: str) -> dict:
        with self._lock:
            record = self.get_run(run_id)
            if record["controller_finished"] and self.controller.session is not None:
                self._update(cleanup_status="running")
                self._thread = threading.Thread(target=self._retry_cleanup, name="RimProbe.Cleanup", daemon=True)
                self._thread.start()
                return {"ok": True, "run_id": run_id, "cleanup_retry_requested": True}
            self._cancel.set()
            return {"ok": True, "run_id": run_id, "cancellation_requested": True}

    def get_artifact(self, run_id: str, name: str) -> dict:
        record = self.get_run(run_id)
        if name not in record["artifacts"]:
            raise ProbeError("invalid_artifact", "Select an artifact name returned by get_run; no arbitrary paths.")
        path = self._directory / name
        if not path.is_file():
            raise ProbeError("artifact_not_ready", "Artifact has not been written yet.")
        if path.stat().st_size > 262144:
            raise ProbeError("artifact_too_large", "Artifact exceeds the bounded response size; inspect the local report.")
        return json.loads(path.read_text(encoding="utf-8"))

    def shutdown(self):
        self._cancel.set()
        if self._thread is not None:
            self._thread.join(timeout=20)
        if self.controller.session is not None:
            self.controller.stop()

    def interact(self, run_id: str, command: str, query: dict | None = None) -> dict:
        if command not in {"inspect_interaction", "enumerate_choices", "select_choice", "cancel_interaction"}:
            raise ProbeError("unsupported", "Unknown typed interaction operation.")
        try:
            validated = InteractionQueryInput.model_validate(query or {}).model_dump()
        except ValueError as error:
            raise ProbeError("invalid_interaction", str(error)[:1000]) from error
        if (validated["x"] is None) != (validated["z"] is None):
            raise ProbeError("invalid_interaction", "Both x and z are required for a map cell candidate.")
        if command in {"select_choice", "cancel_interaction"} and validated["interaction"] is None:
            raise ProbeError("invalid_interaction", "Writes require the discovered interaction handle.")
        if command == "select_choice" and validated["choice"] is None:
            raise ProbeError("invalid_interaction", "Selection requires a discovered choice handle.")
        with self._lock:
            record = self.get_run(run_id)
            if record["controller_finished"] or record["status"] != "running" or record["suite_name"] != "scenario":
                raise ProbeError("interaction_unavailable", "An active owned scenario run is required.")
            history = self._record.setdefault("interaction_events", [])
            if len(history) >= 64:
                raise ProbeError("interaction_budget", "Live interaction call budget (64) exhausted; cancel the run.")
            try:
                state = self.controller.interact(command, run_id, validated)
                result = state.get("interaction")
                if not isinstance(result, dict):
                    raise ProbeError("invalid_response", "Agent omitted interaction evidence.")
            except ProbeError as error:
                history.append({"op": command, "error": error.as_dict()["error"]})
                self._save()
                raise
            history.append({"op": command, "result": result})
            self._save()
            return result
