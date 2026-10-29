# RimProbe：其他项目与 Agent 首次测试说明书

公开仓库读者请先使用 [跨机器快速上手](GETTING_STARTED.md) 与 [通用 MCP 配置](../examples/mcp-portable.json)。本说明书的 E:\Rimbook 等绝对路径是原开发机示例，需替换为本机路径；历史运行目录不随源码发布。

更新：2026-10-29。根据当前项目接口编写；最新已记录真机证据来自 2026-10-25，本次编写说明书没有重新启动游戏。适用本机 Windows 环境。

本次文档核对：5 段 JSON 均可解析，技能示例通过实际 plan 校验器，配置与独立示例文件一致，6 个相对文档链接有效，并通过已安装 MCP SDK 核实默认九工具名称。该核对不属于目标 Mod 的游戏测试。

## 1. 直接交给另一个 Agent 的介绍

复制下面这段，再填写目标项目路径即可。使用前需要按第 2 节接入 MCP。

```text
请用 RimProbe MCP 为当前 RimWorld Mod 做首次运行测试。

项目位置：<填写你的项目或 Mod 绝对路径>
允许阅读及修改的代码范围：<填写；默认只限本项目，不读取其他 Mod 源码>
本次重点：<填写本次新增或修改的功能；请结合实际代码推导测试条件和效果>
RimProbe 说明书：E:\Rimbook\docs\AGENT_QUICKSTART.zh-CN.md

RimProbe 是后台运行真实游戏的测试工具。它通过游戏内 Agent，在主线程准备
一次性 Pawn/物品/建筑，执行正常游戏动作并读取状态，避免截图和鼠标点击。
它不负责反编译；请结合当前源码、Def，必要时用 RimSage 确认原版 API。

请依次执行：
1. 调用 rimprobe_doctor、rimprobe_capabilities，读取当前工具 JSON Schema。
2. 确认游戏版本、被测 DLL/Defs 的实际部署位置、packageId 及依赖。
   extra_mods 只引用已安装包，不会自动安装项目、编译代码或解析所有依赖。
3. 根据实际代码列出前置条件、正常动作、独立效果断言及未覆盖项。
   优先 rimprobe_run_plan；标准施工可用 rimprobe_run_suite。
4. 使用 profile_mode="inherit"，保留用户启用的 Mod/DLC 及相对顺序。
   不修改正常 ModsConfig、Prefs、Mod 设置或存档；只使用本轮 profile。
5. 提交后保留 run_id，用 rimprobe_get_run(run_id, wait_seconds=10)
   等待 controller_finished=true；同时要求 cleanup_status="succeeded" 且
   owned_process_exit_verified=true 才能确认回收成功。cleanup_complete 仅为旧版
   “清理尝试结束”别名；不要只看到 requested 或地图就绪便宣布通过。
6. 读取需要的 report.json、startup.json、diagnostics.json、loaded-mods.json、
   profile-plan.json、stop.json。核对业务断言、新红字、排序、配置指纹和回收。
7. 若失败，先检查 failure_context、前置条件、当前作业和日志再决定是否修改代码。
   不注入预期效果、不强制完工、不放宽断言、不屏蔽新红字来制造成功。
8. 如测试中修复了本项目，重新编译并部署，确认旧测试进程退出后开启新一轮。
   保留失败证据。最终报告实际加载顺序、测试证据、修复、复跑和人工检查项。

所有游戏测试必须保持私有桌面后台运行，不抢系统鼠标、键盘和前台焦点；
不能附加或关闭我的正常游戏进程。缺少通用动作/属性时明确报告 unsupported
或未覆盖；复杂剧情可研究可信编译式测试包，但不得虚构现有 MCP 能力。
当前 1.7 有限定真机证据；1.6 仅有独立编译和离线证据，不能混为一谈。
没有红字、成功编译、冷却开始或建筑生成，都不能替代真实功能断言。
```

## 2. 接入 MCP

当前本机路径：

| 用途 | 路径 |
|---|---|
| RimProbe 项目 | `E:\Rimbook` |
| 已安装 Python 环境 | `E:\Rimbook\.venv\Scripts\python.exe` |
| 当前使用的游戏安装 | `D:\Steam\steamapps\common\RimWorld` |
| 游戏内 Agent Mod | `D:\Steam\steamapps\common\RimWorld\Mods\RimProbe` |

向目标 MCP 客户端添加一个 **stdio** 服务器。支持 `mcpServers` 格式的客户端可使用下面配置；其他客户端填写相同的 command 和 args，配置文件位置按客户端文档确定。

```json
{
  "mcpServers": {
    "rimprobe": {
      "command": "E:/Rimbook/.venv/Scripts/python.exe",
      "args": [
        "-m", "rimprobe",
        "--game", "D:/Steam/steamapps/common/RimWorld",
        "--runs", "E:/Rimbook/runs/external-first-test",
        "serve"
      ]
    }
  }
}
```

可复制文件：[examples/mcp-first-test.json](../examples/mcp-first-test.json)。建议把 `external-first-test` 换成自己项目的英文标识，让各项目报告分开保存；单轮会再生成独立 session 子目录。使用绝对路径，不需要把另一个项目的工作目录改成 RimProbe。

保存后让客户端重新加载 MCP，确认可列出第 4 节的九个工具。客户端可能给工具名添加服务器前缀，以其实际公布的名称为准。客户端单次工具请求超时应大于 15 秒；游戏启动和测试进度通过多次有界轮询取得，不需要让一次工具调用挂住几分钟。

如果需要指定其他测试排序，在 `serve` 之前增加全局参数 `--mods-config` 和一个准备好的测试 `ModsConfig.xml` 绝对路径；源文件只读，运行时仍复制到独立 profile。默认从正常玩家 ModsConfig 继承，**只继承启用列表及顺序，不复制各 Mod 自定义设置或玩家存档**。依赖自定义设置的功能不能据此宣称已按玩家环境复现。

不要直接照搬 `examples/mcp.json` 的全部配置：其中 1.6 路径 `D:/Games/RimWorld1.6` 是示例。本机没有已验证可启动的完整 1.6 安装；取得独立完整安装后再另配服务，使用对应 1.6 Agent，不自动切换当前 Steam 游戏版本。

## 3. 第一次运行前检查

1. 调用 `rimprobe_doctor`，确认当前游戏版本及真实引用指纹；调用 `rimprobe_capabilities`，确认支持的动作/属性和限制。这两项不启动游戏，doctor 不等于完整运行环境验收。
2. 被测 Mod 必须已部署到游戏能发现的位置，且该版本的 DLL、Defs、贴图均为本次构建。只改另一个工作目录里的源码并不会让游戏加载新版本。
3. 从被测 Mod 的 `About/About.xml` 获取真正的 `packageId`。`extra_mods` 使用 packageId，不能填文件夹中文名、DLL 名或路径。缺少的依赖也必须已安装，并按正常加载顺序提供。
4. Agent 必须已安装并匹配游戏版本。**不需要在正常玩家排序里启用它**；控制器在临时 profile 中补入。已安装且一致时无需反复重装或重编译 RimProbe。
5. 默认串行执行，一次测试完成并回收后再开始下一次；不要为同一次测试同时打开多个 MCP 服务实例。

仅当 Agent 缺失或确实需要更新时，在终端执行；命令不会启动游戏：

```powershell
& E:\Rimbook\.venv\Scripts\python.exe -m rimprobe `
  --game D:\Steam\steamapps\common\RimWorld `
  install-agent --mod-source E:\Rimbook\mod
```

若目标已存在而命令拒绝覆盖，先核对安装归属和内容；确认是可更新的 RimProbe 自有安装后才用 `--update-owned`。它会校验清单并备份，不要通过手动覆盖未知文件绕过拒绝。源码、参考 DLL 或编译产物不匹配时，先按 README 的分版本构建说明处理。

`rimprobe_inspect_mod` 可读取被测目录的有界 `.cs`/`.xml` 提示，但不反编译 DLL，不执行代码，也不完整解析继承或证明行为正确；出现截断时继续查看所需源码。只向它传入你被允许阅读的目录。

## 4. 九个工具怎么选

| 工具 | 用途 |
|---|---|
| `rimprobe_doctor` | 无启动检查游戏版本与程序集指纹 |
| `rimprobe_capabilities` | 无启动读取当前动作、属性、配方及限制 |
| `rimprobe_inspect_mod` | 读取授权项目源码/Def 的候选提示 |
| `rimprobe_run_plan` | 主入口：组合准备、正常动作和效果断言，自动启动后台游戏 |
| `rimprobe_run_suite` | 标准建筑放置、供材、搬运和施工；可声明延迟供材 |
| `rimprobe_run_contract` | 现有快捷配方：发电、标准能力、摄入、信息卡 UI |
| `rimprobe_get_run` | 读取本实例当前测试进度，有界长轮询 |
| `rimprobe_get_artifact` | 根据返回的 artifacts 名单读取指定证据 |
| `rimprobe_cancel_run` | 请求取消；仍须继续轮询直到完成回收 |

普通首次测试不需要高级工具，也不需要自己先手动启动游戏。服务器不会附加到已经运行的玩家游戏；每个计划会新开一次后台游戏和一次性地图。run_id 由当前 MCP 实例管理，不支持重启服务后凭旧 run_id 恢复会话；旧证据仍在磁盘。

## 5. 按实际代码设计测试

先写清楚四件事：**什么初始状态 → 执行哪个正常动作 → 读取什么真实变化 → 如何区分成功与失败**。

| 被测改动 | 可用路线 | 需要额外确认 |
|---|---|---|
| 标准建筑 | run_suite，或 plan 的 build 后加断言 | 建成不证明自定义功能；再检查供电/效果等 |
| 标准 AbilityDef | 新建 Pawn → 授予能力 → measure → cast → wait_assert | 资源、种族、目标、昼夜等前置条件以源码为准 |
| 摄入物品 | 新建 Pawn/物品 → measure → ingest → 营养/效果断言 | destroyed 不能单独证明吃下；精确摄入证据可用 item_ingest |
| 武器装备 | 新建 Pawn/物品 → equip → pawn.equipped 断言 | 证明装备，不代表射击/弹药/伤害功能已测 |
| 发电建筑 | 正常施工 → 稳定采样 power.watts/power.connected | 燃料供应、消费端和生产账单未由此覆盖 |
| 信息卡 | ui_info_card 配方 | 真实打开/绘制/边界/关闭，不代表像素和命中正确 |
| 专用技能框架、剧情或自定义组件 | 先检查已有原语；必要时独立可信测试包 | 不假设能远程调用任意字段或方法 |

### 示例 A：建筑初步施工测试

调用 `rimprobe_run_suite`，参数如下。先将两个大写占位值替换为目标真实 Def；不需材质的建筑可省略 `stuff_name`。

```json
{
  "def_name": "YOUR_BUILDING_DEF",
  "stuff_name": "YOUR_ALLOWED_STUFF_DEF",
  "extra_mods": ["your.actual.packageid"],
  "profile_mode": "inherit",
  "timeout_seconds": 180,
  "max_ticks": 60000,
  "supply_delay_ticks": 180
}
```

该项验证正常放置、蓝图、地面材料、真实搬运、Frame 和施工；延迟供材用于观察缺料停滞后恢复。它不会直接填满 Frame 或瞬间造出成品，也不能自动验证任意建筑的特殊功能。初次排查可将 supply_delay_ticks 设为 0，先测基本施工再单独测恢复。

### 示例 B：标准技能产生 Hediff 效果

调用 `rimprobe_run_plan`，参数如下。替换 packageId、能力和 Hediff 的真实 DefName；若要求特定种族/职业，在 spawn_pawn 中填实际 PawnKindDef。默认 Colonist 并不满足所有 Mod 条件。

```json
{
  "profile_mode": "inherit",
  "extra_mods": ["your.actual.packageid"],
  "plan": {
    "schema": 1,
    "intent": "按实际源码：正常施法应使目标指定 Hediff 数量至少增加 1，并等待施法 Job 结束。",
    "max_ticks": 12000,
    "timeout_seconds": 180,
    "steps": [
      {"id": "create_actor", "op": "spawn_pawn", "bind": "actor"},
      {"id": "create_target", "op": "spawn_pawn", "bind": "target", "near": "actor", "distance": 5},
      {"id": "grant", "op": "grant_ability", "actor": "actor", "def_name": "YOUR_ABILITY_DEF"},
      {"id": "before", "op": "measure", "target": "target", "property": "pawn.hediff_count", "def_name": "YOUR_EFFECT_HEDIFF", "bind_value": "before_count"},
      {"id": "use", "op": "cast", "actor": "actor", "target": "target", "def_name": "YOUR_ABILITY_DEF"},
      {"id": "effect", "op": "wait_assert", "target": "target", "property": "pawn.hediff_count", "def_name": "YOUR_EFFECT_HEDIFF", "relative_to": "before_count", "compare": "ge", "value": 1, "ticks": 1200},
      {"id": "finished", "op": "wait_assert", "target": "actor", "property": "pawn.ability_casting", "compare": "eq", "value": 0, "ticks": 1200}
    ]
  }
}
```

这只适用于真正新增该 Hediff 的技能。若原理是提高已有 Hediff 的 severity，数量不一定变，不能套用此断言。伤害可使用 `pawn.injury` 增量，解除状态可比较数量减少；未知私有资源字段不能凭空编成 property。

测试本机工具链本身时可参考 `E:\Rimbook\examples\plans`，但其中部分使用 `RimProbe_Fixture*`。自带 fixture 已从游戏 Mods 目录移出，不要给普通目标 Mod 测试无条件附加 `rimprobe.fixture.abilities`。

### 步骤与属性速查

- 准备：`spawn_pawn`、`spawn_item`、`fixture_hediff`、`grant_ability`。必须在第一条动作、测量、等待或断言之前完成；不能在施法后手动补上预期 Hediff。
- 动作：`cast`、`ingest`、`equip`、`move`、`build`。动作 requested 只是已请求，随后必须独立观察效果。
- 发现与测量：`inspect`、`find_thing`、`query_defs`、`measure`；测试包用 `query_tests`/`registered_test`。
- 控制：`wait`、`assert`、`wait_assert`。优先等待明确状态，避免大段固定空等。
- 常用属性：`spawned`、`destroyed`、`stack_count`、`hp`；`pawn.dead`、`pawn.downed`、`pawn.stunned`、`pawn.food`、`pawn.injury`、`pawn.hediff_count`、`pawn.ability_cooldown`、`pawn.ability_casting`、`pawn.equipped`、`pawn.distance_to`；`power.watts`、`power.connected`。

`bind` 是本轮对象别名；`bind_value` 是数值别名。引用必须先声明且不能重绑定。actor 必须来自本轮 spawn_pawn，不能给 find_thing 找到的任意 Pawn 下达动作。

`relative_to` 表示“当前值减先前 measure 的值”；比较符为 eq/ne/gt/ge/lt/le。只有 hediff_count、ability_cooldown、equipped 需要额外 def_name；distance_to 需要 other 对象别名。`hp` 不可当作 Pawn 健康条，应观察 injury/downed/dead。

连续施法先断言效果，再等待 `pawn.ability_casting=0`；该值不证明冷却就绪或队列为空。`hold_ticks` 仅代表采样期间保持满足，不保证每 Tick 都采到。

计划最多 24 步、含默认字段不超过 24 KiB，总 max_ticks 为 60..120000，timeout_seconds 为 5..600。启动另有约 180 秒等待预算；大 Mod 列表可能花较长时间，不能把单次轮询尚未完成当作卡死。以当前 capabilities 和 MCP Schema 为准。

## 6. 等待、取证与判断结果

提交返回 run_id 后，调用 `rimprobe_get_run`：

```json
{"run_id": "REPLACE_WITH_RETURNED_RUN_ID", "wait_seconds": 10}
```

继续调用，直到 `controller_finished=true`。`cleanup_complete` 为兼容旧客户端保留的“清理尝试结束”别名，**不证明回收成功**。还须核对 `cleanup_status="succeeded"` 与 `owned_process_exit_verified=true`；任一不满足必须报告清理失败/未验证。完成状态可能先于进程清理出现；不要因此立即发下一轮、更新正在加载的 DLL 或关闭 MCP 客户端。

清理失败后仍可用 get_run/get_artifact 只读查询。如果服务保留了该 run 的原始所属 session，可再次调用 cancel_run，请求仅针对该 session 的清理重试；返回 cleanup_retry_requested 后继续轮询。禁止扫描或关闭其他游戏。重试成功也不自动把原测试升级为 passed，原 cleanup_error 保留用于追溯。当前接口不提供服务重启后的进程恢复或任意 PID 重试。

按需调用 `rimprobe_get_artifact`，不要每轮把所有大文件都搬进对话：

```json
{"run_id": "REPLACE_WITH_RETURNED_RUN_ID", "name": "report.json"}
```

| 证据 | 主要检查 |
|---|---|
| report.json | 顶层 status 与 suite 步骤/断言、baseline/compared_value、failure_context、primary_failure 和 cleanup_failures |
| startup.json | 启动红字候选、扫描覆盖与截断；重复 packageId 噪声另行记录 |
| diagnostics.json | 运行增量错误、Agent 红字及覆盖；取消/早期失败时可能尚未生成 |
| profile-plan.json | 原配置指纹、继承顺序和临时追加项 |
| loaded-mods.json / mod-set.json | 实际加载排序及与请求的差异 |
| stop.json | 所属进程回收、源配置是否变化、前台焦点采样及资源记录 |
| contract.json | 实际提交并规范化的测试条件 |

磁盘 session 目录还保存 `run.json`、`state.json` 和本轮日志，可用授权的文件工具查看；get_artifact 只能读取其 artifacts 白名单，并非任意文件读取接口。

必须同时解释顶层与业务结果：suite 断言通过但启动有错误、覆盖不全或加载环境不符，总体不应当作通过。日志是候选和线索，不自动证明被测 Mod 有错；没有红字也不证明效果正确。

| status | 应如何汇报 |
|---|---|
| passed | 仅列明的动作与断言通过，不代表全部功能正确 |
| failed | 断言不满足或运行异常，先看证据再定位；故意负例应明确标注 |
| blocked | 缺前提、环境/排序不符等，不能写成目标功能已失败或已通过 |
| unsupported | 当前动作/观察机制不支持，交代缺口 |
| inconclusive | 无功能断言、预算/证据不足等，不能当作成功 |
| cancelled | 已取消，不代表被测功能通过 |

目前仅按既有用户规则单独接受重复 packageId 扫描噪声，不忽略其他新红字。加载排序不符时不要靠 `--diagnostic-mod-mismatch` 获得通过：它只允许诊断，整体仍 blocked。

若需取消，调用 `rimprobe_cancel_run` 后继续轮询到控制线程结束，并核对上述两个回收成功字段。取消返回只证明请求已发送；若 diagnostics.json 不存在，必须标记运行日志覆盖不足，不能说“全程零红字”。清理报错时保留 report/可取得的 stop；stop.json 缺失不等于成功回收，不扫描或关闭玩家进程。

## 7. 碰到复杂功能怎么办

普通原版机制优先换 Def、前置条件和断言组合，不要求为每个新物品都改 Agent。当前白名单无法表达的专用资源、剧情选择、子地图或窗口，可使用明确安装并审查过的编译式测试包：

1. 为目标版本编译测试包，引用匹配 Agent，注册有界 key。
2. 只把测试包放进临时测试加载集合；通过 query_tests 发现，再调用 registered_test。
3. 正常动作与独立检查推进测试，失败/取消时 Dispose 清理。

详见 [编译式测试包契约](registered-test-packs.md)。MCP 不能上传任意 C#、调用方法名字符串或读取任意私有成员；测试包自身是受信任的游戏内代码，不是沙箱。已有星月师测试包也不会自动适配另一项目。

## 8. 初次测试交付报告模板

```text
目标及版本：Mod / packageId / 源码或构建标识 / 实际游戏版本
部署：实际读取的 DLL/Defs 路径；是否确认为本次构建
测试范围：每项初始状态 → 正常动作 → 预期效果与实际数值
结果：passed / failed / blocked / unsupported / inconclusive / cancelled
错误：启动与运行新增错误；覆盖是否完整；已有噪声单独说明
环境：完整实际加载 MOD/DLC 顺序、临时追加项、请求/实际是否相同
隔离与回收：profile、源配置、controller_finished、cleanup_status、owned_process_exit_verified、stop 证据
修复及复跑：改动文件、旧失败 run_id、新 run_id 及各自证据目录
未覆盖：人工视觉、特殊交互、存读档、长期效果、其他版本等
```

测试计划、初次失败、修复后的报告都保存在目标项目记录中。不要把本项目历史“126 项离线测试通过”当作另一 Mod 的测试结果；编译、离线测试、真实游戏功能验收应分别报告。

## 9. 当前能力边界与进一步阅读

1.7 的建筑、标准能力、摄入、部分 UI、通用计划和可信测试包有历史限定实机证据；1.6 只有真实引用编译与离线验证。quicktest 场景仍随机，可能受自然 AI/其他 Mod 干扰；首次取消回归曾遇到 TicksAbs 启动错误，单次干净复跑不代表根因已修复。

不承诺所有 Mod 零相互影响、并行玩家游戏零性能开销或任意 UI 自动操作。当前未覆盖完整存读档、燃料/生产账单、任意框架动作、精确 VFX/像素命中及所有 DLC/Mod 组合。私有桌面不使用系统输入，但完整游戏仍消耗 CPU、内存和 GPU。

- [当前项目 README](../README.md)：安装、架构、构建与历史证据。
- [通用计划详细语义](composable-plans.md)：完整参数规则和观察限制。
- [验收状态](ACCEPTANCE_STATUS.md)：已完成范围及后续缺口。
- [最近一轮限定真机验证](validation/2026-10-25-failure-diagnostics.md)：连续施法、负例、取消与清理证据。
