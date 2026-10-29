using System.Runtime.Serialization;

namespace RimProbe.Agent;

internal sealed class ProbeStepException : Exception
{
    public string Outcome { get; }
    public ProbeStepException(string outcome, string message) : base(message) { Outcome = outcome; }
}

[DataContract]
internal sealed class ProbeFailure
{
    [DataMember(Name = "type")] public string Type { get; set; } = "";
    [DataMember(Name = "message")] public string Message { get; set; } = "";
    [DataMember(Name = "stack")] public string Stack { get; set; } = "";
    [DataMember(Name = "step_id")] public string? StepId { get; set; }
    [DataMember(Name = "test_key")] public string? TestKey { get; set; }
    [DataMember(Name = "lifecycle_phase")] public string LifecyclePhase { get; set; } = "";
    [DataMember(Name = "test_phase")] public string? TestPhase { get; set; }
    [DataMember(Name = "failure_domain")] public string FailureDomain { get; set; } = "unknown";
    [DataMember(Name = "truncated")] public bool Truncated { get; set; }
    [DataMember(Name = "inner_exception", EmitDefaultValue = false)] public ProbeFailure? InnerException { get; set; }

    internal static ProbeFailure Capture(Exception error, PlanStep? step, string lifecycle, string? phase, string domain, int depth = 0)
    {
        string message = error.Message ?? "";
        string stack = error.StackTrace ?? "";
        return new ProbeFailure { Type = Limit(error.GetType().FullName ?? error.GetType().Name, 200),
            Message = Limit(message, 400), Stack = Limit(stack, 1000), StepId = step?.Id, TestKey = step?.Key,
            LifecyclePhase = lifecycle, TestPhase = phase, FailureDomain = domain,
            Truncated = message.Length > 400 || stack.Length > 1000 || depth >= 2 && error.InnerException != null,
            InnerException = error.InnerException == null || depth >= 2 ? null : Capture(error.InnerException, step, lifecycle, phase, domain, depth + 1) };
    }

    private static string Limit(string value, int limit) => value.Length <= limit ? value : value.Substring(0, limit);
}

internal sealed partial class ScenarioSuite
{
    private string lifecyclePhase = "agent";
    private string? testPhase;
    private PlanStep? lifecycleStep;

    internal static string ClassifyFailure(Exception error) => error is ProbeStepException known ? known.Outcome : "failed";

    internal void HandleFailure(Exception error)
    {
        if (Report == null) return;
        if (registeredTest != null)
        {
            try { testPhase = SnapshotRegisteredEvidence(registeredTest.Report).Phase; }
            catch { }
        }
        Report.PrimaryFailure ??= ProbeFailure.Capture(error, lifecycleStep ?? contract?.Steps?.ElementAtOrDefault(index),
            lifecyclePhase, testPhase, error is ProbeStepException ? "precondition" : "unknown");
        FailCurrentStep(ClassifyFailure(error), Report.PrimaryFailure.Type + ": " + Report.PrimaryFailure.Message);
        BoundFailureEvidence();
    }

    internal void CleanupAction(Action cleanup, PlanStep? step, string phase, string? internalPhase = null)
    {
        try { cleanup(); }
        catch (Exception error)
        {
            Report!.Status = "failed";
            if (Report.CleanupFailures.Count < 4)
                Report.CleanupFailures.Add(ProbeFailure.Capture(error, step, phase, internalPhase, "unknown"));
            else Report.FailureEvidenceTruncated = true;
        }
    }

    private void BoundFailureEvidence()
    {
        if (Report == null || WireJson.Serialize(Report).Length <= 40000) return;
        Report.FailureEvidenceTruncated = true;
        foreach (PlanStepReport entry in Report.Steps)
        {
            entry.RegisteredTest = null;
            entry.FailureContext = null;
            entry.Snapshot = null;
            entry.Definitions = null;
            entry.Construction = null;
            entry.DiagnosticsOmitted = true;
            entry.Detail = Short(entry.Detail);
        }
        Report.Message = Short(Report.Message);
        if (WireJson.Serialize(Report).Length <= 40000) return;
        foreach (ProbeFailure failure in Report.CleanupFailures.Concat(Report.PrimaryFailure == null ? Array.Empty<ProbeFailure>() : new[] { Report.PrimaryFailure }))
        {
            failure.Stack = "";
            failure.InnerException = null;
            failure.Truncated = true;
        }
    }
}
