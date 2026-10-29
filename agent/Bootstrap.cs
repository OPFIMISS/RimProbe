using HarmonyLib;
using RimWorld;
using Verse;

namespace RimProbe.Agent;

[StaticConstructorOnStartup]
public static class Bootstrap
{
    static Bootstrap()
    {
        string? directory = Environment.GetEnvironmentVariable("RIMPROBE_SESSION_DIR");
        string? sessionId = Environment.GetEnvironmentVariable("RIMPROBE_SESSION_ID");
        string? token = Environment.GetEnvironmentVariable("RIMPROBE_TOKEN");
        if (string.IsNullOrWhiteSpace(directory) || string.IsNullOrWhiteSpace(sessionId) || string.IsNullOrWhiteSpace(token))
        {
            return;
        }

        try
        {
            if (!Path.IsPathRooted(directory) || Path.GetFullPath(directory) != directory
                || !Guid.TryParseExact(sessionId, "N", out _) || token.Length != 64)
            {
                throw new InvalidOperationException("Invalid RimProbe session environment.");
            }

            BridgeRuntime runtime = new(directory, sessionId, token);
            BridgeRuntime.Instance = runtime;
            Harmony harmony = new("rimprobe.agent");
            harmony.Patch(
                AccessTools.Method(typeof(Root), nameof(Root.Update)),
                postfix: new HarmonyMethod(typeof(BridgeRuntime), nameof(BridgeRuntime.Pump)));
            harmony.Patch(AccessTools.Method(typeof(Log), nameof(Log.Error), new[] { typeof(string) }),
                postfix: new HarmonyMethod(typeof(ErrorJournal), nameof(ErrorJournal.Record)));
            harmony.Patch(AccessTools.Method(typeof(Thing), nameof(Thing.Ingested)),
                postfix: new HarmonyMethod(typeof(IngestObserver), nameof(IngestObserver.AfterIngest)));
            harmony.Patch(AccessTools.Method(typeof(Dialog_InfoCard), nameof(Dialog_InfoCard.DoWindowContents)),
                postfix: new HarmonyMethod(typeof(UiDrawObserver), nameof(UiDrawObserver.AfterDraw)));
            harmony.Patch(AccessTools.Method(typeof(Frame), nameof(Frame.FailConstruction)),
                postfix: new HarmonyMethod(typeof(ConstructionObserver), nameof(ConstructionObserver.AfterFailure)));
            runtime.Start();
            AppDomain.CurrentDomain.ProcessExit += (_, _) => runtime.Dispose();
            Log.Message("[RimProbe] Agent enabled for an isolated test session.");
        }
        catch (Exception error)
        {
            BridgeRuntime.Instance?.Dispose();
            Log.Error("[RimProbe] Agent startup failed: " + error);
        }
    }
}
