using System.Diagnostics;
using System.Text.RegularExpressions;
using RimWorld;
using UnityEngine;
using Verse;

namespace RimProbe.Agent;

internal sealed partial class ScenarioSuite
{
    private readonly Dictionary<string, (string Interaction, string Choice)> choiceAliases = new();
    private readonly Stopwatch barrierClock = new();
    private int barrierSamples;
    private string? barrierIdentity;
    private string? barrierInitialInteraction;

    internal static void ValidateInteractionStep(PlanStep step, HashSet<string> choices)
    {
        if (step.Op == "wait_until" && (!new[] { "interaction_ready", "interaction_closed", "map_ready", "ability_job_finished" }.Contains(step.Condition)
            || step.TimeoutSeconds < 1 || step.TimeoutSeconds > 120 || step.StableFrames < 2 || step.StableFrames > 120
            || step.CancelIf != null && step.CancelIf != "actor_unavailable"
            || (step.Condition == "ability_job_finished" || step.CancelIf != null) && step.Actor == null))
            throw new ArgumentException("Invalid readiness barrier.");
        if (new[] { "inspect_interaction", "enumerate_choices", "cancel_interaction" }.Contains(step.Op))
        {
            if (step.X.HasValue != step.Z.HasValue || step.X < 0 || step.X > 9999 || step.Z < 0 || step.Z > 9999
                || step.Offset < 0 || step.Offset > 100000 || step.Limit < 1 || step.Limit > 8
                || step.Op != "enumerate_choices" && (step.Target != null || step.BindChoice != null || step.X != null || step.Z != null))
                throw new ArgumentException("Invalid interaction candidate query.");
            if (step.CellAtTarget && (step.Op != "enumerate_choices" || step.Target == null || step.X != null)) throw new ArgumentException("Invalid cell-at-target query.");
            if (step.BindChoice != null && (!Regex.IsMatch(step.BindChoice, "^[A-Za-z][A-Za-z0-9_]{0,31}\\z") || !choices.Add(step.BindChoice)))
                throw new ArgumentException("Invalid or rebound choice alias.");
        }
        if (step.Op == "select_choice" && (step.Choice == null || !choices.Contains(step.Choice)))
            throw new ArgumentException("Choice must be bound by earlier enumeration.");
    }

    internal static string StepFidelity(string op) => new[] { "cast", "ingest", "equip", "move", "build" }.Contains(op) ? "normal_game_action"
        : new[] { "begin_ability", "select_choice", "cancel_interaction" }.Contains(op) ? "validated_semantic_callback"
        : new[] { "spawn_pawn", "spawn_item", "fixture_hediff", "grant_ability" }.Contains(op) ? "fixture_setup"
        : op == "registered_test" ? "test_pack_declared_scope" : "state_observation";

    private bool BeginInteractionStep(PlanStep step)
    {
        if (step.Op == "wait_until") { barrierClock.Restart(); barrierSamples = 0; barrierIdentity = null; barrierInitialInteraction = InteractionHub.Inspect().Handle; return true; }
        if (step.Op == "begin_ability")
        {
            Pawn actor = Actor(step.Actor);
            Ability ability = actor.abilities?.GetAbility(RequireDef<AbilityDef>(step.DefName)) ?? throw new ProbeStepException("blocked", "Ability is not granted.");
            if (!ability.CanCast.Accepted || !ability.CanQueueCast || ability.GizmoDisabled(out _))
                throw new ProbeStepException("blocked", "Ability command is disabled by normal eligibility.");
            Command_Ability? command = ability.GetGizmos().OfType<Command_Ability>().SingleOrDefault();
            if (command == null) throw new ProbeStepException("unsupported", "No unique standard Ability command; missing capability: custom_command_entry.");
            if (command.Disabled) throw new ProbeStepException("blocked", "Ability command disabled.");
            // Select the fixture Pawn inside the owned game only. No OS input or UI hit-test is synthesized.
            Find.Selector.ClearSelection(); Find.Selector.Select(actor);
            int? before = actor.CurJob?.loadID;
            HashSet<int> queued = new(actor.jobs.jobQueue.Select(entry => entry.job.loadID));
            command.ProcessInput(new Event());
            if (actor.CurJob != null && actor.CurJob.loadID != before) Remember(actor, actor.CurJob.loadID);
            foreach (var job in actor.jobs.jobQueue.Select(entry => entry.job).Where(job => !queued.Contains(job.loadID))) Remember(actor, job.loadID);
            CompleteInteraction(step, "requested", "Standard Ability command accepted; target choice and effect assertions remain independent.", InteractionHub.Inspect());
            return true;
        }
        InteractionSnapshot result;
        if (step.Op == "inspect_interaction") result = InteractionHub.Inspect();
        else if (step.Op == "enumerate_choices")
        {
            Thing? target = step.Target == null ? null : Object(step.Target);
            if (target != null && !target.Spawned) throw new ProbeStepException("blocked", "Candidate selector object must be spawned.");
            result = InteractionHub.Enumerate(new InteractionQuery { MapId = target?.Map?.uniqueID, ThingId = target?.thingIDNumber,
                X = step.CellAtTarget ? target!.Position.x : step.X, Z = step.CellAtTarget ? target!.Position.z : step.Z, Offset = step.Offset, Limit = step.Limit });
            if (step.BindChoice != null)
            {
                if (result.Choices.Length != 1) throw new ProbeStepException("unsupported", "bind_choice requires exactly one matching candidate; narrow typed selectors or use live interaction tools.");
                choiceAliases.Add(step.BindChoice, (result.Handle!, result.Choices[0].Handle));
            }
        }
        else if (step.Op == "select_choice")
        {
            var choice = choiceAliases[step.Choice!];
            result = TrackInteractionJobs(() => InteractionHub.Select(new InteractionQuery { Interaction = choice.Interaction, Choice = choice.Choice }));
        }
        else if (step.Op == "cancel_interaction") result = InteractionHub.Cancel(null);
        else return false;
        CompleteInteraction(step, step.Op == "cancel_interaction" ? "requested" : result.Status, "Typed interaction evidence; accepted actions do not prove effects.", result);
        return true;
    }

    private void CompleteInteraction(PlanStep step, string status, string detail, InteractionSnapshot snapshot)
    {
        Complete(step, status, detail);
        PlanStepReport entry = Report!.Steps[Report.Steps.Count - 1];
        entry.Interaction = snapshot;
        if (WireJson.Serialize(Report).Length > 40000)
        {
            entry.Interaction = null; entry.DiagnosticsOmitted = true;
            Finish("inconclusive", "Interaction evidence budget exceeded.");
        }
    }

    private void ObserveBarrier(PlanStep step)
    {
        if (step.CancelIf == "actor_unavailable")
        {
            Pawn actor = (Pawn)Object(step.Actor);
            if (actor.Destroyed || actor.Dead || actor.Downed || !actor.Spawned)
            { FailCurrentStep("cancelled", "Readiness barrier cancellation: actor_unavailable."); return; }
        }
        InteractionSnapshot interaction = InteractionHub.Inspect();
        Report!.Interaction = interaction;
        bool matched = step.Condition == "interaction_ready" ? interaction.Ready
            : step.Condition == "interaction_closed" ? interaction.Kind == "none" || barrierInitialInteraction != null && interaction.Handle != barrierInitialInteraction
            : step.Condition == "map_ready" ? InteractionHub.MapReady
            : ((Pawn)Object(step.Actor)).CurJob?.ability == null;
        string identity = (Current.Game?.CurrentMap?.uniqueID.ToString() ?? "none") + ":" + interaction.Handle;
        barrierSamples = matched ? identity == barrierIdentity ? barrierSamples + 1 : 1 : 0;
        barrierIdentity = matched ? identity : null;
        if (barrierClock.Elapsed.TotalSeconds >= step.TimeoutSeconds)
        { FailCurrentStep("inconclusive", "Readiness phase timeout: " + step.Condition + "; missing readiness is not an effect failure."); return; }
        if (barrierSamples >= step.StableFrames)
            CompleteInteraction(step, "ready", "Observable condition " + step.Condition + " stable for " + barrierSamples + " sampled main-thread frames; not a functional assertion.", interaction);
    }

    internal InteractionSnapshot Interact(string runId, string command, InteractionQuery query)
    {
        if (Report?.Status != "running" || Report.RunId != runId) throw new ProbeStepException("blocked", "Interaction requires the active owned scenario run.");
        // Live writes only while the plan explicitly waits for external interaction.
        if ((command == "select_choice" || command == "cancel_interaction")
            && (contract!.Steps![index].Op != "wait_until" || contract.Steps[index].Condition != "interaction_closed"))
            throw new ProbeStepException("blocked", "Live choice/cancel requires wait_until interaction_closed; deterministic plans control their own actions.");
        if ((command == "select_choice" || command == "cancel_interaction") && query.Interaction != barrierInitialInteraction)
            throw new ProbeStepException("blocked", "Interaction changed; wait for the plan's next explicit interaction_closed barrier.");
        InteractionSnapshot result = command == "inspect_interaction" ? InteractionHub.Inspect()
            : command == "enumerate_choices" ? InteractionHub.Enumerate(query)
            : command == "select_choice" ? TrackInteractionJobs(() => InteractionHub.Select(query)) : InteractionHub.Cancel(query.Interaction);
        return result;
    }

    private InteractionSnapshot TrackInteractionJobs(Func<InteractionSnapshot> action)
    {
        var before = handles.Values.OfType<Pawn>().ToDictionary(pawn => pawn, pawn => new HashSet<int>(pawn.jobs.jobQueue.Select(entry => entry.job.loadID)
            .Concat(pawn.CurJob == null ? Array.Empty<int>() : new[] { pawn.CurJob.loadID })));
        try { return action(); }
        finally
        {
            foreach (var entry in before)
            {
                Pawn pawn = entry.Key;
                if (pawn.CurJob != null && !entry.Value.Contains(pawn.CurJob.loadID)) Remember(pawn, pawn.CurJob.loadID);
                foreach (var queued in pawn.jobs.jobQueue.Where(queued => !entry.Value.Contains(queued.job.loadID))) Remember(pawn, queued.job.loadID);
            }
        }
    }
}
