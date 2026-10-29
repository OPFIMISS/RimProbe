import hashlib
import json
from pathlib import Path
import re

from .errors import ProbeError


def _read(path):
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ProbeError("evidence_invalid", "Evidence file exceeds 8 MiB.")
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition, message):
    if not condition:
        raise ProbeError("evidence_invalid", message)


def audit_evidence(evidence_path: Path, agent_root: Path, game_path: Path | None = None) -> dict:
    """Read-only consistency audit, not a signature or independent gameplay proof."""
    evidence_path = evidence_path.resolve()
    try:
        evidence = _read(evidence_path)
        _require(evidence.get("verification_complete") is True, "Regression is incomplete.")
        _require(evidence.get("player_config_unchanged") is True and evidence.get("player_config_before")
                 and evidence["player_config_before"] == evidence.get("player_config_after"), "Player configuration evidence differs or is missing.")
        cases = evidence.get("cases")
        _require(isinstance(cases, list) and 1 <= len(cases) <= 128, "Expected 1..128 regression cases.")
        results = []
        seen = set()
        for case in cases:
            _require(case.get("checks_validated") is True, "Case assertions were not validated.")
            summary = case["report"]
            directory = Path(summary["directory"]).resolve()
            _require(directory.parent == evidence_path.parent and re.fullmatch(r"[0-9a-f]{32}", directory.name)
                     and directory not in seen, "Case directory is duplicated or outside this regression root.")
            seen.add(directory)
            _require(summary.get("cleanup_complete") is True, "Owned worker cleanup was not completed.")
            if "cleanup_status" in summary:
                _require(summary["cleanup_status"] == "succeeded" and summary.get("owned_process_exit_verified") is True,
                         "Worker ended but owned process cleanup was not verified.")
            report = _read(directory / "report.json")
            run = _read(directory / "run.json")
            stopped = _read(directory / "stop.json")
            if "cleanup_status" in summary:
                _require(report.get("cleanup_status") == "succeeded" and report.get("owned_process_exit_verified") is True
                         and stopped.get("owned_process_exit_verified") is True and type(stopped.get("exit_code")) is int,
                         "Stored process exit evidence is missing or inconsistent.")
            startup = _read(directory / "startup.json")
            stored_suite = {key: value for key, value in report["suite"].items() if key != "events"}
            _require(report["status"] == summary["status"] and stored_suite == summary["suite"], "Cached and stored suite results differ.")
            _require(stopped == summary["stop"] and stopped == report["stop"], "Cleanup evidence differs.")
            _require(run["session_id"] == summary["session_id"] == directory.name, "Session identity differs.")
            _require(summary["profile"]["source_unchanged"] is True, "Run profile source changed.")
            loaded = [entry["package_id"] for entry in report["loaded_mods"]]
            _require(loaded == stopped["requested_mods"] == run["active_mods"], "Actual loaded order differs from requested order.")
            background = stopped["background"]
            _require(background["foreground_samples"] > 0 and not background["foreground_violations"], "Missing foreground audit or foreground violation.")
            _require(startup["error_count"] == 0 and startup["scan_truncated"] is False, "Unaccepted startup error or incomplete startup scan.")
            version = run["game"]["mod_version"]
            _require(version in ("1.6", "1.7"), "Unknown game version.")
            built = agent_root / version / "Assemblies/RimProbe.Agent.dll"
            digest = hashlib.sha256(built.read_bytes()).hexdigest()
            _require(run["agent_sha256"] == digest, "Run Agent differs from the explicitly selected build.")
            if game_path is not None:
                installed = game_path / "Mods/RimProbe" / version / "Assemblies/RimProbe.Agent.dll"
                _require(hashlib.sha256(installed.read_bytes()).hexdigest() == digest, "Installed Agent differs from selected build.")
            diagnostics = None
            if (directory / "diagnostics.json").is_file():
                diagnostics = _read(directory / "diagnostics.json")
                _require(diagnostics["error_count"] == 0 and diagnostics["agent_new_red_errors"] == []
                         and diagnostics["agent_coverage_incomplete"] is False and diagnostics["scan_truncated"] is False,
                         "New runtime errors or incomplete diagnostic coverage.")
            else:
                _require(summary["status"] == "cancelled", "Non-cancelled case has no diagnostics.")
            results.append({"name": case["name"], "status": summary["status"], "agent_sha256": digest,
                            "loaded_mods": loaded, "foreground_samples": background["foreground_samples"],
                            "runtime_diagnostics": "checked" if diagnostics is not None else "not collected on cancellation"})
        return {"ok": True, "evidence": str(evidence_path), "cases": results, "player_config_unchanged": True,
                "full_acceptance": False, "scope": "Read-only artifact consistency, selected build hashes and recorded diagnostics; not tamper-proof or an independent rerun."}
    except (KeyError, TypeError, ValueError, OSError) as error:
        raise ProbeError("evidence_invalid", str(error)) from error
