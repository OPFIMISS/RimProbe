# 第七轮：DLC 恢复后的实际回归

日期：2026-10-25。继承当前玩家启用顺序，在一次性 profile / 私有桌面运行。只读取原版 API、RimProbe 和用户星月师代码；不读取第三方 Mod 代码。

## 计划

1. 已完成：核对玩家最新日志，确认新增异常来自旧设置文件的序列化类型不匹配。正常配置保持原样。
2. 已完成：真实 MCP 启动，确认五个 DLC 全部实际加载，250×250 地图就绪，请求/实际顺序一致。
3. 已完成：运行觉醒、昼夜能力、时停三次传送/自然到期/正常取消、睡眠成长、三信封、留星图片及归月子地图；修复测试包准备和作业等待错误，80 项正例检查通过。
4. 已完成：故意缺失效果负例仅指定 marker 失败且无新红字；测试包双版本真实引用编译零警告/错误，121 项离线测试通过；最终只读证据审计通过，所有最终测试进程已退出，测试包移出游戏目录。

## 当前发现

- 玩家 `Mod_2988200143_Mod_KiiroRace.xml` 的 `ModSettings` Class 为 `AncotLibrary.AncotLibrarySettings`，最新玩家日志期待 `Kiiro.KiiroRaceSettings`。这是配置读取失败的直接证据，不需要读取第三方源码。全新测试 profile 未复制该设置，启动错误候选为零。没有覆盖、删除或修复正常玩家设置。
- 初轮测试包错误地调用 `Pawn_RecordsTracker.AddTo(TimeInBed, ...)`，原版拒绝对 Time 类型使用 AddTo。改为固定编译式 fixture 访问 records，仅准备时间记录，然后调用原有每日觉醒路径；不修改原版定义类型、不屏蔽红字。
- 能力效果发生不等于 Job 已退出。测试应等待上一施法 Job 结束，并记录 cast/queue/apply/target 各项资格，避免将测试调度错误归为 Mod 行为错误。
- 最终五用例结果均符合预期，启动与运行错误候选均为零；`checks_validated=true`、`verification_complete=true`、`full_acceptance=false`。3046 次焦点采样无观察违规，正常 ModsConfig/Prefs 指纹未变。1.6 仍无游戏内证据。

证据目录：`E:/Rimbook/runs/iteration07`。初次失败证据保留在 `initial`、`rerun` 和 `mechanics-diagnostic`，修复后限定回归在 `mechanics-job-wait`，最终完整五例在 `final`。`final/audited-evidence.json` 为原始汇总加上逐例预期校验和审计字段的派生文件；`final/audit.json` 是实际只读审计结果。原始汇总保留不覆盖。各轮 `profile-plan.json` / `loaded-mods.json` / `stop.json` 保存排序、原配置指纹及进程回收证据。

临时包已移到 `runs/iteration07/archived-testpack`，文件哈希见 `archived-testpack-files.json`，最终源码/两版 DLL 和目标 1.7 DLL 哈希及进程退出审计见 `cleanup.json`。未来复跑先重新安装测试包到不存在的专用目录，仅加入一次性 profile。完整矩阵与未覆盖项见 `validation/2026-10-25-kiiro-starmoon-rerun.md`。
