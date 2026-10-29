using System.Runtime.Serialization;
using System.Text.RegularExpressions;
using Verse;

namespace RimProbe.Agent;

public interface IProbeTest : IDisposable
{
    void Start(Map map);
    void Pump();
    ProbeTestReport Report { get; }
}

[DataContract]
public sealed class ProbeTestReport
{
    [DataMember(Name = "status")] public string Status { get; set; } = "running";
    [DataMember(Name = "phase")] public string Phase { get; set; } = "preparing";
    [DataMember(Name = "scope")] public string Scope { get; set; } = "";
    [DataMember(Name = "checks")] public List<ProbeTestCheck> Checks { get; set; } = new();
}

[DataContract]
public sealed class ProbeTestCheck
{
    [DataMember(Name = "name")] public string Name { get; set; } = "";
    [DataMember(Name = "passed")] public bool Passed { get; set; }
    [DataMember(Name = "actual")] public double Actual { get; set; }
    [DataMember(Name = "expected")] public string Expected { get; set; } = "";
}

public static class RegisteredProbeTests
{
    private static readonly Dictionary<string, Func<IProbeTest>> factories = new(StringComparer.Ordinal);

    public static void Register(string key, Func<IProbeTest> factory)
    {
        if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("RIMPROBE_SESSION_ID"))) return;
        if (!Regex.IsMatch(key, "^[a-z][a-z0-9_.]{0,79}\\z") || factory == null || factories.Count >= 64 || factories.ContainsKey(key))
            throw new ArgumentException("Invalid, duplicate or excessive registered test.");
        factories.Add(key, factory);
    }

    public static string[] Keys => factories.Keys.OrderBy(key => key, StringComparer.Ordinal).ToArray();

    internal static IProbeTest Create(string key) => factories.TryGetValue(key, out Func<IProbeTest>? factory)
        ? factory() : throw new ProbeStepException("unsupported", "Test is not registered by an explicitly installed test pack: " + key);
}

internal sealed partial class ScenarioSuite
{
    private IProbeTest? registeredTest;

    internal static ProbeTestReport SnapshotRegisteredEvidence(ProbeTestReport evidence)
    {
        ValidateRegisteredEvidence(evidence);
        return new ProbeTestReport { Status = evidence.Status, Phase = evidence.Phase, Scope = evidence.Scope,
            Checks = evidence.Checks.Select(check => new ProbeTestCheck { Name = check.Name, Passed = check.Passed,
                Actual = check.Actual, Expected = check.Expected }).ToList() };
    }

    internal void StartRegisteredTest(PlanStep step, Map initialMap)
    {
        lifecycleStep = step;
        testPhase = null;
        lifecyclePhase = "factory";
        registeredTest = RegisteredProbeTests.Create(step.Key!) ?? throw new InvalidOperationException("Test factory returned null.");
        lifecyclePhase = "start";
        registeredTest.Start(initialMap);
    }

    internal static void ValidateRegisteredEvidence(ProbeTestReport evidence)
    {
        if (evidence == null || evidence.Checks == null || evidence.Scope == null || evidence.Phase == null || evidence.Status == null
            || evidence.Checks.Count > 64 || evidence.Scope.Length > 1500 || evidence.Phase.Length > 120 || evidence.Status.Length > 30
            || evidence.Checks.Any(check => check == null || check.Name == null || check.Expected == null
                || check.Name.Length > 120 || check.Expected.Length > 300 || double.IsNaN(check.Actual) || double.IsInfinity(check.Actual)))
            throw new InvalidOperationException("Registered test exceeded evidence limits.");
    }

    internal void ObserveRegisteredTest(PlanStep step)
    {
        lifecycleStep = step;
        lifecyclePhase = "report";
        testPhase = SnapshotRegisteredEvidence(registeredTest!.Report).Phase;
        lifecyclePhase = "pump";
        registeredTest!.Pump();
        lifecyclePhase = "report";
        ProbeTestReport evidence = SnapshotRegisteredEvidence(registeredTest.Report);
        testPhase = evidence.Phase;
        Report!.Stage = step.Id + ":registered_test:" + evidence.Phase;
        if (evidence.Status == "running") return;
        bool verified = evidence.Status == "passed" && evidence.Checks.Count > 0 && evidence.Checks.All(check => check.Passed);
        string status = evidence.Status == "passed" ? verified ? "passed" : "inconclusive" : evidence.Status;
        if (!new[] { "passed", "failed", "blocked", "unsupported", "inconclusive", "cancelled" }.Contains(status))
            throw new InvalidOperationException("Registered test returned an invalid outcome.");
        Complete(step, status, "Explicit compiled test pack: " + step.Key);
        if (Report.Status != "running") return;
        Report.Steps[Report.Steps.Count - 1].RegisteredTest = evidence;
        int previousFailures = Report.CleanupFailures.Count;
        DisposeRegisteredTest();
        if (Report.CleanupFailures.Count > previousFailures)
        {
            Finish("failed", "Registered test cleanup failed; inspect cleanup_failures.");
            return;
        }
        if (WireJson.Serialize(Report).Length > 40000)
        {
            Report.Steps[Report.Steps.Count - 1].RegisteredTest = null;
            Finish("inconclusive", "Registered test evidence exceeded the report budget.");
            return;
        }
        if (verified) assertions++;
        else Finish(status, "Registered test stopped; inspect its checks and scope.");
    }

    private void DisposeRegisteredTest()
    {
        IProbeTest? disposing = registeredTest;
        registeredTest = null;
        if (disposing != null) CleanupAction(disposing.Dispose, lifecycleStep, "dispose", testPhase);
    }
}
