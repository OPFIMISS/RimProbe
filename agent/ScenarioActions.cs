using RimWorld;
using Verse;
using Verse.AI;

namespace RimProbe.Agent;

internal sealed partial class ScenarioSuite
{
    private IntVec3 SafeSpawn(PlanStep step)
    {
        IntVec3 anchor = step.Near == null ? map!.mapPawns.FreeColonistsSpawned.FirstOrDefault()?.Position ?? map!.Center : Object(step.Near).Position;
        return GenRadial.RadialCellsAround(anchor, step.Op == "spawn_pawn" ? step.Distance + 8 : 8, true)
            .Where(position => position.InBounds(map!) && !position.Fogged(map!) && position.Standable(map!) && position.GetEdifice(map!) == null
                && (step.Op != "spawn_pawn" || position.GetFirstPawn(map!) == null)
                && (step.Op != "spawn_pawn" || step.Near == null || position.DistanceTo(anchor) >= step.Distance)
                && GenSight.LineOfSight(anchor, position, map!)).DefaultIfEmpty(IntVec3.Invalid).First();
    }

    private void Begin(PlanStep step)
    {
        if (BeginInteractionStep(step)) return;
        if (step.Op == "query_tests")
        {
            Complete(step, "observed", "Registered compiled test keys; not arbitrary methods.", definitions: RegisteredProbeTests.Keys.Take(64).Select(key => new PlanDefSummary { DefName = key, ClassName = "registered_test" }).ToArray(), total: RegisteredProbeTests.Keys.Length);
        }
        else if (step.Op == "registered_test")
        {
            StartRegisteredTest(step, map!);
        }
        else if (step.Op == "spawn_pawn")
        {
            IntVec3 cell = SafeSpawn(step);
            if (!cell.IsValid) throw new ProbeStepException("blocked", "No safe fixture spawn cell.");
            Faction? faction = step.Faction == "player" ? Faction.OfPlayer : Find.FactionManager.AllFactionsListForReading.FirstOrDefault(candidate => candidate.HostileTo(Faction.OfPlayer));
            if (faction == null) throw new ProbeStepException("blocked", "No existing hostile faction; diplomacy was not changed.");
            Pawn pawn = PawnGenerator.GeneratePawn(new PawnGenerationRequest(RequireDef<PawnKindDef>(step.DefName), faction, fixedGender: Gender.Female));
            GenSpawn.Spawn(pawn, cell, map!);
            if (pawn.needs.food != null) pawn.needs.food.CurLevelPercentage = (float)step.FoodFraction;
            handles.Add(step.Bind!, pawn);
            Complete(step, "completed", "New disposable Pawn with declared initial food fraction; expected effects not added.", snapshot: Inspect(pawn));
        }
        else if (step.Op == "spawn_item")
        {
            ThingDef definition = RequireDef<ThingDef>(step.DefName);
            ThingDef? stuff = step.StuffName == null ? GenStuff.DefaultStuffFor(definition) : RequireDef<ThingDef>(step.StuffName);
            if (definition.category != ThingCategory.Item || step.Count > definition.stackLimit
                || definition.MadeFromStuff && (stuff == null || !GenStuff.AllowedStuffsFor(definition).Contains(stuff))
                || !definition.MadeFromStuff && step.StuffName != null) throw new ProbeStepException("unsupported", "Expected valid item/count/stuff fixture; buildings use build.");
            IntVec3 cell = SafeSpawn(step);
            if (!cell.IsValid) throw new ProbeStepException("blocked", "No safe item fixture cell.");
            Thing item = ThingMaker.MakeThing(definition, stuff);
            item.stackCount = step.Count;
            if (!GenPlace.TryPlaceThing(item, cell, map!, ThingPlaceMode.Near)) throw new ProbeStepException("blocked", "Item fixture placement failed.");
            if (item.Destroyed) throw new ProbeStepException("blocked", "Fixture merged into another stack; exact handle cannot be guaranteed.");
            item.SetForbidden(false, false);
            handles.Add(step.Bind!, item);
            Complete(step, "completed", "New ground item; no result mutation.", snapshot: Inspect(item));
        }
        else if (step.Op == "fixture_hediff")
        {
            Actor(step.Actor).health.AddHediff(RequireDef<HediffDef>(step.DefName));
            Complete(step, "completed", "Explicit initial fixture Hediff; only before actions/assertions.");
        }
        else if (step.Op == "grant_ability")
        {
            Pawn actor = Actor(step.Actor);
            if (actor.abilities == null) throw new ProbeStepException("unsupported", "Pawn has no standard ability tracker.");
            actor.abilities.GainAbility(RequireDef<AbilityDef>(step.DefName));
            Complete(step, "completed", "Granted standard ability as fixture setup; no activation or expected effect.");
        }
        else if (step.Op == "cast")
        {
            Pawn actor = Actor(step.Actor);
            Thing target = Object(step.Target);
            if (!target.Spawned || target.Map != map) throw new ProbeStepException("blocked", "Cast target is not spawned on this map.");
            AbilityDef definition = RequireDef<AbilityDef>(step.DefName);
            Ability? ability = actor.abilities?.GetAbility(definition);
            if (ability == null || definition.targetWorldCell || !string.IsNullOrEmpty(definition.confirmationDialogText)) throw new ProbeStepException("unsupported", "No granted standard local ability, or explicit confirmation/world action required.");
            LocalTargetInfo castTarget = new(target);
            AcceptanceReport eligibility = ability.CanCast;
            if (!eligibility.Accepted || !ability.CanQueueCast || !ability.CanApplyOn(castTarget) || !ability.verb.ValidateTarget(castTarget, false))
                throw new ProbeStepException("blocked", "Normal ability eligibility rejected: " + eligibility.Reason);
            int windows = Find.WindowStack.Windows.Count;
            HashSet<int> before = new(actor.jobs.jobQueue.Select(entry => entry.job.loadID));
            int? previous = actor.CurJob?.loadID;
            ability.QueueCastingJob(castTarget, castTarget);
            if (actor.CurJob != null && actor.CurJob.loadID != previous) Remember(actor, actor.CurJob.loadID);
            foreach (Job queued in actor.jobs.jobQueue.Select(entry => entry.job).Where(job => !before.Contains(job.loadID))) Remember(actor, queued.loadID);
            if (Find.WindowStack.Windows.Count > windows) throw new ProbeStepException("unsupported", "Cast opened UI confirmation; no bypass.");
            Complete(step, "requested", "Normal QueueCastingJob requested; later assertions prove effects.");
        }
        else if (step.Op == "ingest" || step.Op == "equip" || step.Op == "move")
        {
            Pawn actor = Actor(step.Actor);
            Thing target = Object(step.Target);
            if (!target.Spawned || target.Map != map) throw new ProbeStepException("blocked", "Action target must be spawned on this map.");
            Job job;
            if (step.Op == "ingest")
            {
                if (!target.IngestibleNow || actor.needs.food == null) throw new ProbeStepException("blocked", "Normal ingestion prerequisites not met.");
                job = JobMaker.MakeJob(JobDefOf.Ingest, target);
                job.count = 1;
            }
            else if (step.Op == "equip")
            {
                if (actor.equipment == null || !target.def.IsWeapon || target.TryGetComp<CompEquippable>() == null) throw new ProbeStepException("unsupported", "Standard weapon/equipment required.");
                job = JobMaker.MakeJob(JobDefOf.Equip, target);
                job.count = 1;
            }
            else
            {
                IntVec3 destination = GenRadial.RadialCellsAround(target.Position, 3, true).Where(cell => cell.InBounds(map!) && cell.Standable(map!) && !cell.Fogged(map!)).DefaultIfEmpty(IntVec3.Invalid).First();
                if (!destination.IsValid) throw new ProbeStepException("blocked", "No walkable cell near target.");
                job = JobMaker.MakeJob(JobDefOf.Goto, destination);
            }
            int id = job.loadID;
            if (!actor.jobs.TryTakeOrderedJob(job)) throw new ProbeStepException("blocked", "Normal ordered job rejected.");
            Remember(actor, id);
            Complete(step, "requested", "Normal " + step.Op + " job requested, loadID=" + id + "; not proof of completion.");
        }
        else if (step.Op == "build")
        {
            construction.Start(new SuiteOptions { RunId = Guid.NewGuid().ToString("N"), DefName = step.DefName, StuffName = step.StuffName,
                MaxTicks = Math.Max(60, contract!.MaxTicks - (Report!.TickObserved - Report.TickStarted)), TimeoutSeconds = contract.TimeoutSeconds, ConstructionOnly = true });
        }
        else if (step.Op == "find_thing")
        {
            IntVec3 center = step.Near == null ? map!.Center : Object(step.Near).Position;
            ThingDef definition = RequireDef<ThingDef>(step.DefName);
            Thing? found = map!.listerThings.ThingsOfDef(definition).Where(thing => thing.Spawned && !thing.Position.Fogged(map)
                && thing.Position.DistanceToSquared(center) <= step.Radius * step.Radius)
                .OrderBy(thing => thing.Position.DistanceToSquared(center)).ThenBy(thing => thing.thingIDNumber).Skip(step.Index).FirstOrDefault();
            if (found == null) throw new ProbeStepException("blocked", "No matching live Thing in the bounded search.");
            handles.Add(step.Bind!, found);
            Complete(step, "observed", "Existing object bound by Def, distance, stable ID and index in this disposable map.", snapshot: Inspect(found));
        }
        else if (step.Op == "measure")
        {
            double observed = Read(step);
            if (double.IsNaN(observed) || double.IsInfinity(observed)) throw new InvalidOperationException("Baseline is non-finite.");
            values.Add(step.BindValue!, observed);
            Complete(step, "observed", "Recorded actual numeric baseline " + step.BindValue + "; no assertion yet.", value: observed);
        }
        else if (step.Op == "inspect") Complete(step, "observed", "Bounded typed live state; no reflection paths.", snapshot: Inspect(Object(step.Target)));
        else if (step.Op == "query_defs")
        {
            IEnumerable<Def> definitions = step.DefType == "ThingDef" ? DefDatabase<ThingDef>.AllDefs.Cast<Def>()
                : step.DefType == "AbilityDef" ? DefDatabase<AbilityDef>.AllDefs.Cast<Def>()
                : step.DefType == "HediffDef" ? DefDatabase<HediffDef>.AllDefs.Cast<Def>()
                : step.DefType == "PawnKindDef" ? DefDatabase<PawnKindDef>.AllDefs.Cast<Def>() : DefDatabase<RecipeDef>.AllDefs.Cast<Def>();
            List<Def> matched = definitions.Where(definition => definition.defName.IndexOf(step.Query ?? "", StringComparison.OrdinalIgnoreCase) >= 0).OrderBy(definition => definition.defName, StringComparer.Ordinal).ToList();
            Complete(step, "observed", "Actual loaded Def catalog, paginated by type; not source proof.", definitions: matched.Skip(step.Offset).Take(step.Limit).Select(definition => new PlanDefSummary { DefName = Short(definition.defName), ClassName = Short(definition.GetType().FullName ?? "") }).ToArray(), total: matched.Count);
        }
        else if (step.Op == "assert") ObserveAssertion(step, false);
    }

    private void ObserveBuild(PlanStep step)
    {
        construction.Pump();
        SuiteReport? result = construction.Report;
        if (result == null || result.Status == "running") return;
        if (result.Status != "passed")
        {
            Complete(step, result.Status, "Normal construction incomplete; see nested evidence.", child: result);
            Finish(result.Status, result.Message);
            return;
        }
        Thing? building = map!.listerThings.AllThings.FirstOrDefault(thing => thing.thingIDNumber == result.TargetId);
        if (building == null || !building.Spawned) throw new InvalidOperationException("Completed building handle unavailable.");
        handles.Add(step.Bind!, building);
        Complete(step, "completed", "Normal construction only; subsequent typed assertions determine function.", child: result);
    }

    private void Remember(Pawn pawn, int jobId)
    {
        if (!jobs.TryGetValue(pawn, out HashSet<int>? owned)) jobs[pawn] = owned = new HashSet<int>();
        owned.Add(jobId);
    }
}
