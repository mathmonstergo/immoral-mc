import json
import operator
from pathlib import Path
from typing import Any, cast

import pytest

from immortal_mmo.cultivation.technique_catalog import (
    EquippedItemRequirement,
    TechniqueCatalog,
    TechniqueDefinition,
    TechniqueEffect,
    TechniqueEffectDefinition,
    TechniquePrerequisite,
    load_technique_catalog,
)

CATALOG_PATH = (
    Path(__file__).parents[2] / "src" / "immortal_mmo" / "cultivation" / "techniques.json"
)


@pytest.fixture
def catalog() -> TechniqueCatalog:
    return load_technique_catalog(CATALOG_PATH)


def test_seeded_techniques_preserve_common_identity_and_groups(catalog: TechniqueCatalog) -> None:
    expected = {
        "GF_YinqiShu_01": ("引气术", "qi", "练气", 1, "辅助"),
        "Gongfa_68726c": ("冰冻术", "qi", "练气", 7, "攻击"),
        "Gongfa_b8d7e3": ("缠绕术", "qi", "练气", 7, "控制"),
        "Gongfa_6fcf01": ("地刺术", "qi", "练气", 9, "攻击"),
        "Gongfa_eff4d0": ("火弹术", "qi", "练气", 3, "攻击"),
        "GF_RanxueZhan_01": ("燃血斩", "level:14", "筑基", 14, "攻击"),
        "Gongfa_8c1470": ("灵力针刺", "level:14", "筑基", 14, "攻击"),
        "Gongfa_Fenglie_01": ("风裂遁刃诀", "level:14", "筑基", 14, "攻击"),
    }

    assert set(catalog.techniques) == set(expected)
    for technique_id, values in expected.items():
        technique = catalog.technique(technique_id)
        assert (
            technique.name,
            technique.group,
            technique.major_realm,
            technique.minimum_player_level,
            technique.category,
        ) == values
        assert technique.max_layer == 13
    assert catalog.group_retention_cap("qi") == 9
    assert catalog.group_retention_cap("level:14") == 5


def test_techniques_have_canonical_time_weights(catalog: TechniqueCatalog) -> None:
    assert catalog.technique("GF_YinqiShu_01").time_weight == 1
    assert catalog.technique("GF_RanxueZhan_01").time_weight == 2


def test_effect_projection_is_typed_and_layer_aware(catalog: TechniqueCatalog) -> None:
    effects = catalog.technique("Gongfa_68726c").project_effects(8)

    assert effects
    assert all(isinstance(effect, TechniqueEffect) for effect in effects)
    attack = next(effect for effect in effects if effect.attribute == "attack")
    assert attack.value == pytest.approx(1.38)
    assert attack.layer == 8
    assert attack.status is None


def test_zero_layer_has_no_projected_effects(catalog: TechniqueCatalog) -> None:
    assert catalog.technique("Gongfa_68726c").project_effects(0) == ()

    with pytest.raises(ValueError, match="0 through 13"):
        catalog.technique("Gongfa_68726c").project_effects(-1)


def test_technique_models_and_views_are_immutable(catalog: TechniqueCatalog) -> None:
    assert TechniqueDefinition.__dataclass_params__.frozen is True
    assert TechniquePrerequisite.__dataclass_params__.frozen is True
    assert EquippedItemRequirement.__dataclass_params__.frozen is True
    with pytest.raises((AttributeError, TypeError)):
        catalog.schema_version = 2
    with pytest.raises(TypeError):
        operator.setitem(catalog.techniques, "new", catalog.technique("GF_YinqiShu_01"))


def test_constructor_rejects_duplicate_ids_and_group_overflow() -> None:
    definition = TechniqueDefinition(
        technique_id="one",
        name="One",
        description="desc",
        group="qi",
        major_realm="练气",
        time_weight=1,
        max_layer=13,
        required_elements=(),
        minimum_player_level=1,
        prerequisites=(),
        equipped_item_requirements=(),
        category="辅助",
        effects=(),
    )
    with pytest.raises(ValueError, match="Duplicate technique"):
        TechniqueCatalog(schema_version=1, techniques=(definition, definition))

    overflow = tuple(
        TechniqueDefinition(
            technique_id=f"qi-{index}",
            name="x",
            description="d",
            group="qi",
            major_realm="练气",
            time_weight=1,
            max_layer=13,
            required_elements=(),
            minimum_player_level=1,
            prerequisites=(),
            equipped_item_requirements=(),
            category="辅助",
            effects=(),
        )
        for index in range(10)
    )
    with pytest.raises(ValueError, match="retention cap"):
        TechniqueCatalog(schema_version=1, techniques=overflow)


@pytest.mark.parametrize("time_weight", [True, 1.0])
def test_constructor_rejects_non_integer_time_weight(time_weight: object) -> None:
    definition = TechniqueDefinition(
        technique_id="invalid-weight",
        name="Invalid",
        description="desc",
        group="qi",
        major_realm="练气",
        time_weight=cast(Any, time_weight),
        max_layer=13,
        required_elements=(),
        minimum_player_level=1,
        prerequisites=(),
        equipped_item_requirements=(),
        category="辅助",
        effects=(),
    )

    with pytest.raises(ValueError, match="time_weight.*integer"):
        TechniqueCatalog(schema_version=1, techniques=(definition,))


@pytest.mark.parametrize(
    ("field", "value"),
    [("layer_start", True), ("layer_start", 1.0), ("layer_end", True), ("layer_end", 13.0)],
)
def test_constructor_rejects_non_integer_effect_layer_bounds(field: str, value: object) -> None:
    bounds = {"layer_start": 1, "layer_end": 13}
    bounds[field] = cast(Any, value)
    effect = TechniqueEffectDefinition(
        attribute="attack",
        kind="attribute",
        status=None,
        effect_type="triggered",
        mode="percent",
        value=1.0,
        growth=0.0,
        chance=None,
        duration_rounds=None,
        stacks=None,
        layer_start=bounds["layer_start"],
        layer_end=bounds["layer_end"],
    )
    definition = TechniqueDefinition(
        technique_id="invalid-effect-layer",
        name="Invalid",
        description="desc",
        group="qi",
        major_realm="练气",
        time_weight=1,
        max_layer=13,
        required_elements=(),
        minimum_player_level=1,
        prerequisites=(),
        equipped_item_requirements=(),
        category="辅助",
        effects=(effect,),
    )

    with pytest.raises(ValueError, match="layer.*integer"):
        TechniqueCatalog(schema_version=1, techniques=(definition,))


@pytest.mark.parametrize("schema_version", [True, 1.0, 2])
def test_constructor_rejects_non_exact_schema_version(schema_version: object) -> None:
    with pytest.raises(ValueError, match="schema_version"):
        TechniqueCatalog(schema_version=cast(Any, schema_version), techniques=())


def test_loader_rejects_unknown_authored_progression_fields(tmp_path: Path) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["techniques"][0]["realm_layer_caps"] = {"foundation": 6}
    path = tmp_path / "techniques.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="realm_layer_caps"):
        load_technique_catalog(path)


def test_loader_rejects_boolean_and_unknown_effect_fields(tmp_path: Path) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["techniques"][0]["minimum_player_level"] = True
    path = tmp_path / "techniques.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="minimum_player_level.*integer"):
        load_technique_catalog(path)

    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["techniques"][0]["effects"][0]["mystery"] = 1
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="mystery"):
        load_technique_catalog(path)


@pytest.mark.parametrize(
    ("effect", "message"),
    [
        (
            {
                "attr": "attack",
                "status": "burn",
                "effect_type": "triggered",
                "mode": "percent",
                "value": 1,
            },
            "(?i)attribute.*status",
        ),
        (
            {"attr": "attack", "effect_type": "status", "mode": "chance", "value": 0.5},
            "(?i)attribute.*effect_type|attribute.*mode",
        ),
        (
            {
                "attr": "attack",
                "effect_type": "triggered",
                "mode": "percent",
                "value": 1,
                "chance": 0.5,
            },
            "(?i)chance.*mode",
        ),
        (
            {
                "kind": "status",
                "status": "burn",
                "effect_type": "cost",
                "mode": "percent",
                "value": 0.5,
            },
            "(?i)status.*effect_type|status.*mode",
        ),
        (
            {
                "kind": "status",
                "status": "burn",
                "effect_type": "status",
                "mode": "percent",
                "value": 0.5,
            },
            "(?i)status.*mode",
        ),
    ],
)
def test_loader_rejects_illegal_effect_shape_combinations(
    tmp_path: Path, effect: dict[str, object], message: str
) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["techniques"][0]["effects"][0] = effect
    path = tmp_path / "techniques.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_technique_catalog(path)


@pytest.mark.parametrize(
    ("container", "field"),
    [("prerequisites", "min_layer"), ("equipped_item_requirements", "quantity")],
)
def test_loader_rejects_boolean_nested_integer_fields(
    tmp_path: Path, container: str, field: str
) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["techniques"][0][container] = [
        {"technique_id": "Gongfa_68726c", field: True}
        if container == "prerequisites"
        else {"item_id": "training_item", field: True}
    ]
    path = tmp_path / "techniques.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match=f"{field}.*integer"):
        load_technique_catalog(path)


def test_loader_rejects_group_realm_minimum_level_mismatch(tmp_path: Path) -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["techniques"][0]["group"] = "level:14"
    path = tmp_path / "techniques.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="group.*major_realm|minimum_player_level"):
        load_technique_catalog(path)


def test_loader_rejects_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "techniques.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_technique_catalog(path)
