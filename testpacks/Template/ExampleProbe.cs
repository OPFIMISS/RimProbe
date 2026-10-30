using RimProbe.Agent;
using Verse;

namespace Example.RimProbeTests;

[StaticConstructorOnStartup]
public static class Registration
{
    static Registration() { RegisteredProbeTests.Register("example.observe", () => new ExampleProbe()); }
}

// Replace this observer with source-derived checks and missing actions for your framework.
// The starter deliberately never returns a functional pass merely because a map exists.
public sealed class ExampleProbe : IProbeTest
{
    private Map? map;
    public ProbeTestReport Report { get; } = new() { Scope = "Template: map readiness only; actual feature checks must be implemented." };
    public void Start(Map initialMap) { map = initialMap; Report.Phase = "observing"; }
    public void Pump()
    {
        Report.Checks.Add(new ProbeTestCheck { Name = "map_registered", Passed = map != null && Find.Maps.Contains(map), Actual = map?.uniqueID ?? -1, Expected = "registered disposable map (not a business assertion)" });
        Report.Status = "inconclusive";
        Report.Phase = "needs_feature_observer";
    }
    public void Dispose() { map = null; } // Release only resources owned by this test; keep cleanup idempotent.
}
