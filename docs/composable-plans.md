# 通用组合计划

2026-10-30：当前共 24 种操作，仍最多 24 步。新增 begin_ability、四个交互操作及 wait_until；readiness 不计为效果断言。完整机制链和边界见 [通用交互](interactions.md)，可执行示例见 [interaction-landing.json](../examples/plans/interaction-landing.json)。

RimProbe 的主要扩展方向是可组合的游戏操作与观察。一个新 AbilityDef、物品或建筑只要使用已有正常入口和可观察状态，就可以换 Def、前置条件和断言来测试，无需修改 Agent DLL。现有固定 recipe 是快捷模板，不是未来逐物品适配的开发路线。

## 最短使用流程

1. 用源码/RimSage 确认目标正常动作、前置条件和预期变化；`rimprobe_inspect_mod` 只提供候选提示。
2. 读 `rimprobe_capabilities.plans` 和 `rimprobe_run_plan` 的 MCP JSON Schema。
3. 一次提交 `plan`，可选 `extra_mods`；默认 `profile_mode=inherit`，保留实际启用的 Mod/DLC 及排序。所有步骤在隔离游戏内自动推进。
4. `rimprobe_get_run(run_id, wait_seconds=10)`，直到 `controller_finished=true`。仅在 `cleanup_status=succeeded` 且 `owned_process_exit_verified=true` 时确认回收成功；`cleanup_complete` 只是旧版“尝试结束”别名。失败可查询证据，对保留的同一所属 session 用 cancel_run 请求清理重试。判断业务 `status`，需要细节再取 `report.json`、`diagnostics.json`、`loaded-mods.json`。

例如能力效果测试可以组合：

```text
spawn_pawn(actor) -> spawn_pawn(target) -> grant_ability(actor, MyAbility)
-> inspect(target) -> measure(target, pawn.hediff_count, MyEffect, before)
-> cast(actor, target, MyAbility)
-> wait_assert(target, pawn.hediff_count, MyEffect, relative_to=before, ge, 1)
```

这里的 MyAbility/MyEffect 是被测 Mod 中实际已加载的 Def；不是为这个名字添加 C# 特例。完整可提交 JSON 在 `examples/plans/ability-marker.json`；另外提供摄入、装备与移动、正常施工后发电、纯发现计划。

MCP 参数为 `{"plan": <JSON 文件内容>, "extra_mods": ["被测 packageId"]}`。自带验证 fixture 仅需 `rimprobe.fixture.abilities`；不属于 Agent 的发布依赖。每份计划是一轮独立游戏，不是跨调用持久调试会话。

## 操作与对象

| 类别 | 操作 | 语义 |
|---|---|---|
| 初始准备 | spawn_pawn, spawn_item, fixture_hediff, grant_ability | 仅在第一条动作、测量、等待或断言之前声明 |
| 正常动作 | cast, ingest, equip, move | 使用游戏 Ability/Job 正常入口；返回 requested 不代表效果通过 |
| 正常施工 | build | 蓝图、地面供材、真实搬运、Frame、施工及初始化；绑定实际成品对象 |
| 发现 | query_defs, find_thing, inspect | 读取真实加载 Def、有限范围已有对象、对象的类型/Comp/能力/Hediff/装备 |
| 基线 | measure | 将真实数值保存为本轮数值别名，不改变状态 |
| 控制 | wait, assert, wait_assert | 有界等待、立即比较、等待条件及连续采样保持 |

`bind` 产生本轮对象别名，引用必须在前面已声明，不能重绑定。`actor` 必须来自本轮 spawn_pawn；find_thing 找到的已有 Pawn 不能被当作可控制 actor。数值基线使用独立 `bind_value` 名称空间；`relative_to` 只能引用前面的 measure。

所有 fixture 均位于一次性地图。初始 Hediff 可以设置要被移除的病症；第一条 measure/action/assert 以后禁止添加 fixture，防止直接写入预期结果。发现操作不关闭初始准备阶段。

## 观察与证据

| 属性 | 额外参数 | 数值 |
|---|---|---|
| hp, spawned, destroyed, stack_count | 无 | 实际耐久、0/1 状态、数量 |
| pawn.dead, pawn.downed, pawn.stunned | 无 | 实际 0/1 状态 |
| pawn.food, pawn.injury | 无 | 当前食物绝对值、所有 injury 的 severity 总和 |
| pawn.hediff_count | def_name=HediffDef | 指定 Hediff 数量 |
| pawn.ability_cooldown | def_name=AbilityDef | 剩余冷却 Tick |
| pawn.ability_casting | 无 | 当前 Job 持有标准 Ability 时为 1，否则为 0 |
| pawn.equipped | def_name=ThingDef | 实际装备该 Def 时为 1 |
| pawn.distance_to | other=对象别名 | Pawn 与另一对象当前距离 |
| power.watts, power.connected | 无 | 实际 CompPowerTrader 输出、实际地图 PowerNet 成员身份 |

`hp` 是 Thing 耐久：Pawn 的继承值可能为 -1，不能作为 Pawn 健康程度；应按需要观察 pawn.injury、倒地或死亡状态。

比较符为 eq/ne/gt/ge/lt/le；`relative_to` 表示“当前值减基线”，不是相对百分比。报告同时保存原始 value、baseline、compared_value。Hediff 数量适合新增/移除检测，不代表 severity 或持续时间已验证。物品 destroyed 不能单独证明吃下，建议同时断言营养/效果变化；需要精确 Ingested 入口证据可继续使用 item_ingest 快捷契约。

`wait_assert` 的 ticks 是等待总预算，hold_ticks 是满足后必须保持的采样 Tick 区间；不满足会重新计时。Root.Update 采样不保证每 Tick 都观察，不能证明采样间没有短暂反转。异步动作后应明确等待目标状态，再发下一个可能覆盖同一 Pawn Job 的动作。

连续施法时，效果断言之后追加 `wait_assert(target=actor, property=pawn.ability_casting, compare=eq, value=0)`，再执行下一动作。它只证明当前没有标准 Ability Job，不能证明技能效果、冷却就绪、队列为空或自定义技能框架完成。示例 `examples/plans/ability-sequence.json` 施放两个不同技能，并分别检查效果和冷却。

失败、阻塞、不支持、预算耗尽及取消的步骤附加 `failure_context`：断言原条件、等待 Tick、采样保持进度，以及最多四个对象快照，直接引用优先，随后补最近正常动作的 actor/target。快照增加 `job_id`、`job_ability`，在清理作业之前采集。个别读取失败记录有界 `error`，不替换原始结果；对象超限标记 `objects_truncated`，整体报告预算不足则省略诊断并标记 `diagnostics_omitted`。不扫描地图、不执行反射、不会根据快照自动判责。正常成功步骤不额外附加这批诊断。

所有显式断言通过才会返回 passed；没有断言的发现或动作计划返回 inconclusive。失败、缺失前提、不支持、预算耗尽、取消分开记录。没有红字、发出 Job 或建成建筑均不能替代功能断言。

## 边界与预算

- 最多 24 步；含默认值的计划不超过 24 KiB；总预算 60..120000 Tick、5..600 秒。
- Def 查询每页最多 8 条；对象摘要每类列表最多 8 条并标记截断；计划业务证据超过 40000 序列化字节时停止且不判通过。
- 不允许任意代码、eval、反射成员路径或远程方法调用。所有游戏对象访问在主线程。
- 目前只有这组受审查的属性和正常入口。全新第三方能力框架、生产账单、燃料交互、其他 Comp 私有字段、自定义 UI、存读档可能需要增加通用原语或只读观察器；不需要为每个使用同一机制的对象重写测试实现。
- quicktest 地图尚不确定；自然 AI、其他殖民者和 Mod 仍可能干扰测试。保留实际证据，不能用强制成功率、篡改 RNG 或直接注入目标效果掩盖失败。
- 本轮计划执行器同时支持 1.6/1.7 独立编译；1.6 游戏实测仍等待完整安装。具体真机结果单独记录，不能用编译代替。
