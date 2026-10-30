# 编译式测试包

可直接复制并构建的双版本 [最小模板](../testpacks/Template/README.md) 已提供；默认返回 inconclusive，需补真实业务动作/observer 后才能有功能通过。两个独立 Def 的可执行机制样例见 [InteractionFixtures](../testpacks/InteractionFixtures/InteractionFixtures.cs) 与 [交互协议](interactions.md)。

RimProbe 的通用计划继续负责 Pawn、物品、建造、施放、数值观察。剧情、专用窗口及自定义组件无法由现有数值属性表达时，可以增加独立测试包；不需要把每个 Mod 的逻辑写进 Agent。

## 契约

测试包引用对应版本的 `RimProbe.Agent.dll`，实现 `IProbeTest`：

- `Start(Map)`：声明并准备一次性测试场景。
- `Pump()`：在游戏主线程有界推进正常动作并观察结果；不能循环阻塞等待。
- `Report`：状态、阶段、测试范围及结构化检查。
- `Dispose()`：结束、失败或取消时清理自己的对象、窗口和交互状态。

通过 `RegisteredProbeTests.Register("owner.feature", factory)` 显式注册。无 `RIMPROBE_SESSION_ID` 时注册不生效。MCP 无法上传、编译或执行任意代码，不能指定类型/方法/字段；只可选择已安装可信测试包注册的 key。测试包本身是游戏内代码，需要开发者审查，与其他已安装 Mod 具有相同的进程权限，不是代码沙箱。

```json
{
  "schema": 1,
  "intent": "按实际源码验证一个功能",
  "steps": [
    {"id": "discover", "op": "query_tests"},
    {"id": "verify", "op": "registered_test", "key": "kiiro.mechanics"}
  ],
  "max_ticks": 120000,
  "timeout_seconds": 180
}
```

用 `rimprobe_run_plan` 提交，`extra_mods` 顺序为 `["rimprobe.agent", "rimprobe.tests.starmoon"]`。正常玩家配置不加入测试包。注册上限 64、key 最长 80 字符、每项最多 64 个检查；整个计划证据仍受 40 KB 限制。注册测试声明 passed 时必须具有检查且所有检查成功，空结果不作为成功。

实际 StarMoon 测试包在 `testpacks/StarMoon`。其固定回调仅引用用户自己的 Mod：技能通过正常 `QueueCastingJob`；读信封通过正常 Job；剧情选择和时停目标通过预先编译的固定回调。后两者验证语义入口，不验证鼠标命中。调试时间、背景、等级、资源和伤口属于准备，不算自然成长、生存或日历等待的验收。

## 运行和证据

先独立编译目标 Mod、Agent、测试包的相应版本。临时复制测试包到一个不存在的 Mod 目录，运行：

```powershell
E:\Rimbook\.venv\Scripts\python.exe E:\Rimbook\scripts\verify-starmoon.py
```

脚本通过真实 stdio MCP 运行五个独立用例：mechanics、envelopes、stay_star、return_moon、negative_control。每个用例建立新 profile 和私有桌面，并由服务器回收进程。故意缺失效果的负例应失败；不能把负例失败当作功能失败或把动作成功当作断言成功。

遇到启动失败，脚本保存检查点并停止后续相同依赖的用例。`verification_complete=false` 表示未跑完。启动失败也要读取 `startup.json`、`state.json`、`loaded-mods.json`、`stop.json`，不要只读最后几行日志。

`serve --diagnostic-mod-mismatch` 为显式诊断开关：保留请求列表，记录游戏实际加载列表，允许在不同环境下收集检查；总体结果固定 blocked，不能作为请求环境的兼容性通过。默认仍在排序不一致时阻止动作。此开关不会启用、禁用、排序、补丁修改或绕过游戏对 DLC 的原生判断。

第六轮曾试验一次原版 Play 场景重试，但当时组合没有恢复主线程，因此已移除这条失败的重试代码，历史证据仍保留。第七轮 DLC 恢复后，原有 quicktest 正常生成地图，无需增加场景重试。当前启动诊断记录窗口类型、quicktest 参数及注册 key，不采集任意窗口文字，不自动切换场景。

有自定义窗口的计划可明确传入 `display_profile: "ui"`，使用私有 1600×1000 / scale 1 profile；默认仍为 simulation。物理尺寸不代表实际逻辑屏幕尺寸，窗口测试必须观察实际边界，不能只信启动参数。

## 当前边界

2026-10-29 第九轮：通用计划将 `primary_failure` 与 `cleanup_failures[]` 分开，记录异常类型、有界消息/堆栈（最多 400/1000 字符）、最多三层异常链、step_id/test_key、调用生命周期和测试包内部 phase。生命周期为 factory/start/pump/report/dispose，以及 construction_cleanup/job_cleanup；未知异常的 failure_domain 保留 unknown，不根据 CLR 类型或堆栈猜测责任 Mod。仅执行器显式识别的领域前提/不支持返回 blocked/unsupported，未知 InvalidOperationException/NotSupportedException 返回 failed。

测试包报告在 Dispose 前经过校验并复制所有 checks，不再共享测试包的可变列表。Dispose 仅尝试一次，异常独立保留，其他施工/作业清理继续；最多保留四条清理异常。超限和报告证据裁剪会标记 failure_evidence_truncated / diagnostics_omitted，不宣称完整堆栈。上述行为已做双版本离线故障注入与真实引用编译；尚无此构建的真机回归，不能用离线证明 Waylith/Mono 全流程通过。

双版本 Agent、目标 Mod 和测试包的编译分别记录；1.6 缺完整安装，不能写成游戏内已验证。第六轮因 DLC 未加载受阻的历史结论保留在 `validation/2026-10-25-kiiro-starmoon.md`；第七轮实际复跑状态见 `ITERATION_07.md`。

`verify-starmoon.py` 将“清单跑完”与“结果符合预期”分开：`verification_complete` 仅表示指定清单已跑完；`checks_validated` 要求正例通过、负例仅缺失指定 marker、启动/运行错误候选为零、原配置指纹不变、焦点无观察违规且有回收证据。所有结果符合预期时，再运行现有 `audit_evidence` 对照落盘报告、实际排序、诊断覆盖与 Agent 构建哈希。审计是只读一致性检查，不是防篡改签名或独立游戏复验。

第七轮修复两项测试准备错误：Time 类型的 `TimeInBed` 不允许 `records.AddTo`，因此仅在可信测试包中为新 Pawn 准备记录初值；连续施放要根据 `CurJob.ability` 等待上一 Job 退出，不能只依赖 `JobDef.abilityCasting`。效果发生不是作业已结束；通过补写结果、强制停止作业或屏蔽红字来制造通过均不可接受。能力用例另包含三次传送和正常取消技能的状态清理断言。
