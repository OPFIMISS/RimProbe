# RimProbe

> [!IMPORTANT]
> **Project stance: help mod authors work more effectively; oppose fully automated mass production of low-quality AI mods.**
>
> This project helps authors develop, diagnose and validate their work with AI tools. It never replaces human playtesting. **Before publishing, authors must personally enter the real game and test their work in the target version and intended mod environment.** Successful compilation, clean logs or an AI-reported pass cannot replace this step. Do not publish work you have not personally playtested as verified content.
>
> **Respect original creators and obtain authorization first.** This project does not encourage decompiling another creator's mod or uploading or feeding their source code or DLLs to AI without authorization from the creator or relevant rights holder. Such use violates the purpose of this project and disrespects the original creator's work. Access to a file does not grant permission to use it this way.
>
> AI is becoming part of development, but **AI is a tool, not a wishing well**. Ideas, judgment, understanding and responsibility remain with the user. Approach AI thoughtfully, consider how you use it, and take responsibility for what you publish.

## Fastest start: give your agent the repository URL

Send this to an **AI/agent that can use local tools**, replacing the paths:

> Read https://github.com/OPFIMISS/RimProbe, its READMEs and docs/GETTING_STARTED.md. Install and configure the RimProbe MCP, then use RimProbe to test my mod in the real game. Game: `D:/Steam/steamapps/common/RimWorld`; target mod: `YOUR_PATH`. Check versions and capabilities, derive tests from the actual implementation, run startup checks, prepare fixtures, request normal actions, assert independent effects, inspect errors and verify cleanup. Preserve player settings, DLC and order. Use disposable profiles and the background private desktop. Report unsupported/uncovered behavior and remaining human checks explicitly.

The agent can start with `git clone https://github.com/OPFIMISS/RimProbe.git`, then follow the installation commands below. **A URL or the phrase “use RimProbe for real-game testing” does not install an MCP automatically.** Local tools, the game, build prerequisites and a configured MCP client are required. Once configured, simply ask: “Use RimProbe to test this mod: check startup, then validate the effects implemented in its code.”

2026-10-30 update: startup-only checks, typed interaction handles, readiness barriers, cross-map state observations, compact polling and read-only startup comparisons. 148 offline tests and both version builds pass; two 1.7 Def effect cases pass while startup errors keep overall results inconclusive. See [protocol and limits](docs/interactions.md) and [validation evidence](docs/validation/2026-10-30-interactions.md).

**Let AI agents launch real RimWorld tests in the background and inspect structured evidence.**

[中文 README](README.md) · [Getting started](docs/GETTING_STARTED.md) · [Architecture & extensions](docs/ARCHITECTURE.md) · [Chinese agent handbook](docs/AGENT_QUICKSTART.zh-CN.md)

RimProbe combines a local MCP stdio server with an in-game Agent mod. Agents derive tests from actual source and Defs, prepare disposable objects, request normal game actions, and assert observable effects. Games run on a private Windows desktop without controlling the system mouse or keyboard.

**Recommended companions: [RimSage](https://github.com/realloon/RimSage) and [rimworld-modding-skill](https://github.com/Kon-on/rimworld-modding-skill).** RimSage is an excellent MCP project that lets AI query the game's decompiled source through tools, grounding code in actual APIs and implementations and substantially reducing errors caused by guesswork. rimworld-modding-skill provides RimWorld mod development guidance and workflows; RimProbe runs real-game tests, observes effects and collects evidence. Together they support a source inspection → development → testing → repair workflow.

**Status: 0.1.0 developer preview, distributed as source.** Useful for basic and explicitly designed multi-stage tests, not automatic certification of every mod. Final playtesting remains a human task.

## Supported workflows

| Area | Current scope |
|---|---|
| Construction | Placement, blueprints, ground materials, real hauling, Frames and construction; delayed-supply recovery |
| Building behavior | Explicit output/network observations after normal construction, not arbitrary functionality |
| Abilities | Fixture Pawns, standard Ability assignment and normal cast jobs; Hediff/injury/cooldown/downed assertions |
| Items | Normal ingestion, equipment and movement with state and numeric-delta observations |
| UI | Real information-card opening, Repaint, bounds and closing; not pixels or input hit-testing |
| Complex mods | Explicitly installed trusted compiled test packs with bounded state machines and independent checks |
| Evidence | Startup/runtime errors, actual load order, profile fingerprints, exception chains and cleanup status |

A new Def using a supported mechanism generally needs a new plan, not a per-object adapter. Unsupported mechanisms remain explicit gaps.

## Requirements and versions

- Windows private Win32 desktops and Job Objects; game control is not implemented for Linux/macOS.
- Python 3.10+, MCP SDK 2.x; tested constraints are in `constraints-tested.txt`.
- .NET 10 SDK; building 1.6 also needs the .NET Framework 4.7.2 targeting pack.
- Your installed game and matching Harmony assemblies. Neither is bundled.

| Game | Runtime / references | Validation |
|---|---|---|
| 1.6 | net472, Unity/Mono, separate Managed references | Real-reference compilation and offline checks; no live acceptance yet |
| 1.7 | net10.0, Waylith, separate game-root references | Per-iteration live evidence; the new interaction-specific record is separate from full live acceptance |

References, outputs and intermediates are separate. Iteration ten adds interaction, startup and baseline checks. Offline tests, real-reference compilation and actual game evidence are recorded separately; they do not certify your target mod. See [acceptance status](docs/ACCEPTANCE_STATUS.md).

## Install from source

PowerShell example; replace checkout, game and Harmony paths. Do not mix game-version assemblies.

```powershell
git clone https://github.com/OPFIMISS/RimProbe.git C:/Projects/RimProbe
Set-Location C:/Projects/RimProbe
py -3 -m venv .venv
& ./.venv/Scripts/python.exe -m pip install -e . -c constraints-tested.txt

./scripts/build-agent.ps1 -Version 1.7 `
  -GamePath 'D:/Steam/steamapps/common/RimWorld' `
  -HarmonyAssembly 'D:/Steam/steamapps/workshop/content/294100/2009463077/1.7/Assemblies/0Harmony.dll'

& ./.venv/Scripts/python.exe -m rimprobe `
  --game 'D:/Steam/steamapps/common/RimWorld' `
  install-agent --mod-source C:/Projects/RimProbe/mod
```

Existing installations are not silently overwritten. Use `--update-owned` for a manifest-verified RimProbe installation; updates preserve a backup. Do not replace DLLs while a game uses them. **Do not enable the Agent in the normal player configuration**; it is added to disposable profiles.

For 1.6, use the same script with `-Version 1.6`, a genuine 1.6 `-GamePath` and matching Harmony. An archived `-ManagedPath` can validate compilation but cannot serve as a launchable installation.

## Connect an MCP client

Clients supporting `mcpServers` can use this stdio configuration. Other clients need equivalent command/args fields; configuration locations and tool prefixes vary. No specific AI provider is required.

```json
{
  "mcpServers": {
    "rimprobe": {
      "command": "C:/Projects/RimProbe/.venv/Scripts/python.exe",
      "args": ["-m", "rimprobe", "--game", "D:/Steam/steamapps/common/RimWorld", "--runs", "C:/Projects/RimProbe/runs/my-mod", "serve"]
    }
  }
}
```

1. Call `rimprobe_doctor` and `rimprobe_capabilities` for the real version, schemas and limits.
2. Deploy the target mod where the game can find it. `extra_mods` contains packageIds, not paths; it does not build/install mods.
3. Submit `rimprobe_run_plan`, use `rimprobe_run_suite` for construction, or `rimprobe_run_contract` for an existing recipe.
4. Poll `rimprobe_get_run(run_id, wait_seconds=10)` until `controller_finished=true`. Successful cleanup also requires `cleanup_status="succeeded"` and `owned_process_exit_verified=true`.
5. Read selected reports, diagnostics, actual load order and stop artifacts with `rimprobe_get_artifact`; use `rimprobe_cancel_run` to cancel or retry cleanup of the original retained owned session.

The default surface has 15 tools, including authorized source/Def hints, `rimprobe_run_startup` without map generation, four typed interaction tools and read-only startup comparison. `get_run` defaults to compact progress and outcome dimensions; request `detail:true` for details. Discovery without assertions does not produce a functional pass. `cleanup_complete` is an attempt-finished alias, not proof of exit. See [the tutorial](docs/GETTING_STARTED.md); no manual launch is needed.

## How it works

```text
AI / MCP client → Python stdio server → runner/controller
                                      ├─ private desktop + disposable profile
                                      └─ authenticated loopback TCP
                                            → Agent main-thread queue
                                            → normal jobs + observations
                                            → evidence + owned-process cleanup
```

The default profile inherits enabled mods/DLC and their relative order read-only, adds required Harmony/Agent and explicit additions, then verifies actual loading. Normal ModsConfig, Prefs and saves are not modified. Per-mod custom settings are **not cloned by default**. Outside a controller-created session, the Agent does not enable its listener or test patches. Game objects are accessed on the main thread; no eval, arbitrary C# or remote reflection paths are exposed.

Private desktops avoid system-input takeover, but a complete game still consumes CPU, memory and GPU resources. Zero interference across all mod combinations or concurrent player sessions has not been established. Errors remain visible except explicitly accepted duplicate-packageId scan noise; errors are not automatically attributed to the target mod.

## Extensibility

- **Compose mechanisms:** up to 24 fixture/measure/action/assert steps; see [plan semantics](docs/composable-plans.md) and `examples/plans/`.
- **Add a mechanism-level primitive:** update strict Python schemas, Agent allowlists/observers, budgets and both version tests. Do not hardcode every Def or expose arbitrary field execution.
- **Use a compiled test pack:** implement `IProbeTest`, register an explicit key, advance bounded main-thread `Pump` calls, clean up in `Dispose`; see [the contract](docs/registered-test-packs.md). Installed packs are trusted mod code, not a sandbox.

`testpacks/StarMoon` is an optional integration example requiring its separately supplied target mod. It does not automatically adapt to another project.

## Validation and limitations

```powershell
& ./.venv/Scripts/python.exe -m unittest discover -s tests -q
& ./.venv/Scripts/python.exe -m pip check
& ./.venv/Scripts/python.exe -m compileall -q src scripts tests
```

Offline tests do not launch games. Real-reference compilation, offline testing and live verification are recorded separately. Local `runs/` evidence is excluded from publication; `docs/validation/` contains historical summaries, not downloadable copies of every local artifact.

Gaps include random quicktest worlds, save/load, fuel/production, Caravan, arbitrary ability frameworks, source/verb Targeter chains, bare world tiles, UI pixels/hit-testing, complete artifact provenance and general historical MCP queries. Startup comparison can read two stored sessions under the run root; general run queries still retain the latest run only. A pass covers declared assertions; no-error logs, accepted actions and readiness do not replace effect checks.

## Documentation and distribution

- [First-test tutorial and agent instructions](docs/GETTING_STARTED.md)
- [Architecture and extension paths](docs/ARCHITECTURE.md)
- [Chinese detailed handbook](docs/AGENT_QUICKSTART.zh-CN.md)
- [Acceptance gates](docs/ACCEPTANCE_STATUS.md) / [historical notes](DEVELOPMENT_HISTORY.zh-CN.md)

This is a source preview, not a stable binary Release. Game, Harmony and target-mod binaries, saves and raw run logs are excluded. A project license has not been selected; no author/license metadata has been invented.
