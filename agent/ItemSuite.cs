using System.Diagnostics;
using RimWorld;
using Verse;
using Verse.AI;

namespace RimProbe.Agent;

internal sealed class ItemSuite
{
    public SuiteReport? Report { get; private set; }
    private BehaviorContract? contract;
    private readonly Stopwatch clock = new();
    private Pawn? actor;
    private Thing? item;
    private Job? job;
    private int jobId = -1;
    private Map? map;
    private bool jobSeen;

    public void Start(SuiteOptions? options)
    {
        BehaviorContract? request = options?.Contract;
        if (request == null || !Guid.TryParseExact(options?.RunId, "N", out _) || request.Schema != 1 || request.Recipe != "item_ingest"
            || request.Fixture == null || request.Expect == null || request.Expect.Length < 1 || request.Expect.Length > 16
            || request.TimeoutSeconds < 5 || request.TimeoutSeconds > 600 || request.MaxTicks < 60 || request.MaxTicks > 120000
            || request.ObserveTicks < 1 || request.ObserveTicks >= request.MaxTicks
            || double.IsNaN(request.Fixture.InitialFoodFraction) || request.Fixture.InitialFoodFraction < 0.05 || request.Fixture.InitialFoodFraction > 0.8)
            throw new ArgumentException("Invalid bounded ingestion contract.");
        if (Report?.RunId == options!.RunId) return;
        if (Report?.Status == "running") throw new InvalidOperationException("An ingestion contract is running.");
        contract = request;
        actor = null;
        item = null;
        job = null;
        jobId = -1;
        IngestObserver.Track(null, null);
        map = null;
        jobSeen = false;
        clock.Restart();
        Report = new SuiteReport { RunId = options.RunId!, DefName = request.DefName!, Recipe = "item_ingest", Intent = request.Intent,
            Excluded = new[] { "UI", "VFX", "unasserted custom effects", "automatic food selection", "multi-stack quantities", "save/load" } };
    }

    public void Cancel()
    {
        if (Report?.Status == "running") Finish("cancelled", "Ingestion contract cancelled.");
    }

    public void Pump()
    {
        if (Report?.Status != "running") return;
        try
        {
            if (clock.Elapsed.TotalSeconds >= contract!.TimeoutSeconds) { Finish("inconclusive", "Ingestion wall-clock budget exhausted."); return; }
            if (LongEventHandler.AnyEventNowOrWaiting || Current.ProgramState != ProgramState.Playing || Current.Game?.CurrentMap == null) return;
            Report.TickObserved = Find.TickManager.TicksGame;
            if (Report.Stage == "prepare") { Prepare(); return; }
            if (Current.Game.CurrentMap != map || actor == null || actor.Dead || !actor.Spawned) { Finish("blocked", "Fixture actor/map unavailable."); return; }
            if (Report.TickObserved - Report.TickStarted >= contract.MaxTicks) { Finish("inconclusive", "Ingestion tick budget exhausted."); return; }
            Observe();
        }
        catch (Exception error) { Finish("failed", error.GetType().Name + ": " + error.Message); }
    }

    private void Prepare()
    {
        map = Current.Game.CurrentMap;
        ThingDef? definition = DefDatabase<ThingDef>.GetNamedSilentFail(contract!.DefName);
        PawnKindDef? kind = DefDatabase<PawnKindDef>.GetNamedSilentFail(contract.Fixture!.ActorKind);
        if (definition?.ingestible == null || definition.MadeFromStuff || definition.category != ThingCategory.Item || kind == null)
        { Finish("unsupported", "Requires an ingestible non-stuff item ThingDef and loaded PawnKindDef."); return; }
        foreach (EffectExpectation expectation in contract.Expect!)
        {
            if (expectation.Subject != "actor" || !(expectation.When == "eventually" || expectation.When == "end")
                || !(expectation.Kind == "item_consumed" || expectation.Kind == "nutrition_increased" || expectation.Kind == "hediff_added" || expectation.Kind == "hediff_removed")
                || expectation.Kind.StartsWith("hediff_") && DefDatabase<HediffDef>.GetNamedSilentFail(expectation.DefName) == null)
            { Finish("unsupported", "Unknown ingestion observer or unloaded HediffDef."); return; }
        }
        IntVec3 anchor = map!.mapPawns.FreeColonistsSpawned.FirstOrDefault()?.Position ?? map.Center;
        IntVec3 cell = GenRadial.RadialCellsAround(anchor, 15, true).Where(position => position.InBounds(map) && !position.Fogged(map)
            && position.Standable(map) && position.GetFirstPawn(map) == null && !position.GetThingList(map).Any(thing => thing.def.category == ThingCategory.Item))
            .DefaultIfEmpty(IntVec3.Invalid).First();
        if (!cell.IsValid) { Finish("blocked", "No safe empty fixture cell."); return; }
        actor = PawnGenerator.GeneratePawn(new PawnGenerationRequest(kind, Faction.OfPlayer, fixedGender: Gender.Female));
        GenSpawn.Spawn(actor, cell, map);
        if (actor.needs.food == null) { Finish("blocked", "Fixture Pawn has no food need."); return; }
        actor.needs.food.CurLevelPercentage = (float)contract.Fixture.InitialFoodFraction;
        foreach (string name in contract.Fixture.ActorHediffs ?? Array.Empty<string>()) actor.health.AddHediff(DefDatabase<HediffDef>.GetNamed(name));
        item = ThingMaker.MakeThing(definition);
        item.stackCount = 1;
        GenSpawn.Spawn(item, cell, map);
        item.SetForbidden(false, false);
        if (!item.IngestibleNow) { Finish("blocked", "Item is not currently ingestible; eligibility was not bypassed."); return; }
        Report!.WorkerId = actor.thingIDNumber;
        Report.TargetId = item.thingIDNumber;
        Report.Cell = cell.ToString();
        Report.TickStarted = Find.TickManager.TicksGame;
        foreach (EffectExpectation expectation in contract.Expect!)
        {
            double before = Read(expectation.Kind!, expectation.DefName);
            if (expectation.Kind == "hediff_removed" && before <= 0) { Finish("blocked", "Hediff removal needs an initial fixture Hediff."); return; }
            Report.Observations.Add(new EffectObservation { Kind = expectation.Kind!, Subject = "actor", DefName = expectation.DefName,
                When = expectation.When!, Before = before, After = before, Peak = before });
        }
        IngestObserver.Track(actor, item);
        job = JobMaker.MakeJob(JobDefOf.Ingest, item);
        job.count = 1;
        jobId = job.loadID;
        if (!actor.jobs.TryTakeOrderedJob(job)) { Finish("blocked", "Normal Ingest job was rejected."); return; }
        Find.TickManager.CurTimeSpeed = TimeSpeed.Normal;
        Report.Stage = "ingest_and_observe";
        Report.Checks.Add(new SuiteCheck { Name = "normal_ingest_requested", Status = "passed", Detail = "One fixture item; normal Ingest job/Toils applies consumption and outcomes. No expected effect was injected." });
        Observe();
    }

    private double Read(string kind, string? name)
    {
        if (kind == "item_consumed") return IngestObserver.Consumed;
        if (kind == "nutrition_increased") return actor!.needs.food.CurLevel;
        return actor!.health.hediffSet.hediffs.Count(hediff => hediff.def.defName == name);
    }

    private void Observe()
    {
        if (actor!.CurJob?.loadID == jobId) jobSeen = true;
        Report!.Job = actor.CurJob?.def.defName;
        foreach (EffectObservation observation in Report.Observations)
        {
            observation.After = Read(observation.Kind, observation.DefName);
            observation.Peak = Math.Max(observation.Peak, observation.After);
            bool met = observation.Kind == "hediff_removed" ? observation.After < observation.Before : observation.After > observation.Before + 0.0001;
            observation.Met = observation.When == "eventually" ? observation.Met || met : met;
        }
        if (Report.TickObserved - Report.TickStarted < contract!.ObserveTicks) return;
        bool consumed = jobSeen && IngestObserver.Consumed > 0;
        Report.Checks.Add(new SuiteCheck { Name = "real_ingestion", Status = consumed ? "passed" : "failed", Detail = "Observed the exact fixture job and Thing.Ingested completion destroying the one-item fixture; hauling/splitting is not consumption." });
        foreach (EffectObservation observation in Report.Observations)
            Report.Checks.Add(new SuiteCheck { Name = observation.Kind, Status = observation.Met ? "passed" : "failed", Detail = "Before=" + observation.Before + ", after=" + observation.After + ", peak=" + observation.Peak });
        bool passed = consumed && Report.Observations.All(observation => observation.Met);
        Finish(passed ? "passed" : "failed", passed ? "Normal ingestion and declared source-derived effects observed." : "Consumption or declared effect was not observed; no fabricated pass.");
    }

    private void Finish(string status, string message)
    {
        Report!.Status = status;
        Report.Message = message;
        IngestObserver.Track(null, null);
        try
        {
            if (actor?.CurJob != null && actor.CurJob.loadID == jobId) actor.jobs.EndCurrentJob(JobCondition.InterruptForced);
        }
        catch (Exception error)
        {
            Report.Status = "failed";
            Report.Message += " Cleanup failed: " + error.Message;
        }
    }
}
