# 2026-10-23 代码驱动契约验证

本文件补充旧阶段记录，不覆盖历史失败/不确定结论。项目尚未全量验收。

## 离线、编译与真机严格分开

- Python：65 项测试通过，覆盖协议、真实 MCP stdio 子进程、配置只读继承/DLC 顺序、源文件完整性、契约错误参数、红字序号溢出和跨轮累积、取消状态、无界面 Win32 子进程。mock 结果不作为游戏行为证据。
- 独立运行环境：`E:/Rimbook/.venv`，MCP 2.3.0 / Pydantic 2.14.1，editable 安装后重新跑 65 项测试、pip check 和实际安装 doctor 均通过；未依赖临时 PYTHONPATH，也未更改全局 pip 配置。实际游戏回归使用原环境的同版本 MCP，独立环境本轮只做离线/传输检查，不冒称另一次游戏验证。
- 1.6：真实引用 Assembly-CSharp 1.6.9676.17735，net472，编译 0 警告/错误；Agent SHA256 `7770b4f6bdf08c5afc5eadb5d66147101718916a44389a8ba7b766d99ee3a98b`。离线通信/有界红字日志测试在本机 .NET Framework 4.8.9363.0 通过；**未在游戏内验证**，仍缺完整 1.6 安装。
- 1.7：真实引用 Assembly-CSharp 1.7.9790.38077，net10.0，编译 0 警告/错误；Agent SHA256 `f7ac7f8a7fdd15c4d44cb7b8ceb771339ea0a1d4c63e315de16b7104f319de02`。离线通信测试在 .NET 10.0.3 通过，最新真机 run.json 与此哈希一致。
- 两个版本的已安装 Agent DLL 与工作区编译输出逐字节 SHA256 相同。构建脚本的 in_game_verified=false 表示该命令只做编译；真机证据单独按哈希对应，不由编译脚本冒充生成。

## 首轮真实 MCP：施工与效果

总证据：`E:/Rimbook/runs/1.7/mcp-validation-1792750156201395800.json`。

| 用例 | 预期 / 实际 | 证据 |
|---|---|---|
| 木墙 | passed | 真实 WoodLog×5 搬运、Frame 和施工，Tick 11 -> 459；301 次焦点采样无违规 |
| 错误材料 | blocked | MedicineIndustrial 不是木墙的正常材料，未伪造施工通过 |
| 能力实际效果 | passed | 生成独立 Pawn、GainAbility、QueueCastingJob 后目标出现指定 Hediff，施放者进入冷却 |
| 故意缺失效果 | failed（符合预期） | 实际成功施放并进入冷却，但目标无指定 Hediff；不是靠异常或红字制造失败 |

## 最新构建真实 MCP：正例、语义负例、取消

总证据：`E:/Rimbook/runs/1.7/mcp-validation-1792750851290043000.json`。服务暴露八个默认工具，实际 SDK 客户端调用 inspect_mod、run_contract、get_run、get_artifact、cancel_run；不是静态注册检查或模型厂商实测。

| 用例 | 会话 | 观察 / 结论 | 焦点采样 |
|---|---|---|---|
| ability_effect | c732e9cb45c34109a367134b7151ed2b | Tick 8 -> 188，Hediff 数量 0 -> 1，冷却峰值 120；整体 passed | 285，违规 0 |
| ability_missing_effect | 9c7b5ddc2ad64cc5908b6c58dcdec61a | Tick 10 -> 190，Hediff 始终 0，冷却峰值 120；整体 failed，正确发现无效果 | 264，违规 0 |
| ability_cancellation | 0dab97b5050e4178bd8f3208e4e2ac8c | 长观察契约运行中主动取消，外层和 Agent suite 均 cancelled，进程自动回收 | 245，违规 0 |

正常结束的正反例运行期文件错误候选和 Agent 新红字均为 0，红字序号覆盖无缺口；负例仍判失败，证明效果断言独立于“有无报错”。取消不会宣称完整观察或生成所有诊断文件。所有轮次使用自己的私有桌面与 profile，无系统鼠标/键盘注入，无前台接管；采样不能证明每个瞬时事件或所有驱动情形。

## 实际加载列表与配置审计

这些能力轮次的实际顺序如下。前五项是原有列表，后两项仅加在一次性副本；没有改正式 ModsConfig。原列表本轮未启用 DLC，不能把这次运行冒称全 DLC 组合测试。DLC 保留/不按来源过滤已做离线顺序测试。

1. brrainz.harmony
2. ludeon.rimworld
3. general.building.texture.adjustment
4. general.building.texture.adjustment.expansion.advanced
5. mingyue.deepveindrill
6. rimprobe.fixture.abilities
7. rimprobe.agent

木墙与错误材料轮次没有第六项 fixture，Agent 为第六项。每轮 loaded-mods.json 与 stop/report 均包含本轮实际完整顺序，不以本文件的示例表替代。报告也保存请求列表、增补项与源指纹。所有汇总证据的正常 ModsConfig.xml / Prefs.xml 前后 SHA256 一致，源文件终止复核 source_unchanged=true；未执行“备份后恢复”覆盖用户配置。

新安装/升级只涉及本项目的 `Mods/RimProbe` 和独立 `Mods/RimProbeAbilityFixture`，已知 Agent 升级备份在 `RimProbeBackups`，没有修改被测第三方 Mod 文件。

## 发现过的真实问题

- 首次能力真机失败：fixture 使用 CompProperties_AbilityGiveHediff 但未声明 compClass。运行时 Ability.Initialize 报 ArgumentNullException，状态采样和新增红字均捕获，契约也发现无效果；已显式补充 CompAbilityEffect_GiveHediff 后复测。
- 最后 16 条红字不是完整日志：控制器跨轮累积，检查序号缺口；覆盖缺失不允许整体通过。
- 取消外层已结束但嵌套 suite 还显示 running：已使用 Agent 取消响应更新最终报告，离线与最新真机复测均验证为 cancelled。
- Pydantic 输入字段 schema 与模型属性重名会告警：内部字段使用别名，外部仍是 schema=1；标准 stdio 参数拒绝测试不启动游戏。
- pip 的当前配置镜像不能获取构建依赖：不修改全局 pip 配置，独立安装可显式用官方索引重试，不使用不安全的 TLS 绕过。

## 可复现命令

```powershell
$env:PYTHONPATH = 'E:\Rimbook\src'
python -m unittest discover -s E:\Rimbook\tests -q
python E:\Rimbook\scripts\verify-live-mcp.py --game 'D:\Steam\steamapps\common\RimWorld' --runs E:\Rimbook\runs\1.7 --contracts-only --include-cancel --execute-live
```

上面显式启动三个后台游戏；移除 contracts-only，改用 include-contracts/include-negative 可同时跑施工正负例。须先编译/安装 Agent，并显式安装独立能力 fixture，不更改正常启用列表。

## 尚未覆盖

1.6 真机、前台玩家游戏同时运行的资源开销、全部 Mod 组合、完整无 Agent 对照、确定性地图、物品使用、缺料/不可达恢复、电网/生产等功能适配、UI/VFX、存读档、非原版 Ability 框架和任意自定义语义。除 Hediff 添加与冷却外的其他观察器目前只有实现/编译覆盖，不能冒称已做真机效果回归。MCP 标准客户端互操作不等于已测试 DeepSeek 等所有模型。
