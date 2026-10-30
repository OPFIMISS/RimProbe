# 第十轮：机制交互、就绪与 Agent 接入

日期：2026-10-30。目标是让 AI 根据实际实现组合测试，而不是为每个 Mod/Def 增加核心业务分支。仍为源码开发预览，不宣布全项目完成或稳定 Release。

## 本轮交付

| 反馈 | 实现与边界 |
|---|---|
| 机制级原语 | 标准 Ability command → 原版世界选点回调 → 正常 Ability Job → 地图落点回调；FloatMenu 可插入同一链。核心不引用两个回归 fixture 的 Def 名称 |
| 带类型的发现协议 | inspect_interaction、enumerate_choices、select_choice、cancel_interaction 同时支持计划和 MCP；运行/交互归属、opaque handles、有限分页、选择前重校验、句柄失效 |
| 正常入口与保真度 | 动作分 normal_game_action、validated_semantic_callback、fixture_setup、state_observation、test_pack_declared_scope；语义选择不冒充实际 UI 输入/命中 |
| readiness barriers | wait_until 支持交互就绪/原轮次结束、地图就绪、Ability Job 结束，独立单调墙钟预算、连续帧身份采样及 actor_unavailable 取消。未观察完整 renderer rebuild 完成 |
| 独立效果 | measure/assert/wait_assert 保留差值和持续检查；新增 map.id、map.tile_id、map.layer_id、position.x/z、pawn.job_active 和跨地图对象状态快照 |
| 开发优先级 | 增加不生成测试地图的 run_startup；世界现有对象/MapParent、回调落点和菜单先行。裸 tile、source/verb Targeter 多段链、Caravan、生产账单、一般运输仍未实现 |
| 轻量测试包 | 可构建的双版本 Template，以及独立可选 InteractionFixtures；复用现有注册、执行、预算、异常与清理，不作为普通安装前置 |
| 诊断效率 | 默认精简 get_run、detail=true 和按名 artifact，功能/启动/运行/清理/整体结果分层；独立 session 启动基线只读比较，不忽略错误、不归责、不升级结论 |
| 快速使用 | 中英文 README 顶部增加可直接发给工具型 Agent 的地址、路径、安装/配置和“使用 RimProbe 进行实测”提示词；明确 URL 不会自动安装 MCP |

默认 15 工具；高级底层控制仍需显式开关，合计 20。组合计划为 24 种操作，仍最多 24 步、24KiB 规范化输入、40KB suite 证据。每交互最多 128 个候选、每轮最多 64 个 live 查询/动作。世界目标保留具体 MapParent 身份以及完整 PlanetTile 层，不能按 tile ID 猜唯一地图。

## 验证

- 148 项 Python 离线测试通过，含真实安装 MCP SDK 的 stdio/schema/wire、启动无地图、精简轮询、归属/句柄参数、预算、基线只读和锁定安装回收检查；pip check / compileall 通过。
- Agent、InteractionFixtures、Template 分别在真实 1.6/net472 与 1.7/net10 引用下编译，零警告/错误；两版 C# 离线预检、异常注入与通信检查通过。
- 1.7 实际 MCP 专项：两个独立 fixture AbilityDef 的正例、三个交互拒绝、取消后状态断言、readiness 超时、无地图启动均完成。功能断言通过的三个用例仍因 33 条启动候选错误保持 overall=inconclusive；未屏蔽这些错误。
- 五个最终用例回收均 verified，玩家 ModsConfig/Prefs 指纹不变，焦点审计未观察违规，实际列表含五个 DLC 且请求排序匹配。1.6 没有完整可启动安装，不声称游戏内通过。

逐例证据和构建 hash 见 [专项验证记录](validation/2026-10-30-interactions.md)。历史失败、安装锁定、临时副本启动超时均保留，不能把最终覆盖以外的运行改成通过。本机原始证据不随仓库分发。

## 踩坑

1. 原版可能反复停止一个本就没有活跃会话的 Targeter。观察钩子必须只失效自己的活跃轮次，不能无条件清空另一选点器的稳定帧计数；第一轮 world_ready 超时促成此修复。
2. 世界回调可能在同一链中打开下一个菜单/落点器。interaction_closed 应观察进入屏障时的交互轮次结束；等待“所有选点器都为空”会卡住连续交互。Live 写入仅接受当前显式让出的轮次。
3. 负例验证脚本一度授予 A 却请求 B，正常被 Agent 拒绝。已修正脚本并增加离线验证“命令技能已经授予”；失败报告保留，不能当作目标功能坏了。
4. 不用角色自然闲逛产生的位置变化来指控取消回调。维护后的取消用例以 marker、地图和层为不变断言；最终实际回归额外的位置检查也通过，但不扩大通用保证。
5. Windows 上游戏使用安装目录时可能拒绝更新。安装失败不得遗留本次 staging，新增离线故障测试；不结束其他游戏。临时运行副本未正常发布 Agent endpoint，记录 startup_timeout，不用于验收；原游戏自然退出后才更新并在原目录完成最终回归。
6. 精确错误行对照仅去除日志开头 HH:MM:SS 时钟；不对栈、数字、Def 或对象 ID 任意归一化。A/B 对照有 19 类共同候选，不能据此屏蔽日志或判定责任。

## 后续门禁

用更多独立真实 Mod 验证机制覆盖，补裸 tile / 图层切换、源选点器完整 Job 链、强渲染就绪 observer、生产/运输机制和程序集/资源 provenance。存读档、前台并行性能、实际 Flash 模型客户端矩阵、1.6 真机仍独立待验收。当前只有自有两个 fixture 的复用证据，不给出夸大的覆盖率或接入耗时承诺。
