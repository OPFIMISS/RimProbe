"""Explicit live MCP regression. Requires the optional InteractionFixtures mod deployment."""
import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def config_hashes():
    root = Path(os.environ["USERPROFILE"]) / "AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios/Config"
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() if (root / name).is_file() else None
            for name in ("ModsConfig.xml", "Prefs.xml")}


def cases():
    first = json.loads((ROOT / "examples/plans/interaction-landing.json").read_text())
    second = json.loads(json.dumps(first).replace("RimProbe_LandingA", "RimProbe_LandingB").replace("RimProbe_LandingMarkerA", "RimProbe_LandingMarkerB"))
    second["steps"][11:11] = [
        {"id": "menu_choice", "op": "enumerate_choices", "target": "actor", "bind_choice": "menu"},
        {"id": "choose_menu", "op": "select_choice", "choice": "menu"},
        {"id": "map_ready", "op": "wait_until", "condition": "interaction_ready"}]
    negative = copy.deepcopy(second)
    negative["steps"] = second["steps"][:6] + [
        {"id": "command", "op": "begin_ability", "actor": "actor", "def_name": "RimProbe_LandingB"},
        {"id": "world_ready", "op": "wait_until", "condition": "interaction_ready"},
        {"id": "world_user", "op": "wait_until", "condition": "interaction_closed", "timeout_seconds": 60},
        {"id": "menu_ready", "op": "wait_until", "condition": "interaction_ready"},
        {"id": "menu_user", "op": "wait_until", "condition": "interaction_closed", "timeout_seconds": 60},
        {"id": "map_ready", "op": "wait_until", "condition": "interaction_ready"},
        {"id": "map_user", "op": "wait_until", "condition": "interaction_closed", "timeout_seconds": 60},
        {"id": "unchanged_marker", "op": "assert", "target": "actor", "property": "pawn.hediff_count", "def_name": "RimProbe_LandingMarkerB", "compare": "eq", "value": 0}
    ] + first["steps"][14:16]  # Ambient idle wandering is not an effect of cancelling a picker.
    timeout = {"schema": 1, "intent": "Deliberate missing interaction readiness must time out without a functional pass.",
        "steps": [{"id": "actor", "op": "spawn_pawn", "bind": "actor"},
                  {"id": "missing", "op": "wait_until", "condition": "interaction_ready", "timeout_seconds": 1}]}
    return [("landing_a", first), ("landing_b_menu", second), ("rejection_stale_cancel", negative), ("readiness_timeout", timeout)]


async def verify(args):
    before = config_hashes()
    args.runs.mkdir(parents=True, exist_ok=True)
    output = args.runs / ("interaction-validation-" + str(time.time_ns()) + ".json")
    evidence = {"verification_complete": False, "cases": [], "scope": "Two owned fixture AbilityDefs; not arbitrary Mod, cross-map transfer or UI hit-test acceptance.", "player_config_before": before}
    def save():
        evidence["player_config_after"] = config_hashes()
        evidence["player_config_unchanged"] = before == evidence["player_config_after"]
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    params = StdioServerParameters(command=sys.executable, args=["-m", "rimprobe", "--game", str(args.game), "--runs", str(args.runs), "serve"], env=env)
    print(json.dumps({"evidence": str(output)}), flush=True)
    try:
        async with stdio_client(params) as streams:
            async with ClientSession(*streams, read_timeout_seconds=20) as client:
                await client.initialize()
                async def call(name, data, reject=False):
                    response = await client.call_tool(name, data)
                    result = json.loads(next(item.text for item in response.content if item.type == "text"))
                    if reject:
                        assert result.get("ok") is False, result
                        assert result.get("error", {}).get("code") == "blocked", result
                        return result
                    if response.is_error or result.get("ok") is False:
                        raise RuntimeError(str(result))
                    return result

                for name, plan in [("startup_only", None), *cases()]:
                    if args.only and name not in args.only:
                        continue
                    case = {"name": name, "verified": False, "live_negative_checks": []}
                    evidence["cases"].append(case)
                    save()
                    extra = ["rimprobe.fixture.interactions"]
                    launched = await call("rimprobe_run_startup" if plan is None else "rimprobe_run_plan", {"extra_mods": extra, **({"plan": plan} if plan else {})})
                    run_id = launched["run_id"]
                    completed_stages, previous, previous_choice = set(), None, None
                    deadline = time.monotonic() + 400
                    while True:
                        state = await call("rimprobe_get_run", {"run_id": run_id, "wait_seconds": 1})
                        case["state"] = state
                        stage = state["stage"]
                        if stage != previous:
                            print(json.dumps({"case": name, "stage": stage}), flush=True)
                            previous = stage
                        if state["controller_finished"]:
                            break
                        if time.monotonic() > deadline:
                            await call("rimprobe_cancel_run", {"run_id": run_id})
                            raise RuntimeError("Live regression deadline exhausted")
                        if name != "rejection_stale_cancel" or stage in completed_stages or stage.split(":")[0] not in {"world_user", "menu_user", "map_user"}:
                            continue
                        interaction = await call("rimprobe_inspect_interaction", {"run_id": run_id})
                        if not interaction["ready"]:
                            continue
                        detail = await call("rimprobe_get_run", {"run_id": run_id, "detail": True})
                        actor = detail["suite"]["steps"][0]["snapshot"]
                        handle = interaction["handle"]
                        query = {"interaction": handle}
                        if stage.startswith("world_user"):
                            query["map_id"] = actor["map_id"]
                        elif stage.startswith("map_user"):
                            query.update(x=9999, z=9999)
                        choices = (await call("rimprobe_enumerate_choices", {"run_id": run_id, "query": query}))["choices"]
                        if stage.startswith("map_user"):
                            assert choices and not choices[0]["available"]
                            case["live_negative_checks"].append(await call("rimprobe_select_choice", {"run_id": run_id, "interaction": handle, "choice": choices[0]["handle"]}, reject=True))
                            if previous_choice:
                                case["live_negative_checks"].append(await call("rimprobe_select_choice", {"run_id": run_id, **previous_choice}, reject=True))
                            await call("rimprobe_cancel_interaction", {"run_id": run_id, "interaction": handle})
                        else:
                            if stage.startswith("menu_user"):
                                disabled = next(choice for choice in choices if not choice["available"])
                                case["live_negative_checks"].append(await call("rimprobe_select_choice", {"run_id": run_id, "interaction": handle, "choice": disabled["handle"]}, reject=True))
                            selected = next(choice for choice in choices if choice["available"])
                            previous_choice = {"interaction": handle, "choice": selected["handle"]}
                            await call("rimprobe_select_choice", {"run_id": run_id, **previous_choice})
                        completed_stages.add(stage)
                    case["report"] = await call("rimprobe_get_artifact", {"run_id": run_id, "name": "report.json"})
                    for key, artifact in (("startup", "startup.json"), ("loaded_mods", "loaded-mods.json"), ("stop", "stop.json")):
                        try:
                            case[key] = await call("rimprobe_get_artifact", {"run_id": run_id, "name": artifact})
                        except RuntimeError as error:
                            case.setdefault("artifact_errors", {})[artifact] = str(error)[:1000]
                    save()
                    assert not case.get("artifact_errors"), case.get("artifact_errors")
                    assert state["cleanup_status"] == "succeeded" and state["owned_process_exit_verified"], state
                    if name == "startup_only":
                        assert case["report"]["suite"]["status"] == "not_applicable"
                    else:
                        expected = "inconclusive" if name == "readiness_timeout" else "passed"
                        assert case["report"]["suite"]["status"] == expected, case["report"]["suite"]
                        if name == "rejection_stale_cancel":
                            assert len(case["live_negative_checks"]) == 3
                    case["verified"] = True
                    case["clean_overall_pass"] = state["status"] == "passed"
                    save()
        evidence["verification_complete"] = True
    finally:
        save()
    assert evidence["player_config_unchanged"], "Player configuration changed; retained evidence, no overwrite attempted."
    print(json.dumps({"evidence": str(output), "cases": [{"name": case["name"], "verified": case["verified"], "overall": case["state"]["status"]} for case in evidence["cases"]]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--execute-live", action="store_true")
    arguments = parser.parse_args()
    if not arguments.execute_live:
        parser.error("Pass --execute-live to launch owned test games.")
    asyncio.run(verify(arguments))
