import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class RealmLevel:
    level_id: int
    name: str
    major_realm: str
    max_exp: int
    next_level_id: int | None


@dataclass(frozen=True, slots=True, init=False)
class RealmCatalog:
    _schema_version: int
    _levels: Mapping[int, RealmLevel]

    def __init__(self, *, schema_version: int, levels: tuple[RealmLevel, ...]) -> None:
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != 1
        ):
            raise ValueError("Unsupported realm catalog schema_version")

        by_id: dict[int, RealmLevel] = {}
        for level in levels:
            if level.level_id in by_id:
                raise ValueError(f"Duplicate realm level: {level.level_id}")
            if isinstance(level.level_id, bool) or not isinstance(level.level_id, int):
                raise ValueError("Realm level ID must be an integer")
            if level.level_id < 1 or level.level_id > 22:
                raise ValueError("Realm level IDs must be 1 through 22")
            if not level.name:
                raise ValueError("Realm level name must not be empty")
            if not level.major_realm:
                raise ValueError("Realm level major_realm must not be empty")
            if (
                isinstance(level.max_exp, bool)
                or not isinstance(level.max_exp, int)
                or level.max_exp <= 0
            ):
                raise ValueError("Realm level max_exp must be a positive integer")
            by_id[level.level_id] = level

        level_ids = sorted(by_id)
        if level_ids and level_ids != list(range(level_ids[0], level_ids[-1] + 1)):
            raise ValueError("Realm level IDs must be contiguous without gaps")

        for level_id in level_ids:
            level = by_id[level_id]
            expected_successor = level_id + 1 if level_id < level_ids[-1] else None
            if level.next_level_id != expected_successor:
                if level_id == level_ids[-1]:
                    raise ValueError("Realm catalog terminal level must not have a successor")
                raise ValueError("Non-terminal realm level has an invalid successor")

        if level_ids != list(range(1, 23)):
            raise ValueError("Realm catalog must contain levels 1 through 22 exactly")

        object.__setattr__(self, "_schema_version", schema_version)
        object.__setattr__(self, "_levels", MappingProxyType(by_id))

    @property
    def schema_version(self) -> int:
        return self._schema_version

    @property
    def levels(self) -> Mapping[int, RealmLevel]:
        return self._levels

    def level(self, level_id: int) -> RealmLevel:
        try:
            return self.levels[level_id]
        except KeyError as error:
            raise KeyError(f"Unknown realm level: {level_id}") from error

    def qi_cumulative_totals(self) -> dict[int, int]:
        total = 0
        result: dict[int, int] = {}
        for level_id in range(1, 14):
            total += self.level(level_id).max_exp
            result[level_id] = total
        return result


def load_realm_catalog(path: Path) -> RealmCatalog:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid realm catalog JSON: {path}") from error
    if not isinstance(document, dict):
        raise ValueError("Realm catalog must be a JSON object")
    _reject_unknown_fields(document, {"schema_version", "levels"}, "realm catalog")

    return RealmCatalog(
        schema_version=_required_int(document, "schema_version"),
        levels=tuple(_parse_level(item) for item in _required_list(document, "levels")),
    )


def _parse_level(document: dict[str, Any]) -> RealmLevel:
    _reject_unknown_fields(
        document,
        {"level_id", "name", "major_realm", "max_exp", "next_level_id"},
        "realm level",
    )
    return RealmLevel(
        level_id=_required_int(document, "level_id"),
        name=_required_str(document, "name"),
        major_realm=_required_str(document, "major_realm"),
        max_exp=_required_int(document, "max_exp"),
        next_level_id=_optional_int(document, "next_level_id"),
    )


def _reject_unknown_fields(document: dict[str, Any], allowed: set[str], label: str) -> None:
    unexpected = sorted(set(document) - allowed)
    if unexpected:
        raise ValueError(f"Unexpected {label} fields: {', '.join(unexpected)}")


def _required_list(document: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Realm catalog field {key} must be a list of objects")
    return value


def _required_str(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Realm catalog field {key} must be a string")
    return value


def _required_int(document: dict[str, Any], key: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Realm catalog field {key} must be an integer")
    return value


def _optional_int(document: dict[str, Any], key: str) -> int | None:
    if key not in document:
        raise ValueError(f"Realm catalog field {key} is required")
    value = document.get(key)
    if value is None:
        return None
    return _required_int(document, key)
