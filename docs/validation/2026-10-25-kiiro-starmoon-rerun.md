# DLC 恢复后星月师实际复跑

日期：2026-10-25。游戏：1.7.4985 rev1269 / Waylith。使用真实 stdio MCP，经私有 Win32 desktop 启动，各用例拥有独立 profile / 进程；没有发送系统鼠标或键盘输入。仅继承启用列表和顺序，未复制正常玩家 Mod 设置，因此此处验证的是默认 Mod 设置。

## 已完成的正例

最终构建回归目录：`E:/Rimbook/runs/iteration07/final`。

| 用例 | 检查数 | 游戏内结果与范围 |
|---|---:|---|
| mechanics | 48 | 觉醒背景/祝福，三级能力解锁及资源上限，空资源拒绝/资源恢复，昼夜流水幻梦的倒地/记忆/睡眠/治疗，昼夜万千回转的成熟/治疗/月光，正常施法扣费，时停/冻结/地图条件，三次固定语义选择传送，自然到期恢复，正常睡眠积累与准备阈值后的真实升级，第二次时停及正常取消能力清理 |
| envelopes | 12 | A/B/C 均通过实际读信封 Job 打开叙事窗口，组件 Variant 一致，实际逻辑屏幕内窗口边界成立 |
| stay_star | 9 | 实际读信封、选择资格、留星结果、结局信，图片可加载且真实 Repaint，白屏→淡入→保持→淡出→credits 顺序成立 |
| return_moon | 11 | 实际读信封、选择资格、子地图生成与居民、结局提交、资源清空，正常 Goto 出口，返回原地图、清理临时地图、结局信 |
| negative_control | 1 | 唯一的 deliberately_absent_marker 检查按预期失败；报告仍为 failed，不把负例改成 passed |

各用例均启动错误候选 0、运行错误候选 0、实际请求排序一致；80 项正例检查通过，故意缺失 marker 的负例正确失败。原始完整汇总 `final/mcp-starmoon-1792916039408918700.json` 保留；派生 `final/audited-evidence.json` 的 `verification_complete=true`、`checks_validated=true`，`final/audit.json` 的只读一致性审计通过，`full_acceptance=false`。

五轮合计 3046 次焦点采样无观察违规，正常 ModsConfig.xml / Prefs.xml 前后 SHA256 相同。测试进程峰值 working set 最大约 2.51 GiB，是整个游戏进程的值，不是 Agent 增量开销，也不是前台并行性能验收。最终五个所属进程均退出；临时测试包已移到 `runs/iteration07/archived-testpack`，游戏 Mods 不再扫描它。清理与构建指纹见 `runs/iteration07/cleanup.json`。

## 修复及归因

本轮发现并修复的是 StarMoon 测试包准备/调度错误：

- `TimeInBed` 是 Time 类型，原版 `records.AddTo` 会报错。可信测试包现仅在新 Pawn 的初始记录中准备 30 天 fixture，然后运行原有每日觉醒判定；不是等待 30 个自然游戏天的验收。
- 首次技能效果已经发生时，`CastAbilityOnThing` 仍在作业队列，导致 `CanQueueCast=false`。现根据 `CurJob.ability` 等待正常退出；没有强制停止上一技能、放宽资格或直接调用效果。
- 复跑脚本明确区分跑完与符合预期，核对正例断言、负例唯一指定失败、红字、配置漂移及回收证据，并接入现有只读证据审计。

没有为了得到 passed 修改星月师玩法代码。留星图片和 1.7 构建/Defs 来自上一轮；本轮真实执行补齐了当时缺少的运行证据。

## 玩家旧设置红字

正常玩家日志的新增错误是：

`SaveableFromNode ... AncotLibrary.AncotLibrarySettings ... Kiiro.KiiroRaceSettings`

只读检查确认 `Config/Mod_2988200143_Mod_KiiroRace.xml` 保存的 Class 为 `AncotLibrary.AncotLibrarySettings`，与日志期待类型不同。此处只读取设置元数据和日志，没有读取或反编译第三方 Mod 代码。独立新 profile 没有这份旧设置，未复现该错误。

修复建议是游戏关闭后，备份该单个旧设置文件，再让对应 Mod 重建默认设置；不要改成别的 Class 后保留不匹配字段，不要清空全部 Config。根据项目 AGENTS.md 的“Never modify normal player saves or Mod configuration”，本轮没有对正常配置执行重置。

后续用户单独批准后，确认游戏未运行，仅将这个文件移到同目录 `Mod_2988200143_Mod_KiiroRace.xml.rimprobe-20261025.bak`，备份 SHA256 一致。下次正常启动由游戏重建默认设置；未启动玩家游戏，尚未复查该红字是否消失。此批准后的单文件操作独立记录在 `runs/iteration07/settings-reset.json`，不追改前述测试期间配置未变的历史证据。

## 本轮加载排序

正常玩家列表未改；一次性副本末尾追加 Agent 与测试包。五 DLC 均实际加载。

| 序号 | packageId |
|---:|---|
| 1 | brrainz.harmony |
| 2 | ludeon.rimworld |
| 3 | ludeon.rimworld.royalty |
| 4 | ludeon.rimworld.ideology |
| 5 | ludeon.rimworld.biotech |
| 6 | ludeon.rimworld.anomaly |
| 7 | ludeon.rimworld.odyssey |
| 8 | ancot.ancotlibrary |
| 9 | void.charactereditor |
| 10 | latta.devl10n |
| 11 | latta.fsharp.core |
| 12 | erdelf.humanoidalienraces |
| 13 | ancot.kiirorace |
| 14 | ray1203.simplecamerasetting |
| 15 | kiiro.starsandmoons |
| 16 | latta.devl10n.zh |
| 17 | zh.ray1203.simplecamerasetting |
| 18 | rimprobe.agent（仅测试副本增补） |
| 19 | rimprobe.tests.starmoon（仅测试副本增补） |

这不是推荐排序，也不是第三方 Mod 全部功能的兼容性背书。

## 验证层级与剩余边界

- 121 项 Python 离线测试通过；包含防止空检查、负例假通过、额外失败/红字、配置漂移与缺失回收证据被接受的回归。
- StarMoon 测试包 1.6 net472 与 1.7 net10.0 分别使用真实引用编译，均零警告/错误；1.6 缺完整运行安装，仍未游戏内验证。
- 1.7 的运行通过只限上述动作与断言。等级/时钟/资源/记录/伤口属于 fixture；三次传送和剧情选择用固定编译回调，未验证鼠标命中。
- 未验收：完整冥想路径、全部被动保护/社交/免疫组合、所有设置分支、长期剧情与草案、存读档、全部窗口排版与像素美术、玩家前台游戏并行性能、任意 Mod 组合、所有模型客户端。
- 图片加载及阶段/Repaint 通过不代表美术节奏已由人确认；最终人类游玩测试仍需要保留。
