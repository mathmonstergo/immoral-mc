import json
import operator
from math import ceil
from pathlib import Path
from typing import Any, cast

import pytest

from immortal_mmo.cultivation.realm_catalog import (
    RealmCatalog,
    RealmLevel,
    load_realm_catalog,
)

CATALOG_PATH = (
    Path(__file__).parents[2] / "src" / "immortal_mmo" / "cultivation" / "realm_catalog.json"
)


@pytest.fixture
def catalog() -> RealmCatalog:
    return load_realm_catalog(CATALOG_PATH)


def test_realm_catalog_has_approved_twenty_two_levels(catalog: RealmCatalog) -> None:
    expected = {
        1: ("练气一层", "练气", 100),
        2: ("练气二层", "练气", 150),
        3: ("练气三层", "练气", 225),
        4: ("练气四层", "练气", 337),
        5: ("练气五层", "练气", 505),
        6: ("练气六层", "练气", 757),
        7: ("练气七层", "练气", 1_135),
        8: ("练气八层", "练气", 1_702),
        9: ("练气九层", "练气", 2_553),
        10: ("练气十层", "练气", 3_829),
        11: ("练气十一层", "练气", 5_169),
        12: ("练气十二层", "练气", 6_978),
        13: ("练气十三层", "练气", 9_420),
        14: ("筑基初期", "筑基", 43_931),
        15: ("筑基中期", "筑基", 74_682),
        16: ("筑基后期", "筑基", 298_728),
        17: ("结丹初期", "结丹", 537_710),
        18: ("结丹中期", "结丹", 967_878),
        19: ("结丹后期", "结丹", 4_839_390),
        20: ("元婴初期", "元婴", 9_678_780),
        21: ("元婴中期", "元婴", 19_357_560),
        22: ("元婴后期", "元婴", 116_145_360),
    }

    assert len(catalog.levels) == 22
    for level_id, (name, major_realm, max_exp) in expected.items():
        level = catalog.level(level_id)
        assert (level.name, level.major_realm, level.max_exp) == (
            name,
            major_realm,
            max_exp,
        )
        assert level.next_level_id == (level_id + 1 if level_id < 22 else None)


def test_realm_levels_and_catalog_view_are_frozen(catalog: RealmCatalog) -> None:
    assert RealmLevel.__dataclass_params__.frozen is True
    with pytest.raises(TypeError):
        operator.setitem(catalog.levels, 1, catalog.level(2))


@pytest.mark.parametrize(("attribute", "value"), [("schema_version", 2), ("levels", {})])
def test_realm_catalog_attributes_cannot_be_reassigned(
    catalog: RealmCatalog,
    attribute: str,
    value: object,
) -> None:
    with pytest.raises((AttributeError, TypeError)):
        setattr(catalog, attribute, value)


def test_qi_cumulative_capacity_uses_three_five_seven_nine_techniques(
    catalog: RealmCatalog,
) -> None:
    totals = catalog.qi_cumulative_totals()

    assert [totals[level] for level in (10, 11, 12, 13)] == [
        11_293,
        16_462,
        23_440,
        32_860,
    ]
    assert [ceil(totals[level] / 3_780) for level in (10, 11, 12, 13)] == [3, 5, 7, 9]


def _level(
    level_id: int,
    *,
    name: str | None = None,
    major_realm: str = "练气",
    max_exp: int = 100,
    next_level_id: int | None | object = ...,
) -> RealmLevel:
    successor = level_id + 1 if next_level_id is ... else next_level_id
    return RealmLevel(
        level_id,
        f"level-{level_id}" if name is None else name,
        major_realm,
        max_exp,
        successor,
    )


@pytest.mark.parametrize(
    ("levels", "message"),
    [
        ((_level(1), _level(1)), "Duplicate realm level"),
        ((_level(1, next_level_id=3), _level(3, next_level_id=None)), "contiguous"),
        ((_level(0, next_level_id=None),), "1 through 22"),
        ((_level(23, next_level_id=None),), "1 through 22"),
        ((_level(1, max_exp=0, next_level_id=None),), "max_exp"),
        ((_level(1, name="", next_level_id=None),), "name"),
        ((_level(1, major_realm="", next_level_id=None),), "major_realm"),
        ((_level(1, next_level_id=None), _level(2, next_level_id=None)), "successor"),
        ((_level(1, next_level_id=2),), "terminal"),
    ],
)
def test_realm_catalog_rejects_invalid_levels(
    levels: tuple[RealmLevel, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        RealmCatalog(schema_version=1, levels=levels)


def test_realm_catalog_rejects_unknown_level(catalog: RealmCatalog) -> None:
    with pytest.raises(KeyError, match="Unknown realm level"):
        catalog.level(23)


@pytest.mark.parametrize("schema_version", [True, 1.0])
def test_realm_catalog_constructor_rejects_non_integer_schema_version(
    catalog: RealmCatalog,
    schema_version: object,
) -> None:
    with pytest.raises(ValueError, match="schema_version"):
        RealmCatalog(
            schema_version=cast(Any, schema_version),
            levels=tuple(catalog.levels.values()),
        )


def test_realm_catalog_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["levels"][0]["unexpected"] = "value"
    path = tmp_path / "realm_catalog.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected"):
        load_realm_catalog(path)


def test_realm_catalog_loader_rejects_boolean_max_exp(tmp_path: Path) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["levels"][0]["max_exp"] = True
    path = tmp_path / "realm_catalog.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="max_exp.*integer"):
        load_realm_catalog(path)


def test_realm_catalog_loader_requires_successor_key_even_when_null(tmp_path: Path) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    del document["levels"][-1]["next_level_id"]
    path = tmp_path / "realm_catalog.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="next_level_id.*required"):
        load_realm_catalog(path)
