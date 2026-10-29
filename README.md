# RimProbe

**让 AI / Agent 在后台启动真实 RimWorld，执行 Mod 功能测试并获取结构化证据。**

[English README](README.en.md) · [快速上手 / Quick start](docs/GETTING_STARTED.md) · [中文 Agent 说明书](docs/AGENT_QUICKSTART.zh-CN.md) · [架构与扩展](docs/ARCHITECTURE.md)

RimProbe 是本地 MCP 服务和游戏内 Agent Mod。AI 根据实际源码与 Def，将对象准备、正常游戏动作和效果断言组合为测试计划。游戏在独立 Windows 桌面运行，不接管系统鼠标或键盘。RimSage 可用于了解实现，RimProbe 检查运行行为；RimProbe 不是反编译器。

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
| 1.7 | net10.0，Waylith，独立根目录引用 | 既往限定构建有真机记录；最新异常/清理改进仅完成编译和离线验证 |

两版输出和中间目录分离。最近记录为 **131 项 Python 离线测试通过**，双版本真实引用编译和 C# 离线检查通过；这不表示另一 Mod 已测试，也不表示最新构建已完成全量真机回归。见 [验收状态](docs/ACCEPTANCE_STATUS.md)。

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

默认九工具，另有 `rimprobe_inspect_mod` 提供授权目录的源码/Def 提示。无断言的发现计划不获功能 passed；`cleanup_complete` 只是“清理尝试结束”的兼容别名。

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

当前缺口包括随机 quicktest、存读档、燃料/生产账单、任意技能框架、UI 像素/命中、完整程序集 provenance、基线差异和历史 MCP 查询。工具仅保留本实例最近运行，旧证据需从本地目录读取。passed 只覆盖列明断言，无红字、排队成功、冷却开始或建成建筑不能替代实际效果。

## 文档与分发

- [English quick start](docs/GETTING_STARTED.md) / [中文 Agent 说明书](docs/AGENT_QUICKSTART.zh-CN.md)
- [Architecture and extensibility](docs/ARCHITECTURE.md)
- [验收门禁](docs/ACCEPTANCE_STATUS.md) / [开发历史与踩坑](DEVELOPMENT_HISTORY.zh-CN.md)

目前以源码预览分发，暂不创建稳定二进制 Release。仓库不包含游戏、Harmony、目标 Mod 二进制或运行存档；尚未选定项目许可证，不添加未经指定的作者/许可元数据。
