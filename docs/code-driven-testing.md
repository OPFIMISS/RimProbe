# 从代码到行为证据

优先使用 [通用组合计划](composable-plans.md)：同一组正常入口与只读状态适用于不同 Def；按代码改变步骤和断言，无需逐对象新增 C#。下文旧 recipe 是保留的快捷模板，不能据此把新功能开发限定为逐类别硬编码。

## 原则

测试集合由目标实现决定，不由固定物品/建筑名单决定。RimSage/源文件用于理解代码，RimProbe 用于验证实际运行。Def 扫描只给候选、类名、Hediff 提示，不宣称理解 C# 控制流、继承或所有 XML Patch。

1. 读取目标 Def、关联 Ability/Comp/Job/Hediff 实现，列出前置条件、正常动作路径和副作用。
2. 把预期写成行为契约：目标、fixture、断言、观察时机、预算、源码依据。不要把“没红字”或“成功排队”当成功能成功。
3. MCP 创建隔离场景，生成测试 Pawn，授予能力，先通过正常施放资格检查，再调用 QueueCastingJob。实际 Verb/Job 执行效果和消耗。
4. 比较目标状态前后变化，输出每条断言、覆盖缺口、新错误以及加载顺序。不能通过直接添加预期 Hediff、直接调用效果 Apply 或跳过消耗使结果成立。
5. 做故意失效的反例，证明断言能发现“施放了但效果没发生”。

## 给轻量模型的最短流程

- 先调用 `rimprobe_capabilities`；使用 `rimprobe_inspect_mod` 发现候选，再用源码/RimSage 确认预期。
- 调用 `rimprobe_run_contract`，只提交下面这种结构化 JSON；接口自身提供字段、枚举、范围的 MCP JSON Schema。
- 得到 run_id 后调用 `rimprobe_get_run`（建议 wait_seconds=10，最多 15 秒，客户端工具超时应更长），等待 cleanup_complete=true。无需逐 Tick 指挥、截图或发送真实鼠标输入。
- 查看业务 status；需要解释失败时读取 report.json / diagnostics.json / loaded-mods.json。不要把 MCP 调用成功当作测试成功。

```json
{
  "contract": {
    "schema": 1,
    "recipe": "ability_cast",
    "def_name": "RimProbe_FixtureMark",
    "intent": "普通施放应为目标添加指定 Hediff，并启动能力冷却",
    "source_refs": ["目标 AbilityDef/comps", "CompAbilityEffect_GiveHediff.Apply"],
    "fixture": {"target": "pawn", "distance": 3},
    "expect": [
      {"kind": "hediff_added", "subject": "target", "def_name": "RimProbe_FixtureMarker", "when": "end"},
      {"kind": "cooldown_started", "subject": "actor", "when": "eventually"}
    ],
    "observe_ticks": 180
  },
  "extra_mods": ["rimprobe.fixture.abilities"],
  "profile_mode": "inherit"
}
```

示例 Def 来自单独测试 Mod `fixtures/AbilityContract`，不是 Agent 的必需依赖；正常被测 Mod 使用自己的任意 AbilityDef/HediffDef。示例未安装/启用时应 unsupported，不凭空创建 Def。fixture 只用于本项目开发验证，不加入正式 ModsConfig。

## 当前契约边界

schema=1；recipe=ability_cast/item_ingest/ui_info_card（以下先说明 ability_cast）；单契约上限 24 KiB、1..16 条断言；未知字段/动作/观察器拒绝。无法由现有操作和属性组合的全新机制需要增加受审查的通用原语或观察器，不开放 eval、任意 C#、方法名或反射路径。

fixture：actor_kind/target_kind 为 PawnKindDef（默认 Colonist），target=self/pawn/cell，target_faction=player/hostile（只使用现有派系，不改外交），distance=1..30。生成独立女 Pawn 作为施放者，不复用原有殖民者。actor_hediffs/target_hediffs 是最多 16 个初始条件，仅写到新测试 Pawn；例如验证移除效果必须先声明初始 Hediff。

| kind | 判定 | 约束 |
|---|---|---|
| hediff_added | 指定 Hediff 数量比初始增多 | 必须提供 def_name；不是任意字段/severity 语义证明 |
| hediff_removed | 指定 Hediff 数量比初始减少 | 初始 fixture 必须存在该 Hediff；不保证所有实例移除 |
| injury_increased | 伤口总严重度增加 | 不等同于指定伤害类型、部位或精确伤害 |
| cooldown_started | 观察到正冷却剩余 Tick | subject 必须 actor；不能单独证明其他效果 |
| stunned | 从未眩晕到眩晕 | Pawn 状态变化 |
| downed | 从未倒地到倒地 | Pawn 状态变化 |

when=eventually 表示观察窗口内曾满足，when=end 表示结束采样满足。observe_ticks 从施放请求开始计算，须覆盖寻路/预热/弹道/延时；默认 180，最大 60000。每帧主线程 Pump 采样，不是每个 Tick 全事件追踪；极短暂效果可能漏检，应调整契约或添加事件观察器，不能据此断言游戏无该效果。max_ticks 默认 6000，上限 120000；timeout_seconds 默认 120，上限 600，超预算明确 inconclusive。

保留正常施放门槛，灵能资源、基因、装备、确认弹窗等条件不自动绕过。世界目标、必须确认的能力、非 Ability 框架、精确 VFX/UI、任意自定义字段暂不覆盖。未知功能返回 unsupported/blocked 或列为 excluded，绝不自动通过。目标 Pawn 可能移动；随机 quicktest 不是确定性场景。一次契约使用一个新游戏，启动成本换取状态隔离。

## 新能力不属于现有观察器时

先记录真实语义和缺口，再扩展契约版本/白名单 action 或 observer：同步修改 Python 验证、MCP schema、C# 类型与主线程实现、双版本编译、正例和故意失败反例、README 证据。适配器应调用玩家正常动作入口，采集独立可观察结果，不能把测试准备与被测结果混写。不要把未经审查的 Mod 类型/方法字符串变成远程执行入口。

普通建筑仍可走标准设计器、蓝图、搬运、Frame、施工流程；通用计划的 build 可绑定成品，再按已暴露属性进行独立功能断言。正常摄入、装备与移动已有通用操作，其他物品使用、生产账单、燃料恢复、自定义 UI、存读档等需后续机制级原语；发电输出/电网成员和信息卡 Stats 绘制已有下文专用契约，不与本次能力支持混淆。

## 配置与诊断

默认继承只读正式/指定 ModsConfig 的启用顺序，不按 DLC 来源过滤。只在一次性副本补入缺失 Harmony、显式额外项与 Agent，原有项相对顺序不变。不会克隆其他 Mod 私有设置，所以相同列表不代表配置完全相同；此限制在 profile.settings_cloned=false 明示。

每轮 profile-plan.json / loaded-mods.json / stop.json 记录原指纹、增补项和实际加载顺序；结束再次读取原配置指纹，遇到用户并发修改只报告、不“恢复”覆盖。实际顺序漂移阻止动作。仅明确重复 packageId 启动消息归类为许可噪声，原日志与 ignored_errors 保留；其他启动错误和动作检查点后的新红字照常报告。红字序号观察有缺口或日志截断时不能整体 passed。

## 物品实际摄入

使用 `examples/contracts/item-marker.json`：recipe=item_ingest，def_name 指向任意已加载可摄入、非材料制 Item ThingDef。fixture 支持 actor_kind、actor_hediffs、initial_food_fraction（有限数 0.05..0.8，默认 0.25）；这些是独立新 Pawn 的初始条件，不是注入期望结果。

Agent 生成一件物品并走正常 Ingest Job/Toils；需要同时观察该次发出的唯一 Job 编号以及该精确物品在 Thing.Ingested 完成时被消耗。搬运、拆分堆叠、单纯排队不能冒充摄入。断言包括 item_consumed、nutrition_increased、hediff_added、hediff_removed；subject 仅 actor，Hediff 必须精确 def_name。when=eventually/end。默认 observe_ticks=1200，预算同能力配方。自动选食、多堆叠、耐久、装备和未知自定义效果不在此适配器内。

本项目 fixture 的正例餐食真实摄入后给 marker；负例同样摄入且增加营养但不加 marker，应 failed。用户 Mod 需按自己的源码改断言，不依赖 fixture Def 名称。

## 后台信息卡 UI

使用 `examples/contracts/ui-info-card.json`：recipe=ui_info_card，目标为已加载 ThingDef；fixture.hold_seconds=1..10（默认 2）。必须同时提供四个独立断言：window_opened、window_drawn、window_in_bounds、window_closed。UI 可能暂停游戏，使用实际墙钟时间，不接受 observe_ticks/max_ticks 作为假预算。

打开真实 Dialog_InfoCard，观察真实 DoWindowContents 的 Repaint postfix，不直接调用绘制或伪造输入。边界用实际逻辑分辨率检查；独立 UI 配置用 1600×1000、UI scale 1，仍可能受平台/DPI影响而 failed。仅 Stats 生命周期/绘制/边界，不覆盖其他页、自定义窗口、像素正确、鼠标命中或截图。

## 缺料恢复

`rimprobe_run_suite(def_name="Wall", stuff_name="WoodLog", supply_delay_ticks=180)` 先临时禁止一次性地图中已有同类可用材料，记录全部变更，确认窗口内无供材/施工，再生成地面材料，继续真实搬运与建造。结束恢复原本允许的堆叠。缺料指无可用材料，不是假称地图里物理不存在资源；不是任意建筑功能或不可达恢复已覆盖。

## 扩展新语义的门禁

增加类别时同步改：受审查的 C# 主线程动作和独立观察器、Python 验证、MCP 嵌套 schema、capabilities、扫描提示、契约例子、预算/取消/失败清理测试、两版编译与分别记录的真机正反例。未知类名不是可执行反射指令；不增加 execute/eval/任意方法名接口。只提交现有适配器能真正触发并观察的断言，否则说明缺口并新增适配器，不生成虚假 passed。


## 建造后的真实发电功能

`examples/contracts/building-power.json` 通过 `rimprobe_run_contract` 提交。`def_name` 可以是任意已加载、已解锁研究、支持标准蓝图/Frame 施工并带 `CompPowerTrader` 的建筑，而非 fixture 名称白名单。首先继续使用正常设计器、地面材料、搬运和施工，绝不直接生成成品。无 Power Comp 的成品返回 `unsupported`，不会把施工成功当发电成功。

fixture 只接受可选 `stuff_name`、`settle_ticks=1..600`（默认 60）和 `construction_skill=0..20`（默认 12）。power 契约生成独立女性 Colonist 工人（最多 4 次筛选，不能禁用建造/搬运），只在新 Pawn 上设置初始建造技能及目标所需艺术技能，不改已有殖民者；不直接改施工成功率或 RNG。实际成功率写入 events，其他 Mod 的健康/能力限制仍可能阻止施工。研究、燃料、天气等前提不会被自动改写；需要这些前提的 Mod 应单独提供相应适配器，或如实留下 blocked/failed/unsupported 的证据，不授予预期结果。

必须同时声明两个不同断言：`{"kind":"power_output_at_least","minimum_watts":90}` 和 `{"kind":"power_net_registered"}`。阈值必须有限、正数、至多 10000000 W；observe_ticks=60..60000，默认 180，max_ticks 必须大于 settle_ticks+observe_ticks，为真实施工留出时间。搬运/施工证据也会按目标地图、坐标和 Frame/蓝图 Def 核对其他殖民者的真实 HaulToContainer/FinishFrame 作业，并记录有界 actor ID 列表，不强行禁止其他殖民者工作。所有检查在主线程，只读取 `PowerOutput`、实际 `PowerNet` 及其 `powerComps` 成员身份和所属地图，从不设置 PowerOutput/PowerOn、不手工注册电网、不直接调用 CompTick。

报告 `power_evidence` 包括首末 Tick、不同 Tick 的采样数、实际网络成员采样数、最低/最高/末次输出；整个采样窗口内最低值达到门槛且每个样本均在实际电网中才通过。正常施工若触发被追踪 Frame 的 FailConstruction（包括其他殖民者代建），会由只读 postfix 记录并快速返回 blocked，不继续等材料耗尽直到超时，也不补入隐藏材料或强制成功；该结果本身不能归因于被测 Mod。采样由正常 Root.Update pump 驱动，不声称捕获每一个模拟 Tick。只证明发电输出/注册，不证明消费端供电、燃料恢复、配方生产或任意自定义 Comp。正例使用普通 CompPowerPlant 生成 100 W；相同造价/工时的零输出负例也必须真实施工，但功能判定 failed。
