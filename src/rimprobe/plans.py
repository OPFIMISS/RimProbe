import copy
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from .errors import ProbeError


Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_]{1,128}$")]
Handle = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")]


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: Handle


class SpawnPawn(Step):
    op: Literal["spawn_pawn"]
    bind: Handle
    def_name: Identifier = "Colonist"
    near: Handle | None = None
    distance: int = Field(default=3, ge=1, le=15)
    faction: Literal["player", "hostile"] = "player"
    food_fraction: float = Field(default=0.25, ge=0.05, le=0.8, allow_inf_nan=False)


class SpawnItem(Step):
    op: Literal["spawn_item"]
    bind: Handle
    def_name: Identifier
    near: Handle | None = None
    stuff_name: Identifier | None = None
    count: int = Field(default=1, ge=1, le=75)


class FixtureHediff(Step):
    op: Literal["fixture_hediff"]
    actor: Handle
    def_name: Identifier


class GrantAbility(Step):
    op: Literal["grant_ability"]
    actor: Handle
    def_name: Identifier


class Cast(Step):
    op: Literal["cast"]
    actor: Handle
    target: Handle
    def_name: Identifier


class ItemAction(Step):
    op: Literal["ingest", "equip"]
    actor: Handle
    target: Handle


class BeginAbility(Step):
    op: Literal["begin_ability"]
    actor: Handle
    def_name: Identifier


class InteractionStep(Step):
    op: Literal["inspect_interaction", "enumerate_choices", "cancel_interaction"]
    target: Handle | None = None
    bind_choice: Handle | None = None
    cell_at_target: bool = False
    x: int | None = Field(default=None, ge=0, le=9999)
    z: int | None = Field(default=None, ge=0, le=9999)
    offset: int = Field(default=0, ge=0, le=100000)
    limit: int = Field(default=8, ge=1, le=8)


class SelectChoice(Step):
    op: Literal["select_choice"]
    choice: Handle


class WaitUntil(Step):
    op: Literal["wait_until"]
    condition: Literal["interaction_ready", "interaction_closed", "map_ready", "ability_job_finished"]
    actor: Handle | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    stable_frames: int = Field(default=3, ge=2, le=120)
    cancel_if: Literal["actor_unavailable"] | None = None


class InteractionQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    interaction: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")] | None = None
    choice: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")] | None = None
    map_id: int | None = Field(default=None, ge=0, le=2147483647)
    thing_id: int | None = Field(default=None, ge=0, le=2147483647)
    x: int | None = Field(default=None, ge=0, le=9999)
    z: int | None = Field(default=None, ge=0, le=9999)
    offset: int = Field(default=0, ge=0, le=100000)
    limit: int = Field(default=8, ge=1, le=8)


class Move(Step):
    op: Literal["move"]
    actor: Handle
    target: Handle


class Build(Step):
    op: Literal["build"]
    bind: Handle
    def_name: Identifier
    stuff_name: Identifier | None = None


class Inspect(Step):
    op: Literal["inspect"]
    target: Handle


class FindThing(Step):
    op: Literal["find_thing"]
    bind: Handle
    def_name: Identifier
    near: Handle | None = None
    radius: int = Field(default=30, ge=1, le=100)
    index: int = Field(default=0, ge=0, le=127)


class QueryDefs(Step):
    op: Literal["query_defs"]
    def_type: Literal["ThingDef", "AbilityDef", "HediffDef", "PawnKindDef", "RecipeDef"]
    query: str = Field(default="", max_length=80)
    offset: int = Field(default=0, ge=0, le=100000)
    limit: int = Field(default=8, ge=1, le=8)


class RegisteredTest(Step):
    op: Literal["registered_test"]
    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{0,79}$")]


class QueryTests(Step):
    op: Literal["query_tests"]


class Wait(Step):
    op: Literal["wait"]
    ticks: int = Field(ge=1, le=60000)


NumericProperty = Literal["hp", "spawned", "destroyed", "stack_count", "map.id", "map.tile_id", "map.layer_id", "position.x", "position.z", "pawn.job_active", "pawn.dead", "pawn.downed", "pawn.stunned", "pawn.food", "pawn.injury", "pawn.hediff_count", "pawn.ability_cooldown", "pawn.ability_casting", "pawn.equipped", "pawn.distance_to", "power.watts", "power.connected"]


class Assertion(Step):
    target: Handle
    property: NumericProperty
    def_name: Identifier | None = None
    other: Handle | None = None
    relative_to: Handle | None = Field(default=None, description="Compare actual minus a previous measure value; static value is the expected delta.")
    compare: Literal["eq", "ne", "gt", "ge", "lt", "le"]
    value: float = Field(allow_inf_nan=False, ge=-1000000000, le=1000000000)


class Measure(Step):
    op: Literal["measure"]
    bind_value: Handle
    target: Handle
    property: NumericProperty
    def_name: Identifier | None = None
    other: Handle | None = None


class ImmediateAssertion(Assertion):
    op: Literal["assert"]


class WaitAssertion(Assertion):
    op: Literal["wait_assert"]
    ticks: int = Field(default=180, ge=1, le=60000)
    hold_ticks: int = Field(default=0, ge=0, le=6000)


PlanStepInput = Annotated[SpawnPawn | SpawnItem | FixtureHediff | GrantAbility | Cast | ItemAction | BeginAbility | InteractionStep | SelectChoice | WaitUntil | Move | Build | Inspect | FindThing | QueryDefs | QueryTests | RegisteredTest | Measure | Wait | ImmediateAssertion | WaitAssertion, Field(discriminator="op")]


class ScenarioPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1] = Field(alias="schema")
    recipe: Literal["scenario"] = "scenario"
    intent: str = Field(min_length=1, max_length=2000)
    source_refs: list[str] = Field(default_factory=list, max_length=16)
    steps: list[PlanStepInput] = Field(min_length=1, max_length=24)
    max_ticks: int = Field(default=12000, ge=60, le=120000)
    timeout_seconds: int = Field(default=180, ge=5, le=600)
    display_profile: Literal["simulation", "ui"] = "simulation"


    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_schema(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("schema must be integer 1, not a boolean or string")
        return value


_named_properties = {"pawn.hediff_count": "HediffDef", "pawn.ability_cooldown": "AbilityDef", "pawn.equipped": "ThingDef"}
_fixture_ops = {"spawn_pawn", "spawn_item", "fixture_hediff", "grant_ability"}
_normal_ops = {"cast", "ingest", "equip", "move", "build", "assert", "wait_assert", "wait", "measure", "registered_test", "begin_ability", "enumerate_choices", "select_choice", "cancel_interaction", "wait_until"}


def validate_plan(payload: dict) -> dict:
    try:
        size = len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError, RecursionError) as error:
        raise ProbeError("invalid_plan", "Plan must contain finite JSON data.") from error
    if not isinstance(payload, dict) or size > 24576:
        raise ProbeError("invalid_plan", "Plan must be an object bounded to 24 KiB.")
    if type(payload.get("schema")) is not int or payload.get("schema") != 1:
        raise ProbeError("invalid_plan", "schema must be integer 1.")
    try:
        model = TypeAdapter(ScenarioPlanInput).validate_python(payload)
    except ValidationError as error:
        raise ProbeError("invalid_plan", str(error)[:2000]) from error
    result = model.model_dump(by_alias=True)
    if len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 24576:
        raise ProbeError("invalid_plan", "Normalized plan exceeds 24 KiB including default fields.")
    if any(len(ref) > 512 for ref in result["source_refs"]):
        raise ProbeError("invalid_plan", "source_refs entries are descriptive and bounded to 512 characters.")
    ids, handles, values, choices = set(), {}, set(), set()
    active = False
    for step in result["steps"]:
        if step["id"] in ids:
            raise ProbeError("invalid_plan", "Step ids must be unique.")
        ids.add(step["id"])
        op = step["op"]
        if active and op in _fixture_ops:
            raise ProbeError("invalid_plan", "Declare all fixture setup before the first action/wait/assert; expected effects cannot be injected later.")
        active |= op in _normal_ops
        for field in ("actor", "target", "near", "other"):
            alias = step.get(field)
            if alias is not None and alias not in handles:
                raise ProbeError("invalid_plan", f"{step['id']}: {field} must reference an earlier bound object.")
        if step.get("actor") is not None and handles[step["actor"]] != "pawn":
            raise ProbeError("invalid_plan", "Action actor must be a fixture Pawn.")
        if op == "wait_until" and ((step["condition"] == "ability_job_finished" or step["cancel_if"] is not None) and step["actor"] is None):
            raise ProbeError("invalid_plan", "This barrier/cancellation condition requires actor.")
        if op in ("inspect_interaction", "enumerate_choices", "cancel_interaction"):
            if (step["x"] is None) != (step["z"] is None):
                raise ProbeError("invalid_plan", "Cell needs both x and z.")
            if op != "enumerate_choices" and any(step.get(key) is not None for key in ("target", "bind_choice", "x", "z")):
                raise ProbeError("invalid_plan", "Only enumerate_choices accepts candidate selectors.")
            if step["cell_at_target"] and (op != "enumerate_choices" or step["target"] is None or step["x"] is not None):
                raise ProbeError("invalid_plan", "cell_at_target requires an object target and excludes explicit coordinates.")
            alias = step.get("bind_choice")
            if alias is not None:
                if alias in choices:
                    raise ProbeError("invalid_plan", "Choice aliases cannot be rebound.")
                choices.add(alias)
        if op == "select_choice" and step["choice"] not in choices:
            raise ProbeError("invalid_plan", "choice requires an earlier enumerate_choices bind_choice.")
        if op in ("assert", "wait_assert", "measure"):
            prop = step["property"]
            if (prop in _named_properties) != (step.get("def_name") is not None):
                raise ProbeError("invalid_plan", "Only hediff_count, ability_cooldown and equipped require def_name.")
            if (prop == "pawn.distance_to") != (step.get("other") is not None):
                raise ProbeError("invalid_plan", "Only pawn.distance_to requires other.")
            if prop.startswith("pawn.") and handles[step["target"]] != "pawn":
                raise ProbeError("invalid_plan", "Pawn properties require a Pawn handle.")
            if step.get("relative_to") is not None and step["relative_to"] not in values:
                raise ProbeError("invalid_plan", "relative_to must reference an earlier measure, never an object handle.")
            if step.get("hold_ticks", 0) > step.get("ticks", 0):
                raise ProbeError("invalid_plan", "hold_ticks requires wait_assert and must not exceed its Tick budget.")
        if op == "measure":
            if step["bind_value"] in values:
                raise ProbeError("invalid_plan", "Measured values cannot be rebound.")
            values.add(step["bind_value"])
        if "bind" in step:
            if step["bind"] in handles:
                raise ProbeError("invalid_plan", "Object aliases cannot be rebound.")
            handles[step["bind"]] = "pawn" if op == "spawn_pawn" else "thing"
    return copy.deepcopy(result)


def plan_catalog() -> dict:
    return {
        "schema": 1, "entry": "rimprobe_run_plan", "maximum_steps": 24,
        "fixture": sorted(_fixture_ops),
        "actions": ["cast", "begin_ability", "select_choice", "cancel_interaction", "ingest", "equip", "move", "build", "registered_test"],
        "test_packs": "Optional explicitly installed compiled packs register bounded keys with independent checks. No runtime code, method or type strings. query_tests discovers available keys inside the loaded game.",
        "discovery": ["query_defs", "find_thing", "inspect", "measure", "query_tests", "inspect_interaction", "enumerate_choices"], "control": ["wait", "assert", "wait_assert", "wait_until"],
        "interactions": {"entry": "begin_ability uses the granted standard Ability command", "kinds": ["world_target", "map_target_callback", "float_menu"], "selection": "Run/interaction-scoped opaque handles; revalidated before selection. Plan bind_choice requires exactly one matching candidate. Live tools require run_id. Standard local verb Targeter chains are unsupported; cast uses normal jobs instead.", "fidelity": "validated_semantic_callback, not real UI input/hit testing", "barriers": "wait_until uses monotonic phase timeout and consecutive main-thread frame samples; observable readiness does not prove renderer rebuild completion"},
        "numeric_properties": list(NumericProperty.__args__),
        "sequential_casts": "After asserting effects, wait_assert actor pawn.ability_casting eq 0 before another action. This observes the current standard Ability Job only; cooldown and effects need separate assertions.",
        "failure_evidence": "Failed/blocked/unsupported/inconclusive/cancelled steps retain failure_context before job cleanup: condition, elapsed/sample-hold ticks and at most four related object snapshots including job_id/job_ability. Diagnostic errors are bounded and do not replace the primary outcome.",
        "comparisons": ["eq", "ne", "gt", "ge", "lt", "le"],
        "semantics": "Bind run-local object aliases. Declare fixture before actions. Actions request normal jobs, not functional passes. measure binds a numeric baseline; assertions can compare deltas with relative_to. wait_assert waits for a condition and optional continuous sampled hold. Plans with no assertions return inconclusive discovery results. No reflection/eval.",
        "limits": "One owned disposable game per plan; not an interactive persistent debugger. Read-only inspect exposes bounded Def/Comp/ability/Hediff/equipment metadata; new framework entry points may need new primitives, never one adapter per object.",
    }
