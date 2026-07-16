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


def test_optional_qi_advance_is_empty_without_deleting_qi_investment() -> None:
    snapshot = project_progress(
        catalog=CATALOG,
        current_level=11,
        group_investments={"qi": 16_462},
        active_entry=entry(
            generation=10,
            source_level=10,
            target_level=11,
            source_group="qi",
            target_group="qi",
            source_floor=11_293,
            target_baseline=16_462,
            transition_kind="failure_advance",
        ),
        unrefined_reserve=0,
        revision=4,
    )
    assert snapshot.realized_total == 16_462
    assert snapshot.current_progress == 0


def test_invalidated_branch_never_rejoins_active_chain() -> None:
    first = entry(
        generation=1,
        source_level=1,
        target_level=2,
        source_group="qi",
        target_group="qi",
        source_floor=100,
        target_baseline=100,
    )
    invalid = entry(
        generation=2,
        source_level=2,
        target_level=3,
        source_group="qi",
        target_group="qi",
        source_floor=250,
        target_baseline=250,
        parent_entry_id=first.realm_entry_id,
        status="invalidated",
    )
    orphan = entry(
        generation=3,
        source_level=3,
        target_level=4,
        source_group="qi",
        target_group="qi",
        source_floor=475,
        target_baseline=475,
        parent_entry_id=invalid.realm_entry_id,
    )
    assert valid_active_chain((first, invalid, orphan), {"qi": 10_000}) == (first,)


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
        ),
        unrefined_reserve=0,
        revision=10,
    )
    assert snapshot.current_progress == 116_145_360
    assert snapshot.progress_full is True
    assert snapshot.can_advance is False
