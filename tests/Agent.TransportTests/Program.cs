using System.Diagnostics;
using System.Net.Sockets;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Text;
using RimProbe.Agent;

string directory = Path.Combine(Path.GetTempPath(), "rimprobe-transport-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(directory);
string sessionId = Guid.NewGuid().ToString("N");
string token = new('a', 64);
using BridgeRuntime runtime = new(directory, sessionId, token);
try
{
    for (int index = 0; index < 20; index++)
    {
        ErrorJournal.Record(new string('x', 1100));
    }
    Assert(ErrorJournal.Sequence == 20, "red journal sequence persists after eviction");
    Assert(ErrorJournal.Snapshot().Length == 16, "red journal is bounded");
    Assert(ErrorJournal.Snapshot()[0].Sequence == 5, "red journal eviction is observable");
    Assert(ErrorJournal.Snapshot()[0].Text.Length == 1000, "red journal text is bounded");
    ScenarioSuite.ValidateSteps(new[] {
        new PlanStep { Id = "find", Op = "find_thing", Bind = "existing", DefName = "Wall", Radius = 30 },
        new PlanStep { Id = "create", Op = "spawn_pawn", Bind = "actor", Distance = 3, FoodFraction = 0.25, Faction = "player" },
        new PlanStep { Id = "measure", Op = "measure", Target = "actor", Property = "hp", BindValue = "before" },
        new PlanStep { Id = "check", Op = "assert", Target = "actor", Property = "hp", Compare = "eq", RelativeTo = "before", Value = 0 }
    });
    void RejectPlan(PlanStep[] steps)
    {
        bool rejected = false;
        try { ScenarioSuite.ValidateSteps(steps); }
        catch (ArgumentException) { rejected = true; }
        Assert(rejected, "unsafe plan rejected before touching game objects");
    }
    RejectPlan(new[] { new PlanStep { Id = "evil", Op = "eval" } });
    ScenarioSuite.ValidateSteps(new[] {
        new PlanStep { Id = "pawn", Op = "spawn_pawn", Bind = "actor", Distance = 3, FoodFraction = 0.25, Faction = "player" },
        new PlanStep { Id = "ready", Op = "wait_until", Condition = "interaction_ready", TimeoutSeconds = 30, StableFrames = 3 },
        new PlanStep { Id = "choices", Op = "enumerate_choices", Target = "actor", BindChoice = "landing", CellAtTarget = true, Limit = 8 },
        new PlanStep { Id = "choose", Op = "select_choice", Choice = "landing" },
        new PlanStep { Id = "observe", Op = "assert", Target = "actor", Property = "map.layer_id", Compare = "eq", Value = 0 }
    });
    RejectPlan(new[] { new PlanStep { Id = "choose", Op = "select_choice", Choice = "future" } });
    RejectPlan(new[] { new PlanStep { Id = "bad", Op = "enumerate_choices", Limit = 9 } });
    RejectPlan(new[] { new PlanStep { Id = "bad", Op = "enumerate_choices", Limit = 8, X = 4 } });
    RejectPlan(new[] { new PlanStep { Id = "bad", Op = "enumerate_choices", Limit = 8, CellAtTarget = true } });
    RejectPlan(new[] { new PlanStep { Id = "bad", Op = "wait_until", Condition = "IsTargeting", TimeoutSeconds = 30, StableFrames = 3 } });
    RejectPlan(new[] { new PlanStep { Id = "bad", Op = "wait_until", Condition = "interaction_ready", TimeoutSeconds = 30, StableFrames = 1 } });
    RejectPlan(new[] { new PlanStep { Id = "bad", Op = "wait_until", Condition = "ability_job_finished", TimeoutSeconds = 30, StableFrames = 3 } });
    Assert(ScenarioSuite.StepFidelity("cast") == "normal_game_action" && ScenarioSuite.StepFidelity("select_choice") == "validated_semantic_callback"
        && ScenarioSuite.StepFidelity("wait_until") == "state_observation", "semantic callbacks and readiness cannot masquerade as UI hit tests or normal-job effect passes");
    InteractionChoice layered = new() { Handle = new string('a', 32), MapId = 7, TileId = 19, LayerId = 3, Available = false, ObjectType = "MapParent" };
    string layeredJson = Encoding.UTF8.GetString(WireJson.Serialize(layered));
    Assert(layeredJson.Contains("\"layer_id\":3") && layeredJson.Contains("\"tile_id\":19") && layeredJson.Contains("\"map_id\":7"), "candidate evidence preserves map identity and full PlanetTile layer separately");
    RejectPlan(new[] { new PlanStep { Id = "find", Op = "find_thing", Bind = "other", DefName = "Human", Radius = 30 },
        new PlanStep { Id = "order", Op = "move", Actor = "other", Target = "other" } });
    RejectPlan(new[] { new PlanStep { Id = "wait", Op = "wait", Ticks = 1 },
        new PlanStep { Id = "late", Op = "spawn_pawn", Bind = "actor", Distance = 3, FoodFraction = 0.25, Faction = "player" } });
    RejectPlan(new[] { new PlanStep { Id = "wait", Op = "wait", Ticks = 1, Bind = "not_an_object" } });
    ScenarioSuite.ValidateSteps(new[] { new PlanStep { Id = "tests", Op = "query_tests" },
        new PlanStep { Id = "test", Op = "registered_test", Key = "owner.feature" } });
    ScenarioSuite.ValidateSteps(new[] {
        new PlanStep { Id = "create", Op = "spawn_pawn", Bind = "actor", Distance = 3, FoodFraction = 0.25, Faction = "player" },
        new PlanStep { Id = "idle", Op = "wait_assert", Target = "actor", Property = "pawn.ability_casting", Compare = "eq", Value = 0, Ticks = 120 }
    });
    RejectPlan(new[] {
        new PlanStep { Id = "find", Op = "find_thing", Bind = "existing", DefName = "Human", Radius = 30 },
        new PlanStep { Id = "idle", Op = "assert", Target = "existing", Property = "pawn.ability_casting", Compare = "eq" }
    });
    PlanStep failedCondition = new() { Id = "missing", Op = "wait_assert", Target = "target", Other = "other",
        Property = "pawn.distance_to", Compare = "le", Value = 3, Ticks = 120, HoldTicks = 20 };
    List<string> inspected = new();
    PlanFailureContext failure = ScenarioSuite.CollectFailureContext(failedCondition, 120, 7,
        new[] { "target", "actor", "fourth", "fifth", "sixth" }, alias =>
        {
            inspected.Add(alias);
            if (alias == "other") throw new InvalidOperationException(new string('x', 1000));
            return new PlanObjectSnapshot { DefName = alias, Job = "CastAbilityOnThing", JobAbility = "Example", JobId = 42 };
        });
    Assert(inspected.SequenceEqual(new[] { "target", "other", "actor", "fourth" }), "diagnostics prioritize references, deduplicate and inspect at most four objects");
    Assert(failure.ObjectsTruncated && failure.Objects.Length == 4, "diagnostic alias truncation is explicit");
    Assert(failure.Objects[1].Snapshot == null && failure.Objects[1].Error!.Length == 120
        && failure.Objects[2].Snapshot!.JobId == 42, "one broken snapshot is bounded and does not prevent later evidence");
    Assert(ReferenceEquals(failure.Condition, failedCondition) && failure.ElapsedTicks == 120 && failure.SampledHoldTicks == 7,
        "failed condition and sampled progress retained");
    string failureJson = Encoding.UTF8.GetString(WireJson.Serialize(new PlanStepReport { Status = "failed", FailureContext = failure }));
    Assert(failureJson.Contains("\"job_ability\":\"Example\"") && failureJson.Contains("\"job_id\":42")
        && failureJson.Contains("\"status\":\"failed\""), "failure evidence serializes with original outcome and job identity");
    PlanFailureContext actionFailure = ScenarioSuite.CollectFailureContext(new PlanStep { Id = "action", Op = "cast", Actor = "actor" },
        -1, -1, Array.Empty<string>(), _ => new PlanObjectSnapshot());
    Assert(actionFailure.Condition == null && actionFailure.ElapsedTicks == 0 && actionFailure.SampledHoldTicks == 0,
        "action diagnostics do not fabricate an assertion or negative progress");
    RejectPlan(new[] { new PlanStep { Id = "test", Op = "registered_test", Key = "owner.feature\n" } });
    string? previousSession = Environment.GetEnvironmentVariable("RIMPROBE_SESSION_ID");
    try
    {
        Environment.SetEnvironmentVariable("RIMPROBE_SESSION_ID", null);
        RegisteredProbeTests.Register("offline.inert", () => throw new Exception("must not run"));
        Assert(!RegisteredProbeTests.Keys.Contains("offline.inert"), "test registry stays inert outside owned sessions");
        Environment.SetEnvironmentVariable("RIMPROBE_SESSION_ID", sessionId);
        RegisteredProbeTests.Register("offline.explicit", () => throw new NotSupportedException("explicit factory only"));
        Assert(RegisteredProbeTests.Keys.SequenceEqual(new[] { "offline.explicit" }), "registered keys discoverable");
        bool unknownRejected = false;
        try { RegisteredProbeTests.Create("unregistered.method"); }
        catch (ProbeStepException error) { unknownRejected = error.Outcome == "unsupported"; }
        Assert(unknownRejected, "unregistered code cannot be selected");
        foreach (string key in new[] { "offline.explicit", "System.IO.File", "../path", "owner.feature\n" })
        {
            bool rejected = false;
            try { RegisteredProbeTests.Register(key, () => throw new Exception("must not run")); }
            catch (ArgumentException) { rejected = true; }
            Assert(rejected, "duplicate/invalid registry key rejected");
        }
    }
    finally { Environment.SetEnvironmentVariable("RIMPROBE_SESSION_ID", previousSession); }
    ScenarioSuite.ValidateRegisteredEvidence(new ProbeTestReport { Scope = "bounded partial evidence" });
    foreach (ProbeTestReport excessive in new[] {
        new ProbeTestReport { Scope = new string('x', 1501) },
        new ProbeTestReport { Checks = new List<ProbeTestCheck> { new() { Actual = double.NaN } } },
        new ProbeTestReport { Checks = Enumerable.Range(0, 65).Select(_ => new ProbeTestCheck()).ToList() }
    })
    {
        bool rejected = false;
        try { ScenarioSuite.ValidateRegisteredEvidence(excessive); }
        catch (InvalidOperationException) { rejected = true; }
        Assert(rejected, "oversized/non-finite test evidence rejected");
    }
    Console.WriteLine("Scenario preflight checks passed without game mutation.");
    Assert(ScenarioSuite.ClassifyFailure(new InvalidOperationException("unexpected")) == "failed"
        && ScenarioSuite.ClassifyFailure(new NotSupportedException("unexpected")) == "failed", "CLR exception types alone cannot mask execution failures");
    Assert(ScenarioSuite.ClassifyFailure(new ProbeStepException("blocked", "missing Def")) == "blocked"
        && ScenarioSuite.ClassifyFailure(new ProbeStepException("unsupported", "no adapter")) == "unsupported", "explicit domain failures preserve known outcomes");
    PlanStep faultStep = new() { Id = "fault", Op = "registered_test", Key = "offline.fault" };
    foreach (string faultPhase in new[] { "factory", "start", "pump", "dispose" })
    {
        FaultProbe fixture = new(faultPhase);
        string faultKey = "offline.fault_" + faultPhase;
        Environment.SetEnvironmentVariable("RIMPROBE_SESSION_ID", sessionId);
        RegisteredProbeTests.Register(faultKey, () => faultPhase == "factory" ? throw new InvalidOperationException("factory broke") : fixture);
        Environment.SetEnvironmentVariable("RIMPROBE_SESSION_ID", previousSession);
        PlanStep execution = new() { Id = "fault", Op = "registered_test", Key = faultKey };
        ScenarioSuite scenario = new();
        scenario.Start(new SuiteOptions { RunId = Guid.NewGuid().ToString("N"), Contract = new BehaviorContract
            { Schema = 1, Recipe = "scenario", Intent = "Offline lifecycle fault injection", Steps = new[] { execution }, MaxTicks = 60, TimeoutSeconds = 5 } });
        try
        {
            scenario.StartRegisteredTest(execution, null!);
            scenario.ObserveRegisteredTest(execution);
        }
        catch (Exception error) { scenario.HandleFailure(error); }
        SuiteReport evidence = scenario.Report!;
        Assert(evidence.Status == "failed", faultPhase + " fault cannot pass");
        if (faultPhase != "dispose")
        {
            Assert(evidence.PrimaryFailure!.LifecyclePhase == faultPhase && evidence.PrimaryFailure.FailureDomain == "unknown"
                && evidence.PrimaryFailure.StepId == "fault" && evidence.PrimaryFailure.TestKey == faultKey,
                faultPhase + " original exception attribution retained");
            Assert(evidence.PrimaryFailure.Stack.Length > 0, "exception includes bounded real stack");
        }
        if (faultPhase == "pump" || faultPhase == "dispose")
        {
            Assert(evidence.CleanupFailures.Count == 1 && evidence.CleanupFailures[0].LifecyclePhase == "dispose", "dispose failure retained separately");
            Assert(evidence.Steps[0].RegisteredTest!.Checks[0].Name == "before_dispose" && fixture.Report.Checks.Count == 0,
                "Dispose mutation cannot rewrite detached check snapshot");
            Assert(fixture.Disposals == 1, "Dispose is not retried after throwing");
        }
        if (faultPhase == "pump")
        {
            Assert(evidence.PrimaryFailure!.InnerException!.Type.Contains("ArgumentException")
                && evidence.PrimaryFailure.TestPhase == "before_throw", "Pump inner chain and test phase retained before Dispose");
        }
        bool laterCleanup = false;
        scenario.CleanupAction(() => throw new Exception("another cleanup"), execution, "job_cleanup");
        scenario.CleanupAction(() => laterCleanup = true, execution, "job_cleanup");
        Assert(laterCleanup && evidence.Status == "failed", "one cleanup exception does not stop subsequent cleanup");
        Assert(WireJson.Serialize(evidence).Length < 40000, "injected failure report stays bounded");
    }
    Exception chain = new Exception(new string('x', 2000));
    for (int depth = 0; depth < 8; depth++) chain = new InvalidOperationException(new string('y', 1000), chain);
    ProbeFailure bounded = ProbeFailure.Capture(chain, faultStep, "pump", "phase", "unknown");
    Assert(bounded.Message.Length == 400 && bounded.InnerException!.InnerException!.InnerException == null
        && bounded.InnerException.InnerException.Truncated, "exception chain depth and message size are bounded");
    runtime.Start();
    string descriptorText = File.ReadAllText(Path.Combine(directory, "bridge.json"));
    TestDescriptor descriptor = TestJson.Deserialize<TestDescriptor>(descriptorText);
    int port = descriptor.Port;
    Assert(!descriptorText.Contains("token") && !descriptorText.Contains(token), "descriptor excludes secret");
    Assert(descriptor.Pid == Process.GetCurrentProcess().Id, "descriptor identifies process");

    string Call(object protocol, string suppliedToken, string command)
    {
        using TcpClient client = new();
        client.Connect("127.0.0.1", port);
        client.ReceiveTimeout = 6000;
        NetworkStream stream = client.GetStream();
        byte[] payload = TestJson.Serialize(new TestRequest
        {
            Protocol = protocol, Id = "request", SessionId = sessionId, Token = suppliedToken, Command = command
        });
        stream.Write(payload, 0, payload.Length);
        stream.WriteByte((byte)'\n');
        using StreamReader reader = new(stream, Encoding.UTF8);
        TestResponse response = TestJson.Deserialize<TestResponse>(reader.ReadLine()!);
        Assert(!response.Ok, "negative path does not pass");
        return response.Error!.Code!;
    }

    Assert(Call(1, "wrong", "get_state") == "unauthorized", "invalid token rejected");
    Assert(Call("not-a-number", token, "get_state") == "invalid_request", "malformed protocol rejected without killing worker");
    Assert(Call(2, token, "get_state") == "protocol_mismatch", "unsupported protocol rejected");
    Assert(Call(1, token, "execute_csharp") == "unknown_command", "arbitrary execution rejected");
    Assert(Call(1, token, "get_state") == "main_thread_timeout", "no main-thread pump times out instead of passing");
    Assert(Call(1, "wrong", "get_state") == "unauthorized", "worker survives timeout");
    Console.WriteLine("Agent transport checks passed on " + System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription);
    Console.WriteLine("No game objects or Unity native methods were exercised.");
}
finally
{
    runtime.Dispose();
    foreach (string file in Directory.GetFiles(directory))
    {
        File.Delete(file);
    }
    Directory.Delete(directory);
}

static void Assert(bool condition, string label)
{
    if (!condition)
    {
        throw new InvalidOperationException(label);
    }

    Console.WriteLine("PASS: " + label);
}

internal static class TestJson
{
    public static byte[] Serialize<T>(T value)
    {
        using MemoryStream buffer = new();
        new DataContractJsonSerializer(typeof(T)).WriteObject(buffer, value);
        return buffer.ToArray();
    }

    public static T Deserialize<T>(string text)
    {
        using MemoryStream buffer = new(Encoding.UTF8.GetBytes(text));
        return (T)new DataContractJsonSerializer(typeof(T)).ReadObject(buffer)!;
    }
}

[DataContract]
internal sealed class TestRequest
{
    [DataMember(Name = "protocol")] public object Protocol { get; set; } = 1;
    [DataMember(Name = "id")] public string? Id { get; set; }
    [DataMember(Name = "session_id")] public string? SessionId { get; set; }
    [DataMember(Name = "token")] public string? Token { get; set; }
    [DataMember(Name = "command")] public string? Command { get; set; }
}

[DataContract]
internal sealed class TestDescriptor
{
    [DataMember(Name = "port")] public int Port { get; set; }
    [DataMember(Name = "pid")] public int Pid { get; set; }
}

[DataContract]
internal sealed class TestResponse
{
    [DataMember(Name = "ok")] public bool Ok { get; set; }
    [DataMember(Name = "error")] public TestError? Error { get; set; }
}

[DataContract]
internal sealed class TestError
{
    [DataMember(Name = "code")] public string? Code { get; set; }
}

internal sealed class FaultProbe : IProbeTest
{
    private readonly string fault;
    public int Disposals { get; private set; }
    public ProbeTestReport Report { get; } = new() { Phase = "ready", Scope = "Offline lifecycle fault fixture",
        Checks = new List<ProbeTestCheck> { new() { Name = "before_dispose", Passed = true, Actual = 1, Expected = "1" } } };
    public FaultProbe(string phase) { fault = phase; }
    public void Start(Verse.Map map)
    {
        if (fault == "start") throw new InvalidOperationException("start broke");
    }
    public void Pump()
    {
        Report.Phase = "before_throw";
        if (fault == "pump") throw new InvalidOperationException("pump broke", new ArgumentException("inner failure"));
        Report.Status = "passed";
    }
    public void Dispose()
    {
        Disposals++;
        Report.Checks.Clear();
        Report.Phase = "mutated_by_dispose";
        if (fault == "pump" || fault == "dispose") throw new NotSupportedException("dispose broke");
    }
}
