using System.Diagnostics;
using System.Runtime.Serialization;
using RimWorld;
using Verse;
using Verse.AI;

namespace RimProbe.Agent;

[DataContract]
internal sealed class SuiteOptions
{
    [DataMember(Name = "interaction")] public InteractionQuery? Interaction { get; set; }
    [DataMember(Name = "construction_only")] public bool ConstructionOnly { get; set; }
    [DataMember(Name = "run_id")] public string? RunId { get; set; }
    [DataMember(Name = "def_name")] public string? DefName { get; set; }
    [DataMember(Name = "stuff_name")] public string? StuffName { get; set; }
    [DataMember(Name = "max_ticks")] public int MaxTicks { get; set; }
    [DataMember(Name = "timeout_seconds")] public int TimeoutSeconds { get; set; }
    [DataMember(Name = "contract")] public BehaviorContract? Contract { get; set; }
    [DataMember(Name = "supply_delay_ticks")] public int SupplyDelayTicks { get; set; }
}

[DataContract]
internal sealed class SuiteCheck
{
    [DataMember(Name = "name")] public string Name { get; set; } = "";
    [DataMember(Name = "status")] public string Status { get; set; } = "";
    [DataMember(Name = "detail")] public string Detail { get; set; } = "";
}

[DataContract]
internal sealed class MaterialEvidence
{
    [DataMember(Name = "def_name")] public string DefName { get; set; } = "";
    [DataMember(Name = "required")] public int Required { get; set; }
    [DataMember(Name = "observed")] public int Observed { get; set; }
}

[DataContract]
internal sealed class PowerEvidence
{
    [DataMember(Name = "tick_started")] public int TickStarted { get; set; }
    [DataMember(Name = "tick_last")] public int TickLast { get; set; }
    [DataMember(Name = "samples")] public int Samples { get; set; }
    [DataMember(Name = "connected_samples")] public int ConnectedSamples { get; set; }
    [DataMember(Name = "minimum_watts")] public double MinimumWatts { get; set; }
    [DataMember(Name = "maximum_watts")] public double MaximumWatts { get; set; }
    [DataMember(Name = "last_watts")] public double LastWatts { get; set; }
}

[DataContract]
internal sealed class SuiteReport
{
    [DataMember(Name = "interaction", EmitDefaultValue = false)] public InteractionSnapshot? Interaction { get; set; }
    [DataMember(Name = "primary_failure", EmitDefaultValue = false)] public ProbeFailure? PrimaryFailure { get; set; }
    [DataMember(Name = "cleanup_failures", EmitDefaultValue = false)] public List<ProbeFailure> CleanupFailures { get; set; } = new();
    [DataMember(Name = "failure_evidence_truncated", EmitDefaultValue = false)] public bool FailureEvidenceTruncated { get; set; }
    [DataMember(Name = "steps", EmitDefaultValue = false)] public List<PlanStepReport> Steps { get; set; } = new();
    [DataMember(Name = "power_evidence", EmitDefaultValue = false)] public PowerEvidence? Power { get; set; }
    [DataMember(Name = "recipe")] public string Recipe { get; set; } = "building_construction";
    [DataMember(Name = "intent")] public string? Intent { get; set; }
    [DataMember(Name = "observations")] public List<EffectObservation> Observations { get; set; } = new();
    [DataMember(Name = "run_id")] public string RunId { get; set; } = "";
    [DataMember(Name = "status")] public string Status { get; set; } = "running";
    [DataMember(Name = "stage")] public string Stage { get; set; } = "prepare";
    [DataMember(Name = "def_name")] public string DefName { get; set; } = "";
    [DataMember(Name = "stuff_name")] public string? StuffName { get; set; }
    [DataMember(Name = "message")] public string Message { get; set; } = "";
    [DataMember(Name = "tick_started")] public int TickStarted { get; set; }
    [DataMember(Name = "tick_observed")] public int TickObserved { get; set; }
    [DataMember(Name = "hauling_actor_ids")] public List<int> HaulingActors { get; set; } = new();
    [DataMember(Name = "construction_actor_ids")] public List<int> ConstructionActors { get; set; } = new();
    [DataMember(Name = "worker_id")] public int WorkerId { get; set; }
    [DataMember(Name = "target_id")] public int? TargetId { get; set; }
    [DataMember(Name = "cell")] public string? Cell { get; set; }
    [DataMember(Name = "job")] public string? Job { get; set; }
    [DataMember(Name = "delivered_count")] public int DeliveredCount { get; set; }
    [DataMember(Name = "required_count")] public int RequiredCount { get; set; }
    [DataMember(Name = "materials")] public List<MaterialEvidence> Materials { get; set; } = new();
    [DataMember(Name = "construction_failures")] public int ConstructionFailures { get; set; }
    [DataMember(Name = "work_observed")] public float WorkObserved { get; set; }
    [DataMember(Name = "checks")] public List<SuiteCheck> Checks { get; set; } = new();
    [DataMember(Name = "events")] public List<string> Events { get; set; } = new();
    [DataMember(Name = "excluded")] public string[] Excluded { get; set; } = {
        "UI hit-testing/rendering", "research unlock workflow", "automatic work-priority scheduling",
        "save/load", "deconstruction", "arbitrary custom functionality", "missing-material recovery", "all rotations" };
}

internal sealed class BuildingSuite
{
    public SuiteReport? Report { get; private set; }
    private SuiteOptions? options;
    private Stopwatch? elapsed;
    private Map? map;
    private Pawn? worker;
    private ThingDef? targetDef;
    private ThingDef? stuff;
    private IntVec3 cell;
    private List<ThingDefCountClass> costs = new();
    private readonly HashSet<int> issuedJobs = new();
    private bool frameSeen;
    private bool deliveryJobSeen;
    private bool constructionJobSeen;
    private int lastOrderTick = -1000;
    private readonly List<Thing> withheld = new();
    private bool supplied;
    private Building? completedBuilding;
    private CompPowerTrader? powerComp;
    private int completedTick;

    public void Start(SuiteOptions? request)
    {
        if (request == null || !Guid.TryParseExact(request.RunId, "N", out _)
            || string.IsNullOrWhiteSpace(request.DefName) || request.DefName!.Length > 128
            || request.MaxTicks < 60 || request.MaxTicks > 120000
            || request.TimeoutSeconds < 5 || request.TimeoutSeconds > 600)
        {
            throw new ArgumentException("Invalid bounded building-suite options.");
        }
        if (Report?.RunId == request.RunId)
        {
            return;
        }
        if (Report?.Status == "running")
        {
            throw new InvalidOperationException("A suite is already running.");
        }
        if (request.SupplyDelayTicks < 0 || request.SupplyDelayTicks > 3600 || request.SupplyDelayTicks >= request.MaxTicks)
        {
            throw new ArgumentException("Invalid supply delay.");
        }
        if (request.Contract != null)
        {
            BehaviorContract contract = request.Contract;
            EffectExpectation[] expected = contract.Expect ?? Array.Empty<EffectExpectation>();
            if (contract.Schema != 1 || contract.Recipe != "building_power" || contract.DefName != request.DefName
                || string.IsNullOrWhiteSpace(contract.Intent) || contract.Intent!.Length > 2000
                || contract.Fixture == null || contract.Fixture.ConstructionSkill < 0 || contract.Fixture.ConstructionSkill > 20
                || contract.Fixture.SettleTicks < 1 || contract.Fixture.SettleTicks > 600
                || contract.ObserveTicks < 60 || contract.ObserveTicks > 60000
                || contract.MaxTicks != request.MaxTicks || contract.TimeoutSeconds != request.TimeoutSeconds
                || (long)contract.ObserveTicks + contract.Fixture.SettleTicks >= request.MaxTicks
                || expected.Length != 2 || expected.Count(entry => entry.Kind == "power_net_registered") != 1
                || expected.Count(entry => entry.Kind == "power_output_at_least" && !double.IsNaN(entry.MinimumWatts)
                    && !double.IsInfinity(entry.MinimumWatts) && entry.MinimumWatts > 0 && entry.MinimumWatts <= 10000000) != 1)
            {
                throw new ArgumentException("Invalid bounded building-power contract.");
            }
            request.StuffName = contract.Fixture.StuffName;
        }
        ConstructionObserver.Reset();
        options = request;
        completedBuilding = null;
        powerComp = null;
        completedTick = 0;
        withheld.Clear();
        supplied = false;
        elapsed = Stopwatch.StartNew();
        Report = new SuiteReport { RunId = request.RunId!, DefName = request.DefName! };
        if (request.Contract != null)
        {
            Report.Recipe = "building_power";
            Report.Intent = request.Contract.Intent;
            Report.Excluded = new[] { "UI", "fuel delivery", "power consumers", "production", "unasserted custom Comp semantics", "save/load", "all rotations" };
        }
        issuedJobs.Clear();
        worker = null;
        map = null;
        frameSeen = deliveryJobSeen = constructionJobSeen = false;
        lastOrderTick = -1000;
    }

    public void Cancel()
    {
        if (Report?.Status == "running")
        {
            Finish("cancelled", "Cancelled by controller; fixture remains only in this disposable session.");
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
            if (elapsed!.Elapsed.TotalSeconds >= options!.TimeoutSeconds)
            {
                Finish("inconclusive", "Wall-clock budget exceeded; inspect current job and logs.");
                return;
            }
            if (LongEventHandler.AnyEventNowOrWaiting || Current.ProgramState != ProgramState.Playing || Current.Game?.CurrentMap == null)
            {
                return;
            }
            Report.TickObserved = Find.TickManager.TicksGame;
            Report.ConstructionFailures = ConstructionObserver.Failures;
            if (Report.ConstructionFailures > 0)
            {
                Event("observed_real_construction_failure frame=" + ConstructionObserver.FailedFrameId + " worker=" + ConstructionObserver.FailedWorkerId);
                Check("construction_botch", "blocked", "Tracked target invoked Frame.FailConstruction for the fixture worker; resources may be lost through normal construction.");
                Finish("blocked", "Real construction failure observed; not automatically attributed to the Mod. No forced success or hidden material retry.");
                return;
            }
            if (Report.Stage == "prepare")
            {
                Prepare();
                return;
            }
            if (Current.Game.CurrentMap != map || worker == null || worker.Dead || worker.Downed || !worker.Spawned)
            {
                Finish("blocked", "Fixture map or capable worker is unavailable.");
                return;
            }
            if (Report.TickObserved - Report.TickStarted >= options.MaxTicks)
            {
                Finish("inconclusive", "Tick budget exceeded without completing real construction.");
                return;
            }
            if (Report.Stage == "power_observe") ObservePower();
            else ObserveConstruction();
        }
        catch (Exception error)
        {
            Finish("failed", error.GetType().Name + ": " + error.Message);
        }
    }

    private void Prepare()
    {
        map = Current.Game.CurrentMap;
        targetDef = DefDatabase<ThingDef>.GetNamedSilentFail(options!.DefName);
        if (targetDef == null || targetDef.category != ThingCategory.Building || !targetDef.BuildableByPlayer
            || targetDef.blueprintDef == null || targetDef.frameDef == null || !targetDef.canGenerateDefaultDesignator)
        {
            Finish("unsupported", "Expected a player-buildable building with the standard designator and frame path.");
            return;
        }
        if (!targetDef.IsResearchFinished || DebugSettings.godMode)
        {
            Finish("blocked", "Research must already be complete and god mode must be disabled.");
            return;
        }
        stuff = string.IsNullOrEmpty(options.StuffName) ? GenStuff.DefaultStuffFor(targetDef) : DefDatabase<ThingDef>.GetNamedSilentFail(options.StuffName);
        if (targetDef.MadeFromStuff && (stuff == null || !GenStuff.AllowedStuffsFor(targetDef).Contains(stuff))
            || !targetDef.MadeFromStuff && !string.IsNullOrEmpty(options.StuffName))
        {
            Finish("blocked", "Invalid or incompatible building material.");
            return;
        }
        Report!.StuffName = stuff?.defName;
        costs = targetDef.CostListAdjusted(stuff);
        if (costs.Count == 0 || costs.Any(cost => cost.count <= 0 || cost.count > 5000 || cost.thingDef.stackLimit < 1)
            || costs.Sum(cost => (long)Math.Ceiling((double)cost.count / Math.Max(1, cost.thingDef.stackLimit))) > 128
            || targetDef.Size.x > 10 || targetDef.Size.z > 10)
        {
            Finish("unsupported", "This recipe requires positive material costs <=5000 per type and footprint <=10x10.");
            return;
        }
        worker = map!.mapPawns.FreeColonistsSpawned.OrderByDescending(pawn => pawn.GetStatValue(StatDefOf.ConstructSuccessChance)).FirstOrDefault(pawn => !pawn.Dead && !pawn.Downed && !pawn.InMentalState
            && pawn.workSettings != null && !pawn.WorkTypeIsDisabled(WorkTypeDefOf.Construction)
            && pawn.skills.GetSkill(SkillDefOf.Construction).Level >= targetDef.constructionSkillPrerequisite
            && pawn.skills.GetSkill(SkillDefOf.Artistic).Level >= targetDef.artisticSkillPrerequisite);
        if (options.Contract != null) worker = CreatePowerWorker();
        if (worker == null)
        {
            Finish("blocked", "No healthy eligible colonist with the required skills in the disposable fixture.");
            return;
        }
        Designator_Build designator = new(targetDef);
        if (stuff != null)
        {
            designator.SetStuffDef(stuff);
        }
        bool found = false;
        int searched = 0;
        foreach (IntVec3 candidate in GenRadial.RadialCellsAround(worker.Position, 60, false))
        {
            if (++searched > 12000) break;
            if (candidate.DistanceToSquared(worker.Position) < 25 || !candidate.InBounds(map) || candidate.Fogged(map) || !candidate.Standable(map))
            {
                continue;
            }
            CellRect area = GenAdj.OccupiedRect(candidate, targetDef.defaultPlacingRot, targetDef.Size).ExpandedBy(3);
            if (!area.FullyContainedWithin(new CellRect(1, 1, map.Size.x - 2, map.Size.z - 2))
                || area.Cells.Any(position => position.GetThingList(map).Any(thing => thing.def.category == ThingCategory.Building
                    || thing.def.category == ThingCategory.Item || thing is Blueprint || thing is Frame))
                || !designator.CanDesignateCell(candidate).Accepted
                || !worker.CanReach(candidate, PathEndMode.Touch, Danger.None))
            {
                continue;
            }
            cell = candidate;
            found = true;
            break;
        }
        if (!found)
        {
            Finish("blocked", "No safe reachable item-free placement area within bounded radius 60; no existing structures/resources were removed.");
            return;
        }
        Report.Cell = cell.ToString();
        Report.WorkerId = worker.thingIDNumber;
        Report.TickStarted = Find.TickManager.TicksGame;
        Check("placement_validation", "passed", "Designator_Build.CanDesignateCell accepted the reachable location; god mode off.");
        if (designator.CanDesignateCell(new IntVec3(-100, 0, -100)).Accepted)
        {
            Finish("failed", "Placement unexpectedly accepted an out-of-bounds cell.");
            return;
        }
        Check("invalid_location", "passed", "Designator rejected an out-of-bounds cell.");
        designator.DesignateSingleCell(cell);
        Blueprint_Build? blueprint = cell.GetThingList(map).OfType<Blueprint_Build>().FirstOrDefault(thing => thing.def.entityDefToBuild == targetDef);
        if (blueprint == null)
        {
            Finish("failed", "Designating a normal paid building did not create its blueprint.");
            return;
        }
        Check("blueprint", "passed", "Normal designator produced blueprint " + blueprint.thingIDNumber);
        Report.RequiredCount = costs.Sum(cost => cost.count);
        Report.Materials = costs.Select(cost => new MaterialEvidence { DefName = cost.thingDef.defName, Required = cost.count }).ToList();
        if (options!.SupplyDelayTicks > 0)
        {
            foreach (Thing existing in map.listerThings.AllThings.Where(thing => thing.Spawned && costs.Any(cost => cost.thingDef == thing.def) && !thing.IsForbidden(worker)))
            {
                existing.SetForbidden(true, false);
                withheld.Add(existing);
            }
            Event("Fixture temporarily forbids " + withheld.Count + " existing supply stacks in this disposable map.");
            Report.Excluded = Report.Excluded.Where(entry => entry != "missing-material recovery").ToArray();
        }
        else if (!PlaceSupplies())
        {
            return;
        }
        if (worker.drafter != null)
        {
            worker.drafter.Drafted = false;
        }
        Find.TickManager.CurTimeSpeed = TimeSpeed.Normal;
        Report.Stage = supplied ? "construction" : "await_supply";
        Event("Blueprint placed; ground supplies only. No frame fill or completion shortcut.");
    }

    private bool PlaceSupplies()
    {
        foreach (ThingDefCountClass cost in costs)
        {
            int remaining = cost.count;
            while (remaining > 0)
            {
                Thing material = ThingMaker.MakeThing(cost.thingDef);
                material.stackCount = Math.Min(remaining, cost.thingDef.stackLimit);
                remaining -= material.stackCount;
                if (!GenPlace.TryPlaceThing(material, cell + new IntVec3(-3, 0, 0), map, ThingPlaceMode.Near))
                {
                    Finish("blocked", "Could not place fixture materials on the ground.");
                    return false;
                }
                material.SetForbidden(false, false);
                Event("fixture_ground_supply " + cost.thingDef.defName + " " + material.stackCount);
            }
        }
        supplied = true;
        return true;
    }

    private void RestoreWithheld()
    {
        foreach (Thing existing in withheld)
        {
            if (!existing.Destroyed)
            {
                existing.SetForbidden(false, false);
            }
        }
        withheld.Clear();
    }

    private void ObserveConstruction()
    {
        Report!.Job = worker!.CurJob?.def.defName;
        if (worker.CurJob != null && issuedJobs.Contains(worker.CurJob.loadID) && Report.Job == JobDefOf.HaulToContainer.defName)
        {
            deliveryJobSeen = true;
        }
        if (worker.CurJob != null && issuedJobs.Contains(worker.CurJob.loadID) && Report.Job == JobDefOf.FinishFrame.defName)
        {
            constructionJobSeen = true;
        }
        foreach (Pawn actor in map!.mapPawns.FreeColonistsSpawned.Take(256))
        {
            Job? actual = actor.CurJob;
            if (actual == null || (actual.def != JobDefOf.HaulToContainer && actual.def != JobDefOf.FinishFrame)) continue;
            Thing? destination = actual.def == JobDefOf.HaulToContainer ? actual.targetB.Thing : actual.targetA.Thing;
            if (destination == null || destination.Map != map || destination.Position != cell
                || !(destination is Frame currentFrame && currentFrame.def.entityDefToBuild == targetDef
                    || destination is Blueprint_Build currentBlueprint && currentBlueprint.def.entityDefToBuild == targetDef)) continue;
            List<int> actors = actual.def == JobDefOf.FinishFrame ? Report.ConstructionActors : Report.HaulingActors;
            if (!actors.Contains(actor.thingIDNumber) && actors.Count < 16)
            {
                actors.Add(actor.thingIDNumber);
                Event("observed_target_job " + actual.def.defName + " worker=" + actor.thingIDNumber + " loadID=" + actual.loadID);
            }
            if (actual.def == JobDefOf.FinishFrame) constructionJobSeen = true;
            else deliveryJobSeen = true;
        }
        List<Thing> things = cell.GetThingList(map!);
        Frame? frame = things.OfType<Frame>().FirstOrDefault(thing => thing.def.entityDefToBuild == targetDef);
        Blueprint_Build? blueprint = things.OfType<Blueprint_Build>().FirstOrDefault(thing => thing.def.entityDefToBuild == targetDef);
        Building? building = things.OfType<Building>().FirstOrDefault(thing => thing.def == targetDef);
        if (frame != null)
        {
            ConstructionObserver.Track(frame);
            if (!frameSeen)
            {
                frameSeen = true;
                Event("frame_observed " + frame.thingIDNumber);
            }
            int previousDelivered = Report.DeliveredCount;
            foreach (MaterialEvidence material in Report.Materials)
            {
                material.Observed = Math.Max(material.Observed, frame.resourceContainer.Where(thing => thing.def.defName == material.DefName).Sum(thing => thing.stackCount));
            }
            Report.DeliveredCount = Report.Materials.Sum(material => material.Observed);
            if (previousDelivered != Report.DeliveredCount)
            {
                Event("delivered_observed " + Report.DeliveredCount);
            }
            if (frame.workDone > Report.WorkObserved + 20 || Report.WorkObserved == 0 && frame.workDone > 0)
            {
                Event("work_observed " + frame.workDone.ToString("F2", System.Globalization.CultureInfo.InvariantCulture));
            }
            Report.WorkObserved = Math.Max(Report.WorkObserved, frame.workDone);
        }
        if (!supplied)
        {
            if (building != null || Report.DeliveredCount > 0 || Report.WorkObserved > 0)
            {
                Finish("failed", "Construction advanced while no permitted supplies were provided; shortage assumption did not hold.");
                return;
            }
            if (Report.TickObserved - Report.TickStarted >= options!.SupplyDelayTicks)
            {
                Check("missing_supply_stalled", "passed", "No delivered resources, work or finished building during the declared shortage window.");
                if (!PlaceSupplies())
                {
                    return;
                }
                Report.Stage = "construction";
                Event("Ground supply released; other stacks stay forbidden until cleanup to identify fixture hauling.");
            }
        }
        if (building != null)
        {
            Report.TargetId = building.thingIDNumber;
            if (!frameSeen || !deliveryJobSeen || !constructionJobSeen || Report.Materials.Any(material => material.Observed != material.Required) || Report.WorkObserved <= 0)
            {
                Finish("inconclusive", "Building exists, but complete hauling/frame/work evidence was not observed. No fabricated pass.");
                return;
            }
            Check("material_delivery", "passed", "Real HaulToContainer job and full material count observed in Frame.resourceContainer.");
            Check("construction", "passed", "Real FinishFrame job, increasing work and completed building observed.");
            bool initialized = building.Faction == Faction.OfPlayer && building.Stuff == stuff
                && building.Rotation == targetDef!.defaultPlacingRot && building.HitPoints > 0 && blueprint == null && frame == null;
            Check("building_initialization", initialized ? "passed" : "failed", "Checked final Faction, Stuff, rotation, positive HP and absence of blueprint/frame at the target origin.");
            if (!initialized)
            {
                Finish("failed", "Completed building initialization did not match the requested fixture.");
                return;
            }
            if (options!.Contract != null)
            {
                completedBuilding = building;
                powerComp = building.GetComp<CompPowerTrader>();
                if (powerComp == null)
                {
                    Finish("unsupported", "Constructed building has no CompPowerTrader; no output is invented.");
                    return;
                }
                completedTick = Report.TickObserved;
                Report.Stage = "power_observe";
                Event("Constructed target; observe natural Comp ticks after settling, never assign power state or output.");
                return;
            }
            if (options!.ConstructionOnly)
            {
                Finish("passed", "Normal construction completed; functionality is reserved for subsequent scenario assertions.");
                return;
            }
            if (targetDef!.defName != "Wall")
            {
                Check("function", "unsupported", "No functional contract for this building; construction success is not functional success.");
                Finish("unsupported", "Construction passed; custom building function requires an explicit adapter.");
                return;
            }
            bool healthyWall = building.HitPoints > 0 && targetDef.passability == Traversability.Impassable && cell.GetEdifice(map!) == building;
            Check("wall_structure", healthyWall ? "passed" : "failed", "Wall exists as the cell edifice, has positive HP, and is impassable by definition; no pathfinding/UI assertion.");
            Finish(healthyWall ? "passed" : "failed", "Wall structural construction recipe complete; excluded coverage is explicit.");
            return;
        }
        Thing? target = (Thing?)frame ?? blueprint;
        if (target == null)
        {
            Finish("failed", "Blueprint/frame disappeared without a completed target building.");
            return;
        }
        if (Report.TickObserved - lastOrderTick < 60 || worker.CurJob != null && issuedJobs.Contains(worker.CurJob.loadID))
        {
            return;
        }
        string giverName = frame == null ? "ConstructDeliverResourcesToBlueprints" : frame.IsCompleted() ? "ConstructFinishFrames" : "ConstructDeliverResourcesToFrames";
        WorkGiver_Scanner giver = (WorkGiver_Scanner)DefDatabase<WorkGiverDef>.GetNamed(giverName).Worker;
        Job? job = giver.JobOnThing(worker, target, true);
        lastOrderTick = Report.TickObserved;
        if (job != null)
        {
            issuedJobs.Add(job.loadID);
            if (worker.jobs.TryTakeOrderedJob(job))
            {
                Event("ordered_vanilla_job " + job.def.defName + " loadID=" + job.loadID);
            }
        }
    }

    private Pawn? CreatePowerWorker()
    {
        IntVec3 anchor = map!.mapPawns.FreeColonistsSpawned.FirstOrDefault()?.Position ?? map.Center;
        IntVec3 spawn = GenRadial.RadialCellsAround(anchor, 15, true).Where(position => position.InBounds(map)
            && !position.Fogged(map) && position.Standable(map) && position.GetEdifice(map) == null
            && !position.GetThingList(map).Any(thing => thing is Pawn)).DefaultIfEmpty(IntVec3.Invalid).First();
        if (!spawn.IsValid) return null;
        for (int attempt = 0; attempt < 4; attempt++)
        {
            Pawn candidate = PawnGenerator.GeneratePawn(new PawnGenerationRequest(PawnKindDefOf.Colonist, Faction.OfPlayer, fixedGender: Gender.Female));
            if (candidate.Dead || candidate.Downed || candidate.InMentalState || candidate.workSettings == null || candidate.skills == null
                || candidate.WorkTypeIsDisabled(WorkTypeDefOf.Construction) || candidate.WorkTypeIsDisabled(WorkTypeDefOf.Hauling)) continue;
            candidate.skills.GetSkill(SkillDefOf.Construction).Level = options!.Contract!.Fixture!.ConstructionSkill;
            candidate.skills.GetSkill(SkillDefOf.Artistic).Level = targetDef!.artisticSkillPrerequisite;
            if (candidate.skills.GetSkill(SkillDefOf.Construction).Level < targetDef.constructionSkillPrerequisite) return null;
            GenSpawn.Spawn(candidate, spawn, map);
            Event("new_power_fixture_worker " + candidate.thingIDNumber + " construction_skill=" + candidate.skills.GetSkill(SkillDefOf.Construction).Level
                + " actual_success_chance=" + candidate.GetStatValue(StatDefOf.ConstructSuccessChance).ToString("F3", System.Globalization.CultureInfo.InvariantCulture));
            return candidate;
        }
        return null;
    }

    private void ObservePower()
    {
        BehaviorContract contract = options!.Contract!;
        if (completedBuilding == null || completedBuilding.Destroyed || !completedBuilding.Spawned || completedBuilding.Map != map)
        {
            Finish("failed", "Constructed power target disappeared during observation.");
            return;
        }
        if (Report!.TickObserved - completedTick < contract.Fixture!.SettleTicks) return;
        double watts = powerComp!.PowerOutput;
        if (double.IsNaN(watts) || double.IsInfinity(watts))
        {
            Finish("failed", "Actual power output is non-finite.");
            return;
        }
        PowerEvidence evidence = Report.Power ??= new PowerEvidence {
            TickStarted = Report.TickObserved, TickLast = -1, MinimumWatts = watts, MaximumWatts = watts };
        if (evidence.TickLast == Report.TickObserved) return;
        evidence.TickLast = Report.TickObserved;
        evidence.Samples++;
        PowerNet? powerNetwork = powerComp.PowerNet;
        if (powerNetwork != null && powerNetwork.Map == map && powerNetwork.powerComps.Contains(powerComp)) evidence.ConnectedSamples++;
        evidence.MinimumWatts = Math.Min(evidence.MinimumWatts, watts);
        evidence.MaximumWatts = Math.Max(evidence.MaximumWatts, watts);
        evidence.LastWatts = watts;
        if (evidence.TickLast - evidence.TickStarted < contract.ObserveTicks) return;
        double threshold = contract.Expect!.Single(entry => entry.Kind == "power_output_at_least").MinimumWatts;
        bool output = evidence.Samples >= 2 && evidence.MinimumWatts >= threshold;
        bool network = evidence.Samples >= 2 && evidence.ConnectedSamples == evidence.Samples;
        Check("power_output_at_least", output ? "passed" : "failed", "Minimum sampled actual output " + evidence.MinimumWatts + " W; required " + threshold + " W.");
        Check("power_net_registered", network ? "passed" : "failed", evidence.ConnectedSamples + "/" + evidence.Samples + " distinct-Tick samples attached to a real PowerNet.");
        Finish(output && network ? "passed" : "failed", "Normal construction followed by bounded actual power sampling; not every Tick, consumer performance or arbitrary Comp verification.");
    }

    private void Check(string name, string status, string detail)
    {
        Report!.Checks.Add(new SuiteCheck { Name = name, Status = status, Detail = detail });
    }

    private void Event(string message)
    {
        if (Report!.Events.Count < 64)
        {
            Report.Events.Add(Find.TickManager.TicksGame + ": " + message);
        }
    }

    private void Finish(string status, string message)
    {
        Report!.Status = status;
        Report.Message = message;
        try
        {
            ConstructionObserver.Reset();
            RestoreWithheld();
            if (worker?.CurJob != null && issuedJobs.Contains(worker.CurJob.loadID))
            {
                worker.jobs.EndCurrentJob(JobCondition.InterruptForced);
            }
        }
        catch (Exception error)
        {
            Report.Status = "failed";
            Report.Message += " Cleanup failed: " + error.Message;
        }
    }
}
