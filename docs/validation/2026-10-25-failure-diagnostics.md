# 第八轮验证：连续施法与失败诊断

日期：2026-10-25。范围为 RimProbe 通用计划的连续标准 Ability Job、失败证据和取消回收；不是重新验收星月师全部功能，也不是完整产品验收。

## 改动与原理

- 新增 `pawn.ability_casting`，读取当前 `CurJob.ability != null`。效果出现后，等待该属性为零再发下一动作；冷却与实际效果仍需独立断言。它不证明队列为空或第三方框架结束。
- 非成功步骤在清理前采集 `failure_context`，包含断言条件、等待/采样保持 Tick，以及最多四个相关别名的快照；当前引用优先，再补最近 cast/ingest/equip/move 的 actor/target。快照增加 `job_id`、`job_ability`。
- 单个对象读取异常写入有界 error，继续其他对象；诊断超过报告预算时明确省略，保留业务结果。没有开放反射或执行字符串。
- 验证脚本对负例和取消也要求启动错误为零、扫描未截断且有日志来源，最终执行只读证据审计；审计失败撤回完成标记并保留错误。

## 离线与编译

126 项 Python unittest、pip check、compileall 通过。

Agent 1.6/net472、1.7/net10.0 分别使用真实游戏引用编译，均零警告/错误。证据副本在 `runs/iteration08/build-evidence-1.6.json`、`build-evidence-1.7.json`。两版 C# 离线检查验证：诊断别名优先级/去重/四对象上限、坏快照隔离、错误长度、原条件与进度、Job 身份序列化及通信鉴权/超时；没有访问真实游戏对象。

1.6 只有程序集归档，仍未进行游戏内验证。1.7 下述三例仅覆盖新构建的限定功能。

## 1.7 实机结果

游戏为 1.7.4985 rev1269，250×250 quicktest 地图，私有 Win32 desktop、独立 profile、真实 MCP stdio。

| 用例 | 结果 | 证据 |
|---|---|---|
| plan_ability-sequence | passed，11 步 | 正常第一施法，marker 增量 1；施法 Job 结束后第二施法，冷却 120 Tick，再确认 Job 结束 |
| plan_failure_context | failed，符合预期，12 步 | 前述两次施法完成；故意断言已生成对象 spawned=0，60 Tick 后失败，实际值 1，保留 target/actor 快照及当时 GotoWander Job ID |
| plan_context_cancellation（复跑） | cancelled，符合预期，12 步 | 两次施法后进入长等待，经 MCP 取消，保留相关对象快照并回收 |

正负例证据：`runs/iteration08/audited-positive-negative.json`，两例共 1237 次焦点采样。取消复跑：`runs/iteration08/cancellation-rerun/audited-evidence.json`，565 次。两份均含成功 `artifact_audit`；合计 1802 次采样无观察违规，源 ModsConfig/Prefs 指纹相同，请求/实际加载顺序一致。正负例启动/运行错误候选为零；取消复跑启动错误为零，当前取消路径没有单独保存最终运行增量 diagnostics，不能宣称其运行错误覆盖完整。

首次取消尝试 `16c05f43d75d4da6977e6e695904683f` 在地图准备时有一条 `Accessing TicksAbs but gameStartAbsTick is not set yet`。栈经过 StartingPawnUtility、PawnGenerator、婚姻关系和 Tale 创建。未确定根因，不读取第三方代码、不屏蔽此红字。原始 `mcp-validation-1792917450704034600.json` 与拒绝结果 `audit.json` 保留；原始脚本曾把取消动作完成当作检查通过，其完整三例结果**未通过证据审计**。两个干净用例的派生汇总明确注明排除了这次取消；随后单独复跑取消并审计通过。一次干净复跑不能证明该启动问题已修复。

四次尝试的所属 PID 10860、34312、36980、37536 均确认退出。fixture 在核对 packageId、清单和哈希后移到 `runs/iteration08/archived-fixture`；最终 Agent 保留安装且不加入正常启用列表。构建副本保存在 `runs/iteration08/agent-build`，便于后续按对应哈希审计；清理证据 `runs/iteration08/cleanup.json`。未修改玩家配置/存档及其他 Mod。

## 完整实际加载顺序

正常源列表及相对顺序保留；仅一次性 profile 追加最后两个测试条目。五个 DLC 均加载。

```text
brrainz.harmony
ludeon.rimworld
ludeon.rimworld.royalty
ludeon.rimworld.ideology
ludeon.rimworld.biotech
ludeon.rimworld.anomaly
ludeon.rimworld.odyssey
ancot.ancotlibrary
void.charactereditor
latta.devl10n
latta.fsharp.core
erdelf.humanoidalienraces
ancot.kiirorace
ray1203.simplecamerasetting
kiiro.starsandmoons
latta.devl10n.zh
zh.ray1203.simplecamerasetting
rimprobe.fixture.abilities
rimprobe.agent
```

## 复跑与只读审计

先把自有 `fixtures/AbilityContract` 安装到不存在的专用 `Mods/RimProbeAbilityFixture`，核对 packageId；只通过 extra_mods 添加到临时 profile。它已从本次游戏 Mods 目录移出，不能直接假设仍安装。

```powershell
& E:\Rimbook\.venv\Scripts\python.exe E:\Rimbook\scripts\verify-live-mcp.py `
  --game D:\Steam\steamapps\common\RimWorld --runs E:\Rimbook\runs\iteration08-recheck `
  --iteration-eight --include-cancel `
  --only plan_ability-sequence plan_failure_context plan_context_cancellation --execute-live

& E:\Rimbook\.venv\Scripts\python.exe E:\Rimbook\scripts\audit-live-evidence.py `
  --evidence E:\Rimbook\runs\iteration08\audited-positive-negative.json `
  --agent-root E:\Rimbook\runs\iteration08\agent-build
```

当前地图仍随机；新红字会阻止干净回归，不自动重试到成功后删除失败证据。存读档、确定性 fixture、1.6 真机、全部 Mod 兼容性及前台并行性能仍是后续门禁。
