# 第三轮：缺料恢复、摄入与真实 UI 验证

日期：2026-10-23。证据层次严格分开：83 项 Python 离线测试、两版真实引用编译、两版独立运行时通信测试、1.7 实际游戏 MCP 验证。不是全项目验收，也不是 1.6 真机证明。

## 当前构建

- 1.6: `net472`，真实 Assembly-CSharp `1.6.9676.17735`；Agent SHA256 `b77b3f9464e3c0b29821ecca35ed5eae080ec79b24ea66a9c8a6643dc54a7e5f`。
- 1.7: `net10.0`，真实 Assembly-CSharp `1.7.9790.38077`；Agent SHA256 `6a94fa6010dad1894cf4e6fc749ce4e20df475ea42d70bf41c3e891d3160e886`。

两版编译均 0 警告、0 错误；输出/引用/obj 分离。1.6 额外引用真实 UnityEngine.IMGUIModule，用于 Event/Repaint；不向 mod 目录打包游戏/Harmony DLL。已核对本地构建、安装的所属 Agent 和下列九轮 run.json 的 Agent 指纹一致。

Python 测试包括原有控制器/协议/日志与新增 item/UI schema、参数边界、归一化幂等、缺料参数转发、有界长轮询、Win32 资源采样/退出等待和独立 JSON-RPC 客户端。MCP SDK 客户端和不用 SDK ClientSession 的 wire 客户端都通过；不冒称已测试特定 Flash 模型。pip check 通过。

1.6 net472 离线程序实际运行于本机 .NET Framework 4.8.9363.0；1.7 离线程序实际运行于 .NET 10.0.3。两者均未在离线测试中创建游戏对象或调用引擎原生方法。完整 1.6 游戏仍不可用。

## 九轮真实游戏

完整汇总：`runs/1.7/mcp-validation-1792753363213299800.json`，`verification_complete=true`，九轮 `checks_validated=true`，`full_acceptance=false`。全部使用 1.7.4985 rev1269、独立 profile、Win32 私有桌面，通过实际 MCP stdio 运行；所有后台进程完成回收。

负例的 failed、错误材料的 blocked、取消的 cancelled 是各自预期，绝不改成 passed。耗时含启动/生成地图，不是纯动作延迟；内存为所属整个游戏进程 OS 峰值工作集，不是 Agent 增量或 GPU 占用。

| 用例 | 实际结果 | 所属进程墙钟秒 | 峰值工作集 MiB | 会话 |
|---|---|---:|---:|---|
| wall_construction | passed | 33.2 | 1658.9 | `dc9d8b4fd5eb4b1c804ccbcab449c553` |
| invalid_material | blocked | 28.4 | 1675.2 | `b94dcab232804ec899febb765a4d231a` |
| ability_effect | passed | 28.2 | 1604.6 | `62b41d148b3444769cc59f695a88fb0e` |
| ability_missing_effect | failed | 28.6 | 1606.8 | `d012aee092f64ab09e9532f7c076dca6` |
| ability_cancellation | cancelled | 30.3 | 1579.4 | `4aed45f0249d404a9b198a13e4257111` |
| wall_supply_recovery | passed | 33.9 | 1680.5 | `ff3e458d50e045d290c9bb16e65b838d` |
| item_effect | passed | 40.3 | 1633.9 | `443386588ed249f192a19427352ac617` |
| item_missing_effect | failed | 41.4 | 1621.5 | `b1bb06edabed43c49fea6757b86dc89b` |
| ui_info_card | passed | 28.2 | 1630.6 | `8d1aa8d87ff94d548238598b9ca89618` |

- 木墙：观察正常设计器、地面 WoodLog×5、HaulToContainer、Frame 资源/真实工作量、FinishFrame、成品初始化；404 Tick 完成。
- 缺料：180 Tick 无材料交付/工作，189 Tick 才放地面供应，继续真实搬运与完工，总 438 Tick。本轮原有同类可用堆叠为 0；已有栈禁止/恢复分支实现存在，但不声称本轮覆盖非零原栈情况。不是不可达恢复或任意建筑功能测试。
- 能力：新女 Pawn 授予 AbilityDef 后经普通 QueueCastingJob，正例实际 Hediff/冷却满足；故意无效果 Def 虽有冷却，Hediff 断言正确 failed。
- 摄入：普通 Ingest 作业 + 精确物品的 Ingested 完成记录。正负例都真实消耗/增加营养，只有正例产生 marker；缺效果负例 failed，不直接调用 Ingested/Apply 或赋予期望结果。
- UI：真实信息卡完成 321 次 Repaint，Rect=(236,64,950,760)，实际逻辑屏幕 1422×889，打开/绘制/边界/关闭都通过。Tick 不增长是窗口暂停，不是没执行；墙钟观察仍有效。未验证像素和鼠标命中。

## 隔离、排序与效率

累计 2744 次前台采样，无测试 PID 违规；未发送系统鼠标/键盘输入。所有运行 source_unchanged=true，正常 ModsConfig.xml/Prefs.xml 前后 SHA256 一致。焦点采样并非对所有瞬态/驱动行为的数学证明。

全部继承的原始顺序：

1. brrainz.harmony
2. ludeon.rimworld
3. general.building.texture.adjustment
4. general.building.texture.adjustment.expansion.advanced
5. mingyue.deepveindrill

施工、错误材料、缺料和 UI 追加第 6 项 rimprobe.agent。能力/摄入轮次追加第 6 项 rimprobe.fixture.abilities、第 7 项 rimprobe.agent。每轮实际完整顺序在 loaded-mods.json、stop.json 和最终报告中。原配置没有启用 DLC，所以本轮不是全 DLC 真机证明；不按来源排除 DLC，保留行为另有离线覆盖。私有 Mod 设置未自动克隆。

九轮含诊断共 55 次工具调用，get_run 34 次；文本响应合计 170763 UTF-8 字节，未换算或宣称 token 数。使用 wait_seconds=10，不需要模型逐 Tick/截图指挥。数据包含九份完整 report.json 和源码候选，不是最小摘要开销。

CPU 为所属进程累计多核 CPU 秒，内存附最后存活采样时刻；它们不能证明 Agent 空闲增量、GPU 占用、与玩家游戏并行的帧时间或零资源影响。

## 保留的失败与修复依据

- `runs/1.7/42cbd729a75f48ce8e07cfff6fcb71bb/report.json`：真实 UI 绘制成功但逻辑 1138×711 放不下高 760 的信息卡，window_in_bounds 正确 failed。只提高 UI 独立 profile 分辨率，不改窗口/断言或玩家 Prefs。
- `runs/1.7/68b796a3446441cbb8215b80a0124423/report.json`：施工供材后停滞，预算超时 inconclusive。源码确认 JobMaker 使用对象池且 Clear 重置 loadID；引用相同不代表同一次作业，现改保存发出时唯一 loadID。此失败保留，不重写成通过。
- `runs/1.7/mcp-validation-1792753066022949100.json`：前五例正确，缺料轮次无安全位置 blocked，检查点 verification_complete=false。原选址只朝单侧，现改双向有界半径 60，且不删除地面物/建筑，不在旧材料堆上放新供材。随机地图仍不是确定性 fixture。
- Win32 Job 关闭后子进程异步退出造成临时日志占用：回收流程等待所属进程结束再关句柄/桌面，离线重复测试及新九轮回收通过。

## 复现

先按 README 编译/安装所属 Agent，并验证 fixture 自有目录后安装 fixtures/AbilityContract，不更改正式启用列表：

```powershell
E:/Rimbook/.venv/Scripts/python.exe -m unittest discover -s E:/Rimbook/tests -q
E:/Rimbook/.venv/Scripts/python.exe E:/Rimbook/scripts/verify-live-mcp.py --game D:/Steam/steamapps/common/RimWorld --runs E:/Rimbook/runs/1.7 --include-contracts --include-negative --include-cancel --iteration-three --execute-live
```

后一条明确启动九个顺序执行的后台测试游戏。只复测 UI 可加 `--only ui_info_card`；只复测恢复可加 `--only wall_supply_recovery`。`--execute-live` 不可省略。每轮先保存汇总检查点再断言，部分中断不算全套通过。

## 未完成项

完整 1.6 游戏内验证、固定场景、非零原材料堆恢复专项、不可达恢复、自定义建筑功能、存读档/长期生命周期、更多物品动作、自定义 UI/像素命中、前台玩家游戏并行性能、全面无 Agent 对照及模型/商业客户端矩阵。参见 `../ACCEPTANCE_STATUS.md`；不将本轮完成标成全项目完成。
