# 2026-10-23：通用组合计划验证

本轮交付是机制级操作/观察与可组合计划，不再以逐个建筑、物品或能力添加固定 recipe 为主路线。相同正常入口的新 Def 使用相同 Agent，通过改变声明式步骤/断言进行测试。全新机制仍可能需要新增通用原语；不是任意反射执行，也不是整个项目已完成。

## 分层验证

- 112 项 Python 离线测试通过，pip check 与 compileall 通过；包含严格 JSON、预算/枚举、别名/类型/前向引用、fixture 边界、测量基线、错误输入不启动、SDK schema、独立 JSON-RPC 客户端拒绝非法计划。
- 1.6：真实归档 Assembly-CSharp/Unity/Harmony 引用，net472 编译零警告/错误；C# 预检与通信在本机 .NET Framework 4.8.9363.0 通过。不是游戏 Mono 实测；缺完整可启动安装，继续延期。
- 1.7：本机 1.7.4985 rev1269，真实 Assembly-CSharp/UnityStubs/Harmony 引用，net10.0 编译零警告/错误；C# 预检/通信在 .NET 10.0.3 通过；另有以下真正 Waylith 游戏与 MCP stdio 证据。
- 1.6 Agent SHA256：ce84a75b0dc4ce78c12e1bb6bafce4298bdcbcd9041991a6e86944a611ee5356。
- 1.7 Agent SHA256：9e0faca13dbf7e163d076b5aa25f5a3941e4911547e7197bc4794cebc94cbe5d。

构建依据在根目录 build-evidence-1.6.json / build-evidence-1.7.json，未把 in_game_verified 编译字段改为真机证明。真实运行记录单独保存在 runs；后续 DLL 被替换时必须选对应历史构建重新审计。

## 实际 MCP 结果

主汇总：runs/1.7/mcp-validation-1792758397968834200.json；补充：runs/1.7/mcp-validation-1792758926245490600.json。两者 verification_complete=true，所有 checks_validated=true，full_acceptance=false。分别通过只读审计并生成同编号 mcp-audit 文件。

下表目录均相对于 runs/1.7：

| 用例 | 实际状态 | 详细报告 |
|---|---|---|
| ability_effect | passed | 0728d6064ad14456bf8678144af62585/report.json |
| ability_missing_effect | failed | f7f695f2f897431899e00b10af8345b2/report.json |
| ability_cancellation | cancelled | 031733d58b634de5a6baf2dcab704901/report.json |
| plan_ability-marker | passed | 47174f3afef640d6bbbb6512476e53b1/report.json |
| plan_item-marker | passed | ebf56e8e7d0e463599be6b4ac25d9698/report.json |
| plan_equip-and-move | passed | 06f7ed7d66be40f890124325fb2be116/report.json |
| plan_build-power | passed | eea6570881db4d7c87502bc0bb8e391e/report.json |
| plan_discovery | inconclusive | 39da63bf479244afb645213cf3a183e2/report.json |
| plan_missing_effect | failed | 7884b9f829d742ecbd3b18c192eac670/report.json |
| plan_cancellation | cancelled | c1e25bd125a94407b20e1edc43d66cfc/report.json |
| plan_find-and-measure | inconclusive | 85cc51f8108a48c8b5c57ff305ed613f/report.json |
| plan_zero_power | failed | 12dc95acb77a417d8dd2d6e9535f7e06/report.json |

- 能力组合：准备两个 Pawn/授予能力 -> inspect -> measure 指定 Hediff 数量 -> 正常 cast -> wait_assert 增量 >=1。正例基线 0、实际/增量 1；仅将 grant/cast Def 改为无效果能力，正常施放仍 requested，但断言增量 0，整体 failed；没有增加专用负例 C#。
- 摄入组合：实际食物值从 0.25 到 1（增量 0.75），同一餐 destroyed=1，指定 marker 数量增量 1。普通 Ingest Job requested 不直接判通过；这些断言本身不代替 item_ingest 快捷契约的精确 Ingested 入口观察。
- 装备/移动组合：地面 Gun_Autopistol -> 正常 Equip -> 实际装备成员断言 -> 正常 Goto -> 与目标 Pawn 实际距离 1，末次 inspect 仍有该武器。
- 建造/发电组合：真实蓝图、Steel×5 地面材料、HaulToContainer、Frame、FinishFrame、实际成品；随后独立通用 power.watts >=90、连续采样保持 120 Tick、真实 PowerNet 成员断言。正例输出 100W；只换成零输出 Def，依然正常完成施工，但输出为 0，功率断言 failed，后面的步骤不再执行。
- 发现：读取实际已加载 AbilityDef/ThingDef；另例以 Def/范围查找到刚生成的武器，其 thing_id 与生成步骤一致，inspect/measure 真实耐久 100。两者无功能断言，整体 inconclusive，不能将发现完成视为功能通过。
- 取消：旧能力观察和新通用 wait 均通过 MCP 请求取消并完成所属 worker 清理。取消路径没有最终 diagnostics 的情况在审计中明确列出，不能称为完整最终日志检查。

## 隔离、兼容和效率

共 3460 次前台采样，零记录违规；两份汇总的正常 ModsConfig.xml / Prefs.xml 前后哈希相同，各轮 source_unchanged=true，所属后台游戏均已回收。不能据此证明所有驱动/弹窗、前台游戏并行性能或无限 Mod 组合完全无影响。

继承的实际原有顺序（没有修改正常配置）：

1. brrainz.harmony
2. ludeon.rimworld
3. general.building.texture.adjustment
4. general.building.texture.adjustment.expansion.advanced
5. mingyue.deepveindrill

除 plan_cancellation 外，本轮显式追加 rimprobe.fixture.abilities，再追加 rimprobe.agent；plan_cancellation 只追加 rimprobe.agent。原有启用列表没有 DLC；DLC 顺序保留由离线测试覆盖，不将此次真机称为全 DLC 验证。各轮 loaded-mods.json / report.json 保存完整顺序。其他 Mod 私有设置没有复制到一次性 profile。

主汇总 59 次工具调用、225311 字节响应文本；补充 13 次、53593 字节。共 72 次、278904 字节，包含启动/轮询/取消/取完整证据；这些数字不是 token 数或全模型测试。模型一次提交整份计划，由主线程状态机自主推进，不逐步截图或注入系统鼠标。

## 踩坑与未完成证据

第一次对象查找补测 runs/1.7/mcp-validation-1792758780594403000.json 保持 verification_complete=false。其游戏计划正确返回 inconclusive，查找到精确武器对象；验证脚本却把 Pawn.HitPoints 当成健康值要求 >0，实际是 -1。修正样例为测量找到的武器耐久，并用 inspect 的同一对象耐久交叉核对。未改旧文件为通过，未改 Agent 游戏状态制造预期。

Power/Job 状态仍按 Root.Update 采样，不承诺每 Tick 捕获。quicktest 地图与自然 Pawn 行为仍有随机性。多次动作的因果解释取决于源码、显式前置条件和独立断言，不能由没有红字直接推断；任意第三方框架、自定义 UI、生产/燃料、存读档和 1.6 真机等门禁仍见 ACCEPTANCE_STATUS.md。

## 复现

只启动第五轮九个通用计划（选择 --only 避免无意重复历史 recipe）：

```powershell
./.venv/Scripts/python.exe scripts/verify-live-mcp.py --game D:/Steam/steamapps/common/RimWorld --runs E:/Rimbook/runs/1.7 --iteration-five --include-cancel --only plan_ability-marker plan_item-marker plan_equip-and-move plan_build-power plan_discovery plan_find-and-measure plan_missing_effect plan_zero_power plan_cancellation --execute-live
```

已完成证据审计不启动游戏：

```powershell
./.venv/Scripts/python.exe scripts/audit-live-evidence.py --evidence E:/Rimbook/runs/1.7/mcp-validation-1792758397968834200.json --agent-root E:/Rimbook/mod --game D:/Steam/steamapps/common/RimWorld
```
