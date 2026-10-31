# 2026-10-31 · Independent all-DLC multi-instance tests

## Result / 结果

RimProbe now accepts `profile_mode="minimal_all_installed_dlc"` on startup, suite, plan, contract and advanced launch tools, and on CLI test/smoke commands. It creates **Harmony → Core → all installed DLC → Agent → explicit extras** in a fresh private profile. It does not inherit or edit the player's normal list. Existing default `inherit` and explicit Core-only `minimal` remain available. A missing Agent now precedes newly added packs, avoiding early `IProbeTest` resolution failures without reordering inherited entries.

Known DLC use release order: Royalty, Ideology, Biotech, Anomaly, Odyssey. Identity comes from installed `Data/*/About/About.xml`, not folder-name guesses or license/source filtering. Unknown future DLC identities append deterministically and still require actual loading audit; no automatic dependency inference or downloads occur.

## Verification levels

| Level | Result | Limits |
|---|---|---|
| Offline Python and real stdio/wire contract checks | 156 tests passed | Includes native private-desktop child checks; not game acceptance |
| 1.6 real-reference build | net472, zero warnings/errors | Archived real 1.6 vanilla/Unity and local Harmony references; no 1.6 game launched |
| 1.7 real-reference build | net10.0, zero warnings/errors | Current 1.7.4990 rev1069 vanilla/Waylith references; no Agent source change or live DLL replacement |
| Two-controller live 1.7 isolation | Verified different process IDs, sessions, ports, profiles; cancelling/stopping B leaves A responding | A was another owned menu instance; no pre-existing player instance was running at audit start |
| Live normal Wall construction with target mod enabled | Seven functional checks passed, zero runtime candidates | Does not test the target mod's own behavior; three startup Workshop-folder candidates keep overall **inconclusive** |
| Installed Pawn Workshop registered test | Loaded and executed; failed on incompatible trait addition after ten preceding checks | Target-pack failure retained, not fixed or reclassified as passed by this RimProbe change |

Python regression coverage includes never reading an invalid player config in all-DLC mode, real metadata-based DLC ordering, Agent-before-pack ordering, inherited-order preservation, 1.6 launch layout, stopping A without touching controller B, rejecting a foreign endpoint, typed MCP mode discovery, and verification-helper endpoint/session/PID/port rejection. No new arbitrary execution interface exists.

## Live evidence / 实机证据

Private runs remain under ignored `runs/concurrent-20261031/`, not in Git. Both verifications used real installed MCP SDK `ClientSession` calls against two separate stdio services. Existing installed Agent was used; rebuilding outputs did not overwrite game DLLs. Actual 1.7 vanilla `Assembly-CSharp.dll` SHA256: `4E61D57205944C113631234BC55136A1A7C1679667B26008BEE5425BCFFA1463`.

Final isolation summary: `concurrent-1793419489435373300.json`.

- A: session `a72b15b5f0e34519863ca2fe86756215`, PID 16104, port 4467, main-menu instance.
- Cancelled B: owned startup run cancelled and process-exit cleanup verified; A still responded afterward.
- Test B: session `c23bc7e5d0e74136ac61dac73a7851b2`, PID 20440, port 8424. Real placement acceptance and rejection, blueprint, hauling into Frame, FinishFrame work, building initialization and Wall structural checks passed.
- A's endpoint descriptor was unchanged after cancelled B and after completed B; authenticated main-thread responses succeeded. Both instances were eventually stopped by their own controllers. No forced-stop fallback was reported. No observed foreground violations or system input injection were recorded.
- Before/after hashes of normal ModsConfig and Prefs matched. No normal save was opened or modified.

Actual B load order matched the requested nine entries exactly:

1. `brrainz.harmony`
2. `ludeon.rimworld`
3. `ludeon.rimworld.royalty`
4. `ludeon.rimworld.ideology`
5. `ludeon.rimworld.biotech`
6. `ludeon.rimworld.anomaly`
7. `ludeon.rimworld.odyssey`
8. `rimprobe.agent`
9. `local.pawnworkshop`

The earlier registered-test run added `local.pawnworkshop.probes` as entry 10, **without explicitly supplying Agent**. It loaded in the corrected order and reached `pawnworkshop.core`. Failure was `InvalidOperationException: 与现有特性冲突。` in the target pack's editing phase, with ten preceding checks retained. Evidence: summary `concurrent-1793419392122144600.json`, B session `79e6b83b2b4c419fae80120b15c27168`. This is evidence that the mechanism reports a real failed test, not proof the target mod is fully functional. Neither the target source nor its uncommitted files were changed in this task.

All three startup candidates in the construction run were `Created WorkshopItem ... but there is no folder for it`. Installed Workshop metadata may still be scanned even when other mods are disabled. They remain visible; no Steam content, subscriptions, player configs or suppression rules were changed. Functional and strict overall results remain separate.

One initial verifier attempt stopped before readiness because a fixed PowerShell process query returned nonzero when one of the two game executable names was absent. Its owned process was still reclaimed. The helper now produces an explicit array/exit code, tests query failure handling, and validates endpoint identities rather than comparing absent snapshot fields. That aborted evidence is retained privately, not presented as a completed game test.

## Reproduce / 复现

Build commands (use your authorized local reference paths; do not distribute game/Harmony DLLs):

```powershell
./scripts/build-agent.ps1 -Version 1.6 -ManagedPath 'YOUR_ARCHIVED_1.6_MANAGED' -HarmonyAssembly 'YOUR_1.6_0Harmony.dll'
./scripts/build-agent.ps1 -Version 1.7 -GamePath 'YOUR_1.7_GAME' -HarmonyAssembly 'YOUR_1.7_0Harmony.dll'
& ./.venv/Scripts/python.exe -m unittest discover -s tests -q
```

Real multi-controller verification with the existing installed Agent:

```powershell
& ./.venv/Scripts/python.exe scripts/verify-concurrent-mcp.py --game 'D:/Steam/steamapps/common/RimWorld' --runs ./runs/concurrent --extra-mod your.target.package
```

Use installed real package IDs, not the example placeholder. A is retained at the menu while B is cancelled and another B performs normal Wall construction. `--registered-test` optionally invokes an explicitly installed trusted pack instead; add its package via `--extra-mod`. The helper records private artifacts and distinguishes isolation completion from strict functional acceptance. It does not attach to any running player process.

## Limits / 边界

本轮验证的是两个受控游戏实例并存；开始时没有正在运行的玩家实例，因此不能声称本轮直接验证了玩家正在游玩的存档。未测前台游戏帧时间、GPU 竞争、长期并行、多人联机或 1.6 实机多开。私有桌面与独立 profile 不等于零资源影响，焦点采样也不是所有瞬间的绝对证明。

每个 MCP 服务仍只有一个活动测试实例；多个独立服务分别拥有自己的进程，不提供按 PID 附着、全局终止或命名实例管理。依赖需显式传入，已安装但未启用的 Mod 元数据仍可能被游戏扫描。未知未来 DLC 的顺序须实测，不能从身份清单推导兼容性。正常玩家配置及存档始终不参与测试；不要在任何实例使用 DLL 时热部署。
