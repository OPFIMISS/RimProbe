using System.Runtime.Serialization;
using HarmonyLib;
using RimWorld;
using RimWorld.Planet;
using Verse;

namespace RimProbe.Agent;

[DataContract]
internal sealed class InteractionQuery
{
    [DataMember(Name = "interaction")] public string? Interaction { get; set; }
    [DataMember(Name = "choice")] public string? Choice { get; set; }
    [DataMember(Name = "map_id")] public int? MapId { get; set; }
    [DataMember(Name = "thing_id")] public int? ThingId { get; set; }
    [DataMember(Name = "x")] public int? X { get; set; }
    [DataMember(Name = "z")] public int? Z { get; set; }
    [DataMember(Name = "offset")] public int Offset { get; set; }
    [DataMember(Name = "limit")] public int Limit { get; set; } = 8;
}

[DataContract]
internal sealed class InteractionChoice
{
    [DataMember(Name = "handle")] public string Handle { get; set; } = "";
    [DataMember(Name = "object_type")] public string ObjectType { get; set; } = "";
    [DataMember(Name = "map_id")] public int? MapId { get; set; }
    [DataMember(Name = "thing_id")] public int? ThingId { get; set; }
    [DataMember(Name = "tile_id")] public int? TileId { get; set; }
    [DataMember(Name = "layer_id")] public int? LayerId { get; set; }
    [DataMember(Name = "x")] public int? X { get; set; }
    [DataMember(Name = "z")] public int? Z { get; set; }
    [DataMember(Name = "label")] public string Label { get; set; } = "";
    [DataMember(Name = "available")] public bool Available { get; set; }
}

[DataContract]
internal sealed class InteractionSnapshot
{
    [DataMember(Name = "handle")] public string? Handle { get; set; }
    [DataMember(Name = "kind")] public string Kind { get; set; } = "none";
    [DataMember(Name = "status")] public string Status { get; set; } = "observed";
    [DataMember(Name = "ready")] public bool Ready { get; set; }
    [DataMember(Name = "stable_frames")] public int StableFrames { get; set; }
    [DataMember(Name = "fidelity")] public string Fidelity { get; set; } = "validated_semantic_callback";
    [DataMember(Name = "readiness_scope")] public string ReadinessScope { get; set; } = "No pending LongEvent; playing; current map identity stable; map registered with drawer; live captured callback/menu. Renderer rebuild completion and hit testing are not observed.";
    [DataMember(Name = "missing_capability")] public string? MissingCapability { get; set; }
    [DataMember(Name = "choices")] public InteractionChoice[] Choices { get; set; } = Array.Empty<InteractionChoice>();
}

// Fixed, version-compiled adapters. No request can name a field, method or CLR type.
internal static class InteractionHub
{
    private sealed class Session
    {
        internal string Handle = Guid.NewGuid().ToString("N");
        internal string Kind = "";
        internal Func<bool> Live = () => false;
        internal Action Cancel = () => { };
        internal Func<GlobalTargetInfo, bool>? World;
        internal Func<GlobalTargetInfo, bool>? WorldValidator;
        internal Action<LocalTargetInfo>? Local;
        internal Func<LocalTargetInfo, bool>? LocalValidator;
        internal TargetingParameters? Parameters;
        internal FloatMenu? Menu;
        internal List<FloatMenuOption>? Options;
        internal readonly Dictionary<string, (InteractionChoice Evidence, Func<bool> Validate, Action Select)> Choices = new();
        internal readonly Dictionary<string, string> Keys = new();
    }
    private static Session? world, local, menu;
    private static bool armed;
    private static string? stateKey;
    internal static int StableFrames { get; private set; }
    internal static bool Enabled => armed;
    internal static void Arm() { Reset(); armed = true; }
    internal static void Reset() { armed = false; world = local = menu = null; stateKey = null; StableFrames = 0; }
    private static Session? Current => menu?.Live() == true ? menu : local?.Live() == true ? local : world?.Live() == true ? world : null;
    internal static bool MapReady => !LongEventHandler.AnyEventNowOrWaiting && CurrentGameMapReady();
    private static bool CurrentGameMapReady() => Verse.Current.ProgramState == ProgramState.Playing
        && Verse.Current.Game?.CurrentMap is Map map && Find.Maps.Contains(map) && map.mapDrawer != null;
    internal static void Pump()
    {
        if (!armed) return;
        string? key = MapReady ? (Current?.Handle ?? "none") + ":" + Verse.Current.Game.CurrentMap.uniqueID : null;
        StableFrames = key == null ? 0 : key == stateKey ? Math.Min(1000000, StableFrames + 1) : 1;
        stateKey = key;
    }
    internal static InteractionSnapshot Inspect()
    {
        Session? session = Current;
        bool unsupported = session == null && MapReady && Find.Targeter.IsTargeting;
        return new InteractionSnapshot { Handle = session?.Handle, Kind = session?.Kind ?? (unsupported ? "map_target_source" : "none"),
            StableFrames = StableFrames, Ready = session != null && MapReady && StableFrames >= 3,
            MissingCapability = unsupported ? "source_targeter_job_chain" : null };
    }
    private static Session Require(string? handle)
    {
        Session? session = Current;
        if (!armed || session == null || handle != null && handle != session.Handle)
        {
            if (armed && Inspect().MissingCapability is string missing)
                throw new ProbeStepException("unsupported", "Missing interaction capability: " + missing);
            throw new ProbeStepException("blocked", "No current interaction or stale interaction handle.");
        }
        return session;
    }
    internal static InteractionSnapshot Enumerate(InteractionQuery query)
    {
        if (query.Offset < 0 || query.Offset > 100000 || query.Limit < 1 || query.Limit > 8
            || query.X.HasValue != query.Z.HasValue || query.X < 0 || query.X > 9999 || query.Z < 0 || query.Z > 9999)
            throw new ArgumentException("Invalid bounded choice query.");
        Session session = Require(query.Interaction);
        if (!Inspect().Ready) throw new ProbeStepException("blocked", "Interaction is not observably ready; use wait_until interaction_ready.");
        List<InteractionChoice> result = new();
        if (session.Kind == "world_target")
        {
            // Preserve MapParent identity even when several parents share the same PlanetTile.
            foreach (WorldObject obj in Find.WorldObjects.AllWorldObjects.OrderBy(obj => obj.ID)
                .Where(obj => query.MapId == null || obj is MapParent parent && parent.Map?.uniqueID == query.MapId).Skip(query.Offset).Take(query.Limit))
            {
                GlobalTargetInfo target = new(obj);
                Map? map = (obj as MapParent)?.Map;
                result.Add(Add(session, "world:" + obj.ID, new InteractionChoice { ObjectType = obj.GetType().FullName ?? "WorldObject",
                    MapId = map?.uniqueID, TileId = obj.Tile.tileId, LayerId = obj.Tile.Layer.LayerID },
                    () => Find.WorldObjects.AllWorldObjects.Contains(obj) && obj.Tile.Valid && (session.WorldValidator?.Invoke(target) ?? true),
                    () => { if (session.World!(target) && ReferenceEquals(world, session)) Find.WorldTargeter.StopTargeting(); }));
            }
        }
        else if (session.Kind == "map_target_callback")
        {
            Map map = Verse.Current.Game.CurrentMap;
            if (query.MapId != null && query.MapId != map.uniqueID) throw new ProbeStepException("blocked", "Landing picker is on a different map.");
            if (query.X.HasValue)
            {
                IntVec3 cell = new(query.X.Value, 0, query.Z!.Value);
                LocalTargetInfo target = new(cell);
                result.Add(LocalChoice(session, target, map, "cell:" + map.uniqueID + ":" + cell, cell.InBounds(map)));
            }
            else
            {
                foreach (Thing thing in map.listerThings.AllThings.Where(thing => thing.Spawned && (query.ThingId == null || thing.thingIDNumber == query.ThingId))
                    .OrderBy(thing => thing.thingIDNumber).Skip(query.Offset).Take(query.Limit))
                    result.Add(LocalChoice(session, new LocalTargetInfo(thing), map, "thing:" + thing.thingIDNumber, true));
            }
        }
        else if (session.Menu != null)
        {
            foreach (FloatMenuOption option in session.Options!.Where(option => query.ThingId == null || option.revalidateClickTarget?.thingIDNumber == query.ThingId)
                .Skip(query.Offset).Take(query.Limit))
            {
                string key = "option:" + session.Options!.IndexOf(option); // Internal identity only; callers receive opaque handles.
                result.Add(Add(session, key, new InteractionChoice { ObjectType = "FloatMenuOption", ThingId = option.revalidateClickTarget?.thingIDNumber,
                    MapId = option.revalidateClickTarget?.Map?.uniqueID, Label = Limit(option.Label) },
                    () => session.Options.Contains(option) && !option.Disabled && option.action != null
                        && (option.revalidateClickTarget == null || (option.targetsDespawned ? !option.revalidateClickTarget.Spawned : option.revalidateClickTarget.Spawned))
                        && (option.revalidateWorldClickTarget == null || Find.WorldObjects.AllWorldObjects.Contains(option.revalidateWorldClickTarget)),
                    () => { option.Chosen(session.Menu.givesColonistOrders, session.Menu); Find.WindowStack.TryRemove(session.Menu); }));
            }
        }
        InteractionSnapshot evidence = Inspect(); evidence.Choices = result.ToArray(); return evidence;
    }
    private static InteractionChoice LocalChoice(Session session, LocalTargetInfo target, Map map, string key, bool inBounds)
    {
        return Add(session, key, new InteractionChoice { ObjectType = target.HasThing ? target.Thing.GetType().FullName ?? "Thing" : "MapCell",
            MapId = map.uniqueID, ThingId = target.HasThing ? target.Thing.thingIDNumber : null, X = target.Cell.x, Z = target.Cell.z,
            TileId = map.Tile.tileId, LayerId = map.Tile.Layer.LayerID },
            () => inBounds && Verse.Current.Game.CurrentMap == map && (!target.HasThing || target.Thing.Spawned && target.Thing.Map == map)
                && session.Parameters != null && session.Parameters.CanTarget(target.HasThing ? new TargetInfo(target.Thing) : new TargetInfo(target.Cell, map))
                && (session.LocalValidator?.Invoke(target) ?? true),
            () => { session.Local!(target); if (ReferenceEquals(local, session)) Find.Targeter.StopTargeting(); });
    }
    private static InteractionChoice Add(Session session, string key, InteractionChoice evidence, Func<bool> validate, Action select)
    {
        if (!session.Keys.TryGetValue(key, out string? handle))
        {
            if (session.Choices.Count >= 128) throw new ProbeStepException("unsupported", "Interaction choice budget exhausted (128); cancel and narrow the query.");
            session.Keys.Add(key, handle = Guid.NewGuid().ToString("N"));
        }
        evidence.Handle = handle; evidence.Available = validate();
        session.Choices[handle] = (evidence, validate, select);
        return evidence;
    }
    internal static InteractionSnapshot Select(InteractionQuery query)
    {
        Session session = Require(query.Interaction);
        if (!Inspect().Ready) throw new ProbeStepException("blocked", "Interaction no longer ready.");
        if (query.Choice == null || !session.Choices.TryGetValue(query.Choice, out var choice))
            throw new ProbeStepException("blocked", "Unknown or stale choice handle.");
        if (!choice.Validate()) throw new ProbeStepException("blocked", "Choice is no longer available; no action invoked.");
        choice.Select();
        // One selection consumes all handles, even if the callback keeps its picker open.
        session.Choices.Clear(); session.Keys.Clear(); stateKey = null; StableFrames = 0;
        InteractionSnapshot result = Inspect(); result.Status = "requested"; return result;
    }
    internal static InteractionSnapshot Cancel(string? handle)
    {
        Session session = Require(handle); session.Cancel();
        session.Choices.Clear(); session.Keys.Clear(); stateKey = null; StableFrames = 0;
        InteractionSnapshot result = Inspect(); result.Status = "cancelled"; return result;
    }
    internal static void Cleanup()
    {
        try { for (int i = 0; i < 3 && Current != null; i++) Current!.Cancel(); }
        finally { Reset(); }
    }
    internal static void Install(Harmony harmony)
    {
        harmony.Patch(AccessTools.Method(typeof(WorldTargeter), nameof(WorldTargeter.BeginTargeting)), postfix: new HarmonyMethod(typeof(InteractionHub), nameof(WorldBegan)));
        harmony.Patch(AccessTools.Method(typeof(WorldTargeter), nameof(WorldTargeter.StopTargeting)), postfix: new HarmonyMethod(typeof(InteractionHub), nameof(WorldStopped)));
        foreach (var method in typeof(Targeter).GetMethods().Where(method => method.Name == nameof(Targeter.BeginTargeting)))
            harmony.Patch(method, postfix: new HarmonyMethod(typeof(InteractionHub), nameof(LocalBegan)));
        harmony.Patch(AccessTools.Method(typeof(Targeter), nameof(Targeter.StopTargeting)), postfix: new HarmonyMethod(typeof(InteractionHub), nameof(LocalStopped)));
        harmony.Patch(AccessTools.Method(typeof(WindowStack), nameof(WindowStack.Add)), postfix: new HarmonyMethod(typeof(InteractionHub), nameof(MenuOpened)));
    }
    private static void WorldBegan(WorldTargeter __instance, Func<GlobalTargetInfo, bool> ___action, Func<GlobalTargetInfo, bool>? ___canSelectTarget)
    {
        if (!armed) return;
        world = new Session { Kind = "world_target", World = ___action, WorldValidator = ___canSelectTarget,
            Live = () => __instance.IsTargeting, Cancel = __instance.StopTargeting };
        stateKey = null; StableFrames = 0;
    }
    private static void WorldStopped() { if (world == null) return; world = null; stateKey = null; StableFrames = 0; }
    private static void LocalBegan(Targeter __instance, Action<LocalTargetInfo>? ___action, TargetingParameters? ___targetParams,
        Func<LocalTargetInfo, bool>? ___targetValidator, bool ___requiresCastedSelected, Pawn? ___caster)
    {
        if (!armed) return;
        // Source/verb Targeter chains require their complete job/selection semantics; never invoke a partial effect path.
        if (__instance.targetingSource != null || ___action == null) { local = null; return; }
        Pawn? caster = ___caster;
        local = new Session { Kind = "map_target_callback", Local = ___action, Parameters = ___targetParams,
            LocalValidator = target => (!___requiresCastedSelected || caster == null || Find.Selector.IsSelected(caster)) && (___targetValidator?.Invoke(target) ?? true),
            Live = () => __instance.IsTargeting, Cancel = __instance.StopTargeting };
        stateKey = null; StableFrames = 0;
    }
    private static void LocalStopped() { if (local == null) return; local = null; stateKey = null; StableFrames = 0; }
    private static void MenuOpened(Window window)
    {
        if (!armed || window is not FloatMenu floatMenu) return;
        List<FloatMenuOption> options = Traverse.Create(floatMenu).Field("options").GetValue<List<FloatMenuOption>>();
        menu = new Session { Kind = "float_menu", Menu = floatMenu, Options = options,
            Live = () => Find.WindowStack.Windows.Contains(floatMenu), Cancel = floatMenu.Cancel };
        stateKey = null; StableFrames = 0;
    }
    private static string Limit(string text) => text.Length <= 120 ? text : text.Substring(0, 120);
}
