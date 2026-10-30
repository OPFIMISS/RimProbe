using RimWorld;
using Verse;
using Verse.AI;

namespace RimProbe.Agent;

internal sealed partial class ScenarioSuite
{
    private void ObserveAssertion(PlanStep step, bool wait)
    {
        double actual = Read(step);
        if (double.IsNaN(actual) || double.IsInfinity(actual)) throw new InvalidOperationException("Observation is non-finite.");
        double? baseline = step.RelativeTo == null ? null : values[step.RelativeTo];
        double compared = actual - (baseline ?? 0);
        bool matched = step.Compare == "eq" ? compared == step.Value : step.Compare == "ne" ? compared != step.Value
            : step.Compare == "gt" ? compared > step.Value : step.Compare == "ge" ? compared >= step.Value
            : step.Compare == "lt" ? compared < step.Value : compared <= step.Value;
        if (matched && heldSince < 0) heldSince = Report!.TickObserved;
        if (!matched) heldSince = -1;
        if (matched && (!wait || Report!.TickObserved - stepTick <= step.Ticks && Report.TickObserved - heldSince >= step.HoldTicks))
        {
            assertions++;
            Complete(step, "passed", step.Property + " " + step.Compare + " " + step.Value + "; sampled hold=" + (wait ? step.HoldTicks : 0), value: actual, baseline: baseline, compared: compared);
        }
        else if (!wait || Report!.TickObserved - stepTick >= step.Ticks)
        {
            Complete(step, "failed", "State condition not met within its bound: " + step.Property, value: actual, baseline: baseline, compared: compared);
            Finish("failed", "Plan assertion failed; action requests are not functional passes.");
        }
    }

    private double Read(PlanStep step)
    {
        Thing thing = Object(step.Target);
        string prop = step.Property!;
        if (prop == "hp") return thing.HitPoints;
        if (prop == "spawned") return thing.Spawned ? 1 : 0;
        if (prop == "destroyed") return thing.Destroyed ? 1 : 0;
        if (prop == "stack_count") return thing.stackCount;
        if (prop.StartsWith("map.", StringComparison.Ordinal))
        {
            Map actualMap = thing.Map ?? throw new ProbeStepException("blocked", "Object is not on a map; no map identity can be inferred.");
            return prop == "map.id" ? actualMap.uniqueID : prop == "map.tile_id" ? actualMap.Tile.tileId : actualMap.Tile.Layer.LayerID;
        }
        if (prop == "position.x" || prop == "position.z")
        {
            if (!thing.Spawned) throw new ProbeStepException("blocked", "Position observation requires a spawned object.");
            return prop == "position.x" ? thing.Position.x : thing.Position.z;
        }
        if (prop.StartsWith("power.", StringComparison.Ordinal))
        {
            CompPowerTrader power = (thing as ThingWithComps)?.GetComp<CompPowerTrader>() ?? throw new ProbeStepException("unsupported", "Handle has no CompPowerTrader.");
            if (prop == "power.watts") return power.PowerOutput;
            return power.PowerNet != null && power.PowerNet.Map == map && power.PowerNet.powerComps.Contains(power) ? 1 : 0;
        }
        Pawn pawn = thing as Pawn ?? throw new ProbeStepException("unsupported", "Property requires a Pawn.");
        if (prop == "pawn.job_active") return pawn.CurJob == null ? 0 : 1;
        if (prop == "pawn.dead") return pawn.Dead ? 1 : 0;
        if (prop == "pawn.downed") return pawn.Downed ? 1 : 0;
        if (prop == "pawn.stunned") return pawn.stances.stunner.Stunned ? 1 : 0;
        if (prop == "pawn.food") return pawn.needs.food?.CurLevel ?? throw new ProbeStepException("unsupported", "Pawn has no food need.");
        if (prop == "pawn.injury") return pawn.health.hediffSet.hediffs.OfType<Hediff_Injury>().Sum(hediff => hediff.Severity);
        if (prop == "pawn.hediff_count") return pawn.health.hediffSet.hediffs.Count(hediff => hediff.def.defName == step.DefName);
        if (prop == "pawn.ability_cooldown") return pawn.abilities?.GetAbility(RequireDef<AbilityDef>(step.DefName))?.CooldownTicksRemaining ?? throw new ProbeStepException("blocked", "Ability is not present.");
        if (prop == "pawn.ability_casting") return pawn.CurJob?.ability != null ? 1 : 0;
        if (prop == "pawn.equipped") return pawn.equipment?.AllEquipmentListForReading.Count(item => item.def.defName == step.DefName) ?? 0;
        if (prop == "pawn.distance_to")
        {
            Thing other = Object(step.Other);
            if (!pawn.Spawned || !other.Spawned || pawn.Map != other.Map) throw new ProbeStepException("blocked", "Distance needs spawned objects on the same map.");
            return pawn.Position.DistanceTo(other.Position);
        }
        throw new ProbeStepException("unsupported", "Unregistered observation property.");
    }

    private static string Short(string text) => text.Length <= 120 ? text : text.Substring(0, 120);

    private PlanObjectSnapshot Inspect(Thing thing)
    {
        Pawn? pawn = thing as Pawn;
        string[] abilities = pawn?.abilities?.abilities.Select(ability => ability.def.defName).ToArray() ?? Array.Empty<string>();
        string[] hediffs = pawn?.health.hediffSet.hediffs.Select(hediff => hediff.def.defName).ToArray() ?? Array.Empty<string>();
        string[] equipment = pawn?.equipment?.AllEquipmentListForReading.Select(item => item.def.defName).ToArray() ?? Array.Empty<string>();
        string[] comps = (thing as ThingWithComps)?.AllComps.Select(comp => comp.GetType().FullName ?? comp.GetType().Name).ToArray() ?? Array.Empty<string>();
        bool power = (thing as ThingWithComps)?.GetComp<CompPowerTrader>() != null;
        return new PlanObjectSnapshot { ThingId = thing.thingIDNumber, DefName = Short(thing.def.defName), ClassName = Short(thing.GetType().FullName ?? ""),
            MapId = thing.Map?.uniqueID, TileId = thing.Map?.Tile.tileId, LayerId = thing.Map?.Tile.Layer.LayerID, X = thing.Position.x, Z = thing.Position.z,
            Cell = thing.Position.ToString(), Spawned = thing.Spawned, Destroyed = thing.Destroyed, HitPoints = thing.HitPoints, Job = pawn?.CurJob == null ? null : Short(pawn.CurJob.def.defName),
            JobAbility = pawn?.CurJob?.ability == null ? null : Short(pawn.CurJob.ability.def.defName), JobId = pawn?.CurJob?.loadID,
            Abilities = abilities.Take(8).Select(Short).ToArray(), Hediffs = hediffs.Take(8).Select(Short).ToArray(), Equipment = equipment.Take(8).Select(Short).ToArray(), Comps = comps.Take(8).Select(Short).ToArray(),
            ListsTruncated = abilities.Length > 8 || hediffs.Length > 8 || equipment.Length > 8 || comps.Length > 8,
            AvailableProperties = NumericProperties.Where(prop => !prop.StartsWith("pawn.", StringComparison.Ordinal) && !prop.StartsWith("power.", StringComparison.Ordinal)
                || pawn != null && prop.StartsWith("pawn.", StringComparison.Ordinal) || power && prop.StartsWith("power.", StringComparison.Ordinal)).ToArray() };
    }

    private void Complete(PlanStep step, string status, string detail, double? value = null, PlanObjectSnapshot? snapshot = null, PlanDefSummary[]? definitions = null, int? total = null, SuiteReport? child = null, double? baseline = null, double? compared = null)
    {
        PlanStepReport entry = new() { Id = step.Id, Op = step.Op, Status = status, Tick = Report!.TickObserved, Detail = detail,
            Fidelity = StepFidelity(step.Op),
            Value = value, Baseline = baseline, ComparedValue = compared, Snapshot = snapshot, Definitions = definitions, TotalMatches = total, Construction = child };
        if (new[] { "failed", "blocked", "unsupported", "inconclusive", "cancelled" }.Contains(status))
        {
            try { entry.FailureContext = CaptureFailureContext(step); }
            catch { entry.DiagnosticsOmitted = true; }
        }
        Report.Steps.Add(entry);
        if (WireJson.Serialize(Report).Length > 40000 && entry.FailureContext != null)
        {
            entry.FailureContext = null;
            entry.DiagnosticsOmitted = true;
        }
        if (WireJson.Serialize(Report).Length > 40000)
        {
            entry.Snapshot = null;
            entry.Definitions = null;
            entry.Construction = null;
            entry.Status = "inconclusive";
            entry.Detail = "Evidence budget exceeded; detail not retained. No pass claimed.";
            Finish("inconclusive", entry.Detail);
            return;
        }
        index++;
        stepTick = heldSince = -1;
    }

    private void Finish(string status, string message)
    {
        if (Report == null) return;
        Report.Status = status;
        Report.Message = message;
        DisposeRegisteredTest();
        CleanupAction(InteractionHub.Cleanup, lifecycleStep, "interaction_cleanup");
        CleanupAction(() =>
        {
            construction.Cancel();
            if (construction.Report?.Message.Contains("Cleanup failed:") == true) throw new InvalidOperationException(construction.Report.Message);
        }, lifecycleStep, "construction_cleanup");
        foreach (KeyValuePair<Pawn, HashSet<int>> owned in jobs)
        {
            CleanupAction(() =>
            {
                Pawn pawn = owned.Key;
                pawn.jobs.jobQueue.RemoveAll(pawn, job => owned.Value.Contains(job.loadID));
                if (pawn.CurJob != null && owned.Value.Contains(pawn.CurJob.loadID)) pawn.jobs.EndCurrentJob(JobCondition.InterruptForced);
            }, lifecycleStep, "job_cleanup");
        }
        BoundFailureEvidence();
    }
}
