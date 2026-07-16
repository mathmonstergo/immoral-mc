from dataclasses import dataclass
from uuid import UUID

from immortal_mmo.cultivation.models import RealmEntry
from immortal_mmo.cultivation.realm_catalog import RealmCatalog


@dataclass(frozen=True, slots=True)
class CultivationProgressSnapshot:
    current_level: int
    realm_name: str
    current_progress: int
    max_exp: int
    realized_total: int
    unrefined_reserve: int
    reserve_cap: int
    revision: int
    progress_full: bool
    reserve_full: bool
    can_advance: bool


def group_for_level(level: int) -> str:
    return "qi" if level <= 13 else f"level:{level}"


def project_progress(
    *,
    catalog: RealmCatalog,
    current_level: int,
    group_investments: dict[str, int],
    active_entry: RealmEntry | None,
    unrefined_reserve: int,
    revision: int,
) -> CultivationProgressSnapshot:
    level = catalog.level(current_level)
    target_group = group_for_level(current_level)
    group_total = group_investments.get(target_group, 0)
    baseline = 0
    if active_entry is not None and active_entry.target_level == current_level:
        baseline = 0 if active_entry.transition_kind == "reentry" else active_entry.target_baseline
    current_progress = min(max(group_total - baseline, 0), level.max_exp)
    progress_full = current_progress >= level.max_exp
    return CultivationProgressSnapshot(
        current_level=current_level,
        realm_name=level.name,
        current_progress=current_progress,
        max_exp=level.max_exp,
        realized_total=sum(group_investments.values()),
        unrefined_reserve=unrefined_reserve,
        reserve_cap=level.max_exp,
        revision=revision,
        progress_full=progress_full,
        reserve_full=unrefined_reserve >= level.max_exp,
        can_advance=progress_full and level.next_level_id is not None,
    )


def valid_active_chain(
    entries: tuple[RealmEntry, ...],
    group_investments: dict[str, int],
) -> tuple[RealmEntry, ...]:
    valid: list[RealmEntry] = []
    expected_parent: UUID | None = None
    for entry in sorted(entries, key=lambda item: item.generation):
        if entry.status != "active" or entry.parent_entry_id != expected_parent:
            break
        if group_investments.get(entry.source_group, 0) < entry.source_floor:
            break
        valid.append(entry)
        expected_parent = entry.realm_entry_id
    return tuple(valid)
