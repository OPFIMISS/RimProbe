import hashlib
import json
import os
from pathlib import Path
import xml.etree.ElementTree as xml


ROOT = Path(__file__).resolve().parents[1]
MOD = Path("D:/Steam/steamapps/common/RimWorld/Mods/绮罗拓展-星月师")
RUNS = ROOT / "runs/iteration06"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    before = json.loads((RUNS / "before.json").read_text(encoding="utf-8-sig"))
    config = Path(os.environ["USERPROFILE"]) / "AppData/LocalLow/Ludeon Studios/RimWorld by Ludeon Studios/Config"
    after_config = {name: digest(config / name) for name in before["player_config"]}
    changed = [{"path": name, "before": value, "after": digest(MOD / name)}
               for name, value in before["files"].items() if digest(MOD / name) != value]
    definitions = []
    for path in sorted((MOD / "1.7/Defs").rglob("*.xml")):
        relative = path.relative_to(MOD / "1.7/Defs")
        xml.parse(path)
        definitions.append({"path": relative.as_posix(), "sha256": digest(path),
                            "identical_to_1_6": digest(path) == digest(MOD / "1.6/Defs" / relative)})
    sessions = []
    for path in sorted(RUNS.rglob("run.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        directory = path.parent
        state = json.loads((directory / "state.json").read_text(encoding="utf-8")) if (directory / "state.json").is_file() else {}
        stop = json.loads((directory / "stop.json").read_text(encoding="utf-8")) if (directory / "stop.json").is_file() else {}
        report = json.loads((directory / "report.json").read_text(encoding="utf-8")) if (directory / "report.json").is_file() else {}
        sessions.append({"directory": str(directory), "session_id": run["session_id"],
                         "game": run["game"]["version"], "requested": run["active_mods"],
                         "loaded": state.get("loaded_mods"), "registered_tests": state.get("registered_tests"),
                         "phase": state.get("phase"), "map_ready": state.get("map_ready"),
                         "quicktest_fallback": state.get("quicktest_fallback"), "report_status": report.get("status"),
                         "error": report.get("error"), "owned_stop_recorded": bool(stop),
                         "foreground": stop.get("background", {}).get("foreground_violations"),
                         "suite": report.get("suite")})
    result = {"scope": "Owner target files and RimProbe-owned evidence only; no third-party Mod source scan.",
              "player_config_before": before["player_config"], "player_config_after": after_config,
              "player_config_unchanged": after_config == before["player_config"], "changed_original_files": changed,
              "defs_1_7": definitions, "defs_count": len(definitions), "all_defs_identical": all(item["identical_to_1_6"] for item in definitions),
              "image_sha256": digest(MOD / "Textures/result_00134_.png"), "sessions": sessions,
              "temporary_test_pack_installed": (MOD.parent / "RimProbeStarMoonTests").exists(),
              "archived_test_pack": str(RUNS / "archived-testpack") if (RUNS / "archived-testpack").is_dir() else None,
              "binaries": {version: {"target": digest(MOD / version / "Assemblies/kiiro_Stars and Moon's.dll"),
                                      "agent": digest(ROOT / "mod" / version / "Assemblies/RimProbe.Agent.dll"),
                                      "test_pack": digest(ROOT / "testpacks/StarMoon/mod" / version / "Assemblies/RimProbe.StarMoon.Tests.dll")}
                           for version in ("1.6", "1.7")}}
    (RUNS / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"audit": str(RUNS / "audit.json"), "player_config_unchanged": result["player_config_unchanged"],
                      "defs": len(definitions), "sessions": len(sessions)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
