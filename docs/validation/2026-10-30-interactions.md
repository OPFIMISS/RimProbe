# 2026-10-30 通用交互专项证据

本页是本机实际回归摘要。原始 runs 不上传；下面 session ID 和本机相对路径用于追溯，并非仓库中的可下载附件。源码测试、真实引用编译和游戏内验证分开记录。

## 离线与构建

148 项 Python 测试通过；pip check、compileall 通过。双版本 Agent 及两个可选包（InteractionFixtures / Template）真实引用编译均零警告/错误，双版本 C# 离线 transport/fault/preflight 通过。1.6 的 .NET Framework 离线进程不是 Mono 游戏实测。

| 构建 | SHA256 |
|---|---|
| Agent 1.6 | `c3e53fa7cfa4134ab292ed8731704220f4305224831d2eca2c03a2ae4b0a1c33` |
| Agent 1.7，实际回归构建 | `1ff8ed75b75a90f0afb07929ed0e13bc9fea6cf24f3640686d91e630a207152c` |
| InteractionFixtures 1.6 | `1208debe1ccc03aa534afcbdea7728dcc7d40d6397097ae894f40996d063f526` |
| InteractionFixtures 1.7 | `28db6f042e2790aaaa7a4d658240e160174d7bac4bef7fed09506c531014e25c` |

## 1.7 游戏内 MCP

RimWorld 1.7.4985 rev1269，真实 stdio MCP，经私有桌面后台启动；继承实际启用列表，不过滤 DLC 或修改玩家配置。两个独立自有 AbilityDef 使用相同核心原语；不读取其他 Mod 源码或反编译其 DLL。

| 用例 | session ID | 功能层 | 整体 | 证据 |
|---|---|---|---|---|
| startup_only | `898b6f462273411d9a401f858dc9aa7d` | not_applicable | inconclusive | 无 quicktest 参数，不请求地图，启动就绪/日志检查 |
| landing_a | `3d6dd8717db946f28def4b06aa6cb0e4` | passed | inconclusive | 世界选点 → 正常施法 Job → 地图落点 → marker、地图、层、坐标共 5 个独立断言 |
| landing_b_menu | `c4f50ab58e354f96a588880280a3b94c` | passed | inconclusive | 另一 AbilityDef 加入 FloatMenu，复用同一协议；5 个效果断言 |
| rejection_stale_cancel | `e006c4bb1cf946a08c0c32091fd06ab9` | passed | inconclusive | disabled 菜单项、越界落点、旧轮次句柄均返回 blocked；取消后本计划 5 项状态断言通过 |
| readiness_timeout | `ca75f903706441a88d18905186a980cb` | inconclusive（预期） | inconclusive | 不创建选点器，1 秒独立 readiness 预算到期，无功能 pass |

所有最终用例启动日志都有 33 条未忽略候选，故整体不升级通过；四个进入 scenario 的用例动作后 runtime_error_candidates=0。startup_only 不宣称运行行为覆盖。这里的“错误候选”不是目标 Mod 责任结论，也不能因共同出现而自动排除。

五次 `cleanup_status=succeeded` 且 `owned_process_exit_verified=true`，焦点审计均无观察违规，玩家 ModsConfig/Prefs 指纹均不变。实际启用五个 DLC（Royalty/Ideology/Biotech/Anomaly/Odyssey），加载列表与本轮临时请求排序匹配。完整每例实际排序导出到本机 `runs/iteration10/final/loaded-order.md`；临时 profile 显式增加 `rimprobe.fixture.interactions`，其他 Mod/DLC 相对顺序保持。

完成后，可选 fixture 已移出游戏 Mods 库并归档到本机 RimProbeBackups；正常玩家列表无需启用它，仓库仅保留其源码。原游戏内 Agent 已更新到上表对应构建。

本机汇总：

- `runs/iteration10/final/interaction-validation-1793347678649248200.json`：startup + 两正例；随后负例脚本授予错误技能而中断，`verification_complete=false` 保留。
- `runs/iteration10/final/interaction-validation-1793347969034867400.json`：修正后的拒绝/旧句柄/取消 + 故意超时，指定两例完成。
- `runs/iteration10/final/verified-summary.json`：只汇总已逐例 verified 的五项，不抹去上述失败。
- `runs/iteration10/final/baseline-comparison.json`：A/B 独立 session 的只读启动对照。

对照的已记录环境字段匹配，19 类共享错误候选、0 类候选侧新增指纹；原 outcome 不变。缺少完整 Mod/资源 binary provenance，不能称严格相同环境或完成责任归因。

## 未纳入通过的尝试

初版世界选点就绪超时（会话稳定帧被无活跃会话的 StopTargeting 重置）、一次安装目录锁定，以及临时运行副本的 startup_timeout 都保留。未结束其他游戏；检测到原进程自然退出后，才将修正版部署到原安装完成上述回归。没有对正常存档或玩家配置做修复性写入。

这轮没有验证实际跨地图传送、世界层切换、任意裸 tile、source/verb Targeter 多段 DestinationSelector、真实 UI 命中、renderer rebuild 完成或所有自定义框架。map/layer 对象句柄与 observer 已实现，不将同地图 fixture 的结果扩展为这些机制已通过。

## 复现

先按 README 构建/安装匹配 Agent，再构建可选 fixture：

```powershell
dotnet build testpacks/InteractionFixtures/1.7/InteractionFixtures.csproj -c Release -p:GamePath='D:/Steam/steamapps/common/RimWorld'
```

将该包的 `mod` 部署到游戏 Mods 下一个新的、自己拥有的目录，不覆盖已有 Mod；无需改玩家排序。随后显式启动回归：

```powershell
& ./.venv/Scripts/python.exe scripts/verify-interactions.py `
  --game 'D:/Steam/steamapps/common/RimWorld' `
  --runs 'C:/Projects/RimProbe/runs/interaction-validation' --execute-live
```

脚本保留分阶段检查点、实际排序、配置指纹、回收证据和失败，不自动屏蔽现有错误。维护后的取消计划只要求 marker、地图和层不变，避免把自然闲逛当作取消造成的位置变化；上表计数来自这次保留的实际原计划。1.6 需未来完整独立安装另行跑相同矩阵，不能拿 1.7 证据代替。
