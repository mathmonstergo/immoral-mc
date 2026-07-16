import json
import operator
from pathlib import Path
from typing import Any, cast

import pytest

from immortal_mmo.cultivation.breakthrough_catalog import (
    BreakthroughCatalog,
    FailurePolicy,
    load_breakthrough_catalog,
)

CATALOG_PATH = (
    Path(__file__).parents[2] / "src" / "immortal_mmo" / "cultivation" / "breakthrough_rules.json"
)


@pytest.fixture
def catalog() -> BreakthroughCatalog:
    return load_breakthrough_catalog(CATALOG_PATH)


def test_breakthrough_profiles_match_approved_tables(catalog: BreakthroughCatalog) -> None:
    assert catalog.profile("one_to_three_root").basis_points == (10_000,)
    assert catalog.profile("one_to_three_root").pill_counts == (1,)
    assert catalog.profile("four_root").basis_points == (
        500,
        1000,
        1600,
        2400,
        3200,
        4200,
        5300,
        6700,
        8200,
        10000,
    )
    assert catalog.profile("five_root").basis_points == (
        200,
        400,
        700,
        1100,
        1600,
        2200,
        2900,
        3600,
        4300,
        5000,
    )


def test_initial_qi_to_foundation_rule_is_frozen_and_typed(catalog: BreakthroughCatalog) -> None:
    rule = catalog.rule("qi_to_foundation")
    assert rule.source_levels == (10, 11, 12, 13)
    assert rule.target_level == 14
    assert rule.duration_seconds == 600
    assert rule.required_item_id == "foundation_pill"
    assert rule.duration_min_seconds == 600
    assert rule.duration_max_seconds == 900
    assert dict(rule.profile_ids) == {
        "one_to_three_root": "one_to_three_root",
        "four_root": "four_root",
        "five_root": "five_root",
    }
    assert rule.failure_policies[10] == FailurePolicy("secondary_50_50", 11)
    assert rule.failure_policies[11] == FailurePolicy("secondary_50_50", 12)
    assert rule.failure_policies[12] == FailurePolicy("secondary_50_50", 13)
    assert rule.failure_policies[13] == FailurePolicy("forced_loss", None)


def test_breakthrough_catalog_is_deeply_immutable(catalog: BreakthroughCatalog) -> None:
    rule = catalog.rule("qi_to_foundation")
    with pytest.raises(TypeError):
        operator.setitem(catalog.profiles, "other", catalog.profile("four_root"))
    with pytest.raises(TypeError):
        operator.setitem(rule.profile_ids, "four_root", "five_root")
    with pytest.raises(TypeError):
        operator.setitem(rule.failure_policies, 10, FailurePolicy("forced_loss"))


def test_breakthrough_catalog_rejects_duplicate_profiles_and_rules(tmp_path: Path) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["profiles"].append(document["profiles"][0])
    path = tmp_path / "breakthrough_rules.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate breakthrough profile"):
        load_breakthrough_catalog(path)

    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["rules"].append(document["rules"][0])
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate breakthrough rule"):
        load_breakthrough_catalog(path)


@pytest.mark.parametrize(
    ("profile_index", "field", "value"),
    [
        (0, "root_counts", [1, 2]),
        (0, "basis_points", [9999]),
        (1, "basis_points", [500, 1000, 1600, 2400, 3200, 4200, 5300, 6700, 8200, 9999]),
        (2, "basis_points", [200, 400, 700, 1100, 1600, 2200, 2900, 3600, 4300, 5001]),
    ],
)
def test_breakthrough_catalog_rejects_semantic_profile_mutations(
    tmp_path: Path, profile_index: int, field: str, value: object
) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["profiles"][profile_index][field] = value
    path = tmp_path / "breakthrough_rules.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="approved|one-to-three-root"):
        load_breakthrough_catalog(path)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("source_levels",), [10, 11, 12]),
        (("target_level",), 15),
        (("duration_seconds",), 601),
        (("duration_min_seconds",), 601),
        (("duration_max_seconds",), 899),
        (("required_item_id",), "other_pill"),
        (("profiles", "four_root"), "five_root"),
        (("failure_policies", "10", "secondary_basis_points"), 5001),
        (("failure_policies", "12", "mode"), "forced_loss"),
        (("failure_policies", "13", "mode"), "secondary_50_50"),
    ],
)
def test_breakthrough_catalog_rejects_semantic_rule_mutations(
    tmp_path: Path, path: tuple[str, ...], value: object
) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    target = document["rules"][0]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    output = tmp_path / "breakthrough_rules.json"
    output.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError):
        load_breakthrough_catalog(output)


def test_breakthrough_loader_rejects_boolean_nested_integer(tmp_path: Path) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["rules"][0]["failure_policies"]["10"]["loss_numerator"] = True
    path = tmp_path / "breakthrough_rules.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="loss_numerator.*integer"):
        load_breakthrough_catalog(path)


def test_breakthrough_catalog_rejects_unknown_fields_and_bad_tables(tmp_path: Path) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["rules"][0]["realm_layer_caps"] = {}
    path = tmp_path / "breakthrough_rules.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="realm_layer_caps"):
        load_breakthrough_catalog(path)

    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["profiles"][1]["basis_points"][0] = 10_001
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="basis"):
        load_breakthrough_catalog(path)


@pytest.mark.parametrize("schema_version", [True, 1.0, 2])
def test_breakthrough_constructor_rejects_non_exact_schema_version(schema_version: object) -> None:
    with pytest.raises(ValueError, match="schema_version"):
        BreakthroughCatalog(schema_version=cast(Any, schema_version), profiles=(), rules=())
