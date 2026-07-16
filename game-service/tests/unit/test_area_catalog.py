import json
import operator
from pathlib import Path

import pytest

from immortal_mmo.cultivation.area_catalog import AreaCatalog, AreaDefinition, load_area_catalog

CATALOG_PATH = Path(__file__).parents[2] / "src" / "immortal_mmo" / "cultivation" / "areas.json"


@pytest.fixture
def catalog() -> AreaCatalog:
    return load_area_catalog(CATALOG_PATH)


def test_seeded_areas_match_approved_basis_points(catalog: AreaCatalog) -> None:
    assert catalog.area("neutral_training_ground").speed_basis_points == 10_000
    assert catalog.area("neutral_training_ground").yield_basis_points == 10_000
    accelerated = catalog.area("accelerated_cave")
    rich = catalog.area("rich_spirit_vein")
    assert (accelerated.speed_basis_points, accelerated.yield_basis_points) == (20_000, 10_000)
    assert (rich.speed_basis_points, rich.yield_basis_points) == (10_000, 15_000)


def test_area_catalog_is_immutable(catalog: AreaCatalog) -> None:
    assert AreaDefinition.__dataclass_params__.frozen is True
    with pytest.raises(TypeError):
        operator.setitem(catalog.areas, "other", catalog.area("neutral_training_ground"))
    with pytest.raises((AttributeError, TypeError)):
        catalog.schema_version = 2


@pytest.mark.parametrize("value", [0, -1, 100_001, True, 1.0])
def test_area_constructor_rejects_invalid_basis_points(value: object) -> None:
    with pytest.raises(ValueError, match="basis_points"):
        AreaCatalog(
            schema_version=1,
            areas=(AreaDefinition("test", "Test", value, 10_000),),  # type: ignore[arg-type]
        )


def test_area_catalog_rejects_duplicate_ids_and_unknown_fields(tmp_path: Path) -> None:
    definition = AreaDefinition("same", "Same", 10_000, 10_000)
    with pytest.raises(ValueError, match="Duplicate area"):
        AreaCatalog(schema_version=1, areas=(definition, definition))

    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    document["areas"][0]["unexpected"] = 1
    path = tmp_path / "areas.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected"):
        load_area_catalog(path)
