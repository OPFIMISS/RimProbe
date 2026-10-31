"""Verify two independent MCP-owned instances; never attach to an existing player game.

Records private evidence; requires an installed Agent. Uses only fixed diagnostic OS queries,
typed MCP operations and an optional explicitly installed registered test pack.
"""
import argparse
import asyncio
from contextlib import AsyncExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def player_processes():
    result = subprocess.run([
        "powershell", "-NoProfile", "-Command",
        "$probeProcesses = @(Get-Process -Name RimWorld,RimWorldWin64 -ErrorAction SilentlyContinue | "
        "Select-Object Id,@{Name='Started';Expression={$_.StartTime.ToUniversalTime().ToString('o')}}); "
        "ConvertTo-Json -InputObject $probeProcesses -Compress; exit 0"
    ], capture_output=True, text=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError("Process audit failed")
    value = json.loads(result.stdout.strip()) if result.stdout.strip() else []
    return value if isinstance(value, list) else [value]


def player_hashes():
    config = Path(os.environ["USERPROFILE"]) / "AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios/Config"
    return {name: hashlib.sha256((config / name).read_bytes()).hexdigest()
            for name in ("ModsConfig.xml", "Prefs.xml") if (config / name).is_file()}


def owned_endpoint(launch):
    descriptor = json.loads((Path(launch["directory"]) / "bridge.json").read_text(encoding="utf-8"))
    if descriptor.get("session_id") != launch["session_id"] or descriptor.get("pid") != launch["pid"]:
        raise RuntimeError("Owned endpoint identity changed")
    if descriptor.get("protocol") != 1 or type(descriptor.get("port")) is not int or not 1 <= descriptor["port"] <= 65535:
        raise RuntimeError("Invalid owned endpoint descriptor")
    return descriptor


async def verify(args):
    args.runs.mkdir(parents=True, exist_ok=True)
    output = args.runs / ("concurrent-" + str(time.time_ns()) + ".json")
    evidence = {"scope": "Two MCP-owned 1.6/1.7-capable controllers, all installed DLC; only the installed version is executed.",
                "player_processes_before": player_processes(), "player_config_before": player_hashes(),
                "full_acceptance": False, "completed": False}

    def save():
        evidence["player_processes_after"] = player_processes()
        evidence["player_config_after"] = player_hashes()
        evidence["original_processes_still_running"] = all(
            item in evidence["player_processes_after"] for item in evidence["player_processes_before"])
        evidence["normal_config_unchanged"] = evidence["player_config_before"] == evidence["player_config_after"]
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    async def call(client, name, arguments=None):
        response = await client.call_tool(name, arguments or {})
        result = json.loads(next(p.text for p in response.content if p.type == "text"))
        if response.is_error or result.get("ok") is False:
            raise RuntimeError(str(result))
        return result

    print(json.dumps({"private_evidence": str(output)}), flush=True)
    save()
    try:
        async with AsyncExitStack() as stack:
            async def connect(name, advanced=False):
                params = StdioServerParameters(command=sys.executable, args=[
                    "-m", "rimprobe", "--game", str(args.game), "--runs", str(args.runs / name),
                    "serve", *(["--advanced-tools"] if advanced else [])])
                streams = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(*streams, read_timeout_seconds=45))
                await session.initialize()
                return session

            a = await connect("A", advanced=True)
            b = await connect("B")
            owned_a = False
            try:
                evidence["A_launch"] = await call(a, "rimprobe_launch", {
                    "quicktest": False, "profile_mode": "minimal_all_installed_dlc"})
                owned_a = True
                save()
                deadline = time.monotonic() + 240
                while True:
                    response = await a.call_tool("rimprobe_get_state", {})
                    state = json.loads(next(p.text for p in response.content if p.type == "text"))
                    error = state.get("error", {}).get("code")
                    if error and error not in {"bridge_not_ready", "bridge_unreachable", "main_thread_timeout"}:
                        raise RuntimeError(str(state))
                    if not error and state.get("phase") == "entry" and state.get("long_event_pending") is False:
                        evidence["A_ready"] = state
                        break
                    if time.monotonic() >= deadline:
                        raise TimeoutError("A startup readiness timeout")
                    await asyncio.sleep(2)
                print("A ready; starting independent B", flush=True)
                def a_identity():
                    return owned_endpoint(evidence["A_launch"])

                evidence["A_endpoint_before"] = a_identity()
                save()

                async def finish(run_id, field):
                    deadline = time.monotonic() + 420
                    previous = None
                    while True:
                        progress = await call(b, "rimprobe_get_run", {"run_id": run_id, "wait_seconds": 10})
                        evidence[field] = progress
                        save()
                        current = (progress["stage"], progress["status"], progress["cleanup_status"])
                        if current != previous:
                            print(json.dumps({"case": field, "stage": current[0], "status": current[1], "cleanup": current[2]}), flush=True)
                            previous = current
                        if progress["controller_finished"]:
                            if progress["cleanup_status"] != "succeeded" or not progress["owned_process_exit_verified"]:
                                raise RuntimeError("B cleanup not verified")
                            return progress
                        if time.monotonic() >= deadline:
                            raise TimeoutError("B run exceeded audit deadline")

                # Cancel a newly launched owned run: the retained A must still respond.
                cancelled = await call(b, "rimprobe_run_startup", {"profile_mode": "minimal_all_installed_dlc"})
                await call(b, "rimprobe_cancel_run", {"run_id": cancelled["run_id"]})
                await finish(cancelled["run_id"], "B_cancelled")
                evidence["A_after_B_cancel"] = await call(a, "rimprobe_get_state")
                evidence["A_endpoint_after_B_cancel"] = a_identity()
                if args.registered_test:
                    request = {"profile_mode": "minimal_all_installed_dlc", "extra_mods": args.extra_mod,
                               "plan": {"schema": 1, "intent": "Concurrent isolated target-mod verification",
                                        "steps": [{"id": "verify", "op": "registered_test", "key": args.registered_test}],
                                        "max_ticks": 120000, "timeout_seconds": 180, "display_profile": "ui"}}
                    started = await call(b, "rimprobe_run_plan", request)
                else:
                    started = await call(b, "rimprobe_run_suite", {"profile_mode": "minimal_all_installed_dlc",
                                         "extra_mods": args.extra_mod, "def_name": "Wall", "stuff_name": "WoodLog"})
                evidence["B_launch"] = started
                result = await finish(started["run_id"], "B_test")
                evidence["B_report"] = await call(b, "rimprobe_get_artifact", {"run_id": started["run_id"], "name": "report.json"})
                evidence["B_loaded_mods"] = await call(b, "rimprobe_get_artifact", {"run_id": started["run_id"], "name": "loaded-mods.json"})
                evidence["A_after_B_test"] = await call(a, "rimprobe_get_state")
                evidence["A_endpoint_after_B_test"] = a_identity()
                for key in ("A_endpoint_after_B_cancel", "A_endpoint_after_B_test"):
                    if evidence[key] != evidence["A_endpoint_before"]:
                        raise RuntimeError("A identity changed")
                evidence["B_endpoint"] = json.loads((Path(result["directory"]) / "bridge.json").read_text(encoding="utf-8"))
                for key in ("session_id", "pid", "port"):
                    if evidence["B_endpoint"][key] == evidence["A_endpoint_before"][key]:
                        raise RuntimeError("Independent instances share endpoint identity")
                if not evidence["B_loaded_mods"]["matches"]:
                    raise RuntimeError("B actual load order differs")
                evidence["completed"] = True
                evidence["full_acceptance"] = result["status"] == "passed"
            finally:
                if owned_a:
                    evidence["A_stop"] = await call(a, "rimprobe_stop")
    except Exception as error:
        evidence["failure"] = str(error)[:2000]
        evidence["completed"] = False
        raise
    finally:
        save()
    evidence["isolation_verified"] = (evidence["completed"] and evidence["normal_config_unchanged"]
                                      and evidence["original_processes_still_running"]
                                      and evidence.get("A_stop", {}).get("owned_process_exit_verified") is True)
    evidence["full_acceptance"] &= evidence["isolation_verified"]
    save()
    print(json.dumps({"completed": evidence["completed"], "full_acceptance": evidence["full_acceptance"],
                      "normal_config_unchanged": evidence["normal_config_unchanged"], "private_evidence": str(output)}), flush=True)
    return 0 if evidence["isolation_verified"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--extra-mod", action="append", default=[])
    parser.add_argument("--registered-test", help="Explicitly installed trusted test-pack key; otherwise test a vanilla Wall")
    arguments = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(asyncio.run(verify(arguments)))
