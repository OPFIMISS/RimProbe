using System.Diagnostics;
using System.Runtime.Serialization;
using System.Text.RegularExpressions;
using RimWorld;
using Verse;
using Verse.AI;

namespace RimProbe.Agent;

[DataContract]
internal sealed class PlanStep
{
    [DataMember(Name = "id")] public string Id { get; set; } = "";
    [DataMember(Name = "key")] public string? Key { get; set; }
    [DataMember(Name = "relative_to")] public string? RelativeTo { get; set; }
    [DataMember(Name = "bind_value")] public string? BindValue { get; set; }
    [DataMember(Name = "radius")] public int Radius { get; set; }
    [DataMember(Name = "index")] public int Index { get; set; }
    [DataMember(Name = "op")] public string Op { get; set; } = "";
    [DataMember(Name = "bind")] public string? Bind { get; set; }
    [DataMember(Name = "actor")] public string? Actor { get; set; }
    [DataMember(Name = "target")] public string? Target { get; set; }
    [DataMember(Name = "near")] public string? Near { get; set; }
    [DataMember(Name = "other")] public string? Other { get; set; }
    [DataMember(Name = "def_name")] public string? DefName { get; set; }
    [DataMember(Name = "stuff_name")] public string? StuffName { get; set; }
    [DataMember(Name = "def_type")] public string? DefType { get; set; }
    [DataMember(Name = "query")] public string? Query { get; set; }
    [DataMember(Name = "offset")] public int Offset { get; set; }
    [DataMember(Name = "limit")] public int Limit { get; set; }
    [DataMember(Name = "distance")] public int Distance { get; set; }
    [DataMember(Name = "faction")] public string? Faction { get; set; }
    [DataMember(Name = "food_fraction")] public double FoodFraction { get; set; }
    [DataMember(Name = "count")] public int Count { get; set; }
    [DataMember(Name = "property")] public string? Property { get; set; }
    [DataMember(Name = "compare")] public string? Compare { get; set; }
    [DataMember(Name = "value")] public double Value { get; set; }
    [DataMember(Name = "ticks")] public int Ticks { get; set; }
    [DataMember(Name = "hold_ticks")] public int HoldTicks { get; set; }
    [DataMember(Name = "choice")] public string? Choice { get; set; }
    [DataMember(Name = "bind_choice")] public string? BindChoice { get; set; }
    [DataMember(Name = "cell_at_target")] public bool CellAtTarget { get; set; }
    [DataMember(Name = "x")] public int? X { get; set; }
    [DataMember(Name = "z")] public int? Z { get; set; }
    [DataMember(Name = "condition")] public string? Condition { get; set; }
    [DataMember(Name = "timeout_seconds")] public int TimeoutSeconds { get; set; }
    [DataMember(Name = "stable_frames")] public int StableFrames { get; set; }
    [DataMember(Name = "cancel_if")] public string? CancelIf { get; set; }
}

[DataContract]
internal sealed class PlanObjectSnapshot
{
    [DataMember(Name = "map_id")] public int? MapId { get; set; }
    [DataMember(Name = "tile_id")] public int? TileId { get; set; }
    [DataMember(Name = "layer_id")] public int? LayerId { get; set; }
    [DataMember(Name = "x")] public int X { get; set; }
    [DataMember(Name = "z")] public int Z { get; set; }
    [DataMember(Name = "thing_id")] public int ThingId { get; set; }
    [DataMember(Name = "def_name")] public string DefName { get; set; } = "";
    [DataMember(Name = "class")] public string ClassName { get; set; } = "";
    [DataMember(Name = "cell")] public string Cell { get; set; } = "";
    [DataMember(Name = "spawned")] public bool Spawned { get; set; }
    [DataMember(Name = "destroyed")] public bool Destroyed { get; set; }
    [DataMember(Name = "hp")] public int HitPoints { get; set; }
    [DataMember(Name = "job")] public string? Job { get; set; }
    [DataMember(Name = "job_ability", EmitDefaultValue = false)] public string? JobAbility { get; set; }
    [DataMember(Name = "job_id", EmitDefaultValue = false)] public int? JobId { get; set; }
    [DataMember(Name = "abilities")] public string[] Abilities { get; set; } = Array.Empty<string>();
    [DataMember(Name = "hediffs")] public string[] Hediffs { get; set; } = Array.Empty<string>();
    [DataMember(Name = "equipment")] public string[] Equipment { get; set; } = Array.Empty<string>();
    [DataMember(Name = "comps")] public string[] Comps { get; set; } = Array.Empty<string>();
    [DataMember(Name = "available_properties")] public string[] AvailableProperties { get; set; } = Array.Empty<string>();
    [DataMember(Name = "lists_truncated")] public bool ListsTruncated { get; set; }
}

[DataContract]
internal sealed class PlanDefSummary
{
    [DataMember(Name = "def_name")] public string DefName { get; set; } = "";
    [DataMember(Name = "class")] public string ClassName { get; set; } = "";
}

[DataContract]
internal sealed class PlanStepReport
{
    [DataMember(Name = "fidelity")] public string Fidelity { get; set; } = "state_observation";
    [DataMember(Name = "interaction", EmitDefaultValue = false)] public InteractionSnapshot? Interaction { get; set; }
    [DataMember(Name = "id")] public string Id { get; set; } = "";
    [DataMember(Name = "op")] public string Op { get; set; } = "";
    [DataMember(Name = "status")] public string Status { get; set; } = "";
    [DataMember(Name = "tick")] public int Tick { get; set; }
    [DataMember(Name = "detail")] public string Detail { get; set; } = "";
    [DataMember(Name = "baseline", EmitDefaultValue = false)] public double? Baseline { get; set; }
    [DataMember(Name = "compared_value", EmitDefaultValue = false)] public double? ComparedValue { get; set; }
    [DataMember(Name = "value", EmitDefaultValue = false)] public double? Value { get; set; }
    [DataMember(Name = "snapshot", EmitDefaultValue = false)] public PlanObjectSnapshot? Snapshot { get; set; }
    [DataMember(Name = "definitions", EmitDefaultValue = false)] public PlanDefSummary[]? Definitions { get; set; }
    [DataMember(Name = "total_matches", EmitDefaultValue = false)] public int? TotalMatches { get; set; }
    [DataMember(Name = "registered_test", EmitDefaultValue = false)] public ProbeTestReport? RegisteredTest { get; set; }
    [DataMember(Name = "construction", EmitDefaultValue = false)] public SuiteReport? Construction { get; set; }
    [DataMember(Name = "failure_context", EmitDefaultValue = false)] public PlanFailureContext? FailureContext { get; set; }
    [DataMember(Name = "diagnostics_omitted", EmitDefaultValue = false)] public bool DiagnosticsOmitted { get; set; }
}

internal sealed partial class ScenarioSuite
{
    private static readonly string[] Operations = { "spawn_pawn", "spawn_item", "fixture_hediff", "grant_ability", "cast", "ingest", "equip", "move", "build", "inspect", "query_defs", "wait", "assert", "wait_assert", "find_thing", "measure", "query_tests", "registered_test", "begin_ability", "inspect_interaction", "enumerate_choices", "select_choice", "cancel_interaction", "wait_until" };
    private static readonly string[] NumericProperties = { "hp", "spawned", "destroyed", "stack_count", "map.id", "map.tile_id", "map.layer_id", "position.x", "position.z", "pawn.job_active", "pawn.dead", "pawn.downed", "pawn.stunned", "pawn.food", "pawn.injury", "pawn.hediff_count", "pawn.ability_cooldown", "pawn.ability_casting", "pawn.equipped", "pawn.distance_to", "power.watts", "power.connected" };
    private readonly Dictionary<string, double> values = new();
    private readonly Dictionary<string, Thing> handles = new();
    private readonly Dictionary<Pawn, HashSet<int>> jobs = new();
    private readonly BuildingSuite construction = new();
    private BehaviorContract? contract;
    private Stopwatch clock = new();
    private Map? map;
    private int index;
    private int stepTick = -1;
    private int heldSince = -1;
    private int assertions;
    public SuiteReport? Report { get; private set; }

    public void Start(SuiteOptions? options)
    {
        BehaviorContract? request = options?.Contract;
        if (options == null || !Guid.TryParseExact(options.RunId, "N", out _) || request == null || request.Schema != 1
            || request.Recipe != "scenario" || request.Steps == null || request.Steps.Length < 1 || request.Steps.Length > 24
            || string.IsNullOrWhiteSpace(request.Intent) || request.Intent!.Length > 2000
            || request.MaxTicks < 60 || request.MaxTicks > 120000 || request.TimeoutSeconds < 5 || request.TimeoutSeconds > 600)
            throw new ArgumentException("Invalid bounded scenario plan.");
        if (Report?.RunId == options.RunId) return;
        if (Report?.Status == "running") throw new InvalidOperationException("A plan is already running.");
        ValidateSteps(request.Steps);
        InteractionHub.Arm();
        choiceAliases.Clear();
        contract = request;
        handles.Clear();
        values.Clear();
        jobs.Clear();
        map = null;
        index = assertions = 0;
        lifecyclePhase = "agent";
        lifecycleStep = null;
        testPhase = null;
        stepTick = heldSince = -1;
        clock = Stopwatch.StartNew();
        Report = new SuiteReport { RunId = options.RunId!, DefName = "Scenario", Recipe = "scenario", Intent = request.Intent,
            Excluded = new[] { "arbitrary reflection/code", "custom framework actions", "save/load", "pixel/input validation", "per-Tick sampling guarantee" } };
    }

    internal static void ValidateSteps(PlanStep[] steps)
    {
        HashSet<string> ids = new();
        HashSet<string> bound = new();
        HashSet<string> pawns = new();
        HashSet<string> measured = new();
        HashSet<string> choices = new();
        bool active = false;
        foreach (PlanStep step in steps)
        {
            if (!Regex.IsMatch(step.Id, "^[A-Za-z][A-Za-z0-9_]{0,31}$") || !ids.Add(step.Id) || !Operations.Contains(step.Op))
                throw new ArgumentException("Unknown action or duplicate/invalid step id.");
            if (step.Op == "registered_test" && (step.Key == null || !Regex.IsMatch(step.Key, "^[a-z][a-z0-9_.]{0,79}\\z"))) throw new ArgumentException("Invalid registered test key.");
            ValidateInteractionStep(step, choices);
            bool fixture = new[] { "spawn_pawn", "spawn_item", "fixture_hediff", "grant_ability" }.Contains(step.Op);
            if (fixture && active) throw new ArgumentException("Fixture setup must precede actions and assertions.");
            active |= !fixture && step.Op != "inspect" && step.Op != "query_defs" && step.Op != "find_thing" && step.Op != "query_tests";
            foreach (string? reference in new[] { step.Actor, step.Target, step.Near, step.Other })
                if (reference != null && !bound.Contains(reference)) throw new ArgumentException("Object references must be bound earlier.");
            if (step.Actor != null && !pawns.Contains(step.Actor)) throw new ArgumentException("Only declared fixture Pawns can be ordered.");
            if (step.Property?.StartsWith("pawn.", StringComparison.Ordinal) == true && (step.Target == null || !pawns.Contains(step.Target))) throw new ArgumentException("Pawn property requires a declared Pawn handle.");
            if (new[] { "spawn_pawn", "spawn_item", "build", "find_thing" }.Contains(step.Op) != (step.Bind != null)) throw new ArgumentException("Only object-producing steps require a binding.");
            if (step.Bind != null && (!Regex.IsMatch(step.Bind, "^[A-Za-z][A-Za-z0-9_]{0,31}$") || !bound.Add(step.Bind)))
                throw new ArgumentException("Invalid or duplicate object binding.");
            if (step.Op == "spawn_pawn") pawns.Add(step.Bind!);
            if (step.Op == "spawn_pawn" && (step.Bind == null || step.Distance < 1 || step.Distance > 15
                || step.FoodFraction < 0.05 || step.FoodFraction > 0.8 || double.IsNaN(step.FoodFraction)
                || step.Faction != "player" && step.Faction != "hostile")) throw new ArgumentException("Invalid Pawn fixture.");
            if (step.Op == "spawn_item" && (step.Bind == null || step.Count < 1 || step.Count > 75)) throw new ArgumentException("Invalid item fixture.");
            if (new[] { "cast", "begin_ability", "ingest", "equip", "move", "grant_ability", "fixture_hediff" }.Contains(step.Op) && step.Actor == null) throw new ArgumentException("Actor required.");
            if (new[] { "cast", "ingest", "equip", "move", "inspect", "assert", "wait_assert", "measure" }.Contains(step.Op) && step.Target == null) throw new ArgumentException("Target required.");
            if (step.Op == "build" && step.Bind == null) throw new ArgumentException("Build requires a binding.");
            if (step.Op == "query_defs" && (step.Query?.Length > 80 || step.Offset < 0 || step.Offset > 100000 || step.Limit < 1 || step.Limit > 8
                || !new[] { "ThingDef", "AbilityDef", "HediffDef", "PawnKindDef", "RecipeDef" }.Contains(step.DefType))) throw new ArgumentException("Invalid Def query.");
            if (step.Op == "wait" && (step.Ticks < 1 || step.Ticks > 60000)) throw new ArgumentException("Invalid wait budget.");
            if (step.Op == "find_thing" && (step.Bind == null || step.Radius < 1 || step.Radius > 100 || step.Index < 0 || step.Index > 127)) throw new ArgumentException("Invalid thing query.");
            if (step.RelativeTo != null && !measured.Contains(step.RelativeTo)) throw new ArgumentException("Missing numeric baseline.");
            if (step.Op == "measure" && (step.BindValue == null || !Regex.IsMatch(step.BindValue, "^[A-Za-z][A-Za-z0-9_]{0,31}$") || !measured.Add(step.BindValue))) throw new ArgumentException("Invalid numeric binding.");
            if (step.Op == "assert" || step.Op == "wait_assert" || step.Op == "measure")
            {
                bool named = new[] { "pawn.hediff_count", "pawn.ability_cooldown", "pawn.equipped" }.Contains(step.Property);
                if (!NumericProperties.Contains(step.Property) || step.Op != "measure" && !new[] { "eq", "ne", "gt", "ge", "lt", "le" }.Contains(step.Compare)
                    || double.IsNaN(step.Value) || double.IsInfinity(step.Value) || Math.Abs(step.Value) > 1000000000
                    || named != (step.DefName != null) || (step.Property == "pawn.distance_to") != (step.Other != null)
                    || step.Op == "wait_assert" && (step.Ticks < 1 || step.Ticks > 60000 || step.HoldTicks < 0 || step.HoldTicks > 6000 || step.HoldTicks > step.Ticks)
                    || step.Op == "assert" && step.HoldTicks != 0) throw new ArgumentException("Invalid bounded state assertion.");
            }
        }
    }

    public void Cancel()
    {
        if (Report?.Status == "running") FailCurrentStep("cancelled", "Plan cancelled; owned jobs and construction cleaned up in disposable session.");
    }

    public void Pump()
    {
        if (Report?.Status != "running") return;
        try
        {
            if (clock.Elapsed.TotalSeconds >= contract!.TimeoutSeconds) { FailCurrentStep("inconclusive", "Scenario wall-clock budget exhausted."); return; }
            if (LongEventHandler.AnyEventNowOrWaiting || Current.ProgramState != ProgramState.Playing || Current.Game?.CurrentMap == null)
            {
                barrierSamples = 0; barrierIdentity = null;
                if (stepTick >= 0 && contract.Steps != null && index < contract.Steps.Length && contract.Steps[index].Op == "wait_until"
                    && barrierClock.Elapsed.TotalSeconds >= contract.Steps[index].TimeoutSeconds)
                    FailCurrentStep("inconclusive", "Readiness phase timeout while game is loading.");
                return;
            }
            Report.TickObserved = Find.TickManager.TicksGame;
            if (map == null)
            {
                map = Current.Game.CurrentMap;
                Report.TickStarted = Report.TickObserved;
                PreflightDefinitions();
                Find.TickManager.CurTimeSpeed = TimeSpeed.Normal;
            }
            if (registeredTest == null && map != Current.Game.CurrentMap) map = Current.Game.CurrentMap;
            if (Report.TickObserved - Report.TickStarted >= contract.MaxTicks) { FailCurrentStep("inconclusive", "Scenario Tick budget exhausted."); return; }
            if (index >= contract.Steps!.Length)
            {
                Finish(assertions > 0 ? "passed" : "inconclusive", assertions > 0 ? "All explicit plan assertions passed; scope is exactly the listed actions and observations." : "Discovery/actions completed without functional assertions; no functional pass claimed.");
                return;
            }
            PlanStep step = contract.Steps[index];
            if (step.Op != "registered_test") { lifecycleStep = step; lifecyclePhase = "agent"; testPhase = null; }
            Report.Stage = step.Id + ":" + step.Op;
            if (stepTick < 0) { stepTick = Report.TickObserved; heldSince = -1; Begin(step); }
            if (Report.Status != "running" || index >= contract.Steps.Length || !ReferenceEquals(step, contract.Steps[index])) return;
            if (step.Op == "wait" && Report.TickObserved - stepTick >= step.Ticks) Complete(step, "completed", "Tick wait completed.");
            else if (step.Op == "wait_assert") ObserveAssertion(step, true);
            else if (step.Op == "build") ObserveBuild(step);
            else if (step.Op == "registered_test") ObserveRegisteredTest(step);
            else if (step.Op == "wait_until") ObserveBarrier(step);
        }
        catch (Exception error) { HandleFailure(error); }
    }

    private void FailCurrentStep(string status, string message)
    {
        if (contract?.Steps != null && index < contract.Steps.Length)
        {
            PlanStep failing = contract.Steps[index];
            ProbeTestReport? partial = null;
            if (registeredTest != null)
            {
                try
                {
                    partial = SnapshotRegisteredEvidence(registeredTest.Report);
                    testPhase = partial.Phase;
                }
                catch { partial = null; Report!.FailureEvidenceTruncated = true; }
            }
            Complete(failing, status, message);
            if (registeredTest != null && partial == null && Report!.Steps.Count > 0)
                Report.Steps[Report.Steps.Count - 1].DiagnosticsOmitted = true;
            if (partial != null && Report!.Steps.Count > 0)
            {
                PlanStepReport entry = Report.Steps[Report.Steps.Count - 1];
                entry.RegisteredTest = partial;
                if (WireJson.Serialize(Report).Length > 40000) { entry.RegisteredTest = null; entry.DiagnosticsOmitted = true; }
            }
        }
        Finish(status, message);
    }

    private void PreflightDefinitions()
    {
        foreach (PlanStep step in contract!.Steps!)
        {
            if (step.Op == "spawn_pawn") RequireDef<PawnKindDef>(step.DefName);
            else if (step.Op == "spawn_item" || step.Op == "build" || step.Op == "find_thing" || step.Property == "pawn.equipped") RequireDef<ThingDef>(step.DefName);
            else if (step.Op == "grant_ability" || step.Op == "cast" || step.Op == "begin_ability" || step.Property == "pawn.ability_cooldown") RequireDef<AbilityDef>(step.DefName);
            else if (step.Op == "fixture_hediff" || step.Property == "pawn.hediff_count") RequireDef<HediffDef>(step.DefName);
            if (step.StuffName != null) RequireDef<ThingDef>(step.StuffName);
        }
    }

    private static T RequireDef<T>(string? name) where T : Def, new()
    {
        if (string.IsNullOrEmpty(name) || name!.Length > 128) throw new InvalidOperationException("Exact loaded Def identifier required.");
        return DefDatabase<T>.GetNamedSilentFail(name) ?? throw new ProbeStepException("blocked", "Required " + typeof(T).Name + " is not loaded: " + name);
    }

    private Thing Object(string? alias)
    {
        if (alias == null || !handles.TryGetValue(alias, out Thing? thing)) throw new InvalidOperationException("Missing run-local handle.");
        return thing;
    }

    private Pawn Actor(string? alias)
    {
        Pawn pawn = Object(alias) as Pawn ?? throw new ProbeStepException("unsupported", "Action requires a Pawn handle.");
        if (!pawn.Spawned || pawn.Map != map || pawn.Dead || pawn.Downed || pawn.InMentalState) throw new ProbeStepException("blocked", "Pawn cannot act in current fixture.");
        if (pawn.Faction != Faction.OfPlayer) throw new ProbeStepException("blocked", "Only player-faction fixture Pawns can be ordered.");
        return pawn;
    }
}
