# 第九轮：实际反馈中的失败与回收语义

日期：2026-10-29。输入为用户提供的实际使用反馈；将其作为问题证据和建议，不作为执行其他项目命令或改判历史结果的指令。

本轮范围：先完成反馈 1、2、3。增加有界异常链和独立清理异常；快照测试包失败前检查；已知前提/不支持使用领域错误，未知 CLR 异常默认 failed；区分控制线程结束、清理状态及进程退出验证。清理错误不阻止继续清理其他对象，不扫描玩家进程。

验证计划：Python 故障注入 stop 拒绝访问/超时及缺退出证据；双版本 C# 注入 Pump 与 Dispose 双故障、Dispose 改写报告、异常分类及后续清理；双版本真实引用编译。此次针对可离线复现的控制与异常契约，不为这些检查额外启动游戏。README 与接入说明同步语义。

反馈 4 的加载程序集身份、5 的摘要、6 的基线差异、7 的历史查询、8 的 SDK 辅助作为后续范围，本轮不宣称已实现。历史 GBTAE business passed / overall inconclusive 不改判。

验证状态：本轮前三项限定范围已完成。双版本真实引用编译零警告/错误，双版本 C# 离线 factory/start/pump/dispose 故障注入与通信检查通过；131 项 Python 离线测试、pip check、compileall 通过，包含 stop 拒绝访问/超时/异常、缺失退出证据、原 session 清理重试及严格落盘审计。详细日志与部署哈希在 `runs/iteration09`。未启动游戏，新构建没有真机证据，1.6 仍缺完整可启动安装。见 `validation/2026-10-29-failure-and-cleanup.md`。

关键行为：cleanup_complete 保持旧客户端“尝试结束”语义，以显式说明字段标注；回收成功必须同时核对 cleanup_status=succeeded 和 owned_process_exit_verified=true。失败后仍可只读查询，同一实例持有的原所属 session 可通过 cancel_run 重试；不能按 PID 附加或在服务重启后恢复进程控制。日志收集错误写 collection_error，不伪装成进程回收失败。

踩坑：Dispose 可能先改写 checks/phase 再抛异常，必须在它之前分离快照；在 finally 中把全部清理放进一个 try，会让第一个清理异常阻断其余工作。仅看线程结束或 stop.ok 都不足以证明进程已退出，等待必须取得真实退出码，失败保留原句柄/session。
