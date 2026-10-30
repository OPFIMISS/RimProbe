# First mod test with RimProbe

[中文 README](../README.md) · [Detailed Chinese handbook](AGENT_QUICKSTART.zh-CN.md) · [English README](../README.en.md)

This guide uses PowerShell on Windows. Paths and identifiers are examples: replace them for your machine and target mod. No game, Harmony or target-mod assemblies are distributed here.

For a tool-capable agent, start by sending the [copyable introduction](../README.en.md#fastest-start-give-your-agent-the-repository-url): repository URL, game/mod paths and “install/configure RimProbe, then use RimProbe for real-game testing.” Installation/configuration must finish before this phrase can invoke tools. Already configured clients can go straight to doctor/capabilities, then startup and code-derived effects.

## 1. Install the controller and Agent

Follow [the source installation commands](../README.en.md#install-from-source). Install Python dependencies into the checkout's virtual environment, compile the matching Agent using your real game/Harmony references, then run `install-agent`.

For 1.6, the build invocation is:

```powershell
./scripts/build-agent.ps1 -Version 1.6 `
  -GamePath 'D:/Games/RimWorld1.6' `
  -HarmonyAssembly 'D:/Mods/Harmony/1.6/Assemblies/0Harmony.dll'
```

Those 1.6 paths are placeholders. Do not point a 1.6 build at a 1.7 installation. An archived `-ManagedPath` can replace `-GamePath` for compilation only; launching still requires a complete game installation.

The Agent lives in the game's `Mods/RimProbe` directory. It need not be enabled in normal play. `install-agent --update-owned` updates only a verified owned installation and keeps a backup; do not force-overwrite a refusal.

## 2. Configure your MCP client

Use [examples/mcp-portable.json](../examples/mcp-portable.json), replacing command/game/run-root paths. The connection uses stdio. Restart or reload the MCP service after configuration or controller updates. Tool prefixes may differ by client; inspect the advertised tool list rather than inventing names or arguments.

Allow individual tool requests more than 15 seconds. The game runs asynchronously; repeated bounded polls cover the much longer startup/test duration. One server owns one active run; use separate run roots for different projects and start tests sequentially.

## 3. Check the target deployment

Call these tools without arguments:

```text
rimprobe_doctor
rimprobe_capabilities
```

They do not launch a game. Doctor checks the configured game's version and assembly fingerprints; it is not complete runtime acceptance. Inspect `capabilities.plans` and the actual input schemas.

Build and deploy your target mod first, including the correct version-specific DLL, Defs and assets. `extra_mods` identifies already installed mods by `About/About.xml` packageId. It does not copy the current source checkout, compile it or resolve every dependency. Append missing dependencies in the intended order; do not reorder normal player configuration to make a test work.

`rimprobe_inspect_mod` accepts `mod_path` and `version`, for example:

```json
{"mod_path":"C:/Projects/MyMod","version":"1.7"}
```

It reads bounded `.cs`/`.xml` hints from a directory you are authorized to inspect. It does not decompile DLLs or prove inheritance and behavior. Inspect actual source/API as needed before defining assertions.

## 4. Choose an entry point

| Tool | Purpose |
|---|---|
| `rimprobe_doctor` | Inspect configured game identity, without launching |
| `rimprobe_capabilities` | Read current mechanisms, schemas and limits |
| `rimprobe_inspect_mod` | Obtain bounded authorized source/Def hints |
| `rimprobe_run_plan` | Compose fixtures, normal actions and observations; primary entry point |
| `rimprobe_run_suite` | Standard construction, real hauling and optional delayed supply |
| `rimprobe_run_contract` | Existing building_power, ability_cast, item_ingest or ui_info_card recipes |
| `rimprobe_get_run` | Poll progress and cleanup outcome |
| `rimprobe_get_artifact` | Read a named evidence artifact |
| `rimprobe_cancel_run` | Cancel, or retry cleanup of the original retained owned session |
| `rimprobe_run_startup` | Check loading at the main menu without quicktest/map generation |
| `rimprobe_inspect_interaction` / `rimprobe_enumerate_choices` | Discover typed pickers/menus and bounded opaque candidates |
| `rimprobe_select_choice` / `rimprobe_cancel_interaction` | Revalidate a handle and select/cancel during an explicit plan yield |
| `rimprobe_compare_startup` | Read-only comparison of independent stored session startup candidates |

Each plan creates its own background game/profile/map; startup-only runs do not request a map. Typed live interactions cooperate with a bounded plan explicitly waiting at `wait_until(interaction_closed)`. See [the bilingual interaction guide](interactions.md). This is not a persistent debugger. Normal player games are not attached to or terminated.

### Construction example

Call `rimprobe_run_suite`, replacing the Def/package identifiers. Omit `stuff_name` for a building that does not require stuff.

```json
{
  "def_name":"YOUR_BUILDING_DEF",
  "stuff_name":"YOUR_ALLOWED_STUFF_DEF",
  "extra_mods":["your.actual.packageid"],
  "profile_mode":"inherit",
  "timeout_seconds":180,
  "max_ticks":60000,
  "supply_delay_ticks":180
}
```

This validates placement, blueprint, ground materials, hauling, Frame and construction. Delayed supply checks a missing-material stall followed by recovery; it does not prove recovery from an unreachable path. Use zero delay for the first basic check. A completed building does not prove custom functionality: follow construction with suitable observations, or use an existing functional contract.

### Ability-effect example

Call `rimprobe_run_plan`. Replace the packageId, AbilityDef and HediffDef with real identifiers. The default PawnKind is Colonist: provide an actual `def_name` on `spawn_pawn` if the feature requires a particular species/kind.

```json
{
  "profile_mode":"inherit",
  "extra_mods":["your.actual.packageid"],
  "plan":{
    "schema":1,
    "intent":"Normal casting must add the source-declared Hediff, then finish its standard Ability Job.",
    "max_ticks":12000,
    "timeout_seconds":180,
    "steps":[
      {"id":"caster","op":"spawn_pawn","bind":"actor"},
      {"id":"subject","op":"spawn_pawn","bind":"target","near":"actor","distance":5},
      {"id":"grant","op":"grant_ability","actor":"actor","def_name":"YOUR_ABILITY_DEF"},
      {"id":"before","op":"measure","target":"target","property":"pawn.hediff_count","def_name":"YOUR_EFFECT_HEDIFF","bind_value":"before_count"},
      {"id":"use","op":"cast","actor":"actor","target":"target","def_name":"YOUR_ABILITY_DEF"},
      {"id":"effect","op":"wait_assert","target":"target","property":"pawn.hediff_count","def_name":"YOUR_EFFECT_HEDIFF","relative_to":"before_count","compare":"ge","value":1,"ticks":1200},
      {"id":"finished","op":"wait_assert","target":"actor","property":"pawn.ability_casting","compare":"eq","value":0,"ticks":1200}
    ]
  }
}
```

This only fits an ability that actually adds that Hediff. Increasing an existing Hediff's severity may leave its count unchanged. Resource, time-of-day, faction and target requirements must come from implementation, not assumptions. Do not inject the expected result into the fixture.

After asserting an effect, wait for `pawn.ability_casting=0` before another action. That observation does not prove cooldown readiness, an empty queue or completion of a custom ability framework. See [all plan rules](composable-plans.md). Repository `RimProbe_Fixture*` examples require the optional fixture mod to be installed explicitly; do not add it to every target-mod test.

## 5. Wait and read evidence

Keep the returned run_id and poll:

```json
{"run_id":"RETURNED_RUN_ID","wait_seconds":10}
```

Wait until `controller_finished=true`. **Successful cleanup additionally requires** `cleanup_status="succeeded"` and `owned_process_exit_verified=true`. `cleanup_complete` is the legacy attempt-finished alias, not independent proof of exit. Do not replace DLLs or start another test before verifying cleanup.

Fetch details with `rimprobe_get_artifact` only when needed:

```json
{"run_id":"RETURNED_RUN_ID","name":"report.json"}
```

| Artifact | What to inspect |
|---|---|
| report.json | Overall result, suite assertions, actual/baseline/delta, failure_context, primary_failure and cleanup_failures |
| startup.json | Startup error candidates and scan coverage |
| diagnostics.json | Incremental runtime errors and Agent red-error coverage; may be absent after early cancellation |
| profile-plan.json | Inherited order, additions and source fingerprint |
| loaded-mods.json / mod-set.json | Actual order and requested/actual differences |
| stop.json | Owned-process exit, source integrity, foreground samples and resource evidence |
| contract.json | The normalized submitted test |

Read overall status and business assertions separately. Business may pass while overall remains inconclusive because startup errors or evidence gaps remain. Logs are candidates, not automatic blame attribution. No red error does not prove functionality.

`passed` covers only declared assertions. `failed`, `blocked`, `unsupported`, `inconclusive` and `cancelled` are distinct. A deliberate negative control should fail its chosen assertion; do not rewrite it to passed. Report absent diagnostics as incomplete coverage, especially on cancellation.

Cancel with `rimprobe_cancel_run` and continue polling. After a cleanup failure, a retained original session can receive another bounded cleanup request through that same tool. No PID scanning/attachment occurs. A successful cleanup retry does not upgrade the original failed result. If the service restarts, previous run_ids cannot be resumed; after another test starts, the previous run is no longer in the MCP runner's single-record state. Its files remain on disk.

## 6. Give another agent this instruction

```text
Use RimProbe MCP to test this project's actual mod changes.
Read capabilities and tool schemas first. Confirm game version, deployment, packageId and dependencies.
Read only source I authorize. Derive initial conditions, normal actions and independent effect assertions from code.
Use profile_mode=inherit and preserve enabled DLC/mod order. Never alter player saves/settings or take over input.
Submit a bounded plan; poll until controller_finished, then verify cleanup_status and owned_process_exit_verified.
Inspect startup/runtime errors, actual load order, source integrity, assertions and failure/cleanup evidence.
Keep failed runs. Fix only authorized project code, redeploy and rerun as needed.
Report actual coverage and unsupported mechanisms; never claim a compile/no-error log proves functionality.
Provide evidence paths, complete actual mod order, fixes/reruns and remaining human checks.
```

## 7. Beyond the first test

Use [architecture and extensions](ARCHITECTURE.md) for mechanism-level additions and trusted test packs. The current [acceptance gaps](ACCEPTANCE_STATUS.md) include save/load, broader fuel/production and UI workflows, deterministic fixtures and 1.6 live validation. Custom settings are not inherited automatically, and the default quicktest map is random.
