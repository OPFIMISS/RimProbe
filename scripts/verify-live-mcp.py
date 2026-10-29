import argparse
import copy
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


def validate_startup_evidence(startup):
    if (type(startup.get("error_count")) is not int or startup["error_count"] != 0
            or startup.get("scan_truncated") is not False or not startup.get("sources")):
        raise RuntimeError("Startup errors or incomplete startup coverage; this case cannot qualify as a clean regression, including cancellation/negative controls.")


def finalize_evidence(evidence, output, agent_root, game):
    evidence.pop("artifact_audit", None)
    evidence.pop("audit_error", None)
    evidence["verification_complete"] = True
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        evidence["artifact_audit"] = audit_evidence(output, agent_root, game)
    except Exception as error:
        evidence["verification_complete"] = False
        evidence["audit_error"] = str(error)
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


def player_config_hashes():
    root = Path(os.environ["USERPROFILE"]) / "AppData" / "LocalLow" / "Ludeon Studios" / "RimWorld by Ludeon Studios" / "Config"
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() if (root / name).is_file() else None
            for name in ("ModsConfig.xml", "Prefs.xml")}


async def verify(arguments):
    before = player_config_hashes()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "rimprobe", "--game", str(arguments.game),
                                      "--runs", str(arguments.runs), "serve"], env=environment)
    arguments.runs.mkdir(parents=True, exist_ok=True)
    output = arguments.runs / ("mcp-validation-" + str(time.time_ns()) + ".json")
    evidence = {"verification_complete": False, "scope": "Actual game through real MCP stdio; not full product acceptance", "cases": [], "transport": {"tool_calls": 0, "response_text_bytes": 0, "by_tool": {}}}
    def checkpoint():
        evidence["player_config_before"] = before
        evidence["player_config_after"] = player_config_hashes()
        evidence["player_config_unchanged"] = before == evidence["player_config_after"]
        evidence["full_acceptance"] = False
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"evidence_checkpoint": str(output)}), flush=True)
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams, read_timeout_seconds=20) as client:
            initialized = await client.initialize()
            evidence["server"] = initialized.server_info.name
            tools = await client.list_tools()
            evidence["tool_names"] = [tool.name for tool in tools.tools]
            assert len(tools.tools) == 9

            async def call(name, params):
                response = await client.call_tool(name, params)
                stats = evidence["transport"]
                stats["tool_calls"] += 1
                stats["response_text_bytes"] += sum(len(item.text.encode("utf-8")) for item in response.content if item.type == "text")
                stats["by_tool"][name] = stats["by_tool"].get(name, 0) + 1
                result = json.loads(next(item.text for item in response.content if item.type == "text"))
                if response.is_error or result.get("ok") is False:
                    raise RuntimeError(str(result))
                return result

            evidence["capabilities"] = await call("rimprobe_capabilities", {})
            cases = [] if arguments.contracts_only else [("wall_construction", "rimprobe_run_suite", {"def_name": "Wall", "stuff_name": "WoodLog", "timeout_seconds": 120})]
            if arguments.include_negative:
                cases.append(("invalid_material", "rimprobe_run_suite", {"def_name": "Wall", "stuff_name": "MedicineIndustrial", "timeout_seconds": 30}))
            if arguments.include_contracts or arguments.contracts_only:
                root = Path(__file__).resolve().parents[1]
                evidence["inspection"] = await call("rimprobe_inspect_mod", {"mod_path": str(root / "fixtures" / "AbilityContract"), "version": "1.7"})
                contract = json.loads((root / "examples" / "contracts" / "ability-marker.json").read_text(encoding="utf-8"))
                cases.append(("ability_effect", "rimprobe_run_contract", {"contract": contract, "extra_mods": ["rimprobe.fixture.abilities"]}))
                negative = dict(contract, def_name="RimProbe_FixtureNoEffect", intent="Negative control: a real cast with no effect must fail the marker assertion.")
                cases.append(("ability_missing_effect", "rimprobe_run_contract", {"contract": negative, "extra_mods": ["rimprobe.fixture.abilities"]}))
                if arguments.include_cancel:
                    cancelled = dict(contract, observe_ticks=60000, max_ticks=120000, timeout_seconds=120)
                    cases.append(("ability_cancellation", "rimprobe_run_contract", {"contract": cancelled, "extra_mods": ["rimprobe.fixture.abilities"]}))
            if arguments.iteration_three:
                root = Path(__file__).resolve().parents[1]
                cases.append(("wall_supply_recovery", "rimprobe_run_suite", {"def_name": "Wall", "stuff_name": "WoodLog", "timeout_seconds": 120, "supply_delay_ticks": 180}))
                item = json.loads((root / "examples/contracts/item-marker.json").read_text(encoding="utf-8"))
                cases.append(("item_effect", "rimprobe_run_contract", {"contract": item, "extra_mods": ["rimprobe.fixture.abilities"]}))
                negative_item = dict(item, def_name="RimProbe_FixtureMealNoEffect", intent="Negative control: real consumption without marker must fail.")
                cases.append(("item_missing_effect", "rimprobe_run_contract", {"contract": negative_item, "extra_mods": ["rimprobe.fixture.abilities"]}))
                ui = json.loads((root / "examples/contracts/ui-info-card.json").read_text(encoding="utf-8"))
                cases.append(("ui_info_card", "rimprobe_run_contract", {"contract": ui}))
            if arguments.iteration_four:
                root = Path(__file__).resolve().parents[1]
                power = json.loads((root / "examples/contracts/building-power.json").read_text(encoding="utf-8"))
                cases.append(("building_power", "rimprobe_run_contract", {"contract": power, "extra_mods": ["rimprobe.fixture.abilities"]}))
                negative_power = dict(power, def_name="RimProbe_FixturePowerZero", intent="Negative control: real construction with zero output must fail the power threshold.")
                cases.append(("building_power_zero", "rimprobe_run_contract", {"contract": negative_power, "extra_mods": ["rimprobe.fixture.abilities"]}))
                non_power = dict(power, def_name="Wall", fixture={"stuff_name": "WoodLog", "settle_ticks": 60}, intent="A real wall must not be declared a functioning generator after normal construction.")
                cases.append(("building_power_unsupported", "rimprobe_run_contract", {"contract": non_power}))
                if arguments.include_cancel:
                    cancelled_power = dict(power, observe_ticks=60000, max_ticks=120000)
                    cases.append(("building_power_cancellation", "rimprobe_run_contract", {"contract": cancelled_power, "extra_mods": ["rimprobe.fixture.abilities"]}))
            if arguments.iteration_five:
                root = Path(__file__).resolve().parents[1]
                for name in ("ability-marker", "item-marker", "equip-and-move", "build-power", "discovery", "find-and-measure"):
                    plan = json.loads((root / "examples/plans" / (name + ".json")).read_text(encoding="utf-8"))
                    cases.append(("plan_" + name, "rimprobe_run_plan", {"plan": plan, "extra_mods": ["rimprobe.fixture.abilities"]}))
                negative = copy.deepcopy(next(options["plan"] for name, tool, options in cases if name == "plan_ability-marker"))
                for step in negative["steps"]:
                    if step["op"] in ("grant_ability", "cast"):
                        step["def_name"] = "RimProbe_FixtureNoEffect"
                cases.append(("plan_missing_effect", "rimprobe_run_plan", {"plan": negative, "extra_mods": ["rimprobe.fixture.abilities"]}))
                zero = copy.deepcopy(next(options["plan"] for name, tool, options in cases if name == "plan_build-power"))
                zero["steps"][0]["def_name"] = "RimProbe_FixturePowerZero"
                cases.append(("plan_zero_power", "rimprobe_run_plan", {"plan": zero, "extra_mods": ["rimprobe.fixture.abilities"]}))
                if arguments.include_cancel:
                    cancelled = {"schema": 1, "intent": "Cancel a generic Tick wait through normal owned-worker cleanup.",
                                 "steps": [{"id": "hold", "op": "wait", "ticks": 60000}], "max_ticks": 120000, "timeout_seconds": 180}
                    cases.append(("plan_cancellation", "rimprobe_run_plan", {"plan": cancelled}))
            if arguments.iteration_eight:
                root = Path(__file__).resolve().parents[1]
                sequence = json.loads((root / "examples/plans/ability-sequence.json").read_text(encoding="utf-8"))
                cases.append(("plan_ability-sequence", "rimprobe_run_plan", {"plan": sequence, "extra_mods": ["rimprobe.fixture.abilities"]}))
                negative = copy.deepcopy(sequence)
                negative["steps"].append(dict(id="absent", op="wait_assert", target="target",
                                               property="spawned", compare="eq", value=0, ticks=60))
                cases.append(("plan_failure_context", "rimprobe_run_plan", {"plan": negative, "extra_mods": ["rimprobe.fixture.abilities"]}))
                if arguments.include_cancel:
                    cancelled = copy.deepcopy(sequence)
                    cancelled["steps"].append(dict(id="hold", op="wait", ticks=60000))
                    cancelled.update(max_ticks=120000, timeout_seconds=180)
                    cases.append(("plan_context_cancellation", "rimprobe_run_plan", {"plan": cancelled, "extra_mods": ["rimprobe.fixture.abilities"]}))
            if arguments.only:
                cases = [case for case in cases if case[0] in arguments.only]
                if not cases or set(arguments.only) - {case[0] for case in cases}:
                    raise ValueError("--only must name cases enabled by the other selection flags")
            for case_name, tool, options in cases:
                launched = await call(tool, dict(options, profile_mode="inherit"))
                run_id = launched["run_id"]
                deadline = time.monotonic() + 330
                cancellation_sent = False
                while True:
                    report = await call("rimprobe_get_run", {"run_id": run_id, "wait_seconds": arguments.poll_wait})
                    if report["cleanup_complete"]:
                        break
                    cancel_stage = {"ability_cancellation": "cast_and_observe", "building_power_cancellation": "power_observe", "plan_cancellation": "hold:wait", "plan_context_cancellation": "hold:wait"}.get(case_name)
                    if cancel_stage is not None and report.get("suite", {}).get("stage") == cancel_stage and not cancellation_sent:
                        await call("rimprobe_cancel_run", {"run_id": run_id})
                        cancellation_sent = True
                    if time.monotonic() > deadline:
                        await call("rimprobe_cancel_run", {"run_id": run_id})
                        raise RuntimeError("Live verification exceeded its own bound")
                    if arguments.poll_wait == 0:
                        await asyncio.sleep(2)
                artifact = await call("rimprobe_get_artifact", {"run_id": run_id, "name": "report.json"})
                case = {"name": case_name, "report": report, "checks_validated": False}
                evidence["cases"].append(case)
                checkpoint()
                startup = json.loads((Path(report["directory"]) / "startup.json").read_text(encoding="utf-8"))
                validate_startup_evidence(startup)
                assert not report["stop"]["background"]["foreground_violations"]
                assert report["stop"]["background"]["foreground_samples"] > 0
                resources = report["stop"]["background"]["resources"]
                assert resources["available"] and resources["cpu_seconds"] > 0
                assert resources["peak_working_set_bytes"] > 0 and resources["private_bytes"] > 0
                assert not resources["measurement_errors"], str(resources)
                assert report["profile"]["source_unchanged"] is True
                assert [entry["package_id"] for entry in report["loaded_mods"]] == report["stop"]["requested_mods"]
                if case_name.startswith("plan_"):
                    suite = artifact["suite"]
                    assert suite["recipe"] == "scenario", str(suite)
                    if case_name in ("plan_cancellation", "plan_context_cancellation"):
                        assert cancellation_sent and report["status"] == suite["status"] == "cancelled", str(report)
                        if case_name == "plan_context_cancellation":
                            context = suite["steps"][-1]["failure_context"]
                            assert suite["steps"][-1]["id"] == "hold"
                            assert {entry["alias"] for entry in context["objects"]} == {"actor", "target"}
                            assert all("snapshot" in entry and "error" not in entry for entry in context["objects"])
                    else:
                        expected = "inconclusive" if case_name in ("plan_discovery", "plan_find-and-measure") else "failed" if case_name in ("plan_missing_effect", "plan_zero_power", "plan_failure_context") else "passed"
                        assert report["status"] == suite["status"] == expected, str(report)
                        steps = {step["id"]: step for step in suite["steps"]}
                        assert len(steps) == (3 if case_name == "plan_zero_power" else len(options["plan"]["steps"])), str(steps)
                        assert report["runtime_error_candidates"] == 0
                        if case_name in ("plan_ability-sequence", "plan_failure_context"):
                            assert steps["first_cast"]["status"] == steps["second_cast"]["status"] == "requested"
                            assert steps["effect"]["compared_value"] >= 1
                            assert steps["cast_finished"]["value"] == steps["second_finished"]["value"] == 0
                            assert steps["second_cooldown"]["value"] > 0
                            if case_name == "plan_failure_context":
                                failed = steps["absent"]
                                context = failed["failure_context"]
                                assert failed["status"] == "failed" and failed["value"] == 1
                                assert context["condition"]["property"] == "spawned" and context["condition"]["value"] == 0
                                assert context["elapsed_ticks"] >= 60 and context["sampled_hold_ticks"] == 0
                                assert {entry["alias"] for entry in context["objects"]} == {"target", "actor"}
                                assert all(entry["snapshot"]["spawned"] and "error" not in entry for entry in context["objects"])
                        elif case_name in ("plan_ability-marker", "plan_missing_effect"):
                            assert steps["cast"]["status"] == "requested"
                            assert steps["effect"]["status"] == ("failed" if expected == "failed" else "passed")
                            assert steps["effect"]["baseline"] == 0
                            assert steps["effect"]["compared_value"] == (0 if expected == "failed" else 1)
                        elif case_name == "plan_item-marker":
                            assert steps["eat"]["status"] == "requested"
                            assert steps["consumed"]["value"] == 1
                            assert steps["nutrition"]["compared_value"] >= 0.1
                            assert steps["marker"]["compared_value"] >= 1
                        elif case_name == "plan_equip-and-move":
                            assert steps["equip"]["status"] == steps["move"]["status"] == "requested"
                            assert steps["equipped"]["value"] == 1 and steps["arrived"]["value"] <= 1.5
                            assert "Gun_Autopistol" in steps["inspect_after"]["snapshot"]["equipment"]
                        elif case_name == "plan_build-power":
                            construction = steps["build"]["construction"]
                            assert construction["status"] == "passed"
                            assert any(check["name"] == "material_delivery" and check["status"] == "passed" for check in construction["checks"])
                            assert steps["output"]["value"] >= 90 and steps["network"]["value"] == 1
                        elif case_name == "plan_zero_power":
                            assert steps["build"]["construction"]["status"] == "passed"
                            assert steps["output"]["status"] == "failed" and steps["output"]["value"] == 0
                        elif case_name == "plan_find-and-measure":
                            assert steps["find"]["status"] == steps["inspect"]["status"] == steps["baseline"]["status"] == "observed"
                            assert steps["find"]["snapshot"]["thing_id"] == steps["item"]["snapshot"]["thing_id"]
                            assert steps["baseline"]["value"] == steps["inspect"]["snapshot"]["hp"] > 0
                        elif case_name == "plan_discovery":
                            assert steps["abilities"]["total_matches"] >= 2
                            assert "RimProbe_FixtureMark" in [entry["def_name"] for entry in steps["abilities"]["definitions"]]
                            assert all(step["status"] == "observed" for step in steps.values())
                elif case_name in ("wall_construction", "wall_supply_recovery"):
                    suite = artifact["suite"]
                    assert suite["status"] == "passed", str(suite)
                    assert all(check["status"] == "passed" for check in suite["checks"])
                    assert suite["materials"] == [{"def_name": "WoodLog", "observed": 5, "required": 5}]
                    if case_name == "wall_supply_recovery":
                        assert any(check["name"] == "missing_supply_stalled" for check in suite["checks"])
                    assert suite["tick_observed"] > suite["tick_started"]
                    assert report["runtime_error_candidates"] == 0
                    assert report["status"] in ("passed", "inconclusive")
                elif case_name in ("building_power", "building_power_zero"):
                    suite = artifact["suite"]
                    positive = case_name == "building_power"
                    assert report["status"] == ("passed" if positive else "failed"), str(report)
                    checks = {entry["name"]: entry["status"] for entry in suite["checks"]}
                    assert checks["construction"] == checks["material_delivery"] == "passed"
                    assert checks["power_output_at_least"] == ("passed" if positive else "failed")
                    assert checks["power_net_registered"] == "passed"
                    power = suite["power_evidence"]
                    assert power["samples"] >= 2 and power["connected_samples"] == power["samples"]
                    assert power["tick_last"] - power["tick_started"] >= 180
                    assert power["minimum_watts"] == power["maximum_watts"] == (100 if positive else 0)
                    assert report["runtime_error_candidates"] == 0
                elif case_name == "invalid_material":
                    assert report["suite"]["status"] == "blocked"
                    assert not any(check["name"] == "construction" and check["status"] == "passed" for check in report["suite"]["checks"])
                elif case_name == "ability_effect":
                    assert report["status"] == "passed", str(report)
                    assert all(observation["met"] for observation in artifact["suite"]["observations"])
                    assert report["runtime_error_candidates"] == 0
                elif case_name == "ability_missing_effect":
                    assert report["status"] == "failed", str(report)
                    observations = {item["kind"]: item for item in artifact["suite"]["observations"]}
                    assert observations["cooldown_started"]["met"] is True
                    assert observations["hediff_added"]["met"] is False
                    assert report["runtime_error_candidates"] == 0
                elif case_name in ("item_effect", "item_missing_effect"):
                    assert report["status"] == ("passed" if case_name == "item_effect" else "failed"), str(report)
                    observations = {entry["kind"]: entry for entry in artifact["suite"]["observations"]}
                    assert observations["item_consumed"]["met"] is True
                    assert observations["nutrition_increased"]["met"] is True
                    assert observations["hediff_added"]["met"] is (case_name == "item_effect")
                    assert any(check["name"] == "real_ingestion" and check["status"] == "passed" for check in artifact["suite"]["checks"])
                    assert report["runtime_error_candidates"] == 0
                elif case_name == "ui_info_card":
                    assert report["status"] == "passed", str(report)
                    assert {check["name"] for check in artifact["suite"]["checks"]} >= {"window_opened", "window_drawn", "window_in_bounds", "window_closed"}
                    assert all(check["status"] == "passed" for check in artifact["suite"]["checks"])
                    assert report["runtime_error_candidates"] == 0
                elif case_name == "building_power_unsupported":
                    assert report["status"] == "unsupported", str(report)
                    assert any(check["name"] == "construction" and check["status"] == "passed" for check in artifact["suite"]["checks"])
                    assert "power_evidence" not in artifact["suite"]
                    assert report["runtime_error_candidates"] == 0
                elif case_name in ("ability_cancellation", "building_power_cancellation"):
                    assert cancellation_sent and report["status"] == "cancelled", str(report)
                    assert report["suite"]["status"] == "cancelled", str(report["suite"])
                case["checks_validated"] = True
                checkpoint()
                print(json.dumps({"case": case_name, "status": report["status"], "directory": report["directory"]}), flush=True)
    evidence["player_config_before"] = before
    evidence["player_config_after"] = player_config_hashes()
    evidence["player_config_unchanged"] = before == evidence["player_config_after"]
    evidence["full_acceptance"] = False
    assert evidence["player_config_unchanged"], "Default player config changed concurrently; inspect without overwriting it"
    finalize_evidence(evidence, output, Path(__file__).resolve().parents[1] / "mod", arguments.game)
    print(json.dumps({"evidence": str(output), "cases": [{"name": case["name"], "status": case["report"]["status"],
                      "checks_validated": case["checks_validated"]} for case in evidence["cases"]],
                      "player_config_unchanged": evidence["player_config_unchanged"], "full_acceptance": False}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Explicit live MCP validation; launches only owned private-desktop test games.")
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--include-negative", action="store_true")
    parser.add_argument("--iteration-three", action="store_true")
    parser.add_argument("--iteration-four", action="store_true")
    parser.add_argument("--iteration-five", action="store_true")
    parser.add_argument("--iteration-eight", action="store_true")
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--poll-wait", type=int, choices=range(16), default=10)
    parser.add_argument("--include-contracts", action="store_true")
    parser.add_argument("--contracts-only", action="store_true")
    parser.add_argument("--include-cancel", action="store_true")
    parser.add_argument("--execute-live", action="store_true")
    options = parser.parse_args()
    if not options.execute_live:
        parser.error("Pass --execute-live explicitly to launch test games.")
    asyncio.run(verify(options))
