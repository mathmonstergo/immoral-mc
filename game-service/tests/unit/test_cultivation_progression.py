from pathlib import Path
from uuid import UUID

from immortal_mmo.cultivation.models import RealmEntry
from immortal_mmo.cultivation.progression import project_progress, valid_active_chain
from immortal_mmo.cultivation.realm_catalog import load_realm_catalog

CATALOG = load_realm_catalog(
    Path(__file__).resolve().parents[2] / "src/immortal_mmo/cultivation/realm_catalog.json"
)


def entry(
    *,
    generation: int,
    source_level: int,
    target_level: int,
    source_group: str,
    target_group: str,
    source_floor: int,
    target_baseline: int,
    transition_kind: str = "adjacent",
    parent_entry_id: UUID | None = None,
    status: str = "active",
) -> RealmEntry:
    return RealmEntry(
        realm_entry_id=UUID(int=generation),
        life_id=UUID(int=100),
        generation=generation,
        parent_entry_id=parent_entry_id,
        source_level=source_level,
        target_level=target_level,
        source_group=source_group,
        target_group=target_group,
        source_floor=source_floor,
        target_baseline=target_baseline,
        transition_kind=transition_kind,
        transition_session_id=None,
        status=status,
        invalidated_at=None,
    )


def test_mortal_projection_uses_fifty_point_entry_stage() -> None:
    snapshot = project_progress(
        catalog=CATALOG,
        current_level=0,
        group_investments={"qi": 49},
        active_entry=None,
        unrefined_reserve=25,
        revision=2,
    )

    assert snapshot.realm_name == "凡人"
    assert snapshot.current_progress == 49
    assert snapshot.max_exp == 50
    assert snapshot.reserve_cap == 50
    assert snapshot.progress_full is False
    assert snapshot.can_advance is False


def test_training_old_group_changes_lifetime_not_current_bar() -> None:
    snapshot = project_progress(
        catalog=CATALOG,
        current_level=14,
        group_investments={"qi": 20_000, "level:14": 1_000},
        active_entry=entry(
            generation=1,
            source_level=13,
            target_level=14,
            source_group="qi",
            target_group="level:14",
            source_floor=9_420,
            target_baseline=0,
            transition_kind="breakthrough",
        ),
        unrefined_reserve=10,
        revision=3,
    )
    assert snapshot.realized_total == 21_000
    assert snapshot.current_progress == 1_000


def test_first_entry_is_empty_but_reentry_restores_retained_target_group() -> None:
    first = project_progress(
        catalog=CATALOG,
        current_level=14,
        group_investments={"level:14": 7_000},
        active_entry=entry(
            generation=1,
            source_level=13,
            target_level=14,
            source_group="qi",
            target_group="level:14",
            source_floor=9_420,
            target_baseline=7_000,
            transition_kind="breakthrough",
        ),
        unrefined_reserve=0,
        revision=1,
    )
    reentry = project_progress(
        catalog=CATALOG,
        current_level=14,
        group_investments={"level:14": 7_000},
        active_entry=entry(
            generation=2,
            source_level=13,
            target_level=14,
            source_group="qi",
            target_group="level:14",
            source_floor=9_420,
            target_baseline=7_000,
            transition_kind="reentry",
        ),
        unrefined_reserve=0,
        revision=2,
    )
    assert first.current_progress == 0
    assert reentry.current_progress == 7_000


def test_same_group_reentry_projects_from_target_baseline() -> None:
    snapshot = project_progress(
        catalog=CATALOG,
        current_level=1,
        group_investments={"qi": 100},
        active_entry=entry(
            generation=2,
            source_level=0,
            target_level=1,
            source_group="qi",
            target_group="qi",
            source_floor=50,
            target_baseline=50,
            transition_kind="reentry",
        ),
        unrefined_reserve=0,
        revision=2,
    )

    assert snapshot.current_progress == 50


def test_optional_qi_advance_is_empty_without_deleting_qi_investment() -> None:
    snapshot = project_progress(
        catalog=CATALOG,
        current_level=11,
        group_investments={"qi": 16_512},
        active_entry=entry(
            generation=10,
            source_level=10,
            target_level=11,
            source_group="qi",
            target_group="qi",
            source_floor=11_343,
            target_baseline=16_512,
            transition_kind="failure_advance",
        ),
        unrefined_reserve=0,
        revision=4,
    )
    assert snapshot.realized_total == 16_512
    assert snapshot.current_progress == 0


def test_invalidated_branch_never_rejoins_active_chain() -> None:
    first = entry(
        generation=1,
        source_level=0,
        target_level=1,
        source_group="qi",
        target_group="qi",
        source_floor=50,
        target_baseline=50,
    )
    invalid = entry(
        generation=2,
        source_level=1,
        target_level=2,
        source_group="qi",
        target_group="qi",
        source_floor=150,
        target_baseline=150,
        parent_entry_id=first.realm_entry_id,
        status="invalidated",
    )
    orphan = entry(
        generation=3,
        source_level=2,
        target_level=3,
        source_group="qi",
        target_group="qi",
        source_floor=300,
        target_baseline=300,
        parent_entry_id=invalid.realm_entry_id,
    )
    assert valid_active_chain((first, invalid, orphan), {"qi": 10_000}) == (first,)


def test_active_chain_without_mortal_root_is_rejected() -> None:
    rootless = entry(
        generation=1,
        source_level=1,
        target_level=2,
        source_group="qi",
        target_group="qi",
        source_floor=150,
        target_baseline=150,
    )

    assert valid_active_chain((rootless,), {"qi": 10_000}) == ()


def test_active_chain_stops_before_discontinuous_source_level() -> None:
    root = entry(
        generation=1,
        source_level=0,
        target_level=1,
        source_group="qi",
        target_group="qi",
        source_floor=50,
        target_baseline=50,
    )
    discontinuous = entry(
        generation=2,
        source_level=2,
        target_level=3,
        source_group="qi",
        target_group="qi",
        source_floor=300,
        target_baseline=300,
        parent_entry_id=root.realm_entry_id,
    )

    assert valid_active_chain((root, discontinuous), {"qi": 10_000}) == (root,)


def test_level_22_is_fillable_without_unlocking_level_23() -> None:
    snapshot = project_progress(
        catalog=CATALOG,
        current_level=22,
        group_investments={"level:22": 116_145_360},
        active_entry=entry(
            generation=22,
            source_level=21,
            target_level=22,
            source_group="level:21",
            target_group="level:22",
            source_floor=19_357_560,
            target_baseline=0,
            transition_kind="breakthrough",
        ),
        unrefined_reserve=0,
        revision=10,
    )
    assert snapshot.current_progress == 116_145_360
    assert snapshot.progress_full is True
    assert snapshot.can_advance is False
