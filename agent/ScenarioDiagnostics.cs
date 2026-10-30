using System.Runtime.Serialization;

namespace RimProbe.Agent;

[DataContract]
internal sealed class PlanFailureObject
{
    [DataMember(Name = "alias")] public string Alias { get; set; } = "";
    [DataMember(Name = "snapshot", EmitDefaultValue = false)] public PlanObjectSnapshot? Snapshot { get; set; }
    [DataMember(Name = "error", EmitDefaultValue = false)] public string? Error { get; set; }
}

[DataContract]
internal sealed class PlanFailureContext
{
    [DataMember(Name = "elapsed_ticks")] public int ElapsedTicks { get; set; }
    [DataMember(Name = "sampled_hold_ticks")] public int SampledHoldTicks { get; set; }
    [DataMember(Name = "condition", EmitDefaultValue = false)] public PlanStep? Condition { get; set; }
    [DataMember(Name = "objects")] public PlanFailureObject[] Objects { get; set; } = Array.Empty<PlanFailureObject>();
    [DataMember(Name = "objects_truncated")] public bool ObjectsTruncated { get; set; }
}

internal sealed partial class ScenarioSuite
{
    internal static PlanFailureContext CollectFailureContext(PlanStep step, int elapsed, int held,
        IEnumerable<string?> relatedAliases, Func<string, PlanObjectSnapshot> inspect)
    {
        string[] aliases = new[] { step.Actor, step.Target, step.Other, step.Near }.Concat(relatedAliases)
            .Where(alias => alias != null).Select(alias => alias!).Distinct(StringComparer.Ordinal).Take(5).ToArray();
        return new PlanFailureContext
        {
            ElapsedTicks = Math.Max(0, elapsed),
            SampledHoldTicks = Math.Max(0, held),
            Condition = step.Op == "assert" || step.Op == "wait_assert" || step.Op == "wait_until" ? step : null,
            ObjectsTruncated = aliases.Length > 4,
            Objects = aliases.Take(4).Select(alias =>
            {
                PlanFailureObject entry = new() { Alias = alias };
                try { entry.Snapshot = inspect(alias); }
                catch (Exception error) { entry.Error = Short(error.GetType().Name + ": " + error.Message); }
                return entry;
            }).ToArray()
        };
    }

    private PlanFailureContext CaptureFailureContext(PlanStep step)
    {
        PlanStep? action = contract!.Steps!.Take(index + 1).LastOrDefault(candidate =>
            new[] { "cast", "ingest", "equip", "move" }.Contains(candidate.Op));
        return CollectFailureContext(step, stepTick < 0 ? 0 : Report!.TickObserved - stepTick,
            heldSince < 0 ? 0 : Report!.TickObserved - heldSince,
            new[] { action?.Actor, action?.Target }, alias => Inspect(Object(alias)));
    }
}
