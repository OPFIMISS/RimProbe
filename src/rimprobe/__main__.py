import argparse
import json
from pathlib import Path
import sys
import time

from .controller import Controller, install_agent, validate_game
from .errors import ProbeError
from .profiles import PROFILE_MODES


def main() -> None:
    parser = argparse.ArgumentParser(prog="rimprobe")
    parser.add_argument("--game", required=True, type=Path, help="RimWorld 1.6 or 1.7 installation directory")
    parser.add_argument("--runs", type=Path, default=Path("runs"))
    parser.add_argument("--mods-config", type=Path, help="Read-only source ModsConfig; otherwise inherit the normal player profile.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    install = commands.add_parser("install-agent")
    install.add_argument("--mod-source", type=Path, required=True)
    install.add_argument("--update-owned", action="store_true")
    serve = commands.add_parser("serve")
    serve.add_argument("--advanced-tools", action="store_true")
    serve.add_argument("--diagnostic-mod-mismatch", action="store_true", help="Collect diagnostic checks despite a load-order mismatch; overall result remains blocked.")
    building = commands.add_parser("test-building")
    building.add_argument("--def-name", default="Wall")
    building.add_argument("--stuff-name")
    building.add_argument("--extra-mod", action="append", default=[])
    building.add_argument("--timeout", type=int, default=180)
    building.add_argument("--max-ticks", type=int, default=60000)
    building.add_argument("--supply-delay-ticks", type=int, default=0)
    building.add_argument("--profile-mode", choices=PROFILE_MODES, default="inherit")
    contract = commands.add_parser("test-contract")
    contract.add_argument("--contract", type=Path, required=True)
    contract.add_argument("--extra-mod", action="append", default=[])
    contract.add_argument("--profile-mode", choices=PROFILE_MODES, default="inherit")
    inspection = commands.add_parser("inspect-mod")
    inspection.add_argument("--mod-path", required=True)
    inspection.add_argument("--version", choices=["1.6", "1.7"], default="1.7")
    smoke = commands.add_parser("smoke")
    smoke.add_argument("--timeout", type=float, default=180)
    smoke.add_argument("--extra-mod", action="append", default=[])
    smoke.add_argument("--profile-mode", choices=PROFILE_MODES, default="inherit")
    arguments = parser.parse_args()
    try:
        if arguments.command == "serve":
            from .server import create_server
            create_server(arguments.game, arguments.runs, arguments.advanced_tools, arguments.mods_config, arguments.diagnostic_mod_mismatch).run(transport="stdio")
            return
        if arguments.command == "inspect-mod":
            from .inspection import inspect_mod
            print(json.dumps(inspect_mod(arguments.mod_path, arguments.version), ensure_ascii=False, indent=2))
            return
        if arguments.command in {"test-building", "test-contract"}:
            from .runner import TestRunner
            runner = TestRunner(Controller(arguments.game, arguments.runs, arguments.mods_config))
            try:
                if arguments.command == "test-contract":
                    if arguments.contract.stat().st_size > 24576:
                        raise ProbeError("invalid_contract", "Contract exceeds 24 KiB.")
                    payload = json.loads(arguments.contract.read_text(encoding="utf-8-sig"))
                    launched = runner.run_contract(payload, arguments.extra_mod, arguments.profile_mode)
                else:
                    launched = runner.run_suite(arguments.def_name, arguments.stuff_name, arguments.extra_mod,
                                               arguments.timeout, arguments.max_ticks, arguments.profile_mode, supply_delay_ticks=arguments.supply_delay_ticks)
                while True:
                    result = runner.get_run(launched["run_id"])
                    if result["cleanup_complete"]:
                        break
                    time.sleep(1)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                if result["status"] != "passed":
                    sys.exit(1)
                return
            finally:
                runner.shutdown()
        if arguments.command == "doctor":
            result = validate_game(arguments.game)
        elif arguments.command == "install-agent":
            result = install_agent(arguments.game, arguments.mod_source, arguments.update_owned)
        else:
            controller = Controller(arguments.game, arguments.runs, arguments.mods_config)
            try:
                launched = controller.launch(extra_mods=arguments.extra_mod, profile_mode=arguments.profile_mode)
                state = controller.wait_ready(arguments.timeout)
                result = {"ok": True, "launch": launched, "readiness": state, "logs": controller.logs()}
            except ProbeError as error:
                result = error.as_dict()
                if controller.session is not None:
                    result["logs"] = controller.logs()
            finally:
                if controller.session is not None:
                    stopped = controller.stop()
                    if "result" in locals():
                        result["stop"] = stopped
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("ok") is False:
            sys.exit(1)
    except json.JSONDecodeError as error:
        print(json.dumps(ProbeError("invalid_json", str(error)).as_dict(), ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except ProbeError as error:
        print(json.dumps(error.as_dict(), ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except OSError as error:
        print(json.dumps(ProbeError("filesystem_error", str(error)).as_dict(), ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
