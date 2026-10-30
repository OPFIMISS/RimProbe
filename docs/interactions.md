# 通用交互 / Typed interactions

这套协议围绕原版机制，不根据目标 Mod 名称或 Def 写专用分支。新 Def 使用既有机制时，只需改计划。复杂框架通过显式编译测试包补动作或 observer；不允许远程指定方法、字段路径、任意 CLR 类型或 C#。

The protocol adapts vanilla mechanisms rather than individual mods/Defs. Reuse plans for new Defs with the same mechanism. Trusted compiled test packs supply missing actions/observers; no runtime code, arbitrary method/field paths or CLR type selection is exposed.

## 入口与发现 / Entry and discovery

先调用 `rimprobe_doctor` / `rimprobe_capabilities`，读取当前工具 Schema。默认 15 个工具，`--advanced-tools` 另加 5 个底层控制工具。保持按项目划分 run root，每个服务顺序执行一次性运行。

Call doctor and capabilities first and use the installed MCP input schemas. There are 15 default tools and five opt-in advanced controls. Each server owns sequential disposable runs under its configured run root.

| 能力 / Capability | 使用方式 / Entry | 实际范围 / Scope |
|---|---|---|
| 启动检查 / Startup | `rimprobe_run_startup(extra_mods=[...])` | 不传 quicktest，不请求地图；主菜单就绪与启动日志。无功能通过结论 / no functional behavior claim |
| 标准技能入口 / Ability entry | plan `begin_ability(actor, def_name)` | 实际 Ability command，CanCast/CanQueueCast/GizmoDisabled/Disabled 检查；不直接 Activate |
| 发现交互 / Inspect | plan `inspect_interaction`; tool `rimprobe_inspect_interaction(run_id)` | world_target、map_target_callback、float_menu；source/verb Targeter 诚实标记缺能力 |
| 枚举 / Enumerate | plan `enumerate_choices`; tool `rimprobe_enumerate_choices(run_id, query)` | 每页最多 8，offset、limit；有界 typed metadata 与 opaque handles |
| 选择 / Select | plan `select_choice(choice)`; tool `rimprobe_select_choice(run_id, interaction, choice)` | 重新校验可用性，消耗当轮 choice handles；动作接受不等于效果成立 |
| 取消 / Cancel | plan `cancel_interaction`; tool `rimprobe_cancel_interaction(run_id, interaction)` | 原版 StopTargeting / FloatMenu.Cancel；取消后不变需独立断言 |
| 就绪屏障 / Barrier | plan `wait_until` | condition、timeout_seconds、stable_frames、cancel_if |
| 启动基线 / Baseline | `rimprobe_compare_startup(baseline_session_id, candidate_session_id)` | 同一 run root 下两个独立运行；只读、精确错误行指纹，不忽略错误或升级结论 |

`rimprobe_run_startup` reports `functional=not_applicable`. A startup-only pass covers its bounded loading/log check; it does not certify every lazy-loaded asset. Definition and rendering work deferred until first use still needs a functional/UI test.

## 句柄与候选 / Handles and candidates

运行 ID、交互 ID、choice handle 都有归属边界。交互和候选句柄是 32 位十六进制随机标识，不是标签或列表下标。一次选择后原候选失效，即使回调保持选点器开启；新交互、取消、运行结束均不得复用旧句柄。枚举相同活跃候选返回稳定句柄，每交互最多保留 128 个，每轮最多 64 次 live 查询/动作，超限要求缩小范围或取消。

Run IDs, interaction IDs and opaque choice handles are separate. Handles remain stable for the same live candidate, expire after selection/cancellation/replacement/end-of-run, and are revalidated before invoking anything. At most 128 candidates per interaction and 64 live calls per run are retained. Labels are diagnostic only and never accepted as selectors.

世界候选当前枚举**现有 WorldObject / MapParent**，保留具体对象身份、`map_id`、`tile_id`、`layer_id`。相同 tile 上的多张地图不折叠；不通过 MapParentAt(tile) 猜目标。当前不枚举任意裸 tile、不创建地图、不提供任意图层切换。仅依赖 onUpdate/鼠标位置才能工作的自定义 world callback 未验收。

World candidates currently enumerate existing WorldObjects/MapParents, preserving exact object identity and full PlanetTile layer information, including overlapping parents. Arbitrary bare tile enumeration, map creation and general layer switching are not implemented. Callbacks that require mouse/onUpdate state have not been accepted.

地图回调候选是当前地图上的对象，或明确 `x/z` 的格子。计划还可指定 `target` 对象和 `cell_at_target:true` 获取该对象实际所在格；不依赖屏幕坐标。检查当前地图身份、边界、TargetingParameters 和 targetValidator 后调用捕获的真实回调。原版 source/verb Targeter 的多段 DestinationSelector、分组施法等尚不支持，返回缺失能力；现有本地图标准施法仍用 `cast` 正常 Job。

Local callback choices use typed map cells or live Things and apply TargetingParameters and targetValidator. `cell_at_target:true` selects a bound object's actual cell. These are world/map coordinates, never screen pixels. Source/verb Targeter chains remain unsupported; use normal-job `cast` for supported local abilities.

FloatMenu 调用原版 `Chosen`，检查 option.Disabled、action、重校验对象状态。自定义额外按钮区域、鼠标悬停副作用及教程/UI 点击门禁未覆盖；不可把语义菜单选择当作真实按钮命中测试。

FloatMenu selection calls vanilla `Chosen` after availability and target revalidation. Extra GUI controls, hover side effects and tutor/input gating are not covered by semantic selection. No UI hit-test pass is claimed.

## 批量计划 / Batched plans

完整示例：[interaction-landing.json](../examples/plans/interaction-landing.json)。需要显式安装 [InteractionFixtures](../testpacks/InteractionFixtures/mod/About/About.xml)；这个可选回归模组不是普通使用的依赖。

The example executes: fixture Pawn → grant Ability → snapshot/measure → actual command → ready barrier → world choice → normal Ability Job → landing-ready barrier → validated map callback → independent marker/map/layer/coordinate assertions → Job-finished barrier.

`enumerate_choices.bind_choice` 只在查询**恰好返回一个候选**时绑定；零个或多个明确返回 unsupported，不按首项或中文标签猜测。绑定到不可用候选可以用于负例，选择时仍正常拒绝。24 步、24KiB 输入、40KB suite 证据和整体预算继续生效。

`bind_choice` requires exactly one candidate. Zero/ambiguous matches are unsupported instead of choosing the first row. An unavailable candidate can be bound for a rejection test but remains unavailable on selection. Existing plan and evidence budgets still apply.

## Live 协作 / Live interaction during a bounded plan

计划用 `wait_until condition="interaction_closed"` 明确让出选择权。Agent 根据 get_run 的阶段变化调用发现与枚举，再用返回的 interaction/choice 句柄选择或取消。写操作只在这个显式等待阶段接受；普通确定性计划执行期间不会接受竞争写入。每次操作保存有界证据到 report.json。运行结束后不提供持久调试会话。

A plan explicitly yields at `wait_until(interaction_closed)`. Live tools can then discover, enumerate and select/cancel using the returned handles. Writes outside this phase are blocked to avoid races with deterministic plan steps. This is bounded cooperation with a running scenario, not an unbounded persistent debugger.

```json
{"id":"external_selection","op":"wait_until","condition":"interaction_closed","timeout_seconds":60,"stable_frames":3}
```

```json
{"run_id":"RETURNED_RUN_ID","query":{"interaction":"RETURNED_32_HEX_HANDLE","map_id":1,"limit":8}}
```

Never invent handles. Polling should follow stage changes; do not repeatedly download full evidence.

## 就绪和效果 / Readiness and effects

`wait_until` 支持 `interaction_ready`、`interaction_closed`、`map_ready`、`ability_job_finished`。阶段使用独立单调墙钟超时（1–120 秒）；连续主线程帧采样（2–120）与地图/交互身份匹配，中途加载或身份变化会重置计数。可用 `cancel_if:"actor_unavailable"` 取消。就绪不计为功能断言。

Barriers use independent monotonic phase deadlines and consecutive main-thread frame samples, resetting on loading/identity changes. Supported conditions observe ready/closed interactions, map registration/drawer availability or the standard Ability Job ending. `actor_unavailable` can cancel a barrier. Readiness is never counted as a functional assertion.

**这不是完整渲染重建屏障。** 当前 readiness 只观察 Playing、无 LongEvent、注册地图及 drawer、活跃回调/菜单、连续帧身份稳定；没有证明世界网格或地图 section 重建结束。此前“延后三帧未复现”仍不是根因结论。需要强渲染保证的机制应补可信 observer，不能用固定延迟冒充。

**Renderer rebuild completion is not observed.** Stable frames reduce obvious transition races but do not prove that world mesh/section rendering has settled. The earlier three-frame observation is not a root-cause finding. Mechanisms requiring stronger readiness must supply a trusted observer.

独立 `measure` / `assert` / `wait_assert` 支持前后差值、持续采样成立和取消后不变。新增 `map.id`、`map.tile_id`、`map.layer_id`、`position.x/z`、`pawn.job_active`，保留原对象引用跨地图观察，不按当前地图重新搜错对象。对象离图时明确 blocked，不编造地图或位置。完整 PlanetTile 检查须同时断言 tile 和 layer，地图身份还须单独检查 map.id。

Independent observations support numeric snapshots/deltas, sampled holds and cancellation invariants. New map/layer/position/job properties operate on the original object handle across map changes. Off-map observations are blocked rather than invented. Tile ID alone is insufficient: assert layer and map identity separately.

## 结果与诊断 / Results and diagnosis

`get_run` 默认精简：阶段、检查数量、错误摘要和 `outcomes.functional/startup/runtime/cleanup/overall`。`detail:true` 或按名读取 artifact 获取证据。整体结论不因功能通过、共同错误候选或后续清理重试而自动放宽。`controller_finished` 只是控制线程结束；成功回收还须 `cleanup_status="succeeded"`、`owned_process_exit_verified=true`。

Default polls contain progress, counts, a bounded error summary and separate outcome dimensions. Use `detail:true` or named artifacts for evidence. Functional success does not hide startup/runtime/cleanup problems, and shared baseline candidates never upgrade the strict overall outcome.

启动对照精确比较已记录的 game、Mod 列表/排序、Agent hash、profile 源指纹和显示参数；环境不匹配和日志截断单独标记。**尚无所有 Mod/资源二进制 provenance**，所以环境字段一致也不能当作严格受控环境相同，更不能仅凭堆栈或共同错误给目标 Mod 定责。基线与目标必须独立启动，比较工具只读。

## 扩展与验收 / Extensions and acceptance

用 [测试包契约](registered-test-packs.md) 扩展缺失动作/observer，复用执行器、预算、检查、异常快照和清理。最小模板见 [Template](../testpacks/Template/ExampleProbe.cs)；可执行的机制回归样例见 InteractionFixtures。重复实现同一机制后再提取到核心。

Production bills, hauling/transport workflows beyond existing construction, Caravan operations, arbitrary custom commands/UI and all framework integrations remain gaps. Do not claim those are implemented merely because this protocol exists.

新增机制验收至少应服务两个独立 Def/Mod 用例，并覆盖不可用、旧句柄、取消、超时。验收明确分离离线测试、双版本真实引用编译和游戏内结果。建议记录：无专用代码覆盖率、首次接入耗时、每轮墙钟时间、读取证据次数；本轮不凭两个自有 fixture 声称广泛 Mod 覆盖率。

Require at least two Def/mod uses plus rejection, stale-handle, cancellation and timeout controls before broader acceptance. Track onboarding time, elapsed run time, evidence reads and coverage without custom code. Two owned fixture Defs do not establish a general mod-ecosystem coverage rate.
