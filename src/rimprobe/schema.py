from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class AbilityFixtureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_kind: str = Field(default="Colonist", pattern=r"^[A-Za-z0-9_]{1,128}$")
    target_kind: str = Field(default="Colonist", pattern=r"^[A-Za-z0-9_]{1,128}$")
    target: Literal["self", "pawn", "cell"] = "pawn"
    target_faction: Literal["player", "hostile"] = "player"
    distance: int = Field(default=3, ge=1, le=30, description="Minimum fixture distance in cells; normal range/LOS eligibility still applies.")
    actor_hediffs: list[str] = Field(default_factory=list, max_length=16, description="Initial fixture setup only, not expected cast results.")
    target_hediffs: list[str] = Field(default_factory=list, max_length=16)


class EffectExpectationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["hediff_added", "hediff_removed", "injury_increased", "cooldown_started", "stunned", "downed"]
    subject: Literal["actor", "target"] = "target"
    def_name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_]{1,128}$", description="Exact HediffDef required only for hediff_added/hediff_removed.")
    when: Literal["eventually", "end"] = "eventually"


class AbilityContractInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = Field(alias="schema")
    recipe: Literal["ability_cast"]
    def_name: str = Field(pattern=r"^[A-Za-z0-9_]{1,128}$", description="Exact loaded AbilityDef, derived from the target source/Def.")
    intent: str = Field(min_length=1, max_length=2000, description="Expected behavior from actual implementation, not merely no errors.")
    source_refs: list[str] = Field(default_factory=list, max_length=16)
    fixture: AbilityFixtureInput = Field(default_factory=AbilityFixtureInput)
    expect: list[EffectExpectationInput] = Field(min_length=1, max_length=16)
    observe_ticks: int = Field(default=180, ge=1, le=60000, description="Observation ticks after cast request; include warmup/travel/effect delay.")
    timeout_seconds: int = Field(default=120, ge=5, le=600)
    max_ticks: int = Field(default=6000, ge=60, le=120000)


class ItemFixtureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_kind: str = Field(default="Colonist", pattern=r"^[A-Za-z0-9_]{1,128}$")
    actor_hediffs: list[str] = Field(default_factory=list, max_length=16)
    initial_food_fraction: float = Field(default=0.25, ge=0.05, le=0.8, description="Initial condition on a newly generated fixture Pawn only.")


class ItemExpectationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["item_consumed", "nutrition_increased", "hediff_added", "hediff_removed"]
    subject: Literal["actor"] = "actor"
    def_name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_]{1,128}$")
    when: Literal["eventually", "end"] = "eventually"


class ItemContractInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = Field(alias="schema")
    recipe: Literal["item_ingest"]
    def_name: str = Field(pattern=r"^[A-Za-z0-9_]{1,128}$", description="Exact ingestible ThingDef; one item is consumed through a normal Ingest job.")
    intent: str = Field(min_length=1, max_length=2000)
    source_refs: list[str] = Field(default_factory=list, max_length=16)
    fixture: ItemFixtureInput = Field(default_factory=ItemFixtureInput)
    expect: list[ItemExpectationInput] = Field(min_length=1, max_length=16)
    observe_ticks: int = Field(default=1200, ge=1, le=60000)
    timeout_seconds: int = Field(default=120, ge=5, le=600)
    max_ticks: int = Field(default=6000, ge=60, le=120000)


class UiFixtureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hold_seconds: float = Field(default=2, ge=1, le=10)


class UiExpectationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["window_opened", "window_drawn", "window_in_bounds", "window_closed"]


class UiContractInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = Field(alias="schema")
    recipe: Literal["ui_info_card"]
    def_name: str = Field(pattern=r"^[A-Za-z0-9_]{1,128}$", description="Loaded ThingDef whose real information-card Stats tab will be drawn.")
    intent: str = Field(min_length=1, max_length=2000)
    source_refs: list[str] = Field(default_factory=list, max_length=16)
    fixture: UiFixtureInput = Field(default_factory=UiFixtureInput)
    expect: list[UiExpectationInput] = Field(min_length=4, max_length=4, description="Require all four distinct window lifecycle/draw/bounds checks; not pixel or mouse hit-testing.")
    timeout_seconds: int = Field(default=30, ge=5, le=600)


class PowerFixtureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    construction_skill: int = Field(default=12, ge=0, le=20, strict=True, description="Initial skill on a newly generated fixture worker only; not a success-chance or result override.")
    stuff_name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_]{1,128}$")
    settle_ticks: int = Field(default=60, ge=1, le=600)


class PowerOutputInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["power_output_at_least"]
    minimum_watts: float = Field(gt=0, le=10000000, allow_inf_nan=False, strict=True)


class PowerNetworkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["power_net_registered"]


class PowerContractInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = Field(alias="schema")
    recipe: Literal["building_power"]
    def_name: str = Field(pattern=r"^[A-Za-z0-9_]{1,128}$")
    intent: str = Field(min_length=1, max_length=2000)
    source_refs: list[str] = Field(default_factory=list, max_length=16)
    fixture: PowerFixtureInput = Field(default_factory=PowerFixtureInput)
    expect: list[Annotated[PowerOutputInput | PowerNetworkInput, Field(discriminator="kind")]] = Field(min_length=2, max_length=2)
    observe_ticks: int = Field(default=180, ge=60, le=60000)
    max_ticks: int = Field(default=6000, ge=60, le=120000)
    timeout_seconds: int = Field(default=120, ge=5, le=600)


BehaviorContractInput = Annotated[AbilityContractInput | ItemContractInput | UiContractInput | PowerContractInput, Field(discriminator="recipe")]
