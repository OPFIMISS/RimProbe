# 2026-10-23：真实施工后的发电功能

本轮限定范围：标准施工后的实际发电输出、电网成员观察。不是完整项目验收。

## 版本与引用

- 1.7 游戏：D:/Steam/steamapps/common/RimWorld，1.7.4985 rev1269，Waylith/net10.0。
- 用户迁移清单为 2026-10-13 的 1.7.4976 API 快照，仅用于研究线索；实际编译/运行依当前本地安装。
- 1.6 归档引用：D:/Steam/steamapps/common/RimWorld/Mods/自定义贴图调整/1.6/Assemblies；用户暂时无法提供可运行安装，因此不切换 Steam，真机验证延期。
- 98 项 Python 单测通过；pip check 与 compileall 通过。两版真实引用编译零警告/错误，两版离线通信通过。1.6 通信运行于 .NET Framework 4.8.9363.0，不等于 Mono 游戏测试；1.7 通信运行于 .NET 10.0.3，不等于 Waylith 游戏测试。
- 1.6 Agent SHA256：90814631e3b461335d717c52a914c4270fd195eece852b325e3f2874d3917f20。
- 1.7 Agent SHA256：2b298d9e65f1032e40dc80c09d12fc43629c36196b306e4e9e2392ccf13d66a2。
- 首轮构建文件、已安装文件、两轮 run.json 记录指纹相同；后续重编译需再核对，不能用旧证据背书新 DLL。

## 首轮真实 MCP 正反例

汇总：runs/1.7/mcp-validation-1792754741626320800.json。verification_complete=true，full_acceptance=false。

| 用例 | 结果 | 证据 |
|---|---|---|
| building_power | passed | 63701ab6a44e47fc8766cbcc987d3c1d/report.json；正常供材/施工，522 Tick 总过程，181 个不同 Tick 样本均实际 100W 且属于本地图真实电网 |
| building_power_zero | failed（预期） | 55c597bbf72e42b9b066e208b4287df1/report.json；相同造价/正常施工，556 Tick 总过程，181 个样本均实际 0W，电网成员断言通过但 90W 阈值失败 |

观察窗口为 180 Tick，施工后等待 60 Tick。不写输出/PowerOn、不手动注册电网、不调用 CompTick，不用 XML 标称功率冒充实际输出。样本在 Root.Update 的不同模拟 Tick 取得，不承诺逐 Tick 捕获。断言依据观察窗口的最低实际输出。

两次均自动回收，正式 ModsConfig/Prefs 指纹未变；369+355=724 次前台采样，零违规。两轮启动均仅有 3 条明确重复 packageId 许可噪声，其他启动错误为零；动作后的文件错误、新红字为空，序号覆盖完整。13 次 MCP 工具调用、42777 UTF-8 文本响应字节；不是 token 估计。

## 本轮实际加载顺序

1. brrainz.harmony
2. ludeon.rimworld
3. general.building.texture.adjustment
4. general.building.texture.adjustment.expansion.advanced
5. mingyue.deepveindrill
6. rimprobe.fixture.abilities
7. rimprobe.agent

继承用户启用列表的相对顺序，仅在独立副本追加 fixture/Agent；正常列表没有改动。当前源列表未启用 DLC，不代表全 DLC 组合已真机验证。其他 Mod 的私有设置没有克隆。

## 只读证据审计

新增 scripts/audit-live-evidence.py。它核对汇总/分散报告/stop 的一致性、Mod 顺序、配置指纹、选定构建和可选当前安装的 Agent 哈希、前台审计、未截断日志及新红字。负例的 failed 会原样保留；取消若未采集动作诊断则明确标注。compact get_run 故意省略 events，只对其余 suite 字段比较。

```powershell
./.venv/Scripts/python.exe scripts/audit-live-evidence.py --evidence runs/1.7/mcp-validation-1792754741626320800.json --agent-root mod --game 'D:/Steam/steamapps/common/RimWorld'
```

这是可复用的一致性核对，不是签名、防篡改或独立重跑。历史证据需选择对应构建；不能把当前新 DLL 与历史哈希不符视为历史测试本身无效。

## 未覆盖

- 没有测试负载用电、实际能量输送/储存、燃料恢复、太阳能日照/遮挡变化、生产账单或任意自定义 Comp。
- fixture 使用原版 CompPowerPlant，证明适配器正负判定；用户自定义发电机仍需其对应源码/契约与实际回归。
- 未证明与前台玩家游戏同时运行时的帧率/GPU/输入影响，也不宣称所有 Mod 兼容。
- 固定场景、存读档、更广 UI 与 1.6 真机门禁仍保留。


## 保留的扩展回归中断

runs/1.7/mcp-validation-1792754907466382400.json 为未完成汇总，不得标成整套通过。前 11 个用例符合各自预期，第 12 个 building_power_unsupported（Wall）在 ef85816a96f849c28a6f07dac2b1511b/report.json 返回 inconclusive：资源已到齐、曾施工到 work=43.031254，之后未完成且达到 6000 Tick 预算。它仍自动回收，不能把结果改成 unsupported 或删除。

查原版 JobDriver_ConstructFinishFrame.MakeNewToils / Frame.FailConstruction：正常施工按 ConstructSuccessChance 随机失败，可能损耗材料并重新生成蓝图。旧样本没有 FailConstruction 观测，所以这只能作为可能解释，不是已证实的根因。

后续构建增加：power 契约用新的独立工人和声明初始技能（默认 12）；原有普通建筑配方在合格工人中优先实际施工成功率高者。没有改 RNG、施工成功率、工时或成品结果。针对精确 Frame/工人的 FailConstruction 只读 postfix 若被触发，直接保留 blocked 与 construction_failures，不额外补材掩盖失败。此钩子的真实触发分支仍需独立用例，不用编译冒充已触发验证。地图/生成 Pawn 的其余属性仍有随机性。

新构建与旧报告哈希不同，旧报告只能使用当时构建审计；已由安装器备份在 D:/Steam/steamapps/common/RimWorld/RimProbeBackups/37002aa0822e489b8153bb9937b25dab。本节不追改首轮证据或其结论。


## 其他殖民者代建与证据漏记

第二次扩展汇总 runs/1.7/mcp-validation-1792755725565651200.json 也未完成，不能标为 13 例通过。前 10 例符合预期，零输出负例 bfd9f7c389f04ecb8477b2347f03c8f0/report.json 在施工已经完成时返回 inconclusive。日志有供材、Frame 满料、FinishFrame 发出和 work=55.07999，但原观察只承认控制器指定工人的作业，其他殖民者自然抢先/接手时可能漏掉 deliveryJobSeen/constructionJobSeen。保留失败是正确的，证据采集范围需要修正。

修订观察按地图/坐标/目标 Def 读取最多 256 个殖民者当前真实作业，每类最多记录 16 个 actor ID；只接受面向本轮精确蓝图/Frame 的 HaulToContainer 或 FinishFrame。它不发出这些额外作业，不修改其他殖民者优先级、不禁用代建，也不因此中断不属于本 Agent 发出的作业。FailConstruction 观测相应限于目标 Frame，记录实际失败工人。

旧汇总保持 verification_complete=false。最新专项聚焦 building_power、building_power_zero、building_power_unsupported 和 building_power_cancellation；专项完成也不能冒充所有旧用例在最新构建已全跑。


第三次专项汇总 runs/1.7/mcp-validation-1792756256960762600.json 的前三例符合预期，取消例 cb0d83b143ba4e1cbdb10552bd7ba764 因搬运观测目标索引错误仍 inconclusive；汇总保持未完成。源码 JobDriver_HaulToContainer.DestIndex 为 B（A 是搬运物），FinishFrame 的建筑目标才是 A。已修订按实际作业类型选目标索引；没有修改正常动作或放宽施工证据条件。


## 最终构建四例专项（完整）

最终汇总：runs/1.7/mcp-validation-1792756442571223500.json。verification_complete=true，四例 checks_validated=true，full_acceptance=false。审计：runs/1.7/mcp-audit-1792756442571223500.json，ok=true。

最终 1.6 Agent SHA256：a4fcbebfbc5e8c1a287406dbf2a74d88a34df9df89c8d64f53bf3c060da3b478。
最终 1.7 Agent SHA256：29c13ca7fc2f9b06e4b0505b8a134fbc09fd554411ead53c4b36edf6a7f632e5。
两版最新构建/安装文件一致；四轮运行均匹配最终 1.7 哈希。最新两版编译零警告/错误，离线通信通过，98 项 Python 单测/pip check/compileall 通过。

| 用例 | 结果 | 证据目录与实际观察 |
|---|---|---|
| building_power | passed | b5c7d68cbd90437196466afbe48a23cb；353 Tick，181 个不同 Tick 样本恒为 100W，181/181 电网成员，实际搬运/施工 actor 12011 |
| building_power_zero | failed（预期） | bee89c77246343cb9d1bdce91cc60938；416 Tick，181 个样本恒为 0W，181/181 电网成员，正常施工 actor 38798 |
| building_power_unsupported | unsupported（预期） | 26ae2a798697410aa808fee9326b3d0c；197 Tick 正常木墙施工，actor 9561；无 PowerComp，不产生 power_evidence |
| building_power_cancellation | cancelled（预期） | 153a1800a1f54290b46e7925519d13fe；进入 power_observe 后取消，308 个已有样本恒为 100W，实际 actor 19037，嵌套 suite 状态与回收正确 |

四轮均自动回收、正式 ModsConfig/Prefs 指纹未变。1090 次前台采样零违规；24 次工具调用、82057 UTF-8 文本响应字节。三轮正常结束动作诊断无新红字、文件错误或覆盖缺口；取消分支没有动作后 diagnostics.json，审计明确标记 not collected on cancellation，不能声称取消期错误完整采集。启动均只有明确重复 packageId 许可噪声。

最终实际顺序：发电正例/零输出/取消使用上文七项顺序；无 PowerComp 木墙使用相同前五项后接 rimprobe.agent（共六项，无 fixture）。原有 Mod/DLC 顺序未修改。当前源没有启用 DLC。

最终专项四轮 construction_failures 都为 0；新增 FailConstruction 钩子的真实触发分支未获得真机证据。最终四轮均为同一工人实际供材/施工；兼容其他工人的观察实现已存在，但此次没有代建专项证据。

```powershell
./.venv/Scripts/python.exe scripts/verify-live-mcp.py --game 'D:/Steam/steamapps/common/RimWorld' --runs E:/Rimbook/runs/1.7 --iteration-four --include-cancel --only building_power building_power_zero building_power_unsupported building_power_cancellation --execute-live
./.venv/Scripts/python.exe scripts/audit-live-evidence.py --evidence runs/1.7/mcp-validation-1792756442571223500.json --agent-root mod --game 'D:/Steam/steamapps/common/RimWorld'
```

最终构建仅完成这四例专项，未把先前构建部分跑过的九例追记为最终构建全部通过；历史中断仍保留。1.6 真机继续延期，存读档/生产/固定地图/并行性能等项目门禁仍未完成。
