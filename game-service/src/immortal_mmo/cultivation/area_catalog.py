from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


class AreaCatalogError(ValueError):
    """Raised when an area catalog fails strict validation."""


MAX_BASIS_POINTS = 100_000


@dataclass(frozen=True, slots=True)
class AreaDefinition:
    area_id: str
    name: str
    speed_basis_points: int
    yield_basis_points: int
    version: int = 1


@dataclass(frozen=True, slots=True, init=False)
class AreaCatalog:
    _schema_version: int
    _areas: Mapping[str, AreaDefinition]
    _revision: str

    def __init__(self, *, schema_version: int, areas: tuple[AreaDefinition, ...]) -> None:
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != 1
        ):
            raise AreaCatalogError("Unsupported area catalog schema_version")
        by_id: dict[str, AreaDefinition] = {}
        for area in areas:
            self._validate_area(area)
            if area.area_id in by_id:
                raise AreaCatalogError(f"Duplicate area ID: {area.area_id}")
            by_id[area.area_id] = area
        object.__setattr__(self, "_schema_version", schema_version)
        object.__setattr__(self, "_areas", MappingProxyType(by_id))
        object.__setattr__(self, "_revision", _revision(schema_version, by_id))

    @staticmethod
    def _validate_area(area: AreaDefinition) -> None:
        if not isinstance(area.area_id, str) or not area.area_id:
            raise AreaCatalogError("Area ID must not be empty")
        if not isinstance(area.name, str) or not area.name:
            raise AreaCatalogError("Area name must not be empty")
        for field in ("speed_basis_points", "yield_basis_points"):
            value = getattr(area, field)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= MAX_BASIS_POINTS
            ):
                raise AreaCatalogError(
                    f"Area {field} must be a positive bounded integer basis_points"
                )
        if isinstance(area.version, bool) or not isinstance(area.version, int) or area.version != 1:
            raise AreaCatalogError("Area version must be the exact integer 1")

    @property
    def schema_version(self) -> int:
        return self._schema_version

    @property
    def areas(self) -> Mapping[str, AreaDefinition]:
        return self._areas

    @property
    def revision(self) -> str:
        return self._revision

    def area(self, area_id: str) -> AreaDefinition:
        try:
            return self._areas[area_id]
        except KeyError as error:
            raise KeyError(f"Unknown cultivation area: {area_id}") from error


def load_area_catalog(path: Path) -> AreaCatalog:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise AreaCatalogError(f"Invalid area catalog JSON: {path}") from error
    if not isinstance(document, dict):
        raise AreaCatalogError("Area catalog must be a JSON object")
    _reject_unknown_fields(document, {"schema_version", "areas"}, "area catalog")
    return AreaCatalog(
        schema_version=_required_int(document, "schema_version"),
        areas=tuple(_parse_area(item) for item in _required_list(document, "areas")),
    )


def _parse_area(document: dict[str, Any]) -> AreaDefinition:
    _reject_unknown_fields(
        document,
        {"area_id", "name", "version", "speed_basis_points", "yield_basis_points"},
        "area",
    )
    return AreaDefinition(
        area_id=_required_str(document, "area_id"),
        name=_required_str(document, "name"),
        speed_basis_points=_required_int(document, "speed_basis_points"),
        yield_basis_points=_required_int(document, "yield_basis_points"),
        version=_required_int(document, "version"),
    )


def _revision(schema_version: int, areas: Mapping[str, AreaDefinition]) -> str:
    payload = {
        "schema_version": schema_version,
        "areas": [
            {
                "area_id": area.area_id,
                "name": area.name,
                "version": area.version,
                "speed_basis_points": area.speed_basis_points,
                "yield_basis_points": area.yield_basis_points,
            }
            for area in sorted(areas.values(), key=lambda item: item.area_id)
        ],
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _required_list(document: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise AreaCatalogError(f"Area catalog field {key} must be a list of objects")
    return value


def _required_str(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise AreaCatalogError(f"Area catalog field {key} must be a string")
    return value


def _required_int(document: dict[str, Any], key: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AreaCatalogError(f"Area catalog field {key} must be an integer")
    return value


def _reject_unknown_fields(document: dict[str, Any], allowed: set[str], label: str) -> None:
    unexpected = sorted(set(document) - allowed)
    if unexpected:
        raise AreaCatalogError(f"Unexpected {label} fields: {', '.join(unexpected)}")
