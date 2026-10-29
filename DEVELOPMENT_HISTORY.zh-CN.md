# RimProbe 开发历史（本机研究记录）

此文件保存发布前的开发记录与踩坑。绝对路径、Mod 组合和 runs/ 引用属于原开发环境，不是可直接复现的公共样例；原始游戏日志、运行目录和本机编译指纹不随仓库发布。公开安装与当前用法见 [README.md](README.md) 和 [README.en.md](README.en.md)。历史通过只适用于当时对应构建，不代表当前构建已完成全量真机验收。

2026-10-29 第九轮完成反馈前三项的限定改进：通用计划增加有界主异常链与独立清理异常，Dispose 前复制测试包检查，未知 CLR 异常默认 failed；清理报告区分 controller_finished、cleanup_status 和 owned_process_exit_verified。cleanup_complete 只保留“尝试已结束”的兼容语义，不能单独证明回收成功；保留原所属 session 时可用 cancel_run 受控重试，原失败不自动改判。双版本真实引用编译和离线故障注入通过，新 Agent 已校验备份后更新安装；本轮未启动游戏、未改玩家配置或存档，不改判 GBTAE 的 inconclusive。范围、验证和剩余建议见 [ITERATION_09](docs/ITERATION_09.md) 与 [本轮验证记录](docs/validation/2026-10-29-failure-and-cleanup.md)。

**在另一个项目中首次使用：**先读 [Agent 接入与首次测试说明书](docs/AGENT_QUICKSTART.zh-CN.md)，其中包含可直接转交的 Agent 指令、九工具流程、建筑/能力示例、证据判断和能力边界；单个 1.7 stdio 服务配置见 [mcp-first-test.json](examples/mcp-first-test.json)。

2026-10-25 第八轮完成限定迭代：增加 `pawn.ability_casting`，连续动作可以等待标准施法 Job 结束；失败清理前自动保留最多四个相关对象、作业身份及断言进度，诊断读取异常不覆盖原始结果。126 项离线测试、双版本真实引用编译及离线 C# 通信/诊断检查通过；1.7 连续施法正例、故意失败负例和取消复跑分别通过预期检查与只读证据审计，1802 次焦点采样无观察违规，玩家配置指纹不变，四个尝试进程全部退出，临时 fixture 已移出游戏。首次取消尝试有一条 quicktest 启动红字，审计拒绝，原证据保留；验证脚本现对负例/取消也检查启动覆盖，并在最终审计失败时撤回完成标记。见 [本轮计划与踩坑](docs/ITERATION_08.md)、[验证、排序与复跑命令](docs/validation/2026-10-25-failure-diagnostics.md)。1.6 真机、存读档及全量验收仍未完成。

2026-10-25 用户单独批准旧设置修复后：确认游戏未运行，仅把 `Config/Mod_2988200143_Mod_KiiroRace.xml` 移到同目录 `.rimprobe-20261025.bak` 备份，哈希一致，等待下次正常启动生成默认设置。未修改 Mod 列表、其他设置或存档；尚未复查正常启动日志，不宣布该红字已消失。证据：`runs/iteration07/settings-reset.json`。

2026-10-25 第七轮已完成本轮回归：真实 MCP 五用例的结果均符合预期，80 项正例检查通过，1 项故意缺失效果负例正确失败；五个 DLC 全部实际加载，启动/运行错误候选均为零，实际加载顺序与请求一致。覆盖觉醒、等级/资源、昼夜技能、时停三次传送/自然到期/正常取消、三信封及双结局图片/子地图。121 项离线测试与测试包双版本真实引用编译通过；只读证据审计通过，3046 次焦点采样无观察违规，玩家配置指纹不变，所属进程已退出，临时测试包已移出游戏。最新玩家红字定位到绮罗种族旧设置文件类型不匹配；按规则未修改正常配置。见 [实际验证与完整排序](docs/validation/2026-10-25-kiiro-starmoon-rerun.md)、[计划与踩坑](docs/ITERATION_07.md)。这不是全项目/1.6 真机/全部 Mod 功能验收。

2026-10-25 第六轮：增加 `query_tests` / `registered_test`，复杂 Mod 可用显式安装的编译式测试包复用主线程执行、结构化断言、后台进程和报告链。通用计划现在有 18 种操作。星月师已有独立测试包与双版本迁移/图片过渡代码；实际 1.7 启动发现 DLC 请求/实际加载不符，且尚未进入可用地图，**未完成技能/结局游戏内验收**。见 [测试包契约](docs/registered-test-packs.md) 与 [本轮验证](docs/validation/2026-10-25-kiiro-starmoon.md)。默认仍拒绝排序差异；显式诊断模式允许收集检查但总体不能 passed。启动失败也保留完整日志扫描。

2026-10-25 测试残留清理：核对正常游戏 Logs/Player.log，仅有 Orion.Hospitality、Alfie.oneclickconvert、Solaris.RatkinRaceMod 三条重复 packageId ERROR，没有 RimProbe ERROR；与开发前已有噪声一致，不清理第三方 Mod 或屏蔽日志。确认已安装样例与项目 fixtures/AbilityContract 文件逐项哈希一致后，将 Mods/RimProbeAbilityFixture 移至 E:/Rimbook/runs/cleanup-2026-10-25/RimProbeAbilityFixture，退出正常 Mod 扫描范围。Agent 保留；正常启用列表中没有 Agent 或 fixture。未启动游戏、未改玩家配置/存档。未来重跑自带样例前需要重新安装 fixture，仅添加到一次性 profile；历史验证证据不因此追改。

当前架构改为**通用组合计划**：AI 根据实际代码，把对象准备、正常动作、状态发现、数值基线和断言拼成一次测试；使用同一机制的新 Def 不需要逐个写 C# 适配器。通过 `rimprobe_run_plan` 一次提交，游戏内自动推进，默认 MCP 共 9 个工具。原理、完整动作/属性目录、示例及边界见 [docs/composable-plans.md](docs/composable-plans.md)，执行计划见 [docs/ITERATION_05.md](docs/ITERATION_05.md)。本轮 1.7 真机完成 12 例 MCP 验证（9 个通用计划与 3 个旧能力契约回归），结果均符合预期，两份完整汇总的只读证据审计通过；112 项离线测试、两版真实引用编译和离线 C# 预检/通信通过。详细证据见 [docs/validation/2026-10-23-composable-plans.md](docs/validation/2026-10-23-composable-plans.md)。

## 当前迭代：代码导向测试

历史第四轮限定发电功能闭环已完成：增加 `building_power`，通过同一正常施工链后观察实际发电输出及电网成员身份，支持显式瓦数门槛、稳定观察窗口与零输出负例。计划见 `docs/ITERATION_04.md`，示例见 `examples/contracts/building-power.json`。98 项 Python 离线测试及两版真实引用编译/离线通信已通过；首轮 1.7 真机发电正例 passed、零输出负例 failed，后者同样正常完成施工并注册电网；证据见 `docs/validation/2026-10-23-building-power.md`，扩展回归暴露施工停滞和其他殖民者代建漏记，未完成汇总原样保留；第四轮最终构建四例专项全部符合预期（发电 passed、零输出 failed、无 PowerComp unsupported、取消 cancelled），只读证据审计通过；该构建未重跑全部历史用例。用户当前无法提供 1.6 可启动安装，保留双版本支持并延期其真机门禁，不切换 Steam 版本。


第三轮限定范围已完成：83 项离线测试、两版真实引用零警告编译、两版离线通信测试通过；最新 1.7 Agent 经真实 MCP 的九例回归全部符合预期，包括故意失败负例。证据见 `docs/validation/2026-10-23-runtime-adapters.md`，后续门禁见 `docs/ACCEPTANCE_STATUS.md`；仍不是全项目完成。

2026-10-23 按新要求推进，执行计划见 `docs/ITERATION_02.md`。默认只读继承正式或指定的 ModsConfig，保留启用 Mod/DLC 的相对顺序，只在每轮独立副本补入 Harmony/Agent 或显式追加项；不会按 DLC 来源筛除。`profile-plan.json`、`loaded-mods.json` 和最终报告公开请求/实际顺序、增补项和原配置指纹。最小配置仅供显式选择，不再作为默认。后文旧阶段证据使用的是当时的最小配置，不代表新默认策略。

已许可的重复 packageId 扫描噪声会单独保留，不再阻止其他检查通过；不会把所有启动红字或动作后的新异常都忽略。新方向是源码/Def -> 可组合声明式契约 -> Pawn/场景准备 -> 真实操作 -> 效果断言，而非固定清单之外不测试。尚未实现或未经验证的能力仍明确标记。

### 2026-10-23 后台实测更新

上一轮代码契约证据（历史）：`runs/1.7/mcp-validation-1792750851290043000.json`。实际效果正例 passed，无效果但正常冷却的负例 failed，主动取消 cancelled 并自动回收；三轮正式配置指纹不变。完整加载顺序、逐项证据和未覆盖项见 `docs/validation/2026-10-23-code-contracts.md`。以下首次 smoke 记录作为历史保留。

1.7.4985 首次后台 smoke 已完成：独立 Win32 desktop 加载 Agent、进入 250×250 地图并回收进程，420 次前台采样未发现测试 PID 抢焦点。证据：`runs/1.7/a83055583f3b424194cd934122d2d0a5/stop.json`。这只是启动/通信证据，不是建筑、UI 或兼容性通过。

该轮还发现空 `knownExpansions` 会触发游戏自动启用全部已安装 DLC，故该轮不能算指定 Mod 集通过。控制器现根据本机 Data 元数据预填已知 DLC，并核对实际加载顺序，偏移返回 `mod_set_mismatch` 且保存 `mod-set.json`。不修改玩家配置，不把现有 Mod 库扫描错误归因于 Agent。1.6 目前仅完成真实引用编译，尚缺完整运行安装。

RimWorld 自动化测试探针：游戏外 MCP 控制器 + 游戏内 Agent Mod。读取真实状态、执行受控操作、保存证据，减少截图和鼠标点击。

> 2026-10-23：开发中，**不是全项目完成版**。具备双版本独立构建链、后台 worker、高层 MCP、标准建筑施工与代码驱动能力契约。1.7 已通过真实 MCP 完成建筑施工、能力施放/效果正例、故意缺失效果的负例；1.6 尚缺完整可启动安装。正常摄入和信息卡绘制已有首轮 1.7 证据；通用计划已增加装备与移动；自定义物品交互、UI/像素命中、任意建筑功能和生命周期回归未完成。

## 目标与当前范围

用户指定的 `D:\Steam\steamapps\common\RimWorld` 为 1.7.4985 rev1269，不是 1.6。独立 Win32 desktop + Job Object worker 已通过无界面子进程桌面验证及初轮真实游戏验证；只设本轮 profile 的静音、后台运行和模拟用 1280×800、信息卡 UI 用 1600×1000 / UI scale 1，不切换用户桌面、不发送系统输入。

完整计划与验收标准见 [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)。所有启动路径强制使用私有桌面，失败不退回前台。尚未验证与玩家前台游戏同时运行的资源开销、所有弹窗/驱动行为和任意 Mod 组合；不能把有限前台采样视为全面无干扰证明。

- 已实现代码：版本识别、独立测试数据目录、进程启动与回收、日志尾部读取、会话认证、主线程状态查询、MCP stdio 接口。
- Agent 白名单：`get_state`、`start_building_suite`、`start_contract`、`cancel_suite`。读取与所有游戏操作均在主线程；Log.Error postfix 仅采集有界字符串，不屏蔽异常。
- 标准建筑配方：设计器放置校验与越界拒绝 -> 正常蓝图 -> 地面 fixture 材料 -> 真实 HaulToContainer -> Frame 资源种类/数量与 workDone -> FinishFrame -> 成品初始化。Wall 仅提供结构断言，不冒充路径查找或完整功能测试。
- 能力契约：任意已加载 AbilityDef -> 生成独立 Pawn -> GainAbility -> 正常资格检查/QueueCastingJob -> Hediff/伤害/冷却/眩晕/倒地前后变化断言；不是只给预设能力测试。完整用法与边界见 `docs/code-driven-testing.md`。
- 缺料恢复：指定 `supply_delay_ticks=180`，暂时禁止测试地图中原有可用同类堆叠，确认未施工后补入地面材料，继续正常搬运/建造，结束恢复禁止状态；不直接填 Frame。
- 摄入契约：`item_ingest` -> 新测试 Pawn + 初始饥饿条件 -> 正常 Ingest 作业 -> 精确物品 Ingested 完成观察 -> 摄入/营养/Hediff 断言。示例 `examples/contracts/item-marker.json`。
- UI 契约：`ui_info_card` 对已加载 ThingDef 打开真实信息卡，观察实际 Repaint、逻辑边界和关闭；不代表截图、像素或鼠标命中正确。示例 `examples/contracts/ui-info-card.json`。
- 发电契约：`building_power` 使用同一正常施工链，随后有界采样实际 PowerOutput、地图内 PowerNet 的成员身份；两项显式断言都满足才 passed。当前不代替燃料、用电端、生产配方或任意 Comp 测试。
- 通用执行器：18 种操作可组合，包含 Def/对象发现、inspect、measure、增量断言及编译式测试包发现/执行；正常装备/移动和建造后独立观察也使用同一计划。扩展以机制级原语为单位，不逐个对象适配。
- 后续缺口：固定场景、不可达恢复、账单/燃料等其他正常交互、自定义 UI、存读档及 1.6 真机验证。
- **没有红字不等于功能正确，地图就绪不等于测试通过。** 原型的 `smoke` 只检查启动就绪，不给被测 Mod 的功能背书。

## 原理

```text
AI -> MCP stdio -> RimProbe Python 控制器 -> 127.0.0.1 TCP -> RimProbe Agent
                         |                                     |
                   进程 / 日志 / 报告              有界队列 -> Root.Update 主线程
```

RimSage 查实现，RimProbe 验证运行，不重新开发反编译器。Agent 是开发测试 Mod，不修改游戏本体，不应成为被测 Mod 的发布依赖。后台线程只处理通信，游戏对象访问调度到主线程。启动时必须存在本轮环境变量，否则 Agent 不开启监听、不安装测试补丁。

控制器持有自己创建的进程句柄；不能附加任意 PID，也不扫描并关闭玩家游戏。进程在挂入带 KILL_ON_JOB_CLOSE 的 Job Object 后才恢复运行；控制器退出时由系统回收所属 Job 进程，已有无界面子进程验证。系统崩溃等情况不承诺可写出最终报告。

## 双版本策略

| 项目 | 1.6 | 1.7 |
|---|---|---|
| 引擎 / 运行时 | Unity / Mono | Waylith / .NET 10 |
| Agent 目标 | net472 | net10.0 |
| 项目 | `agent/1.6/RimProbe.Agent.1.6.csproj` | `agent/1.7/RimProbe.Agent.1.7.csproj` |
| 游戏引用 | `RimWorldWin64_Data/Managed` | 游戏根目录 |
| 图形兼容引用 | `UnityEngine.CoreModule.dll` + `UnityEngine.IMGUIModule.dll` | `UnityStubs.dll` |
| Windows 启动文件 | `RimWorldWin64.exe` | `RimWorld.exe` |
| 日志 | `-logFile <本轮Player.log>` | `-NoFileLog` + stdout/stderr 重定向 |
| Mod 输出 | `mod/1.6/Assemblies` | `mod/1.7/Assemblies` |

共享协议与调度源码，不共享编译产物或 obj 目录。JSON 使用两个运行时都可用的 DataContractJsonSerializer，不给 1.6 强行带入 .NET 10 序列化库。两版都依赖对应版本的 Harmony，不打包 Harmony 或游戏原版 DLL。

## 环境准备

- Windows；Python 3.10+；当前实现使用 MCP Python SDK 2.x 的 `MCPServer`，不是旧 `FastMCP`。
- .NET 10 SDK；编译 1.6 还需要 .NET Framework 4.7.2 targeting pack。
- 自己安装的游戏和 Harmony。DLL 快照可以用于编译，但不能伪装成可启动的游戏安装。
- 作者与发布许可由项目所有者指定；当前不代填作者，也未授予开源许可。

```powershell
Set-Location E:\Rimbook
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e . -c constraints-tested.txt
```

后续 `python` 命令应使用安装了本项目的解释器。MCP 配置中的 `command` 也推荐改成该解释器的绝对路径。以下本机 1.7 路径已经确认存在；`D:\Games\RimWorld1.6` 仅是示例，必须换成真实 1.6 安装。

本机已建立 `E:\Rimbook\.venv` 并安装本项目，MCP 2.3.0 / Pydantic 2.14.1 下 112 项离线测试及 pip check 通过；不依赖临时 PYTHONPATH。`examples/mcp.json` 使用该解释器绝对路径，不自动修改任何客户端配置。constraints-tested.txt 只固定已验证的直接契约依赖，不是全依赖锁；依赖升级后应重新测试。当前 pip 镜像曾无法取得构建依赖，必要时给安装命令加 `--index-url https://pypi.org/simple`，不要关闭 TLS 校验或修改全局 pip 配置。

## 编译 Agent

1.7：

```powershell
.\scripts\build-agent.ps1 -Version 1.7 `
  -GamePath 'D:\Steam\steamapps\common\RimWorld' `
  -HarmonyAssembly 'D:\Steam\steamapps\workshop\content\294100\2009463077\1.7\Assemblies\0Harmony.dll'
```

1.6，完整安装：

```powershell
.\scripts\build-agent.ps1 -Version 1.6 `
  -GamePath 'D:\Games\RimWorld1.6' `
  -HarmonyAssembly 'D:\Steam\steamapps\workshop\content\294100\2009463077\1.6\Assemblies\0Harmony.dll'
```

如果只有保留的 1.6 DLL，可用 `-ManagedPath '<归档Managed目录>'` 替代 `-GamePath` 做编译验证。脚本核对 Assembly-CSharp 的真实程序集版本，拒绝跨版本引用，输出独立的 `build-evidence-1.6.json` / `build-evidence-1.7.json`，记录引用来源、SHA256、目标框架与未完成真机验证的状态。

## 安装与使用

显式安装只复制本项目 Mod，不改正式 ModsConfig。普通安装拒绝覆盖；`--update-owned` 仅更新内容与本项目安装清单哈希一致的已知安装。旧安装只能在与源文件完全一致时收养；有未知/被修改文件则拒绝覆盖。更新前备份到游戏根目录 RimProbeBackups，避免被 Mod 扫描器当成重复 Mod。

```powershell
python -m rimprobe --game 'D:\Steam\steamapps\common\RimWorld' doctor
python -m rimprobe --game 'D:\Steam\steamapps\common\RimWorld' install-agent --mod-source E:\Rimbook\mod
python -m rimprobe --game 'D:\Steam\steamapps\common\RimWorld' install-agent --mod-source E:\Rimbook\mod --update-owned
```

**下一条命令真的启动后台测试游戏**，等待地图就绪，读日志，再终止所属进程；不是正常保存退出。建议首次试用时不要与正式游戏并行，以便先评估资源开销。

```powershell
python -m rimprobe --game 'D:\Steam\steamapps\common\RimWorld' --runs E:\Rimbook\runs\1.7 smoke --timeout 180
python -m rimprobe --game 'D:\Steam\steamapps\common\RimWorld' --runs E:\Rimbook\runs\1.7 test-building --def-name Wall --stuff-name WoodLog --timeout 120
```

1.6 使用同一 CLI，将 `--game` 换成真实 1.6 安装目录。额外被测 Mod 用 `--extra-mod package.id` 按依赖顺序重复指定；控制器不会自动补齐所有依赖或默认启用 DLC。

每轮生成新的 `runs/<会话ID>/profile/Config/ModsConfig.xml`，默认只读继承正式 ModsConfig 的启用列表，保留 Mod/DLC 相对顺序，只在副本补入缺失 Harmony、显式 extra-mod 和 Agent。不修改原文件，不加载正式存档；`--mods-config <文件>` 可指定只读来源，`--profile-mode minimal` 才显式采用最小列表。缺失/异常来源会阻止启动，不静默删库修复。其他 Mod 私有设置未克隆，profile.settings_cloned=false 明示此差异。游戏原生缓存、日志清理、Steam 等行为不构成完整操作系统沙箱；不可宣称游戏绝不触及目录外文件。

## MCP 接入

```powershell
python -m rimprobe --game 'D:\Steam\steamapps\common\RimWorld' --runs E:\Rimbook\runs\1.7 serve
```

通用客户端配置见 `examples/mcp.json`，分别列出 1.6 / 1.7 服务。1.6 路径是占位示例，不能直接当作本机已安装。stdio 的 stdout 只用于 MCP 协议，游戏输出进入会话目录。

| 工具 | 实际能力 |
|---|---|
| `rimprobe_doctor` | 不启动游戏，读取版本和游戏引用指纹 |
| `rimprobe_capabilities` | 返回已实现配方、限制、结果枚举，无需启动游戏 |
| `rimprobe_inspect_mod` | 有界扫描可信本地源码/Def，返回候选与源码线索，不执行代码 |
| `rimprobe_run_plan` | 一次提交最多 24 步的类型化组合计划；fixture、发现、正常动作、基线、等待及断言，返回 run_id |
| `rimprobe_run_contract` | 按代码效果契约生成 Pawn、正常施放、比较实际效果；返回 run_id，接口自带嵌套参数 schema |
| `rimprobe_run_suite` | 自动启动、读启动日志、测试建筑、保存证据、回收进程；立即返回 run_id |
| `rimprobe_get_run` | 读取紧凑进度与各检查结果，不额外查询游戏；检查 cleanup_complete |
| `rimprobe_cancel_run` | 请求取消和自动回收，仅针对当前所属会话 |
| `rimprobe_get_artifact` | 按返回的白名单名称读取证据，不接受任意文件路径 |

推荐先读 `rimprobe_capabilities.plans`，按源码用 `rimprobe_run_plan` 提交 `examples/plans` 的同类组合；查询与比较由 Agent 主线程批量执行，使用 `rimprobe_get_run(wait_seconds=10)` 等待自动回收。原有快捷配方仍可使用。

建筑快捷参数：`rimprobe_run_suite` 传入 `{"def_name":"Wall","stuff_name":"WoodLog"}` -> 每两秒 `rimprobe_get_run` 传入返回的 run_id -> 必要时读 artifact。高层执行器负责 Tick/作业推进，不需要模型逐帧看图。`serve --advanced-tools` 才额外公开 launch、get_state、wait_ready、read_logs、stop；这些低层工具不要与正在运行的高层任务混用。

必须检查业务 status，而非仅检查 MCP 调用成功：passed / failed / blocked / unsupported / inconclusive / cancelled。默认每个服务只持有一轮当前报告，旧轮报告保留在磁盘。完整结束需 `cleanup_complete=true`。`test-building` / `test-contract` 非 passed 返回退出码 1，inconclusive 不伪装为成功。

能力契约 CLI（被测 Mod 需实际提供对应 Def）：

```powershell
python -m rimprobe --game 'D:\Steam\steamapps\common\RimWorld' inspect-mod --mod-path E:\Rimbook\fixtures\AbilityContract --version 1.7
python -m rimprobe --game 'D:\Steam\steamapps\common\RimWorld' test-contract --contract E:\Rimbook\examples\contracts\ability-marker.json --extra-mod rimprobe.fixture.abilities
```

示例 fixture 是单独开发用 Mod：从 `fixtures/AbilityContract` 复制到一个不存在的新 Mod 目录后，只通过 extra-mod 加入一次性配置。不要覆盖现有第三方目录，不要加入正常 ModsConfig。具体字段、观察器边界与扩展规范见 `docs/code-driven-testing.md`。

建筑配方用 quicktest 的健康且符合技能要求的现有殖民者，不提高技能、不禁用正常失败机制。只在一次性测试地图上放置地面材料并发出原版有预约/路径/搬运/施工的工作命令；不直接填 Frame、不改 workDone、不调用强制完工。它测试真实工作执行，但不测试自动工作优先级调度；无合适工人/地点/研究条件时明确 blocked。标准设计器无法覆盖的自定义建筑或未知功能返回 unsupported。原版 quicktest 随机地图仍不是固定 fixture；能力契约则生成独立测试 Pawn，不复用这些殖民者。

## 只读审计已完成的 MCP 回归

`audit-live-evidence.py` 不启动游戏，核对分散报告与汇总、加载顺序、配置指纹、日志覆盖、Agent 构建哈希和可选当前安装。指定证据必须已完成；故意失败负例保持 failed。它检查证据一致性，不提供签名或独立重跑证明。历史回归应选其对应构建。

```powershell
./.venv/Scripts/python.exe scripts/audit-live-evidence.py --evidence <本轮完整汇总.json> --agent-root E:/Rimbook/mod --game D:/Steam/steamapps/common/RimWorld
```

## 证据与安全边界

会话目录保存 `run.json`（版本、引用指纹、Mod 顺序、启动参数）、`bridge.json`（无密钥端点）、`state.json`、`mod-set.json`、`logs.json`、`stop.json`。另有 `profile-plan.json`、`loaded-mods.json` 审计原配置/增补/实际排序，结束再次核对原配置指纹，不恢复覆盖用户并发修改。高层任务额外保存 `report.json`、启动扫描 `startup.json`，正常完成的动作有 `diagnostics.json`，能力契约还有 `contract.json`，记录断言、作业、对象 ID 与覆盖缺口；取消/提前阻塞时部分 artifact 可能尚未生成。

启动日志先扫描，再执行配方；仅用户许可的重复 packageId 扫描消息归入 ignored_errors，保留原文但不否决通过。其他启动错误防止整体 passed，动作检查点后的新红字否决通过。每个日志源最多 2 MiB；主线程状态含有界 Log.Error 序号日志，多轮累积，序号缺口/日志截断/缺失会降为 inconclusive，不把漏读当无异常。尚未实现无 Agent / 带 Agent 的完整对照实验，不能自动把错误归因于目标 Mod。

仅监听本机 IPv4 回环；每轮独立随机密钥，经子进程环境传递，不写入命令行或报告。密钥不防御同账户恶意进程；任意 Mod 本身也是可信代码。不存在 `eval`、任意 C#、任意反射调用工具。协议见 `docs/protocol.md`。

## 验证记录

| 范围 | 状态 |
|---|---|
| 1.6 真正的旧 Assembly-CSharp + Unity DLL 编译 | 已通过；来源为本机保留的 1.6 DLL 快照，非完整游戏安装 |
| 1.7 当前安装 DLL 编译 | 已通过；游戏 Version.txt 为 `1.7.4985 rev1269` |
| Python 控制器 / 协议 / MCP / 原生后台 / 执行器测试 | 112 项通过；包含配置继承、DLC 保留、能力契约、日志覆盖、嵌套 MCP schema、无启动的错误参数拒绝；mock 不作为真机证据 |
| Agent 1.6 离线通信测试 | 通过，net472 程序实际运行于本机 .NET Framework 4.8.9363.0；不是游戏内 Mono 验证 |
| Agent 1.7 离线通信测试 | 通过，实际运行于本机 .NET 10.0.3；不是游戏内 Waylith 验证 |
| MCP 真实 stdio 握手 | 两种版本配置均通过真实子进程的 initialize、list_tools、doctor、无会话失败检查；使用合成安装目录，不启动游戏 |
| 1.7 游戏内启动、状态、日志闭环 | 已验证，Core+Harmony+Agent 顺序一致，后台加载地图、Tick 推进和回收 |
| 1.7 木墙真实搬运/施工 | 新策略和继承配置下整体 passed；错误材料 blocked；旧阶段 inconclusive 留作历史证据 |
| 1.7 代码驱动能力契约 | 实际生成 Pawn、授予能力、施放并观察 Hediff/冷却，正例 passed；无效果负例 failed，不靠红字判断 |
| 1.6 游戏内测试 | 未验证，缺完整可启动安装 |
| 1.7 缺料与恢复 | 180 Tick 缺料窗口、真实地面供材/搬运/施工通过；非零原栈恢复分支仍待专项 |
| 1.7 物品摄入 | 正例 passed；同样摄入但缺少效果的负例 failed |
| 1.7 信息卡 UI | 真实 Repaint、实际逻辑边界和生命周期通过；不等于像素/命中正确 |
| 1.7 建造后发电 | 正常施工与实际 100W 输出/电网成员正例 passed，零输出负例 failed；不代替用电端/燃料测试 |
| 1.7 通用组合计划 | 能力/摄入/装备移动/施工后发电 passed；缺效果与零输出 failed；纯发现 inconclusive；取消 cancelled；详见第五轮验证记录 |
| 其他自定义物品动作 / 自定义 UI / 任意建筑功能 / 生命周期 | 未完成；未注册语义不作为通过项 |

本轮首轮真实 MCP 证据：`runs/1.7/mcp-validation-1792750156201395800.json`，八工具，继承原有配置；木墙 passed、错误材料 blocked、能力效果 passed、故意无效果 failed；正常 ModsConfig/Prefs 哈希不变。历史六工具证据 `runs/1.7/mcp-validation-1792748242115719800.json` 保留当时的 inconclusive 结论，不追改。标准 SDK 互操作不等于 DeepSeek 等所有模型已实测。详细记录见 `docs/validation/2026-10-23.md` 与本轮补充证据。

复现真实 MCP 检查（会启动两个独立后台游戏，分别测试木墙与错误材料；脚本通过断言不表示产品全量验收）：

```powershell
python scripts/verify-live-mcp.py --game 'D:\Steam\steamapps\common\RimWorld' --runs E:\Rimbook\runs\1.7 --include-negative --execute-live
```

离线测试：

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
```

Agent 离线通信检查认证失败、非法协议、未知命令、主线程未响应超时和超时后继续服务；不调用游戏对象或 Unity 原生函数。复现命令：

```powershell
dotnet run --project tests/Agent.TransportTests -c Release `
  '-p:GamePath=D:\Steam\steamapps\common\RimWorld' `
  '-p:HarmonyAssembly=D:\Steam\steamapps\workshop\content\294100\2009463077\1.7\Assemblies\0Harmony.dll'

dotnet build tests/Agent.TransportTests.1.6 -c Release `
  '-p:ManagedPath=<你的1.6归档Managed目录>' `
  '-p:HarmonyAssembly=D:\Steam\steamapps\workshop\content\294100\2009463077\1.6\Assemblies\0Harmony.dll'
.\tests\Agent.TransportTests.1.6\bin\Release\net472\Agent.TransportTests.1.6.exe
```

本次 1.6 编译输入为已有的 `D:\Steam\steamapps\common\RimWorld\Mods\自定义贴图调整\1.6\Assemblies`，引用身份为 `Assembly-CSharp 1.6.9676.17735`。这是只读归档引用，不代表该 Mod 目录可以启动 1.6 游戏。当前尚未确认可运行的完整 1.6 安装位置。

## 踩坑与决策记录

| 日期 | 问题 / 决策 | 应对 |
|---|---|---|
| 2026-10-23 | 1.7 已换 Waylith/.NET 10，不是换版本号的 Unity | 实际安装 DLL 编译，两版项目 / 引用 / obj / 输出隔离 |
| 2026-10-23 | 本机保留的 1.6 DLL 在既有 Mod 目录里 | 仅作为只读编译输入，绝不复制进 RimProbe；不冒充完整可运行安装 |
| 2026-10-23 | MCP SDK 2.x 删除 FastMCP 导入 | 按本机 SDK 的 MCPServer 实际签名实现并做注册测试 |
| 2026-10-23 | MCP SDK 2.x Python 属性使用 snake_case，例如 server_info | 真实 stdio 客户端测试发现旧式 serverInfo 访问失败，修正测试，不把传输握手当作全部接口已验证 |
| 2026-10-23 | 原版 quicktest 使用随机种子和起始地点 | 仅作启动冒烟测试，后续引入版本化固定场景 |
| 2026-10-23 | 1.7 原生日志根目录不随 savedatafolder 改变 | 只读反编译当前 RimWorld.dll 的 Bootstrap / Program，确认 NoFileLog 开关及 Console logger；捕获本轮 stdout/stderr，日志完整性仍需真机验证 |
| 2026-10-23 | 同名 Unity 兼容 API 不代表旧语义 | 迁移清单仅作研究线索；针对两个版本分别编译与运行，不声称完整兼容 |
| 2026-10-23 | 后台线程直接读游戏对象容易竞态 | 主线程队列；加载期间避免遍历部分初始化的地图 |
| 2026-10-23 | 请求超时后晚执行会污染测试 | 排队项带截止时间和取消状态；已开始的动作不宣称可事务回滚，按同一 run_id 查询 |
| 2026-10-23 | Windows apply_patch 包装器对多行参数转义不可靠 | 用 Python subprocess 直接传 UTF-8 patch 参数给 apply_patch 入口，避免跨 shell 转义 |
| 2026-10-23 | 不抢鼠标、失焦继续 Tick、后台渲染和低资源竞争是不同要求 | 分别设立真机门禁；失败不自动改为前台，不声称任意硬件下并行无影响 |
| 2026-10-23 | Python 3.10 subprocess 会忽略额外设置的 STARTUPINFO.lpDesktop | 无界面 Python 子进程实测落到 Default 桌面；游戏启动被门禁阻止，改用原生 CreateProcessW + STARTUPINFOEX，挂入 Job 后才恢复执行 |
| 2026-10-23 | 生成建筑或直接填材料不能证明玩家建造链正常 | 后续配方必须走设计器、真实搬运和施工工作，功能未知则报告 unsupported |
| 2026-10-23 | 正常施工也会随机失败并损耗材料，不能把所有停滞归因于 Mod | power 使用独立初始技能工人；只读追踪精确 Frame.FailConstruction（记录实际工人，包括其他殖民者代建），触发则报告 blocked，不改 RNG/成功率、不隐藏补材；旧未观测超时保留 inconclusive |
| 2026-10-23 | 缓存摘要会省略 events；预期负例失败也可能混入新红字 | 只读证据审计核对其余完整字段、构建/安装哈希、日志覆盖与排序，负例 failed 不会被改写为 passed |
| 2026-10-23 | 空 knownExpansions 会自动激活安装的 DLC | 从 Data 的真实元数据预填已知项，核对实际运行 Mod 顺序，偏移阻止测试 |
| 2026-10-23 | 960×540 在本机 DPI/UI 下触发 Resolution too small | 独立 profile 改为 1280×800、uiScale=1；复测运行错误由 1 降到 0，不改玩家分辨率 |
| 2026-10-23 | 未启用的第三方库也会产生重复 packageId 日志 | 用户明确许可后仅该消息单独归类 ignored_errors；保留原日志，不泛化忽略其他错误 |
| 2026-10-23 | 备份放在 Mods 下会被继续扫描 | 受所有权清单保护的升级备份放在游戏根目录 RimProbeBackups |
| 2026-10-23 | Win32 Job 关闭可用退出码 0 杀死子进程 | 测试验收及时结束和进程存活状态，不误以为非零退出码才证明被回收 |
| 2026-10-23 | 能力可以正常施放/进入冷却，却根本没产生效果 | 必须独立断言实际效果，故意无效果负例已抓出；成功排队不算功能成功 |
| 2026-10-23 | CompProperties_AbilityGiveHediff 没有自动设置 compClass | fixture 显式声明 CompAbilityEffect_GiveHediff；真实 Log.Error 捕获该错误，不忽略后硬判通过 |
| 2026-10-23 | 最新 16 条红字可能在两次轮询之间溢出 | 跨轮积累并检查单调序号缺口，覆盖不完整时禁止假通过 |
| 2026-10-23 | Pawn.HitPoints 实测为 -1，不能当健康条 | 对象查找补测保留未完成汇总；改为测找到的武器耐久，Pawn 使用 injury/downed/dead 等语义状态 |
| 2026-10-23 | 一种新对象不应要求一个专用测试类 | 通用 plan 将受审查动作/只读属性/增量断言组合，新增同机制 Def 只改计划；新机制再扩展原语 |
| 2026-10-23 | Windows 单次命令参数过长（错误 206） | 拆分 apply_patch 调用及 partial 源文件，避免超过进程参数长度上限 |
| 2026-10-23 | Pydantic 的 schema 属性与字段重名 | MCP 输入使用 alias 保持外部 schema=1，内部 schema_version，避免告警污染日志 |

研究参考：用户提供的 `GBTA_1.7_API研究与迁移清单_20261013.md`（2026-10-13 的历史研究，不是当前版本证明）；RimSage 1.6 / 1.7 源码；当前安装 DLL 的只读反编译。没有修改该参考文件或其他 Mod。

## 后续开发约定

每次实现或调查都更新本文的用法、目标、原理、验证证据、已知限制和踩坑。离线通过、编译通过和真机通过分开记录。准备环境可以走捷径，被测行为不能被绕过；功能断言必须有明确预期与故意失败的反例。未知能力不猜测，未实现能力不写成可调用接口。

## 第三轮实现与复盘（2026-10-23）

- MCP 仍为默认八工具；`rimprobe_get_run(run_id, wait_seconds=10)` 可在完成回收或等待上限时返回，范围 0..15，不额外访问游戏、不占住控制器锁。客户端工具超时须大于等待值。轻量模型不必每 2 秒进行一次对话轮询。
- `stop.background.resources` 提供所属进程累计 CPU 秒、工作集/峰值工作集/私有内存字节；退出后内存可为带采样时刻的最后存活值，失败明确不可用。不冒称 Agent 独占开销、GPU 占用或前台游戏并行性能已验收。
- 除 MCP SDK 客户端测试外，`tests/test_mcp_wire.py` 用独立实现的逐行 JSON-RPC 客户端验证握手、工具 schema、调用与错误；未测试所有商业客户端或特定 DeepSeek 模型。
- 1.6 的 Event/EventType 在 IMGUIModule，必须分版本显式引用；不打包该程序集。
- 本机 UI 实测 1280×800 对应逻辑 1138×711，信息卡高 760，边界断言正确 failed。仅信息卡独立配置提高到 1600×1000 后通过；不缩小窗口或放松断言，不改正常 Prefs。
- JobMaker 使用 SimplePool，Job.Clear 重置 loadID；同一对象引用不是同一次作业。施工和摄入改按发出时的唯一 loadID 追踪，不把复用后的 GotoWander 当仍在施工，也不任意中断后续非本轮作业。
- Job Object 关闭后进程退出存在短暂延迟：worker 等待所属进程结束后再关闭句柄/桌面，避免临时日志仍被占用。
- 验证脚本逐轮保存汇总检查点；`verification_complete=false` 或 `checks_validated=false` 不得当整套通过。初次 UI 越界和施工停滞的失败报告保留供复盘。
