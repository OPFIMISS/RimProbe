using RimWorld;
using RimWorld.Planet;
using Verse;

namespace RimProbe.InteractionFixtures;

// Optional, separately installed regression fixture. No target-specific code belongs in the Agent.
public sealed class LandingProperties : CompProperties_AbilityEffect
{
    public HediffDef marker = null!;
    public bool offerMenu;
    public LandingProperties() { compClass = typeof(LandingEffect); }
}

public sealed class LandingEffect : CompAbilityEffect
{
    public override bool Valid(GlobalTargetInfo target, bool throwMessages = false) => target.WorldObject is MapParent parent && parent.Map != null;
    public override bool CanApplyOn(GlobalTargetInfo target) => Valid(target);
    public override void Apply(GlobalTargetInfo target)
    {
        Map? map = (target.WorldObject as MapParent)?.Map;
        if (map == null) return;
        Current.Game.CurrentMap = map;
        CameraJumper.TryHideWorld();
        if (((LandingProperties)props).offerMenu)
        {
            Find.WindowStack.Add(new FloatMenu(new List<FloatMenuOption> {
                new("choose landing", () => BeginLanding(map), revalidateClickTarget: parent.pawn),
                new("unavailable fixture choice", null)
            }) { vanishIfMouseDistant = false });
        }
        else BeginLanding(map);
    }
    private void BeginLanding(Map map)
    {
        Find.Targeter.BeginTargeting(new TargetingParameters { canTargetLocations = true, canTargetPawns = false, canTargetBuildings = false },
            local =>
            {
                // This fixture's actual effect, reached only through the normal Ability Job + landing callback.
                parent.pawn.Position = local.Cell;
                parent.pawn.Notify_Teleported();
                parent.pawn.health.AddHediff(((LandingProperties)props).marker);
            }, highlightAction: null, targetValidator: local => local.Cell.InBounds(map) && local.Cell.Standable(map) && !local.Cell.Fogged(map));
    }
}
