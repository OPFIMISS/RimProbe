import copy
import json
import math
import re

from .errors import ProbeError

OBSERVERS = {"hediff_added", "hediff_removed", "injury_increased", "cooldown_started", "stunned", "downed"}


def validate_contract(contract: dict) -> dict:
    if not isinstance(contract, dict) or len(json.dumps(contract, ensure_ascii=False).encode("utf-8")) > 24576:
        raise ProbeError("invalid_contract", "Contract must be an object bounded to 24 KiB.")
    allowed = {"schema", "recipe", "def_name", "intent", "source_refs", "fixture", "expect", "observe_ticks", "timeout_seconds", "max_ticks"}
    if set(contract) - allowed or type(contract.get("schema")) is not int or contract.get("schema") != 1 or contract.get("recipe") not in ("ability_cast", "item_ingest", "ui_info_card", "building_power"):
        raise ProbeError("unsupported_contract", "Use schema=1 with ability_cast/item_ingest/ui_info_card/building_power and documented fields; scripts/reflection are not supported.")
    result = copy.deepcopy(contract)
    def identifier(value):
        return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_]{1,128}", value) is not None
    if not identifier(result.get("def_name")) or not isinstance(result.get("intent"), str) or not 1 <= len(result["intent"]) <= 2000:
        raise ProbeError("invalid_contract", "Provide an exact Def identifier and explicit bounded behavioral intent.")
    refs = result.setdefault("source_refs", [])
    if not isinstance(refs, list) or len(refs) > 16 or any(not isinstance(item, str) or len(item) > 512 for item in refs):
        raise ProbeError("invalid_contract", "source_refs is a bounded list of descriptive source/symbol references, never executable inputs.")
    if result["recipe"] == "building_power":
        return _validate_power(result, identifier)
    if result["recipe"] != "ability_cast":
        return _validate_other(result, identifier)
    fixture = result.setdefault("fixture", {})
    if not isinstance(fixture, dict) or set(fixture) - {"actor_kind", "target_kind", "target", "target_faction", "distance", "actor_hediffs", "target_hediffs"}:
        raise ProbeError("invalid_fixture", "Unsupported fixture fields.")
    fixture.setdefault("actor_kind", "Colonist")
    fixture.setdefault("target_kind", "Colonist")
    fixture.setdefault("target", "pawn")
    fixture.setdefault("target_faction", "player")
    fixture.setdefault("distance", 3)
    for field in ("actor_hediffs", "target_hediffs"):
        values = fixture.setdefault(field, [])
        if not isinstance(values, list) or len(values) > 16 or any(not identifier(value) for value in values):
            raise ProbeError("invalid_fixture", "Fixture Hediffs must be bounded exact identifiers; they prepare only newly generated test Pawns.")
    if not identifier(fixture["actor_kind"]) or not identifier(fixture["target_kind"]) or not isinstance(fixture["target"], str) or fixture["target"] not in {"self", "pawn", "cell"} or not isinstance(fixture["target_faction"], str) or fixture["target_faction"] not in {"player", "hostile"}:
        raise ProbeError("invalid_fixture", "Invalid PawnKindDef, target or faction.")
    if type(fixture["distance"]) is not int or not 1 <= fixture["distance"] <= 30:
        raise ProbeError("invalid_fixture", "Fixture distance must be 1..30.")
    expectations = result.get("expect")
    if not isinstance(expectations, list) or not 1 <= len(expectations) <= 16:
        raise ProbeError("missing_assertions", "At least one explicit effect assertion is required; successful casting alone is not functional success.")
    for assertion in expectations:
        if not isinstance(assertion, dict) or set(assertion) - {"kind", "subject", "def_name", "when"}:
            raise ProbeError("invalid_assertion", "Unsupported assertion fields.")
        if not isinstance(assertion.get("kind"), str) or assertion["kind"] not in OBSERVERS:
            raise ProbeError("unsupported_observer", "Effect is not measurable by a registered observer; add a reviewed observer rather than inventing success.")
        assertion.setdefault("subject", "target")
        assertion.setdefault("when", "eventually")
        if not isinstance(assertion["subject"], str) or assertion["subject"] not in {"actor", "target"} or not isinstance(assertion["when"], str) or assertion["when"] not in {"eventually", "end"}:
            raise ProbeError("invalid_assertion", "subject: actor/target; when: eventually/end.")
        if assertion["kind"] == "cooldown_started" and assertion["subject"] != "actor":
            raise ProbeError("invalid_assertion", "Ability cooldown belongs to actor.")
        if assertion["kind"].startswith("hediff_") and not identifier(assertion.get("def_name")):
            raise ProbeError("invalid_assertion", "Hediff observers require an exact HediffDef identifier.")
        if fixture["target"] == "cell" and assertion["subject"] == "target":
            raise ProbeError("unsupported_observer", "Pawn observers cannot inspect a cell; choose actor or add an explicit cell observer.")
    for field, default, minimum, maximum in (("observe_ticks", 180, 1, 60000), ("max_ticks", 6000, 60, 120000), ("timeout_seconds", 120, 5, 600)):
        value = result.setdefault(field, default)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ProbeError("invalid_budget", f"{field}: {minimum}..{maximum}.")
    if result["observe_ticks"] >= result["max_ticks"]:
        raise ProbeError("invalid_budget", "max_ticks must leave time for casting before the observation window finishes.")
    return result


def _validate_other(result, identifier):
    ui = result["recipe"] == "ui_info_card"
    fixture = result.setdefault("fixture", {})
    fields = {"hold_seconds"} if ui else {"actor_kind", "actor_hediffs", "initial_food_fraction"}
    if not isinstance(fixture, dict) or set(fixture) - fields:
        raise ProbeError("invalid_fixture", "Use only fields documented for this recipe.")
    if ui:
        if "observe_ticks" in result or "max_ticks" in result:
            raise ProbeError("invalid_budget", "UI uses fixture.hold_seconds and timeout_seconds, not simulation Tick budgets.")
        hold = fixture.setdefault("hold_seconds", 2)
        if type(hold) not in (int, float) or not math.isfinite(hold) or not 1 <= hold <= 10:
            raise ProbeError("invalid_fixture", "hold_seconds must be finite and 1..10.")
    else:
        fixture.setdefault("actor_kind", "Colonist")
        fixture.setdefault("actor_hediffs", [])
        fraction = fixture.setdefault("initial_food_fraction", 0.25)
        if not identifier(fixture["actor_kind"]) or type(fraction) not in (int, float) or not math.isfinite(fraction) or not 0.05 <= fraction <= 0.8:
            raise ProbeError("invalid_fixture", "Loaded PawnKindDef and finite initial_food_fraction 0.05..0.8 required.")
        if not isinstance(fixture["actor_hediffs"], list) or len(fixture["actor_hediffs"]) > 16 or any(not identifier(name) for name in fixture["actor_hediffs"]):
            raise ProbeError("invalid_fixture", "actor_hediffs must be a bounded list of exact HediffDef identifiers.")
    assertions = result.get("expect")
    ui_kinds = {"window_opened", "window_drawn", "window_in_bounds", "window_closed"}
    item_kinds = {"hediff_added", "hediff_removed", "item_consumed", "nutrition_increased"}
    if not isinstance(assertions, list) or not 1 <= len(assertions) <= 16:
        raise ProbeError("missing_assertions", "Explicit bounded effect assertions are required.")
    for assertion in assertions:
        allowed = {"kind"} if ui else {"kind", "subject", "def_name", "when"}
        if not isinstance(assertion, dict) or set(assertion) - allowed:
            raise ProbeError("invalid_assertion", "Unexpected observer fields for this recipe.")
        kind = assertion.get("kind")
        if not isinstance(kind, str) or kind not in (ui_kinds if ui else item_kinds):
            raise ProbeError("unsupported_observer", "Observer is not registered for this recipe.")
        if not ui:
            assertion.setdefault("subject", "actor")
            assertion.setdefault("when", "eventually")
            if assertion["subject"] != "actor" or assertion["when"] not in ("eventually", "end"):
                raise ProbeError("invalid_assertion", "Ingestion observes actor, with eventually/end timing.")
            if kind.startswith("hediff_") and not identifier(assertion.get("def_name")):
                raise ProbeError("invalid_assertion", "Hediff observers require an exact HediffDef.")
            if not kind.startswith("hediff_") and assertion.get("def_name") is not None:
                raise ProbeError("invalid_assertion", "Only Hediff observers accept def_name.")
    if ui and (len(assertions) != 4 or {entry["kind"] for entry in assertions} != ui_kinds):
        raise ProbeError("missing_assertions", "UI lifecycle requires all four distinct window_* checks.")
    budgets = (("timeout_seconds", 30, 5, 600),) if ui else (("observe_ticks", 1200, 1, 60000), ("max_ticks", 6000, 60, 120000), ("timeout_seconds", 120, 5, 600))
    for field, default, minimum, maximum in budgets:
        value = result.setdefault(field, default)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ProbeError("invalid_budget", f"{field}: {minimum}..{maximum}.")
    if not ui and result["observe_ticks"] >= result["max_ticks"]:
        raise ProbeError("invalid_budget", "max_ticks must exceed observe_ticks.")
    return result


def _validate_power(result, identifier):
    fixture = result.setdefault("fixture", {})
    if not isinstance(fixture, dict) or set(fixture) - {"stuff_name", "settle_ticks", "construction_skill"}:
        raise ProbeError("invalid_fixture", "Power fixture accepts only stuff_name, settle_ticks and construction_skill; no forced output, fuel or research.")
    stuff = fixture.setdefault("stuff_name", None)
    if stuff is not None and not identifier(stuff):
        raise ProbeError("invalid_fixture", "stuff_name must be an exact ThingDef or null.")
    skill = fixture.setdefault("construction_skill", 12)
    if type(skill) is not int or not 0 <= skill <= 20:
        raise ProbeError("invalid_fixture", "construction_skill is an initial new-Pawn skill, integer 0..20.")
    settle = fixture.setdefault("settle_ticks", 60)
    if type(settle) is not int or not 1 <= settle <= 600:
        raise ProbeError("invalid_fixture", "settle_ticks must be 1..600.")
    assertions = result.get("expect")
    required = {"power_output_at_least", "power_net_registered"}
    if not isinstance(assertions, list) or len(assertions) != 2:
        raise ProbeError("missing_assertions", "Power requires exactly one output threshold and one network assertion.")
    kinds = []
    for assertion in assertions:
        if not isinstance(assertion, dict):
            raise ProbeError("invalid_assertion", "Power assertions must be objects.")
        kind = assertion.get("kind")
        if not isinstance(kind, str) or kind not in required:
            raise ProbeError("unsupported_observer", "Unregistered power observer.")
        fields = {"kind", "minimum_watts"} if kind == "power_output_at_least" else {"kind"}
        if set(assertion) != fields:
            raise ProbeError("invalid_assertion", "Output requires minimum_watts; network accepts only kind.")
        if kind == "power_output_at_least":
            watts = assertion["minimum_watts"]
            if type(watts) not in (int, float) or not math.isfinite(watts) or not 0 < watts <= 10000000:
                raise ProbeError("invalid_assertion", "minimum_watts must be finite, positive and <=10000000.")
        kinds.append(kind)
    if set(kinds) != required:
        raise ProbeError("missing_assertions", "Both distinct power assertions are required.")
    for field, default, minimum, maximum in (("observe_ticks", 180, 60, 60000), ("max_ticks", 6000, 60, 120000), ("timeout_seconds", 120, 5, 600)):
        value = result.setdefault(field, default)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ProbeError("invalid_budget", f"{field}: {minimum}..{maximum}.")
    if result["observe_ticks"] + settle >= result["max_ticks"]:
        raise ProbeError("invalid_budget", "max_ticks must leave construction time before settling and observation.")
    return result
