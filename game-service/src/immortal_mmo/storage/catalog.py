from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


class StorageCatalogError(ValueError):
    """Raised when the regional storage catalog is invalid."""


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


@dataclass(frozen=True, slots=True)
class StorageDefinition:
    area_id: str
    page_count: int
    item_slots_per_page: int
    permission: str


@dataclass(frozen=True, slots=True, init=False)
class StorageCatalog:
    _schema_version: int
    _storages: Mapping[str, StorageDefinition]
    _revision: str

    def __init__(
        self,
        *,
        schema_version: int,
        storages: tuple[StorageDefinition, ...],
    ) -> None:
        if isinstance(schema_version, bool) or schema_version != 1:
            raise StorageCatalogError("Unsupported storage catalog schema_version")
        by_area: dict[str, StorageDefinition] = {}
        for definition in storages:
            _validate_definition(definition)
            if definition.area_id in by_area:
                raise StorageCatalogError(
                    f"Duplicate regional storage area: {definition.area_id}"
                )
            by_area[definition.area_id] = definition
        if not by_area:
            raise StorageCatalogError("Storage catalog must define at least one area")
        object.__setattr__(self, "_schema_version", schema_version)
        object.__setattr__(self, "_storages", MappingProxyType(by_area))
        object.__setattr__(self, "_revision", _revision(schema_version, by_area))

    @property
    def schema_version(self) -> int:
        return self._schema_version

    @property
    def storages(self) -> Mapping[str, StorageDefinition]:
        return self._storages

    @property
    def revision(self) -> str:
        return self._revision

    def storage(self, area_id: str) -> StorageDefinition:
        try:
            return self._storages[area_id]
        except KeyError as error:
            raise KeyError(f"Unknown regional storage area: {area_id}") from error


def load_storage_catalog(path: Path) -> StorageCatalog:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StorageCatalogError(f"Invalid storage catalog JSON: {path}") from error
    if not isinstance(document, dict):
        raise StorageCatalogError("Storage catalog must be a JSON object")
    _reject_unknown(document, {"schema_version", "storages"}, "storage catalog")
    storages = document.get("storages")
    if not isinstance(storages, list) or not all(isinstance(item, dict) for item in storages):
        raise StorageCatalogError("Storage catalog storages must be a list of objects")
    return StorageCatalog(
        schema_version=_required_int(document, "schema_version"),
        storages=tuple(_parse_definition(item) for item in storages),
    )


def _parse_definition(document: dict[str, Any]) -> StorageDefinition:
    _reject_unknown(
        document,
        {"area_id", "page_count", "item_slots_per_page", "permission"},
        "storage definition",
    )
    return StorageDefinition(
        area_id=_required_str(document, "area_id"),
        page_count=_required_int(document, "page_count"),
        item_slots_per_page=_required_int(document, "item_slots_per_page"),
        permission=_required_str(document, "permission"),
    )


def _validate_definition(definition: StorageDefinition) -> None:
    if _IDENTIFIER.fullmatch(definition.area_id) is None:
        raise StorageCatalogError("Storage area_id must be a stable identifier")
    if not 1 <= definition.page_count <= 100:
        raise StorageCatalogError("Storage page_count must be between 1 and 100")
    if not 1 <= definition.item_slots_per_page <= 45:
        raise StorageCatalogError(
            "Storage item_slots_per_page must be between 1 and 45"
        )
    if _IDENTIFIER.fullmatch(definition.permission) is None:
        raise StorageCatalogError("Storage permission must be a stable identifier")


def _revision(
    schema_version: int,
    storages: Mapping[str, StorageDefinition],
) -> str:
    payload = {
        "schema_version": schema_version,
        "storages": [
            {
                "area_id": item.area_id,
                "page_count": item.page_count,
                "item_slots_per_page": item.item_slots_per_page,
                "permission": item.permission,
            }
            for item in sorted(storages.values(), key=lambda value: value.area_id)
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _required_str(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise StorageCatalogError(f"Storage catalog field {key} must be a string")
    return value


def _required_int(document: dict[str, Any], key: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise StorageCatalogError(f"Storage catalog field {key} must be an integer")
    return value


def _reject_unknown(document: dict[str, Any], allowed: set[str], label: str) -> None:
    unexpected = sorted(set(document) - allowed)
    if unexpected:
        raise StorageCatalogError(f"Unexpected {label} fields: {', '.join(unexpected)}")
