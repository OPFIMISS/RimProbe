# 第九轮：异常与清理契约验证

日期：2026-10-29。依据用户提供的实际使用反馈实现前三项 P1 改进；没有改动反馈项目、读取其他 Mod 代码、修改玩家配置/存档或启动游戏。历史业务通过但整体 inconclusive 的运行不改判。

## 已实现

- 通用计划 `primary_failure` 与 `cleanup_failures[]` 分离。保存异常类型、400 字符消息、1000 字符堆栈、最多三层异常链、step_id/test_key、生命周期和测试包 phase。未知来源为 unknown；有界裁剪标记 truncated / failure_evidence_truncated，不承诺完整堆栈。
- 测试包有效 checks 在 Dispose 前复制为分离对象，Dispose 改写原报告不会更改已保存检查。Dispose 不重复调用；最多四条清理异常，后续施工/逐 Pawn 作业清理仍继续。报告超过 40 KB 时显式裁剪附加证据并保留异常根信息。
- 执行器显式识别的缺 Def/前提失败为 blocked，未支持机制为 unsupported；来源不明的 InvalidOperationException、NotSupportedException 等均 failed。不根据异常堆栈出现哪个 Mod 推断责任。本轮改变限定于通用 Scenario 执行链，旧固定配方未做全面异常重构。
- `controller_finished` 反映工作线程结束，`cleanup_status` 为 pending/running/succeeded/failed，`owned_process_exit_verified` 仅在 stop 返回明确退出验证时成立。`cleanup_complete` 是旧兼容别名，表示尝试结束。stop 必须取得整数退出码，超时/拒绝访问/退出未验证时保留原 session。
- 失败后可继续 get_run/get_artifact；cancel_run 可对同一实例保留的原所属 session 请求一次有界清理重试，不扫描或附加其他进程。重试成功不自动升级业务结果，原 cleanup_error 保留。日志收集错误另记 collection_error。
- 新格式只读审计核对摘要、落盘 report 与 stop 的退出证据，不能靠线程结束字段通过审计。旧历史格式仍按其原有字段审计，不倒填新的验证字段。

## 验证层次

Python 131 项完整离线测试通过，pip check 与 compileall 通过；结果见 `runs/iteration09/python-tests.txt`、`dependencies.txt`，新增故障检查见 `runner-tests.txt`、`evidence-tests.txt`。测试覆盖拒绝访问、两次等待超时、未知停止异常、缺退出码/标记、阻止未回收时启动新一轮、同一所属 session 重试、收集失败但回收成功，以及严格落盘审计。

1.6/net472 与 1.7/net10.0 均用真实引用编译，零警告/错误。C# 两版离线测试实际注入 factory/start/pump/dispose 异常；Pump 内异常和 Dispose 异常同时保留，检查快照未被 Dispose 清空污染，堆栈真实存在且有界，异常链有界，后续清理可继续。它们运行在普通 .NET/.NET Framework 测试进程，**未访问真实地图对象或执行游戏渲染，不等于 Mono/Waylith 实机验证**。

证据：`runs/iteration09/build-1.6.txt`、`build-1.7.txt`、`agent-offline-1.6.txt`、`agent-offline-1.7.txt` 及两份 build-evidence。`validation.json` 校对构建/安装/编译证据的 Agent SHA256 一致。

确认没有 RimWorld/RimWorldWin64 进程后，使用自有安装清单校验的 install-agent --update-owned 更新本机 Agent；安装结果和备份目录见 `runs/iteration09/install.json`。没有手动覆盖未知文件，没有创建或启用测试包，也没有改 Mod 排序。其他项目已启动的 MCP 服务需要重新加载后才能使用新的 Python 逻辑；新一轮游戏会加载更新的 Agent。

## 仍未覆盖

新构建的真实游戏故障与取消回归尚未执行，1.6 仍缺完整安装。非游戏离线测试不能证明所有原生 API/Mod 清理路径都成功；游戏进程退出验证也不等于所有外部资源行为已穷举。剩余反馈：目标/测试包的实际程序集来源与 MVID/哈希、compact summary、保守基线差异、历史只读查询、SDK 时钟与 typed evidence 均留待后续，不作为本轮已完成功能。
