# RimProbe

> [!IMPORTANT]
> **项目立场：帮助 Mod 作者提高效率，反对全自动量产低质 AI Mod。**
>
> 本项目旨在帮助作者借助 AI 工具开发、排错和验证，绝不替代真人实测。**发布前，作者必须亲自进入真实游戏，在目标版本与预期 Mod 环境中测试自己的作品。** 编译通过、没有红字或 AI 报告“通过”，都不能替代这一步；请勿将未经亲自实测的作品当作已验证内容发布。
>
> **尊重原作者，先取得授权。** 本项目绝不鼓励在未获得原作者或相应权利人授权的情况下，反编译他人的 Mod，或将其源码、DLL 上传、投喂给 AI。这样的使用违背本项目初衷，也是不尊重原作者劳动成果的行为。能够访问文件，不代表有权这样使用。
>
> AI 正在成为开发工具的一部分，但 **AI 是工具，不是许愿池**。构思、判断、理解与责任始终属于使用者。请理性看待 AI，认真思考如何使用它，并对最终发布的作品负责。

## 最快开始：把地址交给你的 Agent

把下面这段话发给**能调用本机工具的 AI / Agent**，替换游戏和目标 Mod 路径即可：

> 项目：https://github.com/OPFIMISS/RimProbe 。请阅读中英文 README 和 docs/GETTING_STARTED.md，安装并配置 RimProbe MCP，使用 RimProbe 对我的 Mod 进行实测。游戏目录：`D:/Steam/steamapps/common/RimWorld`；目标 Mod：`请填写实际路径`。先检查版本和能力，再围绕实际代码效果设计测试：启动加载 → 准备对象 → 正常动作 → 独立效果断言 → 读取错误和清理证据。保持玩家配置、DLC 和排序，使用一次性 profile 和后台私有桌面；明确报告未覆盖、不支持及人工仍需验证的部分。

Agent 可以先执行 `git clone https://github.com/OPFIMISS/RimProbe.git`，再按下方命令建立虚拟环境、构建和安装匹配版本的 Agent、配置 MCP stdio。**发链接或说“使用 RimProbe 进行实测”本身不会自动安装 MCP**；需要本机工具权限、可用游戏、构建环境及支持 MCP 的客户端。已经配置好时，直接说“使用 RimProbe 对这个 Mod 进行实测，先做启动检查，再验证代码中的实际效果”即可。

2026-10-30 更新：新增启动检查、带句柄的通用交互、就绪屏障、跨地图状态观察、精简轮询及只读启动基线对照。148 项离线测试和双版本编译通过；1.7 两 Def 专项效果通过，启动错误仍使整体保持 inconclusive。见 [通用交互说明](docs/interactions.md) 和 [验证记录](docs/validation/2026-10-30-interactions.md)。

**让 AI / Agent 在后台启动真实 RimWorld，执行 Mod 功能测试并获取结构化证据。**

[English README](README.en.md) · [快速上手 / Quick start](docs/GETTING_STARTED.md) · [中文 Agent 说明书](docs/AGENT_QUICKSTART.zh-CN.md) · [架构与扩展](docs/ARCHITECTURE.md)

RimProbe 是本地 MCP 服务和游戏内 Agent Mod。AI 根据实际源码与 Def，将对象准备、正常游戏动作和效果断言组合为测试计划。游戏在独立 Windows 桌面运行，不接管系统鼠标或键盘。

**推荐搭配 [RimSage](https://github.com/realloon/RimSage) 和 [rimworld-modding-skill](https://github.com/Kon-on/rimworld-modding-skill) 使用。** RimSage 是优秀的 MCP 项目，让 AI 通过工具查询游戏本体的反编译源码，依据真实 API 与实现编写代码，大幅减少猜测导致的错误。rimworld-modding-skill 提供 RimWorld Mod 开发指南与工作流程；RimProbe 则负责在真实游戏中执行测试、观察效果并收集证据。三者可配合完成“查询源码 → 开发 → 实测 → 修复”的流程。

**状态：0.1.0 开发预览，源码分发。** 适合基础测试和明确设计的多阶段测试，不是任意 Mod 的全自动验收工具；最终体验仍需人工确认。

## 当前能力

| 场景 | 支持范围 |
|---|---|
| 建筑 | 正常放置校验、蓝图、地面供材、真实搬运、Frame 与施工；延迟供材恢复 |
| 功能 | 施工后发电输出、电网注册等显式观察，不等于任意建筑功能 |
| 技能 | 本轮 Pawn、标准 Ability、正常施法 Job；Hediff、伤害、冷却、倒地等断言 |
| 物品 | 正常摄入、装备、移动，以及真实状态和数值增量观察 |
| UI | 信息卡打开、真实 Repaint、边界和关闭，不代表像素/命中正确 |
| 复杂 Mod | 明确安装的可信编译式测试包、有界状态机和独立效果检查 |
| 证据 | 启动/运行错误、实际排序、配置指纹、异常链及清理结果 |

同一机制下的新 Def 通常只需换计划，不需为每个物品重写 Agent。缺少机制时明确报告不支持或未覆盖。

## 环境与版本

- Windows：私有 Win32 desktop + Job Object；暂不支持 Linux/macOS 游戏控制。
- Python 3.10+、MCP SDK 2.x；已验证依赖约束见 `constraints-tested.txt`。
- .NET 10 SDK；构建 1.6 另需 .NET Framework 4.7.2 targeting pack。
- 自行安装游戏和对应 Harmony；仓库不附带它们的程序集。

| 版本 | 目标与引用 | 验证状态 |
|---|---|---|
| 1.6 | net472，Unity/Mono，独立 Managed 引用 | 真实引用编译和离线检查通过；尚无真机验收 |
| 1.7 | net10.0，Waylith，独立根目录引用 | 分轮记录游戏内证据；最新通用交互专项见下方验收记录，不等于全量真机通过 |

两版输出和中间目录分离。第十轮已增加通用交互/启动/基线回归检查；离线、真实引用编译和游戏内结果分别记录，不能替代另一 Mod 的验证。见 [验收状态](docs/ACCEPTANCE_STATUS.md)。

## 快速安装

PowerShell 示例；替换仓库、游戏及 Harmony 路径，不要混用版本程序集。

```powershell
git clone https://github.com/OPFIMISS/RimProbe.git C:/Projects/RimProbe
Set-Location C:/Projects/RimProbe
py -3 -m venv .venv
& ./.venv/Scripts/python.exe -m pip install -e . -c constraints-tested.txt

./scripts/build-agent.ps1 -Version 1.7 `
  -GamePath 'D:/Steam/steamapps/common/RimWorld' `
  -HarmonyAssembly 'D:/Steam/steamapps/workshop/content/294100/2009463077/1.7/Assemblies/0Harmony.dll'

& ./.venv/Scripts/python.exe -m rimprobe `
  --game 'D:/Steam/steamapps/common/RimWorld' `
  install-agent --mod-source C:/Projects/RimProbe/mod
```

已有安装会拒绝静默覆盖。更新已验证归属的安装时用 `--update-owned`，保留自动备份；不要在游戏使用 DLL 时更新。正常玩家排序中**不必启用 Agent**，控制器只给一次性 profile 增补。

构建 1.6：同一脚本传 `-Version 1.6`、真实 1.6 `-GamePath` 和对应 Harmony；也可传真实归档 `-ManagedPath` 仅作编译。归档程序集不能当作可启动安装。

## 接入 MCP

支持 `mcpServers` 的客户端使用下列 stdio 配置；其他客户端填写相同 command/args。配置位置和工具前缀由客户端决定，不绑定某个 AI 厂商。

```json
{
  "mcpServers": {
    "rimprobe": {
      "command": "C:/Projects/RimProbe/.venv/Scripts/python.exe",
      "args": ["-m", "rimprobe", "--game", "D:/Steam/steamapps/common/RimWorld", "--runs", "C:/Projects/RimProbe/runs/my-mod", "serve"]
    }
  }
}
```

1. `rimprobe_doctor`、`rimprobe_capabilities`：读取真实版本、参数和边界。
2. 将目标 Mod 部署到游戏可发现的位置；`extra_mods` 填真实 packageId，它不自动安装或编译 Mod。
3. 根据代码提交 `rimprobe_run_plan`；标准施工用 `rimprobe_run_suite`，现有配方用 `rimprobe_run_contract`。
4. `rimprobe_get_run(run_id, wait_seconds=10)` 等到 `controller_finished=true`；成功回收还须 `cleanup_status="succeeded"` 且 `owned_process_exit_verified=true`。
5. 用 `rimprobe_get_artifact` 读取所需报告、日志诊断、实际排序和 stop 证据；用 `rimprobe_cancel_run` 取消或重试原所属 session 的清理。

默认 15 个工具，包括授权源码/Def 提示、无需地图的 `rimprobe_run_startup`、四个交互工具及只读启动对照。`get_run` 默认返回精简进度和分层结果，`detail:true` 可取详情。无断言的发现计划不获功能 passed；`cleanup_complete` 只是“清理尝试结束”的兼容别名。

完整建筑/技能参数见 [快速上手](docs/GETTING_STARTED.md) 和 [中文说明书](docs/AGENT_QUICKSTART.zh-CN.md)。首次使用不需要手动打开游戏。

## 原理与隔离

```text
AI / MCP client → Python stdio server → runner/controller
                                      ├─ private desktop + disposable profile
                                      └─ authenticated loopback TCP
                                            → Agent main-thread queue
                                            → normal jobs + observations
                                            → evidence + owned-process cleanup
```

默认只读继承启用 Mod/DLC 的相对顺序，临时增补 Harmony/Agent 和显式测试包，核对实际排序。不改正常 ModsConfig、Prefs 或存档；各 Mod 自定义设置**不默认复制**。无本轮环境变量时 Agent 不开启监听和测试补丁。游戏对象在主线程访问，不开放 eval、任意 C# 或远程反射路径。

私有桌面避免系统输入控制，但完整游戏仍消耗 CPU/内存/GPU；没有证明所有组合零干扰或前台并行零开销。除明确接受的重复 packageId 扫描噪声外，其他新错误保持可见，不自动归责目标 Mod。

## 可拓展性

- **组合机制**：最多 24 步，fixture → measure → 正常动作 → wait_assert；见 [计划语义](docs/composable-plans.md) 和 `examples/plans/`。
- **新增机制级原语**：同步严格 Python Schema、Agent 白名单/观察器、预算和双版本测试；不逐个 Def 硬编码，不开放任意字段执行。
- **复杂测试包**：实现 `IProbeTest`，注册显式 key，在主线程有界 Pump，在 Dispose 清理；见 [测试包契约](docs/registered-test-packs.md)。编译包是可信 Mod 代码，不是沙箱。

`testpacks/StarMoon` 是针对独立 Mod 的集成样例，需自行提供目标构建；不是基础安装前置，也不会自动适配其他项目。

## 验证与限制

```powershell
& ./.venv/Scripts/python.exe -m unittest discover -s tests -q
& ./.venv/Scripts/python.exe -m pip check
& ./.venv/Scripts/python.exe -m compileall -q src scripts tests
```

离线测试不自动启动游戏。真实引用编译、离线测试和真机验收分别记录。本机 `runs/` 原始证据不随源码发布；`docs/validation/` 是历史摘要，引用的本机文件不是下载附件。

当前缺口包括随机 quicktest、存读档、燃料/生产账单、Caravan、任意技能框架、source/verb Targeter 多段链、裸世界 tile、UI 像素/命中、完整程序集 provenance 和一般历史 MCP 查询。启动对照可只读访问同一 run root 的两个 session；一般工具仍只保留本实例最近运行。passed 只覆盖列明断言，无红字、动作接受或就绪不能替代实际效果。

2026-10-31 更新：新增仅指定 Mod＋全已安装 DLC 的独立多开测试模式；156 项测试与双版本引用编译通过，1.7 两实例隔离及真实建造已验证，遗留启动错误仍保留严格结论。

## 多开隔离测试：保留当前游戏

玩家可继续使用当前游戏；Agent 另开一个后台测试进程。调用启动、计划或契约工具时，显式设置 `profile_mode="minimal_all_installed_dlc"`，并在 `extra_mods` 中给出目标 Mod、必要依赖和测试包的包 ID（按依赖顺序）。测试实例仅启用 Harmony → Core → 全部已安装 DLC → RimProbe Agent → 指定 Mod／测试包，不继承玩家的其他 Mod，也不修改正常配置或存档。

```json
{"profile_mode":"minimal_all_installed_dlc","extra_mods":["your.target.package","your.testpack.package"],"timeout_seconds":180}
```

上例用于 `rimprobe_run_startup`，只检查启动；随后用同一模式的 `rimprobe_run_plan` 或 `rimprobe_run_contract` 执行功能断言。只传目标 Mod 时，省略测试包。Mod 必须已经安装；依赖不会自动猜测或添加。全 DLC 指本机 `Data/*/About/About.xml` 中识别出的已安装 DLC，不做来源或许可证过滤，不下载缺失 DLC。已知五个 DLC 按发行顺序加入，未知未来 DLC 追加并在实际加载审计中核对。

默认 `inherit` 仍保留玩家启用列表与相对顺序；旧 `minimal` 仍只有 Harmony、Core、Agent 及指定新增项。自动补入的 Agent 现在排在新增测试包之前；继承列表中已有条目的顺序不擅自重排。

每轮有独立 profile、私有桌面、进程句柄、会话令牌和端点；取消只回收该控制器拥有的进程，不扫描或结束玩家进程。每个 MCP 服务同时拥有一个测试实例，多个服务可独立运行。后台运行仍会占用 CPU／内存／显卡，不承诺零性能影响。查看 `profile-plan.json`、`loaded-mods.json`、`stop.json`，只有实际排序一致、独立功能断言通过、清理成功才构成相应证据。没有红字不等于功能通过。

本轮离线、双版本引用编译与多开实机证据见[验证记录](docs/validation/2026-10-31-multi-instance.md)。

## 文档与分发

- [English quick start](docs/GETTING_STARTED.md) / [中文 Agent 说明书](docs/AGENT_QUICKSTART.zh-CN.md)
- [Architecture and extensibility](docs/ARCHITECTURE.md)
- [验收门禁](docs/ACCEPTANCE_STATUS.md) / [开发历史与踩坑](DEVELOPMENT_HISTORY.zh-CN.md)

目前以源码预览分发，暂不创建稳定二进制 Release。仓库不包含游戏、Harmony、目标 Mod 二进制或运行存档；尚未选定项目许可证，不添加未经指定的作者/许可元数据。
