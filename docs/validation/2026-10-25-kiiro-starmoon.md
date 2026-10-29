# 2026-10-25：星月师迁移与实际测试记录

**第六轮历史记录。后续第七轮用户恢复 DLC 后，原有 quicktest 已正常运行，实际五用例均符合预期。最新证据、80 项正例检查、负例、排序与清理见 [DLC 恢复后复跑](2026-10-25-kiiro-starmoon-rerun.md)。下文保留当时的失败结论，不代表当前仍被同一问题阻塞。**

## 结论

本轮完成了独立双版本构建、1.7 Defs/支持版本声明、留星图片过渡，以及 RimProbe 编译式测试包接口和 StarMoon 测试包。**实际游戏验证受阻，不能宣布星月师 1.7 全功能兼容，不能宣布 RimProbe 全项目完成。**

只读取 RimProbe、用户自己的星月师、明确指定的 GBTA 迁移研究文档和原版 API。第三方组件只在游戏正常加载日志中出现，没有进入其源码或反编译其程序集。没有调整正常玩家 Mod 列表、升级其他 Mod、禁用 DLC 或修改玩家存档。

## 验证层级

| 层级 | 证据 / 结果 | 不代表什么 |
|---|---|---|
| Python 离线 | 116 项通过；包含 MCP stdio/wire、计划 schema、注册 key、显式 UI profile、诊断排序差异及启动失败日志落盘 | 不是游戏内功能通过 |
| Python 环境 | pip check 通过，compileall 通过 | 不是跨所有客户端/模型验证 |
| Agent 1.6 | 使用真实 1.6 DLL 独立 net472 编译，通信/注册接口测试在 .NET Framework 4.8 通过 | 不是 Mono 游戏实测 |
| Agent 1.7 | 使用当前真实 DLL 独立 net10.0 编译，通信/注册接口测试在 .NET 10 通过 | 不是完整 Waylith 场景验收 |
| 星月师 1.6 | 独立 Build1.6 net472 编译，0 警告/错误 | 当前没有完整 1.6 游戏安装，未启动验证 |
| 星月师 1.7 | 独立 Build1.7，游戏 1.7.4985 rev1269，0 警告/错误 | 不证明技能、绘制、子地图正常 |
| StarMoon 测试包 | 两版分别编译；五个固定 key 在实际 1.7 状态中可发现 | 注册成功不代表用例已经执行 |
| XML / 资源 | 28 个 1.7 Def XML 可解析，逐个 SHA256 与自身 1.6 Defs 相同；图片存在并可打开 | 依赖缺失时 cross-reference 仍可能失败 |
| 实际 1.7 MCP | 严格模式返回 blocked / mod_set_mismatch；owned worker 已退出 | 没有形成任何 StarMoon 功能 passed |
| 图片视觉 | 原 PNG 已查看；运行窗口/阶段断言已编写 | 未完成真实游戏画面和节奏的人工确认 |

## 实际启动问题

最终严格复跑目录：

`E:/Rimbook/runs/iteration06/final-strict/38cdbc72cf064ddb9ebd22a700dfe12d`

- `state.json`：phase=entry，map_ready=false，quicktest 参数存在；注册了 `kiiro.envelopes`、`kiiro.mechanics`、`kiiro.negative_control`、`kiiro.return_moon`、`kiiro.stay_star`。
- `mod-set.json` / `loaded-mods.json`：请求中的 Royalty、Ideology、Biotech、Anomaly、Odyssey 没有出现在实际加载列表。控制器没有删除这些请求；原版实际加载存在差异。没有绕过原版 DLC 判断。
- `startup.json`：23 个启发式错误候选、3 个用户接受的重复 packageId 候选。候选包括异常堆栈行和 WARN 缺失引用，不等于“23 条独立新红字”。Better Log 的 transpiler 异常和 VacuumResistance、MeditationFocusGain、Prefab 物件/地形等缺失引用仍然可见。
- `report.json`：在任何测试动作前 blocked。没有执行技能、读信封、归月或图片过渡；后续用例因同一启动前提未满足而未启动。
- `stop.json`：所属进程已退出，486 个前台采样没有观察到焦点违规。峰值 working set 约 1.96 GB，private bytes 约 2.53 GB；这是本轮整个进程的数据，不是 Agent 开销，也不能证明与前台游戏并行零影响。

此前诊断轮保留了请求排序和实际排序，尝试继续等待地图；没有得到可用地图，后续主线程请求超时并达到有界队列上限。一次试验性原版 Play 场景重试也没有恢复，**已移除该失败重试代码**，不作为项目能力交付。历史 JSON 保留重试字段。

有一轮控制脚本中途终止，旧报告停在 running 且没有 stop.json；不将其伪造为正常完成。最终进程审计单独确认没有本轮游戏进程残留。其余已结束轮有 stop.json；复跑以 final-strict 的完整回收证据为准。

## 最终请求与实际加载排序

正常配置未改变；只在私有副本追加 Agent 和测试包。

| 请求序号 | packageId | 实际序号 |
|---:|---|---:|
| 1 | brrainz.harmony | 1 |
| 2 | ludeon.rimworld | 2 |
| 3 | bs.betterlog | 3 |
| 4 | ludeon.rimworld.royalty | 未加载 |
| 5 | ludeon.rimworld.ideology | 未加载 |
| 6 | ludeon.rimworld.biotech | 未加载 |
| 7 | ludeon.rimworld.anomaly | 未加载 |
| 8 | ludeon.rimworld.odyssey | 未加载 |
| 9 | ancot.ancotlibrary | 4 |
| 10 | zh.betterlog | 5 |
| 11 | void.charactereditor | 6 |
| 12 | latta.devl10n | 7 |
| 13 | latta.fsharp.core | 8 |
| 14 | erdelf.humanoidalienraces | 9 |
| 15 | ancot.kiirorace | 10 |
| 16 | ray1203.simplecamerasetting | 11 |
| 17 | kiiro.starsandmoons | 12 |
| 18 | latta.devl10n.zh | 13 |
| 19 | zh.ray1203.simplecamerasetting | 14 |
| 20 | rimprobe.agent | 15 |
| 21 | rimprobe.tests.starmoon | 16 |

不能把这个列表当作建议排序或已证明兼容的组合。

## 已编写的功能矩阵

| 用例 | 正常动作 / 观察 | 准备与范围限制 | 实际状态 |
|---|---|---|---|
| mechanics：觉醒 | 每日 GameComponentTick 路径产生背景、祝福 | 新 Pawn、30 天床上记录和时钟属于 fixture；不冒充真实等待 30 天 | 未执行 |
| mechanics：等级 | I/II/III 对应技能数和资源上限；正常睡眠跨升级阈值 | 等级/179 进度为初始条件，未证明数百小时自然成长 | 未执行 |
| mechanics：星月力 | 空资源拒绝消耗、保护性恢复、正常 LayDown 后积累、真实施放后减少 | 初始资源调试补满；效果观察期不写预期结果 | 未执行 |
| mechanics：流水幻梦 | 正常 Ability Job，昼间敌倒地/友军记忆，夜间敌睡眠/友军治愈 | 新敌友 Pawn、预置伤口和时间 | 未执行 |
| mechanics：万千回转 | 正常 Ability Job，昼夜植物成熟、治疗/月光 Hediff | 新植物、初始 Growth=0.2 | 未执行 |
| mechanics：牵星移月 | 正常 Ability Job，时停条件、冻结/施法者 Hediff、到期恢复、一次传送 | 传送目标采用固定编译回调，未覆盖系统鼠标、三次传送及完整取消组合 | 未执行 |
| envelopes | A/B/C 各自正常读信封 Job → 实际叙事窗口、Variant、实际窗口边界 | 窗口关闭使用语义入口，未验证鼠标命中/所有文本排版 | 未执行 |
| stay_star | 正常读信封 Job → 固定选择回调 → 白屏/淡入/保持/淡出/credits、图片 Repaint、结局信 | 背景/等级/时间/星月力初始条件；不做像素美术评价 | 未执行 |
| return_moon | 正常读信封 Job → 固定选择回调 → PocketMap、居民、清空星月力、正常 Goto 出口、回原图、清图、结局信 | 不直接写出口位置；尚不验证存读档与全部场景视觉 | 未执行 |
| negative_control | 缺失月光 Hediff 必须失败 | 不制造 Log.Error，不给正常游戏留下故意报错 | 未执行 |

README 内的草案、自然长期剧情触发、全部显现/社交/免疫组合、存读档、渲染像素及平衡性未被上述清单穷举，仍需后续验证。

## 修改与复跑

星月师：About.xml 增加 1.7；新增 1.7/Defs 和独立 Build1.6/Build1.7；两版 DLL 独立输出；留星入口改用 `Window_StarMoonStayStarImageCredits`。原图 SHA256：

`a04d65e133d24e4dc3dfdea1c1ab613ad5e672476b09e595e7a6a9e38de498ab`

留星时间轴：白屏 2.25 秒 → 淡入 3 秒 → 保持 2 秒 → 淡出至白色 3 秒 → 原版 credits。图按比例显示；缺图警告并继续 credits；关闭清理 ScreenFader。归月路径未修改。

RimProbe：测试包注册/发现/执行/清理、空断言不通过、有界证据与超时部分结果、显式私有 UI profile、实际加载差异诊断模式、启动错误报告补全、窗口/注册 key 状态发现。默认 MCP 工具仍为 9 个；模型只需要有界 JSON 计划和长轮询。

`scripts/verify-starmoon.py` 提供真实 MCP 复跑，`scripts/audit-starmoon.py` 提供只读文件和配置审计。测试包只临时装入测试 profile；已核对路径、packageId 和文件清单，将测试安装移出游戏 Mods，归档到 `E:/Rimbook/runs/iteration06/archived-testpack`，文件哈希见 `archived-testpack-files.json`。当前测试包源码/双版本输出留在项目中供复跑。再次运行前须把编译后的 `testpacks/StarMoon/mod` 安装到一个不存在的专用临时 Mod 目录。

正常 ModsConfig.xml 和 Prefs.xml 前后 SHA256 相同，明细见 `runs/iteration06/audit.json`。没有根据测试副本恢复/覆盖正常配置。当前最先需要解决的是**私有进程的 DLC 实际加载和 quicktest 地图初始化**；在这些前提满足前，不重复宣称功能测试成功。
