using System.Diagnostics;
using System.Runtime.Serialization;
using RimWorld;
using Verse;
using Verse.AI;

namespace RimProbe.Agent;

[DataContract]
internal sealed class BehaviorContract
{
    [DataMember(Name = "steps")] public PlanStep[]? Steps { get; set; }
    [DataMember(Name = "schema")] public int Schema { get; set; }
    [DataMember(Name = "recipe")] public string? Recipe { get; set; }
    [DataMember(Name = "def_name")] public string? DefName { get; set; }
    [DataMember(Name = "intent")] public string? Intent { get; set; }
    [DataMember(Name = "fixture")] public ScenarioFixture? Fixture { get; set; }
    [DataMember(Name = "expect")] public EffectExpectation[]? Expect { get; set; }
    [DataMember(Name = "observe_ticks")] public int ObserveTicks { get; set; }
    [DataMember(Name = "timeout_seconds")] public int TimeoutSeconds { get; set; }
    [DataMember(Name = "max_ticks")] public int MaxTicks { get; set; }
}

[DataContract]
internal sealed class ScenarioFixture
{
    [DataMember(Name = "construction_skill")] public int ConstructionSkill { get; set; }
    [DataMember(Name = "stuff_name")] public string? StuffName { get; set; }
    [DataMember(Name = "settle_ticks")] public int SettleTicks { get; set; }
    [DataMember(Name = "actor_kind")] public string? ActorKind { get; set; }
    [DataMember(Name = "target_kind")] public string? TargetKind { get; set; }
    [DataMember(Name = "target")] public string? Target { get; set; }
    [DataMember(Name = "target_faction")] public string? TargetFaction { get; set; }
    [DataMember(Name = "distance")] public int Distance { get; set; }
    [DataMember(Name = "initial_food_fraction")] public double InitialFoodFraction { get; set; }
    [DataMember(Name = "hold_seconds")] public double HoldSeconds { get; set; }
    [DataMember(Name = "actor_hediffs")] public string[]? ActorHediffs { get; set; }
    [DataMember(Name = "target_hediffs")] public string[]? TargetHediffs { get; set; }
}

[DataContract]
internal sealed class EffectExpectation
{
    [DataMember(Name = "minimum_watts")] public double MinimumWatts { get; set; }
    [DataMember(Name = "kind")] public string? Kind { get; set; }
    [DataMember(Name = "subject")] public string? Subject { get; set; }
    [DataMember(Name = "def_name")] public string? DefName { get; set; }
    [DataMember(Name = "when")] public string? When { get; set; }
}

[DataContract]
internal sealed class EffectObservation
{
    [DataMember(Name = "kind")] public string Kind { get; set; } = "";
    [DataMember(Name = "subject")] public string Subject { get; set; } = "";
    [DataMember(Name = "def_name")] public string? DefName { get; set; }
    [DataMember(Name = "when")] public string When { get; set; } = "";
    [DataMember(Name = "before")] public double Before { get; set; }
    [DataMember(Name = "after")] public double After { get; set; }
    [DataMember(Name = "peak")] public double Peak { get; set; }
    [DataMember(Name = "met")] public bool Met { get; set; }
}

internal sealed class AbilitySuite
{
    public SuiteReport? Report { get; private set; }
    private BehaviorContract? contract;
    private Stopwatch clock = new();
    private Pawn? actor;
    private Pawn? target;
    private Ability? ability;
    private Map? map;
    private int castTick;

    public void Start(SuiteOptions? options)
    {
        BehaviorContract? request = options?.Contract;
        if (options == null || !Guid.TryParseExact(options.RunId, "N", out _)
            || request == null || request.Schema != 1 || request.Recipe != "ability_cast" || string.IsNullOrWhiteSpace(request.DefName)
            || request.Fixture == null || request.Expect == null || request.Expect.Length < 1 || request.Expect.Length > 16
            || request.ObserveTicks < 1 || request.ObserveTicks > 60000 || request.TimeoutSeconds < 5 || request.TimeoutSeconds > 600
            || request.MaxTicks < 60 || request.MaxTicks > 120000 || request.ObserveTicks >= request.MaxTicks
            || request.Fixture.Distance < 1 || request.Fixture.Distance > 30)
        {
            throw new ArgumentException("Invalid bounded ability contract.");
        }
        if (Report?.RunId == options.RunId)
        {
            return;
        }
        if (Report?.Status == "running")
        {
            throw new InvalidOperationException("A contract is already running.");
        }
        contract = request;
        actor = target = null;
        ability = null;
        map = null;
        clock = Stopwatch.StartNew();
        Report = new SuiteReport { RunId = options.RunId!, DefName = request.DefName!, Recipe = "ability_cast", Intent = request.Intent,
            Excluded = new[] { "UI hit-testing", "VFX/rendering", "unasserted custom semantics", "save/load", "ability removal/lifecycle" } };
    }

    public void Cancel()
    {
        if (Report?.Status == "running")
        {
            Finish("cancelled", "Contract cancelled; only disposable fixture Pawns were used.");
        }
    }

    public void Pump()
    {
        if (Report?.Status != "running")
        {
            return;
        }
        try
        {
            if (clock.Elapsed.TotalSeconds >= contract!.TimeoutSeconds)
            {
                Finish("inconclusive", "Contract wall-clock timeout; no fabricated effect pass.");
                return;
            }
            if (LongEventHandler.AnyEventNowOrWaiting || Current.ProgramState != ProgramState.Playing || Current.Game?.CurrentMap == null)
            {
                return;
            }
            Report.TickObserved = Find.TickManager.TicksGame;
            if (Report.Stage == "prepare")
            {
                Prepare();
                return;
            }
            if (Current.Game.CurrentMap != map || actor == null || ability == null || !actor.Spawned)
            {
                Finish("blocked", "Fixture actor/map is unavailable.");
                return;
            }
            if (Report.TickObserved - Report.TickStarted >= contract.MaxTicks)
            {
                Finish("inconclusive", "Contract tick budget exhausted.");
                return;
            }
            Observe();
        }
        catch (Exception error)
        {
            Finish("failed", error.GetType().Name + ": " + error.Message);
        }
    }

    private void Prepare()
    {
        map = Current.Game.CurrentMap;
        AbilityDef? definition = DefDatabase<AbilityDef>.GetNamedSilentFail(contract!.DefName);
        ScenarioFixture fixture = contract.Fixture!;
        if (definition == null)
        {
            Finish("unsupported", "AbilityDef is not loaded; inspect actual Mods/DLC order and the target code/framework.");
            return;
        }
        if (definition.targetWorldCell)
        {
            Finish("unsupported", "World-target abilities require a world fixture/action adapter.");
            return;
        }
        if (!string.IsNullOrWhiteSpace(definition.confirmationDialogText))
        {
            Finish("unsupported", "This ability requires an explicit UI confirmation adapter; confirmation is not bypassed.");
            return;
        }
        PawnKindDef? actorKind = DefDatabase<PawnKindDef>.GetNamedSilentFail(fixture.ActorKind);
        PawnKindDef? targetKind = DefDatabase<PawnKindDef>.GetNamedSilentFail(fixture.TargetKind);
        if (actorKind == null || targetKind == null || fixture.Target != "pawn" && fixture.Target != "self" && fixture.Target != "cell"
            || fixture.TargetFaction != "player" && fixture.TargetFaction != "hostile")
        {
            Finish("blocked", "Invalid fixture PawnKind/target/faction.");
            return;
        }
        foreach (EffectExpectation expectation in contract.Expect!)
        {
            if (!Supported(expectation) || (expectation.Kind == "hediff_added" || expectation.Kind == "hediff_removed")
                && DefDatabase<HediffDef>.GetNamedSilentFail(expectation.DefName) == null)
            {
                Finish("unsupported", "An assertion lacks a supported observer or loaded HediffDef; add a reviewed adapter.");
                return;
            }
        }
        IntVec3 anchor = map!.mapPawns.FreeColonistsSpawned.FirstOrDefault()?.Position ?? map.Center;
        IntVec3 actorCell = GenRadial.RadialCellsAround(anchor, 15, true).Where(position => SafeCell(position)).DefaultIfEmpty(IntVec3.Invalid).First();
        if (!SafeCell(actorCell))
        {
            Finish("blocked", "No safe unfogged fixture spawn cell.");
            return;
        }
        IntVec3 targetCell = fixture.Target == "self" ? actorCell : GenRadial.RadialCellsAround(actorCell, fixture.Distance + 1, false).Where(position =>
            SafeCell(position) && position.DistanceTo(actorCell) >= fixture.Distance && GenSight.LineOfSight(actorCell, position, map)).DefaultIfEmpty(IntVec3.Invalid).First();
        if (fixture.Target != "self" && !SafeCell(targetCell))
        {
            Finish("blocked", "No safe reachable target cell at the requested distance.");
            return;
        }
        Faction? targetFaction = fixture.TargetFaction == "player" ? Faction.OfPlayer : Find.FactionManager.AllFactionsListForReading.FirstOrDefault(faction => faction.HostileTo(Faction.OfPlayer));
        if (fixture.Target == "pawn" && targetFaction == null)
        {
            Finish("blocked", "No existing hostile faction for the target fixture; diplomacy was not modified.");
            return;
        }
        actor = PawnGenerator.GeneratePawn(new PawnGenerationRequest(actorKind, Faction.OfPlayer, fixedGender: Gender.Female));
        GenSpawn.Spawn(actor, actorCell, map);
        if (fixture.Target == "self")
        {
            target = actor;
        }
        else if (fixture.Target == "pawn")
        {
            target = PawnGenerator.GeneratePawn(targetKind, targetFaction);
            GenSpawn.Spawn(target, targetCell, map);
        }
        AddFixtureHediffs(actor, fixture.ActorHediffs);
        if (target != null)
        {
            AddFixtureHediffs(target, fixture.TargetHediffs);
        }
        if (actor.abilities == null)
        {
            actor.abilities = new Pawn_AbilityTracker(actor);
        }
        actor.abilities.GainAbility(definition);
        ability = actor.abilities.GetAbility(definition);
        if (actor.drafter != null)
        {
            actor.drafter.Drafted = true;
        }
        Report!.WorkerId = actor.thingIDNumber;
        Report.TargetId = target?.thingIDNumber;
        Report.Cell = targetCell.ToString();
        Report.TickStarted = Find.TickManager.TicksGame;
        Check("fixture", "passed", "Generated separate test Pawn(s); original colonists were not reused or modified.");
        Check("ability_granted", "passed", "GainAbility produced " + ability.GetType().FullName + "; expected effects were not injected.");
        LocalTargetInfo castTarget = fixture.Target == "cell" ? new LocalTargetInfo(targetCell) : new LocalTargetInfo(target!);
        AcceptanceReport canCast = ability.CanCast;
        if (!canCast.Accepted || !ability.CanQueueCast || !ability.CanApplyOn(castTarget) || !ability.verb.ValidateTarget(castTarget, false))
        {
            Finish("blocked", "Normal cast eligibility rejected: " + canCast.Reason + "; requirements were not forced or bypassed.");
            return;
        }
        foreach (EffectExpectation expectation in contract.Expect!)
        {
            double before = Read(expectation.Kind!, expectation.Subject!, expectation.DefName);
            if (expectation.Kind == "hediff_removed" && before <= 0)
            {
                Finish("blocked", "Removal assertion requires the Hediff in the initial fixture.");
                return;
            }
            Report.Observations.Add(new EffectObservation { Kind = expectation.Kind!, Subject = expectation.Subject!, DefName = expectation.DefName,
                When = expectation.When!, Before = before, After = before, Peak = before });
        }
        int windowCount = Find.WindowStack.Windows.Count;
        castTick = Find.TickManager.TicksGame;
        Report.Stage = "cast_and_observe";
        Find.TickManager.CurTimeSpeed = TimeSpeed.Normal;
        ability.QueueCastingJob(castTarget, castTarget);
        if (Find.WindowStack.Windows.Count > windowCount)
        {
            Finish("blocked", "Casting opened a confirmation window; no desktop click or silent confirmation was used.");
            return;
        }
        Check("normal_cast_requested", "passed", "Validated ability and called QueueCastingJob; normal Verb/Job handles activation and costs.");
        Observe();
    }

    private bool SafeCell(IntVec3 position)
    {
        return position.InBounds(map!) && !position.Fogged(map!) && position.Standable(map!) && position.GetFirstPawn(map!) == null;
    }

    private static bool Supported(EffectExpectation expectation)
    {
        return (expectation.Subject == "actor" || expectation.Subject == "target") && (expectation.When == "eventually" || expectation.When == "end")
            && (expectation.Kind == "hediff_added" || expectation.Kind == "hediff_removed" || expectation.Kind == "injury_increased"
                || expectation.Kind == "cooldown_started" && expectation.Subject == "actor" || expectation.Kind == "stunned" || expectation.Kind == "downed");
    }

    private static void AddFixtureHediffs(Pawn pawn, string[]? names)
    {
        if (names == null)
        {
            return;
        }
        if (names.Length > 16)
        {
            throw new ArgumentException("Too many fixture Hediffs.");
        }
        foreach (string name in names)
        {
            HediffDef definition = DefDatabase<HediffDef>.GetNamed(name);
            pawn.health.AddHediff(definition);
        }
    }

    private double Read(string kind, string subject, string? defName)
    {
        Pawn pawn = subject == "actor" ? actor! : target ?? throw new InvalidOperationException("Pawn observer has no target Pawn.");
        if (kind == "hediff_added" || kind == "hediff_removed")
        {
            return pawn.health.hediffSet.hediffs.Count(hediff => hediff.def.defName == defName);
        }
        if (kind == "injury_increased")
        {
            return pawn.health.hediffSet.hediffs.OfType<Hediff_Injury>().Sum(hediff => hediff.Severity);
        }
        if (kind == "cooldown_started")
        {
            return ability!.CooldownTicksRemaining;
        }
        if (kind == "stunned")
        {
            return pawn.stances.stunner.Stunned ? 1 : 0;
        }
        return pawn.Downed ? 1 : 0;
    }

    private void Observe()
    {
        string? job = actor!.CurJob?.def.defName;
        if (job != Report!.Job && Report.Events.Count < 64)
        {
            Report.Events.Add(Find.TickManager.TicksGame + ": job=" + job);
        }
        Report.Job = job;
        foreach (EffectObservation observation in Report.Observations)
        {
            observation.After = Read(observation.Kind, observation.Subject, observation.DefName);
            observation.Peak = Math.Max(observation.Peak, observation.After);
            bool met = observation.Kind == "hediff_removed" ? observation.After < observation.Before
                : observation.Kind == "cooldown_started" ? observation.After > 0
                : observation.After > observation.Before + 0.0001;
            observation.Met = observation.When == "eventually" ? observation.Met || met : met;
        }
        if (Find.TickManager.TicksGame - castTick < contract!.ObserveTicks)
        {
            return;
        }
        foreach (EffectObservation observation in Report.Observations)
        {
            Check(observation.Kind + ":" + observation.Subject, observation.Met ? "passed" : "failed",
                "Before=" + observation.Before + ", after=" + observation.After + ", peak=" + observation.Peak + ", when=" + observation.When);
        }
        bool passed = Report.Observations.All(observation => observation.Met);
        Finish(passed ? "passed" : "failed", passed ? "Declared code-derived effects observed through the normal casting path; unasserted semantics remain excluded." : "At least one declared effect was not observed; successful queueing does not imply functional success.");
    }

    private void Check(string name, string status, string detail)
    {
        Report!.Checks.Add(new SuiteCheck { Name = name, Status = status, Detail = detail });
    }

    private void Finish(string status, string message)
    {
        Report!.Status = status;
        Report.Message = message;
        try
        {
            if (actor != null && actor.CurJob?.ability == ability && ability != null)
            {
                actor.jobs.EndCurrentJob(JobCondition.InterruptForced);
            }
        }
        catch (Exception error)
        {
            Report.Status = "failed";
            Report.Message += " Cleanup: " + error.Message;
        }
    }
}
