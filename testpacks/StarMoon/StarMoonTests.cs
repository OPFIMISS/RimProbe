using System.Reflection;
using KiiroStarMoon;
using RimProbe.Agent;
using RimWorld;
using UnityEngine;
using Verse;
using Verse.AI;

namespace RimProbe.StarMoon.Tests;

[StaticConstructorOnStartup]
public static class Registration
{
    static Registration()
    {
        RegisteredProbeTests.Register("kiiro.mechanics", () => new StarMoonTest("mechanics"));
        RegisteredProbeTests.Register("kiiro.envelopes", () => new StarMoonTest("envelopes"));
        RegisteredProbeTests.Register("kiiro.return_moon", () => new StarMoonTest("return_moon"));
        RegisteredProbeTests.Register("kiiro.stay_star", () => new StarMoonTest("stay_star"));
        RegisteredProbeTests.Register("kiiro.negative_control", () => new StarMoonTest("negative_control"));
    }
}

public sealed class StarMoonTest : IProbeTest
{
    private readonly string mode;
    private Map map;
    private Pawn caster;
    private Pawn friend;
    private Pawn enemy;
    private Plant plant;
    private Thing envelope;
    private int phase;
    private int phaseTick;
    private float phaseTime;
    private float beforePower;
    private string abilityName;
    private string pendingCast;
    private Window_StarMoonStayStarImageCredits transition;
    private readonly List<Thing> owned = new();
    private readonly List<string> imagePhases = new();
    private int lettersBefore;
    private int mapsBefore;
    private int envelopeIndex;
    private int originalStartAbsTick;
    public ProbeTestReport Report { get; } = new();

    public StarMoonTest(string mode) => this.mode = mode;

    public void Start(Map initialMap)
    {
        map = initialMap;
        originalStartAbsTick = Find.TickManager.gameStartAbsTick;
        Report.Scope = "Owner StarMoon source-derived tests. Debug fixture: new Pawns, backstory/level/power, time of day, injuries, sleep records. "
            + "Normal ability jobs and envelope read jobs; fixed compiled UI callbacks for ending choices/teleport selection. "
            + "No simulated mouse, no arbitrary remote reflection. Not a visual/aesthetic, balance, long-term or save/load acceptance.";
        mapsBefore = Find.Maps.Count;
        caster = Spawn("Kiiro_StarMoonUser", Faction.OfPlayer, map.Center);
        SetLevel(3);
        StarMoonUtility.GetPowerHediff(caster).Debug_AddPower(10000f);
        if (mode == "mechanics")
        {
            friend = Spawn("Colonist", Faction.OfPlayer, caster.Position + new IntVec3(2, 0, 0));
            Faction hostile = Find.FactionManager.AllFactionsListForReading.FirstOrDefault(candidate => candidate.HostileTo(Faction.OfPlayer));
            if (hostile == null) throw new InvalidOperationException("No hostile faction available.");
            enemy = Spawn("Colonist", hostile, caster.Position + new IntVec3(3, 0, 0));
            enemy.jobs.StartJob(JobMaker.MakeJob(JobDefOf.Wait, 60000), JobCondition.InterruptForced);
            if (friend.Position.DistanceTo(caster.Position) > 5.5f || enemy.Position.DistanceTo(caster.Position) > 5.5f)
                throw new InvalidOperationException("Fixture Pawns are outside the actual daytime effect radius.");
            CheckAwakening();
            SetLevel(3);
            SetHour(12);
            Cast("KiiroFlowingDream");
        }
        else if (mode == "negative_control")
        {
            Check("deliberately_absent_marker", Has(caster, "KiiroMoonlightGlow"), 0, "1; intentional negative control must fail");
            Finish();
        }
        else
        {
            SetHour(0);
            lettersBefore = Find.LetterStack.LettersListForReading.Count;
            ReadEnvelope();
        }
    }

    private Pawn Spawn(string kind, Faction faction, IntVec3 anchor)
    {
        Pawn pawn = PawnGenerator.GeneratePawn(new PawnGenerationRequest(DefDatabase<PawnKindDef>.GetNamed(kind), faction,
            forceGenerateNewPawn: true, fixedGender: Gender.Female));
        owned.Add(pawn);
        GenSpawn.Spawn(pawn, FreeCell(anchor), map);
        pawn.abilities ??= new Pawn_AbilityTracker(pawn);
        if (pawn.drafter != null) pawn.drafter.Drafted = true;
        return pawn;
    }

    private IntVec3 FreeCell(IntVec3 anchor) => GenRadial.RadialCellsAround(anchor, 35, true)
        .First(cell => cell.InBounds(map) && cell.Standable(map) && !cell.Fogged(map) && cell.GetEdifice(map) == null && cell.GetFirstPawn(map) == null);

    private void SetLevel(int level)
    {
        caster.story.Adulthood = null;
        if (caster.abilities != null)
            foreach (Ability ability in caster.abilities.AllAbilitiesForReading.Where(StarMoonUtility.IsStarMoonAbility).ToArray())
                caster.abilities.RemoveAbility(ability.def);
        foreach (string name in new[] { "KiiroStarMoonLevel_I", "KiiroStarMoonLevel_II", "KiiroStarMoonLevel_III" })
        {
            Hediff existing = caster.health.hediffSet.GetFirstHediffOfDef(DefDatabase<HediffDef>.GetNamed(name));
            if (existing != null) caster.health.RemoveHediff(existing);
        }
        caster.health.AddHediff(DefDatabase<HediffDef>.GetNamed("KiiroStarMoonLevel_" + new[] { "", "I", "II", "III" }[level]));
        caster.story.Adulthood = StarMoonDefOf.KiiroStarMoonUser;
        StarMoonHediffProtection.EnsureStarMoonHediffs(caster);
        ((Hediff_StarMoonLevel)caster.health.hediffSet.GetFirstHediffOfDef(StarMoonDefOf.KiiroStarMoonLevel_Tracker)).Debug_SetLevel(level);
        StarMoonUtility.EnsureAbilitiesForLevel(caster, level);
    }

    private void CheckAwakening()
    {
        Pawn candidate = Spawn("Kiiro_StarMoonUser", Faction.OfPlayer, caster.Position + new IntVec3(5, 0, 0));
        candidate.story.Childhood = AwakeningDefOf.KiiroDreamlike;
        candidate.story.Adulthood = null;
        Hediff blessing = candidate.health.hediffSet.GetFirstHediffOfDef(AwakeningDefOf.KiiroStarMoonBlessing);
        if (blessing != null) candidate.health.RemoveHediff(blessing);
        Check("awakening_initially_ineligible_state_absent", !StarMoonUtility.IsStarMoonUser(candidate), 0, "not awakened before scheduled processing");
        int originalTick = Find.TickManager.TicksGame;
        AwakeningTracker tracker = AwakeningTracker.GetTracker();
        try
        {
            Find.TickManager.DebugSetTicksGame(originalTick + 60000);
            tracker.GameComponentTick();
            var records = (DefMap<RecordDef, float>)typeof(Pawn_RecordsTracker)
                .GetField("records", BindingFlags.NonPublic | BindingFlags.Instance).GetValue(candidate.records);
            records[AwakeningDefOf.TimeInBed] += 30f * 60000f;
            Find.TickManager.DebugSetTicksGame(originalTick + 120000);
            tracker.GameComponentTick();
        }
        finally { Find.TickManager.DebugSetTicksGame(originalTick); }
        Check("scheduled_awakening_backstory", candidate.story.Adulthood == AwakeningDefOf.KiiroStarMoonUser, 1, "scheduled daily trigger after fixture sleep records");
        Check("scheduled_awakening_blessing", candidate.health.hediffSet.HasHediff(AwakeningDefOf.KiiroStarMoonBlessing), 1, "blessing applied by awakening");
        for (int level = 1; level <= 3; level++)
        {
            SetLevel(level);
            int count = caster.abilities.AllAbilitiesForReading.Count(StarMoonUtility.IsStarMoonAbility);
            Check("level_" + level + "_ability_unlock", count == level, count, "exactly " + level + " abilities after debug level preparation; not natural growth");
            float expected = new[] { 0f, 100f, 260f, 500f }[level];
            Check("level_" + level + "_power_cap", Math.Abs(StarMoonUtility.GetPowerHediff(caster).MaxPower - expected) < 0.01f,
                StarMoonUtility.GetPowerHediff(caster).MaxPower, expected.ToString());
        }
        Hediff_StarMoonPower power = StarMoonUtility.GetPowerHediff(caster);
        power.ClearPower();
        Check("empty_power_rejects_spend", !power.TryConsumePower(10f) && power.CurrentPower == 0f, power.CurrentPower, "zero; insufficient resource must be rejected");
        caster.health.RemoveHediff(power);
        int resourceCount = caster.health.hediffSet.hediffs.Count(hediff => hediff.def == StarMoonDefOf.KiiroStarMoonPower);
        Check("core_resource_restored_once", resourceCount == 1, resourceCount, "one resource Hediff after normal RemoveHediff protection");
    }

    private void SetHour(int hour)
    {
        int current = GenLocalDate.HourOfDay(map);
        Find.TickManager.gameStartAbsTick += (hour - current) * 2500;
        if (Find.TickManager.gameStartAbsTick <= 0) Find.TickManager.gameStartAbsTick += 60000;
    }

    private void Cast(string name)
    {
        if (caster.CurJob?.ability != null)
        {
            pendingCast = name;
            phaseTime = Time.realtimeSinceStartup;
            return;
        }
        pendingCast = null;
        abilityName = name;
        StarMoonUtility.GetPowerHediff(caster).Debug_AddPower(10000f);
        beforePower = StarMoonUtility.GetPowerHediff(caster).CurrentPower;
        Ability ability = caster.abilities.GetAbility(DefDatabase<AbilityDef>.GetNamed(name));
        ability.ResetCooldown();
        LocalTargetInfo target = new(caster.Position);
        bool canCast = ability.CanCast.Accepted;
        bool canQueue = ability.CanQueueCast;
        bool canApply = ability.CanApplyOn(target);
        bool valid = ability.verb.ValidateTarget(target, false);
        bool eligible = canCast && canQueue && canApply && valid;
        Check(name + "_eligible", eligible, eligible ? 1 : 0,
            $"normal eligibility: cast={canCast}, queue={canQueue}, apply={canApply}, target={valid}; job={caster.CurJobDef?.defName}; identity={StarMoonUtility.IsStarMoonUser(caster)}");
        if (!eligible) { Finish(); return; }
        ability.QueueCastingJob(target, target);
        Advance(phase + 1);
    }

    private void Advance(int next)
    {
        phase = next;
        phaseTick = Find.TickManager.TicksGame;
        phaseTime = Time.realtimeSinceStartup;
        Report.Phase = mode + ":" + phase;
    }

    private static bool Has(Pawn pawn, string name) => pawn.health.hediffSet.HasHediff(DefDatabase<HediffDef>.GetNamed(name));
    private void Check(string name, bool passed, double actual, string expected)
        => Report.Checks.Add(new ProbeTestCheck { Name = name, Passed = passed, Actual = actual, Expected = expected });

    public void Pump()
    {
        if (Report.Status != "running") return;
        if (Time.realtimeSinceStartup - phaseTime > 65f) { Check("phase_timeout_" + phase, false, 65, "complete within 65 real seconds"); Finish(); return; }
        if (pendingCast != null)
        {
            if (caster.CurJob?.ability == null) Cast(pendingCast);
            return;
        }
        if (mode == "mechanics") PumpMechanics();
        else if (mode != "negative_control") PumpEnding();
    }

    private void PumpMechanics()
    {
        if (phase == 1 || phase == 2 || phase == 3 || phase == 4 || phase == 5)
        {
            float spent = beforePower - StarMoonUtility.GetPowerHediff(caster).CurrentPower;
            if (spent <= 0f && Find.TickManager.TicksGame - phaseTick < 600) return;
            Check(abilityName + "_power_spent_" + phase, spent > 0f, spent, ">0 after actual cast job");
            if (phase == 1)
            {
                Check("flowing_day_hostile_downed", Has(enemy, "KiiroFlowingDream_Downed") && enemy.Downed, enemy.Downed ? 1 : 0, "downed after daytime cast");
                Check("flowing_day_friend_memory", friend.needs.mood.thoughts.memories.Memories.Any(memory => memory.def.defName == "KiiroFlowingDream_Comfortable"), 1, "positive memory added");
                Remove(enemy, "KiiroFlowingDream_Downed");
                InjureFriend();
                SetHour(0);
                Cast("KiiroFlowingDream");
            }
            else if (phase == 2)
            {
                Check("flowing_night_enemy_sleep", Has(enemy, "KiiroFlowingDream_Sleep"), 1, "sleep Hediff after night cast");
                Check("flowing_night_heals_friend", !friend.health.hediffSet.hediffs.OfType<Hediff_Injury>().Any(), 0, "no remaining fixture injuries");
                Remove(enemy, "KiiroFlowingDream_Sleep");
                InjureFriend();
                plant = (Plant)ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Plant_Rice"));
                owned.Add(plant);
                GenSpawn.Spawn(plant, FreeCell(caster.Position + new IntVec3(1, 0, 1)), map);
                plant.Growth = 0.2f;
                SetHour(12);
                Cast("KiiroThousandTurns");
            }
            else if (phase == 3)
            {
                Check("thousand_day_plant_mature", plant.Growth >= 1f, plant.Growth, "1 after cast");
                Check("thousand_day_friend_healed", !friend.health.hediffSet.hediffs.OfType<Hediff_Injury>().Any(), 0, "fixture injury removed");
                plant.Growth = 0.2f;
                SetHour(0);
                Cast("KiiroThousandTurns");
            }
            else if (phase == 4)
            {
                Check("thousand_night_plant_mature", plant.Growth >= 1f, plant.Growth, "1 after night cast");
                Check("thousand_night_enemy_moonlight", Has(enemy, "KiiroMoonlightGlow"), 1, "moonlight Hediff after cast");
                Cast("KiiroStarMoon_TimeStop");
            }
            else
            {
                Check("time_stop_caster", Has(caster, "KiiroTimeStop_Caster"), 1, "caster Hediff after cast");
                Check("time_stop_friend_frozen", Has(friend, "KiiroTimeStop_Frozen"), 1, "non-StarMoon pawn frozen");
                Check("time_stop_condition", map.gameConditionManager.ActiveConditions.Any(condition => condition.def.defName == "KiiroTimeStop_Filter"), 1, "real map condition");
                for (int teleport = 1; teleport <= 3; teleport++)
                {
                    Invoke(typeof(TimeStopTeleportManager), "OnTargetSelected", null, new LocalTargetInfo(friend));
                    IntVec3 destination = FreeCell(caster.Position + new IntVec3(4 + teleport, 0, 4));
                    Invoke(typeof(TimeStopTeleportManager), "OnDestinationSelected", null, new LocalTargetInfo(destination));
                    Check("time_stop_callback_teleport_" + teleport, friend.Position == destination,
                        friend.Position.DistanceTo(destination), "0; fixed selection callbacks, no OS input");
                }
                Find.Targeter.StopTargeting();
                Advance(6);
            }
        }
        else if (phase == 6 && Find.TickManager.TicksGame - phaseTick >= 900)
        {
            Check("time_stop_expires", !Has(friend, "KiiroTimeStop_Frozen") && !Has(caster, "KiiroTimeStop_Caster"), 0, "timed Hediffs removed by normal ticking");
            Check("time_stop_global_resumed", !TimeStopManager.IsPaused, TimeStopManager.IsPaused ? 1 : 0, "0; global time stop ended");
            SetLevel(1);
            StarMoonUtility.GetPowerHediff(caster).ClearPower();
            Hediff_StarMoonLevel tracker = (Hediff_StarMoonLevel)caster.health.hediffSet.GetFirstHediffOfDef(StarMoonDefOf.KiiroStarMoonLevel_Tracker);
            typeof(Hediff_StarMoonLevel).GetField("upgradeProgress", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(tracker, 179f);
            caster.drafter.Drafted = false;
            caster.needs.rest.CurLevelPercentage = 0.15f;
            Job sleep = JobMaker.MakeJob(JobDefOf.LayDown, caster.Position);
            sleep.forceSleep = true;
            caster.jobs.TryTakeOrderedJob(sleep, JobTag.Misc);
            Find.TickManager.CurTimeSpeed = TimeSpeed.Superfast;
            Advance(7);
        }
        else if (phase == 7 && Find.TickManager.TicksGame - phaseTick >= 2800)
        {
            float power = StarMoonUtility.GetPowerHediff(caster).CurrentPower;
            Check("normal_sleep_accumulates_power", power > 0f, power, ">0 after real LayDown ticks; no power injected after zero baseline");
            Check("normal_sleep_crosses_prepared_level_boundary", StarMoonUtility.GetLevel(caster) == 2,
                StarMoonUtility.GetLevel(caster), "II after ticking from fixture progress 179/180; not full natural lifetime");
            Check("normal_sleep_unlocks_second_ability", caster.abilities.GetAbility(StarMoonDefOf.KiiroStarMoon_TimeStop) != null, 1,
                "time-stop ability granted by real level transition");
            caster.drafter.Drafted = true;
            Cast("KiiroStarMoon_TimeStop");
        }
        else if (phase == 8)
        {
            float spent = beforePower - StarMoonUtility.GetPowerHediff(caster).CurrentPower;
            if (spent <= 0f && Find.TickManager.TicksGame - phaseTick < 600) return;
            Check("second_time_stop_active", spent > 0f && TimeStopManager.IsPaused
                && Has(caster, "KiiroTimeStop_Caster"), spent, "normal second cast activates time stop");
            Cast("KiiroCancelTimeStop");
        }
        else if (phase == 9)
        {
            if (Find.TickManager.TicksGame - phaseTick < 120) return;
            Check("cancel_time_stop_normal_job", !TimeStopManager.IsPaused && !Has(caster, "KiiroTimeStop_Caster")
                && !Has(friend, "KiiroTimeStop_Frozen"), TimeStopManager.IsPaused ? 1 : 0,
                "normal cancel ability removes caster/frozen states and resumes global ticking");
            Check("cancel_ability_removed", caster.abilities.GetAbility(DefDatabase<AbilityDef>.GetNamed("KiiroCancelTimeStop")) == null,
                caster.abilities.AllAbilitiesForReading.Count(ability => ability.def.defName == "KiiroCancelTimeStop"),
                "zero temporary cancel abilities after cancellation");
            Check("cancel_filter_removed", !map.gameConditionManager.ActiveConditions.Any(
                condition => condition.def.defName == "KiiroTimeStop_Filter"), 0, "no time-stop map condition after cancellation");
            Finish();
        }
    }

    private void InjureFriend()
    {
        Hediff injury = HediffMaker.MakeHediff(HediffDefOf.Cut, friend, friend.RaceProps.body.corePart);
        injury.Severity = 2f;
        friend.health.AddHediff(injury);
        Check("fixture_injury_" + phase, friend.health.hediffSet.hediffs.OfType<Hediff_Injury>().Any(), 1, "injury exists BEFORE cast");
    }

    private static void Remove(Pawn pawn, string name)
    {
        Hediff existing = pawn.health.hediffSet.GetFirstHediffOfDef(DefDatabase<HediffDef>.GetNamed(name));
        if (existing != null) pawn.health.RemoveHediff(existing);
    }

    private void PumpEnding()
    {
        if (phase == 20)
        {
            Dialog_StarMoonEndingNarrative narrative = Find.WindowStack.Windows.OfType<Dialog_StarMoonEndingNarrative>().FirstOrDefault();
            if (narrative == null) return;
            Check("normal_read_job_opens_narrative_" + envelopeIndex, true, 1, "narrative created by actual read job");
            Check("narrative_in_bounds_" + envelopeIndex, narrative.windowRect.xMin >= 0 && narrative.windowRect.yMin >= 0
                && narrative.windowRect.xMax <= UI.screenWidth && narrative.windowRect.yMax <= UI.screenHeight,
                narrative.windowRect.height, "entire narrative window fits actual logical screen");
            narrative.Close(false);
            if (mode == "envelopes")
            {
                Check("envelope_variant_" + envelopeIndex, envelope.TryGetComp<CompStarMoonEndingEnvelope>().Variant == new[] { "A", "B", "C" }[envelopeIndex],
                    envelopeIndex, "actual component variant matches the read Def");
                envelope.DeSpawn();
                envelopeIndex++;
                if (envelopeIndex < 3) ReadEnvelope();
                else Finish();
                return;
            }
            Dialog_StarMoonEndingChoice choice = new(caster, envelope);
            Find.WindowStack.Add(choice);
            StarMoonEndingChoice ending = mode == "return_moon" ? StarMoonEndingChoice.ReturnMoon : StarMoonEndingChoice.StayStar;
            object[] allowedArgs = { ending, TaggedString.Empty };
            bool allowed = (bool)Invoke(typeof(Dialog_StarMoonEndingChoice), "CanChoose", choice, allowedArgs);
            Check("ending_choice_gate", allowed, allowed ? 1 : 0, "level III and resource/time eligibility");
            if (!allowed) { Finish(); return; }
            Invoke(typeof(Dialog_StarMoonEndingChoice), "ChooseEnding", choice, ending);
            Advance(21);
        }
        else if (phase == 21 && mode == "return_moon")
        {
            if (caster.Map == map) return;
            MapComponent_StarMoonReturnMoonScene scene = caster.Map.GetComponent<MapComponent_StarMoonReturnMoonScene>();
            Check("return_moon_pocket_map", scene != null && scene.endingSceneActive, Find.Maps.Count - mapsBefore, "new active ending PocketMap");
            Check("return_moon_scene_residents", scene.sceneResidents.Count > 0, scene.sceneResidents.Count, ">0 generated residents");
            Check("return_moon_committed", GameComponent_StarMoonEvents.CurrentEndingChoice == StarMoonEndingChoice.ReturnMoon, 1, "committed after successful transfer");
            Check("return_moon_power_cleared", StarMoonUtility.GetPowerHediff(caster).CurrentPower == 0f, StarMoonUtility.GetPowerHediff(caster).CurrentPower, "0");
            IntVec3 exit = scene.exitCells.First(cell => cell.Standable(caster.Map));
            caster.jobs.TryTakeOrderedJob(JobMaker.MakeJob(JobDefOf.Goto, exit), JobTag.Misc);
            Find.TickManager.CurTimeSpeed = TimeSpeed.Superfast;
            Advance(22);
        }
        else if (phase == 21 && mode == "stay_star")
        {
            transition ??= Find.WindowStack.Windows.OfType<Window_StarMoonStayStarImageCredits>().FirstOrDefault();
            if (transition != null && (imagePhases.Count == 0 || imagePhases.Last() != transition.Phase))
                imagePhases.Add(transition.Phase);
            if (!Find.WindowStack.Windows.OfType<Screen_Credits>().Any()) return;
            Check("stay_star_image_loaded", transition != null && transition.ImageLoaded, transition?.ImageLoaded == true ? 1 : 0, "texture resolved");
            Check("stay_star_phase_order", imagePhases.SequenceEqual(new[] { "white", "fade_in", "hold", "fade_out", "credits" }),
                imagePhases.Count, "white -> fade_in -> hold -> fade_out -> credits");
            Check("stay_star_image_repaint", transition != null && transition.ImageRepaints > 2, transition?.ImageRepaints ?? 0, "actual image Repaint >2; not aesthetic proof");
            Check("stay_star_committed", GameComponent_StarMoonEvents.HasStayStarEnding, 1, "stay-star outcome committed");
            Check("stay_star_epilogue", Find.LetterStack.LettersListForReading.Count > lettersBefore, Find.LetterStack.LettersListForReading.Count - lettersBefore, "epilogue letter added");
            Finish();
        }
        else if (phase == 22 && Find.WindowStack.Windows.OfType<Screen_Credits>().Any())
        {
            Check("return_moon_original_map", caster.Map == map, caster.Map.uniqueID, "Pawn returned to original map");
            Check("return_moon_scene_cleaned", Find.Maps.Count == mapsBefore, Find.Maps.Count - mapsBefore, "0 temporary maps remaining");
            Check("return_moon_epilogues", Find.LetterStack.LettersListForReading.Count - lettersBefore >= 3,
                Find.LetterStack.LettersListForReading.Count - lettersBefore, "at least 3 epilogue/village letters");
            Finish();
        }
    }

    private static object Invoke(Type type, string name, object instance, params object[] arguments)
        => type.GetMethod(name, BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static).Invoke(instance, arguments);

    private void ReadEnvelope()
    {
        envelope = ThingMaker.MakeThing(DefDatabase<ThingDef>.GetNamed("Kiiro_EndingEnvelope_" + new[] { "A", "B", "C" }[envelopeIndex]));
        owned.Add(envelope);
        GenSpawn.Spawn(envelope, FreeCell(caster.Position + new IntVec3(1, 0, 0)), map);
        bool enabled = envelope.TryGetComp<CompStarMoonEndingEnvelope>().CompFloatMenuOptions(caster).Any(option => !option.Disabled);
        Check("envelope_read_option_" + envelopeIndex, enabled, enabled ? 1 : 0, "enabled normal read option");
        if (!enabled) { Finish(); return; }
        caster.drafter.Drafted = false;
        caster.jobs.TryTakeOrderedJob(JobMaker.MakeJob(StarMoonDefOf.Kiiro_ReadEndingEnvelope, envelope), JobTag.Misc);
        Advance(20);
    }

    private void Finish()
    {
        Report.Status = Report.Checks.Count > 0 && Report.Checks.All(check => check.Passed) ? "passed" : "failed";
        Report.Phase = "completed";
    }

    public void Dispose()
    {
        Find.TickManager.gameStartAbsTick = originalStartAbsTick;
        Find.Targeter.StopTargeting();
        if (caster?.Spawned == true && caster.Map != map
            && caster.Map.GetComponent<MapComponent_StarMoonReturnMoonScene>()?.sourceMap == map)
            StarMoonReturnMoonSceneUtility.ToggleTestScene(caster);
        foreach (Window window in Find.WindowStack.Windows.ToArray())
            if (window is Dialog_StarMoonEndingNarrative || window is Dialog_StarMoonEndingChoice
                || window is Window_StarMoonStayStarImageCredits || window is Screen_Credits)
                window.Close(false);
        ScreenFader.SetColor(Color.clear);
        foreach (Thing thing in owned.AsEnumerable().Reverse())
        {
            if (thing is Pawn pawn) pawn.jobs?.StopAll();
            if (thing.Spawned) thing.DeSpawn();
        }
    }
}
