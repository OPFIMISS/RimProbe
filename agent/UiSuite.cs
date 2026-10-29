using System.Diagnostics;
using Verse;

namespace RimProbe.Agent;

internal sealed class UiSuite
{
    public SuiteReport? Report { get; private set; }
    private BehaviorContract? contract;
    private readonly Stopwatch clock = new();
    private readonly Stopwatch showing = new();
    private Dialog_InfoCard? window;

    public void Start(SuiteOptions? options)
    {
        BehaviorContract? request = options?.Contract;
        if (request == null || !Guid.TryParseExact(options?.RunId, "N", out _) || request.Schema != 1 || request.Recipe != "ui_info_card"
            || request.Fixture == null || request.Expect == null || request.Expect.Length != 4 || request.Expect.Select(entry => entry.Kind).Distinct().Count() != 4
            || request.TimeoutSeconds < 5 || request.TimeoutSeconds > 600 || double.IsNaN(request.Fixture.HoldSeconds)
            || request.Fixture.HoldSeconds < 1 || request.Fixture.HoldSeconds > 10) throw new ArgumentException("Invalid bounded UI contract.");
        if (Report?.RunId == options!.RunId) return;
        if (Report?.Status == "running") throw new InvalidOperationException("A UI contract is running.");
        contract = request;
        window = null;
        clock.Restart();
        showing.Reset();
        Report = new SuiteReport { RunId = options.RunId!, DefName = request.DefName!, Recipe = "ui_info_card", Intent = request.Intent,
            Excluded = new[] { "pixel correctness", "screenshots", "mouse/keyboard hit-testing", "arbitrary custom windows", "other tabs", "save/load" } };
    }

    public void Cancel()
    {
        if (Report?.Status == "running") Finish("cancelled", "UI contract cancelled.");
    }

    public void Pump()
    {
        if (Report?.Status != "running") return;
        try
        {
            if (clock.Elapsed.TotalSeconds >= contract!.TimeoutSeconds) { Finish("inconclusive", "UI wall-clock budget exhausted."); return; }
            if (LongEventHandler.AnyEventNowOrWaiting || Current.ProgramState != ProgramState.Playing) return;
            Report.TickObserved = Find.TickManager.TicksGame;
            if (Report.Stage == "prepare")
            {
                ThingDef? definition = DefDatabase<ThingDef>.GetNamedSilentFail(contract.DefName);
                if (definition == null) { Finish("unsupported", "Target ThingDef is not loaded."); return; }
                if (contract.Expect!.Any(expectation => expectation.Kind != "window_opened" && expectation.Kind != "window_drawn" && expectation.Kind != "window_in_bounds" && expectation.Kind != "window_closed"))
                { Finish("unsupported", "Unknown UI observer."); return; }
                window = new Dialog_InfoCard(definition);
                UiDrawObserver.Track(window);
                Find.WindowStack.Add(window);
                Report.TickStarted = Find.TickManager.TicksGame;
                Check("window_opened", Find.WindowStack.Windows.Contains(window), "Opened the real game information card; no callback substituted for drawing.");
                Report.Stage = "ui_draw_and_observe";
                showing.Restart();
                return;
            }
            if (showing.Elapsed.TotalSeconds < contract!.Fixture!.HoldSeconds) return;
            if (window == null) { Finish("failed", "Tracked window is missing."); return; }
            Check("window_drawn", UiDrawObserver.Draws > 0, "Completed real DoWindowContents repaint calls=" + UiDrawObserver.Draws + "; no direct manual draw call.");
            UnityEngine.Rect bounds = window.windowRect;
            bool inBounds = bounds.width > 0 && bounds.height > 0 && bounds.xMin >= -1 && bounds.yMin >= -1
                && bounds.xMax <= UI.screenWidth + 1 && bounds.yMax <= UI.screenHeight + 1;
            Check("window_in_bounds", inBounds, "Rect=" + bounds + ", logical screen=" + UI.screenWidth + "x" + UI.screenHeight);
            window.Close(false);
            Check("window_closed", !Find.WindowStack.Windows.Contains(window), "Closed only this adapter-owned window through its normal Close method.");
            bool passed = Report.Checks.All(check => check.Status == "passed");
            Finish(passed ? "passed" : "failed", "Info-card lifecycle/drawing/bounds checks complete; pixel and input hit-testing remain excluded.");
        }
        catch (Exception error) { Finish("failed", error.GetType().Name + ": " + error.Message); }
    }

    private void Check(string name, bool passed, string detail)
    {
        Report!.Checks.Add(new SuiteCheck { Name = name, Status = passed ? "passed" : "failed", Detail = detail });
    }

    private void Finish(string status, string message)
    {
        Report!.Status = status;
        Report.Message = message;
        try
        {
            if (window != null && Find.WindowStack.Windows.Contains(window)) window.Close(false);
        }
        catch (Exception error)
        {
            Report.Status = "failed";
            Report.Message += " Cleanup failed: " + error.Message;
        }
        finally
        {
            UiDrawObserver.Track(null);
        }
    }
}
