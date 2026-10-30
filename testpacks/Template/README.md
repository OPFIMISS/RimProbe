# Minimal compiled test pack / 最小测试包

Copy this directory into your own project. Rename the packageId, namespace and registered key, add your real target dependency/loadAfter, then implement only missing actions and independent observers in `ExampleProbe.cs`. Do not invent author/license metadata. The starter deliberately returns **inconclusive**, not a false feature pass.

复制目录后改 packageId、命名空间、注册 key，加入实际目标依赖/顺序；只补缺失动作和独立 observer。Start/Pump/Report/Dispose 都在游戏主线程调用，Pump 必须立即返回，禁止 sleep、无界循环和后台读游戏对象。沿用计划整体 Tick/墙钟预算、最多 64 个 checks、有界证据和独立清理异常。

Build the matching core Agent first, then:

```powershell
dotnet build testpacks/Template/1.7/ExampleProbe.csproj -c Release -p:GamePath='D:/Games/RimWorld1.7'
dotnet build testpacks/Template/1.6/ExampleProbe.csproj -c Release -p:ManagedPath='D:/References/RimWorld1.6/Managed'
```

Paths are placeholders. Deploy the resulting `mod` directory as a **new** mod directory under your real game; do not overwrite an unrelated mod. Include your renamed packageId in `extra_mods` for the disposable run. `query_tests` discovers the key, then `registered_test` invokes it. No MCP client needs permission to name arbitrary methods or code strings.

将生成的 mod 放入游戏的新目录，通过一次性 profile 的 extra_mods 显式加载。正常玩家列表无需启用。删除/清理仅限自己创建且已确认归属的目录；不要移除目标 Mod、存档或玩家配置。

```json
{"schema":1,"intent":"Run explicitly installed feature observers","steps":[{"id":"discover","op":"query_tests"},{"id":"feature","op":"registered_test","key":"example.observe"}]}
```

Use normal Jobs and typed core interactions whenever they already exist. Avoid directly writing expected results, restoring modified gameplay state as if it had passed, or attributing unknown CLR failures to a target mod. See [SDK contract](../../docs/registered-test-packs.md) and the executable [interaction fixture](../InteractionFixtures/InteractionFixtures.cs).
