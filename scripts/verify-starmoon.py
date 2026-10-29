import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rimprobe.evidence import audit_evidence


def config_hashes():
    config = Path(os.environ["USERPROFILE"]) / "AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios/Config"
    return {name: hashlib.sha256((config / name).read_bytes()).hexdigest()
            for name in ("ModsConfig.xml", "Prefs.xml") if (config / name).is_file()}


def summarize_case(key, artifact):
    registered = next((step["registered_test"] for step in artifact.get("suite", {}).get("steps", [])
                       if step.get("registered_test")), {})
    checks = registered.get("checks", [])
    failed = [check["name"] for check in checks if not check["passed"]]
    expected = "failed" if key == "negative_control" else "passed"
    matches = (
        artifact.get("status") == expected
        and artifact.get("startup_error_candidates") == 0
        and artifact.get("runtime_error_candidates") == 0
        and bool(checks)
        and (failed == ["deliberately_absent_marker"] if key == "negative_control" else not failed)
        and artifact.get("stop", {}).get("profile", {}).get("source_unchanged") is True
        and artifact.get("stop", {}).get("background", {}).get("foreground_violations") == []
    )
    return {"expected_status": expected, "check_count": len(checks),
            "failed_checks": failed, "matches_expected": bool(matches), "checks_validated": bool(matches)}


async def verify(options):
    options.runs.mkdir(parents=True, exist_ok=True)
    evidence_path = options.runs / f"mcp-starmoon-{time.time_ns()}.json"
    evidence = {"scope": "Actual private-desktop game via MCP; compiled owner-specific tests, not full acceptance.",
                "diagnostic_mod_mismatch": options.diagnostic, "cases": [], "player_config_before": config_hashes(),
                "full_acceptance": False, "verification_complete": False, "checks_validated": False}

    def checkpoint():
        evidence["player_config_after"] = config_hashes()
        evidence["player_config_unchanged"] = evidence["player_config_before"] == evidence["player_config_after"]
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    arguments = ["-m", "rimprobe", "--game", str(options.game), "--runs", str(options.runs), "serve"]
    if options.diagnostic:
        arguments.append("--diagnostic-mod-mismatch")
    print(json.dumps({"evidence": str(evidence_path)}), flush=True)
    checkpoint()
    async with stdio_client(StdioServerParameters(command=sys.executable, args=arguments)) as streams:
        async with ClientSession(*streams, read_timeout_seconds=30) as client:
            await client.initialize()

            async def call(name, arguments):
                response = await client.call_tool(name, arguments)
                result = json.loads(next(part.text for part in response.content if part.type == "text"))
                if response.is_error or result.get("ok") is False:
                    raise RuntimeError(str(result))
                return result

            for key in options.case or ["mechanics", "envelopes", "stay_star", "return_moon", "negative_control"]:
                plan = {"schema": 1, "intent": "Owner StarMoon source-derived real game verification: " + key,
                        "steps": [{"id": "discover", "op": "query_tests"},
                                  {"id": "verify", "op": "registered_test", "key": "kiiro." + key}],
                        "timeout_seconds": 180, "max_ticks": 120000, "display_profile": "ui"}
                started = await call("rimprobe_run_plan", {"plan": plan, "profile_mode": "inherit",
                                     "extra_mods": ["rimprobe.agent", "rimprobe.tests.starmoon"]})
                entry = {"name": key, "key": key, "run_id": started["run_id"]}
                evidence["cases"].append(entry)
                checkpoint()
                deadline = time.monotonic() + 420
                while True:
                    report = await call("rimprobe_get_run", {"run_id": entry["run_id"], "wait_seconds": 10})
                    entry["report"] = report
                    checkpoint()
                    print(json.dumps({"key": key, "status": report["status"], "stage": report.get("stage"),
                                      "cleanup": report["cleanup_complete"]}), flush=True)
                    if report["cleanup_complete"]:
                        break
                    if time.monotonic() >= deadline:
                        await call("rimprobe_cancel_run", {"run_id": entry["run_id"]})
                        raise TimeoutError("Verification exceeded its bounded deadline.")
                entry["artifact"] = await call("rimprobe_get_artifact", {"run_id": entry["run_id"], "name": "report.json"})
                entry.update(summarize_case(key, entry["artifact"]))
                checkpoint()
                if not entry["artifact"].get("suite"):
                    evidence["stopped_early"] = "Startup failed; remaining game-dependent cases were not launched."
                    checkpoint()
                    return
    evidence["verification_complete"] = True
    evidence["checks_validated"] = bool(evidence["cases"]) and all(
        entry.get("matches_expected") for entry in evidence["cases"])
    checkpoint()
    if evidence["checks_validated"]:
        evidence["artifact_audit"] = audit_evidence(
            evidence_path, Path(__file__).resolve().parents[1] / "mod", options.game)
        checkpoint()
    print(json.dumps({"complete": str(evidence_path), "config_unchanged": evidence["player_config_unchanged"],
                      "checks_validated": evidence["checks_validated"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=Path, default=Path("D:/Steam/steamapps/common/RimWorld"))
    parser.add_argument("--runs", type=Path, default=Path("E:/Rimbook/runs/iteration06/starmoon"))
    parser.add_argument("--case", action="append", choices=["mechanics", "envelopes", "stay_star", "return_moon", "negative_control"])
    parser.add_argument("--diagnostic", action="store_true")
    asyncio.run(verify(parser.parse_args()))
