using RimWorld;
using UnityEngine;
using Verse;

namespace RimProbe.Agent;

public static class IngestObserver
{
    private static Pawn? actor;
    private static Thing? item;
    public static int Consumed { get; private set; }
    public static void Track(Pawn? pawn, Thing? thing)
    {
        actor = pawn;
        item = thing;
        Consumed = 0;
    }
    public static void AfterIngest(Thing __instance, Pawn ingester)
    {
        if (ReferenceEquals(actor, ingester) && ReferenceEquals(item, __instance) && __instance.Destroyed)
        {
            Consumed++;
        }
    }
}


public static class ConstructionObserver
{
    private static Frame? frame;
    public static int Failures { get; private set; }
    public static int FailedFrameId { get; private set; }
    public static int FailedWorkerId { get; private set; }
    public static void Reset()
    {
        frame = null;
        Failures = 0;
        FailedFrameId = 0;
        FailedWorkerId = 0;
    }
    public static void Track(Frame target)
    {
        frame = target;
    }
    public static void AfterFailure(Frame __instance, Pawn worker)
    {
        if (ReferenceEquals(frame, __instance))
        {
            Failures++;
            FailedFrameId = __instance.thingIDNumber;
            FailedWorkerId = worker.thingIDNumber;
        }
    }
}

public static class UiDrawObserver
{
    private static Dialog_InfoCard? window;
    public static int Draws { get; private set; }
    public static void Track(Dialog_InfoCard? target)
    {
        window = target;
        Draws = 0;
    }
    public static void AfterDraw(Dialog_InfoCard __instance)
    {
        if (ReferenceEquals(window, __instance) && Event.current != null && Event.current.type == EventType.Repaint)
        {
            Draws++;
        }
    }
}
