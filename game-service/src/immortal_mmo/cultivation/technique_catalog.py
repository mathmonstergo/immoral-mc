from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


class TechniqueCatalogError(ValueError):
    """Raised when committed technique content does not satisfy its schema."""


_GROUP_REALMS = {
    "qi": ("练气", 1),
    "level:14": ("筑基", 2),
    "level:15": ("筑基", 2),
    "level:16": ("筑基", 2),
    "level:17": ("结丹", 5),
    "level:18": ("结丹", 5),
    "level:19": ("结丹", 5),
    "level:20": ("元婴", 10),
    "level:21": ("元婴", 10),
    "level:22": ("元婴", 10),
}
_CANONICAL_ELEMENTS = frozenset({"metal", "wood", "water", "fire", "earth", "ice", "wind"})
_EFFECT_FIELDS = {
    "attr",
    "kind",
    "status",
    "effect_type",
    "mode",
    "value",
    "growth",
    "chance",
    "duration_rounds",
    "stacks",
    "layer_start",
    "layer_end",
}


@dataclass(frozen=True, slots=True)
class TechniquePrerequisite:
    technique_id: str
    min_layer: int


@dataclass(frozen=True, slots=True)
class EquippedItemRequirement:
    item_id: str
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class TechniqueEffectDefinition:
    attribute: str | None
    kind: str
    status: str | None
    effect_type: str
    mode: str
    value: float
    growth: float
    chance: float | None
    duration_rounds: int | None
    stacks: int | None
    layer_start: int
    layer_end: int


@dataclass(frozen=True, slots=True)
class TechniqueEffect:
    attribute: str | None
    status: str | None
    effect_type: str
    mode: str
    value: float
    layer: int
    chance: float | None
    duration_rounds: int | None
    stacks: int | None


@dataclass(frozen=True, slots=True)
class TechniqueDefinition:
    technique_id: str
    name: str
    description: str
    group: str
    major_realm: str
    time_weight: int
    max_layer: int
    required_elements: tuple[str, ...]
    minimum_player_level: int
    prerequisites: tuple[TechniquePrerequisite, ...]
    equipped_item_requirements: tuple[EquippedItemRequirement, ...]
    category: str
    effects: tuple[TechniqueEffectDefinition, ...]

    @property
    def id(self) -> str:
        return self.technique_id

    @property
    def min_level(self) -> int:
        return self.minimum_player_level

    @property
    def effects_v2(self) -> tuple[TechniqueEffectDefinition, ...]:
        return self.effects

    def project_effects(self, layer: int) -> tuple[TechniqueEffect, ...]:
        if (
            isinstance(layer, bool)
            or not isinstance(layer, int)
            or not 1 <= layer <= self.max_layer
        ):
            raise ValueError("Technique effect layer must be an integer from 1 through 13")
        result: list[TechniqueEffect] = []
        for effect in self.effects:
            if layer < effect.layer_start or layer > effect.layer_end:
                continue
            value = effect.value + effect.growth * (layer - effect.layer_start)
            result.append(
                TechniqueEffect(
                    attribute=effect.attribute,
                    status=effect.status,
                    effect_type=effect.effect_type,
                    mode=effect.mode,
                    value=value,
                    layer=layer,
                    chance=effect.chance,
                    duration_rounds=effect.duration_rounds,
                    stacks=effect.stacks,
                )
            )
        return tuple(result)


@dataclass(frozen=True, slots=True, init=False)
class TechniqueCatalog:
    _schema_version: int
    _techniques: Mapping[str, TechniqueDefinition]

    def __init__(self, *, schema_version: int, techniques: tuple[TechniqueDefinition, ...]) -> None:
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != 1
        ):
            raise TechniqueCatalogError("Unsupported technique catalog schema_version")
        by_id: dict[str, TechniqueDefinition] = {}
        counts: dict[str, int] = {}
        for technique in techniques:
            self._validate_definition(technique)
            if technique.technique_id in by_id:
                raise TechniqueCatalogError(f"Duplicate technique ID: {technique.technique_id}")
            by_id[technique.technique_id] = technique
            counts[technique.group] = counts.get(technique.group, 0) + 1
        for group, count in counts.items():
            cap = 9 if group == "qi" else 5
            if count > cap:
                raise TechniqueCatalogError(f"Technique group {group} exceeds retention cap {cap}")
        for technique in by_id.values():
            unknown = {
                prerequisite.technique_id
                for prerequisite in technique.prerequisites
                if prerequisite.technique_id not in by_id
            }
            if unknown:
                raise TechniqueCatalogError(f"Unknown prerequisite technique: {sorted(unknown)[0]}")
        object.__setattr__(self, "_schema_version", schema_version)
        object.__setattr__(self, "_techniques", MappingProxyType(by_id))

    @staticmethod
    def _validate_definition(technique: TechniqueDefinition) -> None:
        if not isinstance(technique.technique_id, str) or not technique.technique_id:
            raise TechniqueCatalogError("Technique ID must not be empty")
        for field in ("name", "description", "major_realm", "category"):
            if not isinstance(getattr(technique, field), str) or not getattr(technique, field):
                raise TechniqueCatalogError(f"Technique {field} must not be empty")
        if technique.group not in _GROUP_REALMS:
            raise TechniqueCatalogError(f"Unsupported technique group: {technique.group}")
        expected_realm, expected_weight = _GROUP_REALMS[technique.group]
        if technique.major_realm != expected_realm:
            raise TechniqueCatalogError("Technique group and major_realm are inconsistent")
        if technique.time_weight != expected_weight:
            raise TechniqueCatalogError("Technique time_weight is inconsistent with major realm")
        if technique.max_layer != 13:
            raise TechniqueCatalogError("Technique max_layer must be 13")
        if (
            isinstance(technique.minimum_player_level, bool)
            or not isinstance(technique.minimum_player_level, int)
            or not 1 <= technique.minimum_player_level <= 22
        ):
            raise TechniqueCatalogError(
                "Technique minimum_player_level must be an integer from 1 through 22"
            )
        if technique.group == "qi":
            if not 1 <= technique.minimum_player_level <= 13:
                raise TechniqueCatalogError(
                    "qi technique minimum_player_level must be 1 through 13"
                )
        else:
            group_level = int(technique.group.split(":", 1)[1])
            if technique.minimum_player_level < group_level:
                raise TechniqueCatalogError(
                    "Technique minimum_player_level is below its group level"
                )
        if len(set(technique.required_elements)) != len(technique.required_elements):
            raise TechniqueCatalogError("Technique required_elements must not contain duplicates")
        for element in technique.required_elements:
            if element not in _CANONICAL_ELEMENTS:
                raise TechniqueCatalogError(f"Unknown canonical technique element: {element}")
        for prerequisite in technique.prerequisites:
            if not prerequisite.technique_id:
                raise TechniqueCatalogError("Technique prerequisite ID must not be empty")
            if (
                isinstance(prerequisite.min_layer, bool)
                or not isinstance(prerequisite.min_layer, int)
                or not 1 <= prerequisite.min_layer <= 13
            ):
                raise TechniqueCatalogError("Technique prerequisite min_layer must be 1 through 13")
        for requirement in technique.equipped_item_requirements:
            if not requirement.item_id:
                raise TechniqueCatalogError("Equipped item ID must not be empty")
            if (
                isinstance(requirement.quantity, bool)
                or not isinstance(requirement.quantity, int)
                or requirement.quantity <= 0
            ):
                raise TechniqueCatalogError("Equipped item quantity must be a positive integer")
        for effect in technique.effects:
            if effect.attribute is None and effect.kind != "status":
                raise TechniqueCatalogError("Technique effect requires attr or status kind")
            if effect.attribute is not None and not effect.attribute:
                raise TechniqueCatalogError("Technique effect attr must not be empty")
            if effect.kind == "status" and not effect.status:
                raise TechniqueCatalogError("Status technique effect requires status")
            if effect.effect_type not in {"cost", "triggered", "persistent", "status"}:
                raise TechniqueCatalogError(
                    f"Unsupported technique effect_type: {effect.effect_type}"
                )
            if effect.mode not in {"value", "percent", "chance"}:
                raise TechniqueCatalogError(f"Unsupported technique effect mode: {effect.mode}")
            if effect.chance is not None and effect.mode != "chance":
                raise TechniqueCatalogError(
                    "Technique effect chance is only compatible with mode=chance"
                )
            if effect.kind == "status":
                if effect.effect_type != "status":
                    raise TechniqueCatalogError(
                        "Status technique effect requires effect_type=status"
                    )
                if effect.mode != "chance":
                    raise TechniqueCatalogError("Status technique effect requires mode=chance")
            else:
                if effect.status is not None:
                    raise TechniqueCatalogError("Attribute technique effect must not define status")
                if effect.effect_type == "status":
                    raise TechniqueCatalogError(
                        "Attribute technique effect must not use effect_type=status"
                    )
                if effect.mode == "chance":
                    raise TechniqueCatalogError(
                        "Attribute technique effect must not use mode=chance"
                    )
            if not math.isfinite(effect.value) or not math.isfinite(effect.growth):
                raise TechniqueCatalogError("Technique effect values must be finite")
            if effect.chance is not None and (
                not math.isfinite(effect.chance) or not 0 <= effect.chance <= 1
            ):
                raise TechniqueCatalogError("Technique effect chance must be between 0 and 1")
            if effect.duration_rounds is not None and (
                isinstance(effect.duration_rounds, bool)
                or not isinstance(effect.duration_rounds, int)
                or effect.duration_rounds < 0
            ):
                raise TechniqueCatalogError(
                    "Technique effect duration_rounds must be a non-negative integer or null"
                )
            if effect.stacks is not None and (
                isinstance(effect.stacks, bool)
                or not isinstance(effect.stacks, int)
                or effect.stacks <= 0
            ):
                raise TechniqueCatalogError(
                    "Technique effect stacks must be a positive integer or null"
                )
            if not 1 <= effect.layer_start <= effect.layer_end <= 13:
                raise TechniqueCatalogError(
                    "Technique effect layer range must be within 1 through 13"
                )

    @property
    def schema_version(self) -> int:
        return self._schema_version

    @property
    def techniques(self) -> Mapping[str, TechniqueDefinition]:
        return self._techniques

    def technique(self, technique_id: str) -> TechniqueDefinition:
        try:
            return self._techniques[technique_id]
        except KeyError as error:
            raise KeyError(f"Unknown technique: {technique_id}") from error

    def group_retention_cap(self, group: str) -> int:
        if group not in _GROUP_REALMS:
            raise KeyError(f"Unknown technique group: {group}")
        return 9 if group == "qi" else 5


def load_technique_catalog(path: Path) -> TechniqueCatalog:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise TechniqueCatalogError(f"Invalid technique catalog JSON: {path}") from error
    if not isinstance(document, dict):
        raise TechniqueCatalogError("Technique catalog must be a JSON object")
    _reject_unknown_fields(document, {"schema_version", "techniques"}, "technique catalog")
    return TechniqueCatalog(
        schema_version=_required_int(document, "schema_version"),
        techniques=tuple(_parse_technique(item) for item in _required_list(document, "techniques")),
    )


def _parse_technique(document: dict[str, Any]) -> TechniqueDefinition:
    allowed = {
        "technique_id",
        "name",
        "description",
        "group",
        "major_realm",
        "time_weight",
        "max_layer",
        "required_elements",
        "minimum_player_level",
        "prerequisites",
        "equipped_item_requirements",
        "category",
        "effects",
    }
    _reject_unknown_fields(document, allowed, "technique")
    return TechniqueDefinition(
        technique_id=_required_str(document, "technique_id"),
        name=_required_str(document, "name"),
        description=_required_str(document, "description"),
        group=_required_str(document, "group"),
        major_realm=_required_str(document, "major_realm"),
        time_weight=_required_int(document, "time_weight"),
        max_layer=_required_int(document, "max_layer"),
        required_elements=tuple(_required_str_list(document, "required_elements")),
        minimum_player_level=_required_int(document, "minimum_player_level"),
        prerequisites=tuple(
            _parse_prerequisite(item) for item in _required_list(document, "prerequisites")
        ),
        equipped_item_requirements=tuple(
            _parse_item_requirement(item)
            for item in _required_list(document, "equipped_item_requirements")
        ),
        category=_required_str(document, "category"),
        effects=tuple(_parse_effect(item) for item in _required_list(document, "effects")),
    )


def _parse_prerequisite(document: dict[str, Any]) -> TechniquePrerequisite:
    _reject_unknown_fields(document, {"technique_id", "min_layer"}, "technique prerequisite")
    return TechniquePrerequisite(
        _required_str(document, "technique_id"), _required_int(document, "min_layer")
    )


def _parse_item_requirement(document: dict[str, Any]) -> EquippedItemRequirement:
    _reject_unknown_fields(document, {"item_id", "quantity"}, "equipped item requirement")
    return EquippedItemRequirement(
        _required_str(document, "item_id"), _required_int(document, "quantity")
    )


def _parse_effect(document: dict[str, Any]) -> TechniqueEffectDefinition:
    _reject_unknown_fields(document, _EFFECT_FIELDS, "technique effect")
    has_attr = "attr" in document
    has_kind = "kind" in document
    if has_attr == has_kind:
        raise TechniqueCatalogError("Technique effect must contain exactly one of attr or kind")
    kind = _required_str(document, "kind") if has_kind else "attribute"
    attribute = _required_str(document, "attr") if has_attr else None
    status = _optional_str(document, "status")
    if kind == "status" and status is None:
        raise TechniqueCatalogError("Status technique effect requires status")
    return TechniqueEffectDefinition(
        attribute=attribute,
        kind=kind,
        status=status,
        effect_type=_required_str(document, "effect_type"),
        mode=_required_str(document, "mode"),
        value=_required_number(document, "value"),
        growth=_optional_number(document, "growth", 0.0),
        chance=_optional_number_or_null(document, "chance"),
        duration_rounds=_optional_int_or_null(document, "duration_rounds"),
        stacks=_optional_int_or_null(document, "stacks"),
        layer_start=_optional_int(document, "layer_start", 1),
        layer_end=_optional_int(document, "layer_end", 13),
    )


def _required_list(document: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TechniqueCatalogError(f"Technique catalog field {key} must be a list of objects")
    return value


def _required_str_list(document: dict[str, Any], key: str) -> list[str]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TechniqueCatalogError(f"Technique catalog field {key} must be a list of strings")
    return value


def _required_str(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise TechniqueCatalogError(f"Technique catalog field {key} must be a string")
    return value


def _optional_str(document: dict[str, Any], key: str) -> str | None:
    value = document.get(key)
    if value is not None and not isinstance(value, str):
        raise TechniqueCatalogError(f"Technique catalog field {key} must be a string or null")
    return value


def _required_int(document: dict[str, Any], key: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TechniqueCatalogError(f"Technique catalog field {key} must be an integer")
    return value


def _optional_int(document: dict[str, Any], key: str, default: int) -> int:
    if key not in document:
        return default
    return _required_int(document, key)


def _optional_int_or_null(document: dict[str, Any], key: str) -> int | None:
    if key not in document or document[key] is None:
        return None
    return _required_int(document, key)


def _required_number(document: dict[str, Any], key: str) -> float:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TechniqueCatalogError(f"Technique catalog field {key} must be a number")
    return float(value)


def _optional_number(document: dict[str, Any], key: str, default: float) -> float:
    if key not in document or document[key] is None:
        return default
    return _required_number(document, key)


def _optional_number_or_null(document: dict[str, Any], key: str) -> float | None:
    if key not in document or document[key] is None:
        return None
    return _required_number(document, key)


def _reject_unknown_fields(document: dict[str, Any], allowed: set[str], label: str) -> None:
    unexpected = sorted(set(document) - allowed)
    if unexpected:
        raise TechniqueCatalogError(f"Unexpected {label} fields: {', '.join(unexpected)}")
