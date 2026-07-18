import hashlib
import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from immortal_mmo.core.errors import ConflictError, NotFoundError, RuleViolationError
from immortal_mmo.core.uow import UnitOfWorkFactory
from immortal_mmo.cultivation.allocation import allocate_equal
from immortal_mmo.cultivation.area_catalog import AreaCatalog, load_area_catalog
from immortal_mmo.cultivation.breakthrough import resolve_breakthrough_decision
from immortal_mmo.cultivation.breakthrough_catalog import (
    BreakthroughCatalog,
    load_breakthrough_catalog,
)
from immortal_mmo.cultivation.errors import (
    CultivationSeclusionConflictError,
    CultivationSeclusionNotFoundError,
    CultivationSeclusionRuleError,
)
from immortal_mmo.cultivation.models import (
    BreakthroughTechniqueDebit,
    CultivationSession,
    RealmEntry,
    SessionTechnique,
    TechniqueInvestmentChange,
)
from immortal_mmo.cultivation.penalties import (
    allocate_breakthrough_penalty,
    breakthrough_penalty,
)
from immortal_mmo.cultivation.progression import (
    group_for_level,
    project_progress,
    valid_active_chain,
)
from immortal_mmo.cultivation.realm_catalog import RealmCatalog
from immortal_mmo.cultivation.repository import ActiveCultivationSessionExists
from immortal_mmo.cultivation.schemas import (
    BreakthroughSnapshotResponse,
    CultivationSnapshotResponse,
    ItemAdjustmentResponse,
    SeclusionSnapshotResponse,
    TechniqueMutationResponse,
    TechniqueSnapshotResponse,
)
from immortal_mmo.cultivation.seclusion import (
    CULTIVATION_CYCLE_SECONDS,
    base_cycle_rate,
    cumulative_cycle_budget,
    full_mastery_seconds_for_major_realm,
    reserve_required_for_retained,
    scaled_cycle_rate,
    speed_weight_for_major_realm,
)
from immortal_mmo.cultivation.technique_catalog import (
    TechniqueCatalog,
    load_technique_catalog,
)
from immortal_mmo.item.errors import ItemInsufficientQuantityError
from immortal_mmo.item.models import (
    InsufficientItemQuantity,
    ItemConsumptionType,
    ItemOperationConflict,
)
from immortal_mmo.player.service import PlayerAccountNotFoundError, PlayerLifecycleError

DEFAULT_TRANSFER_PROFILES = {
    "Trans_Gongfa_01": 5_000,
    "Trans_Gongfa_02": 8_000,
}
TECHNIQUE_MUTATION_CONTENT_VERSION = "technique-mutation:v1"
BREAKTHROUGH_CONTENT_VERSION = "breakthrough:v1"


class CultivationMutationConflictError(ConflictError):
    code = "cultivation.technique_mutation_conflict"
    message = "Technique mutation conflicts with current cultivation state."


class CultivationTechniqueNotFoundError(NotFoundError):
    code = "cultivation.technique_not_found"
    message = "Life technique was not found."


class CultivationTechniqueRuleError(RuleViolationError):
    code = "cultivation.technique_rule_violation"
    message = "Technique mutation is not allowed."


class CultivationBreakthroughConflictError(ConflictError):
    code = "cultivation.breakthrough_conflict"
    message = "Breakthrough conflicts with current cultivation state."


class CultivationBreakthroughRuleError(RuleViolationError):
    code = "cultivation.breakthrough_rule_violation"
    message = "Breakthrough requirements are not satisfied."


class CultivationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        realm_catalog: RealmCatalog,
        *,
        area_catalog: AreaCatalog | None = None,
        breakthrough_catalog: BreakthroughCatalog | None = None,
        technique_catalog: TechniqueCatalog | None = None,
        clock: Callable[[], datetime] | None = None,
        transfer_profiles: Mapping[str, int] | None = None,
        basis_point_roll: Callable[[], int] | None = None,
        entropy_source: Callable[[], bytes] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._realm_catalog = realm_catalog
        self._area_catalog = area_catalog or load_area_catalog(
            Path(__file__).resolve().parent / "areas.json"
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._breakthrough_catalog = breakthrough_catalog or load_breakthrough_catalog(
            Path(__file__).resolve().parent / "breakthrough_rules.json"
        )
        self._technique_catalog = technique_catalog or load_technique_catalog(
            Path(__file__).resolve().parent / "techniques.json"
        )
        self._basis_point_roll = basis_point_roll or (
            lambda: secrets.randbelow(10_000) + 1
        )
        self._entropy_source = entropy_source or (lambda: secrets.token_bytes(32))
        configured_profiles = transfer_profiles or DEFAULT_TRANSFER_PROFILES
        if not configured_profiles or any(
            not profile_id
            or isinstance(basis_points, bool)
            or not isinstance(basis_points, int)
            or not 0 <= basis_points <= 10_000
            for profile_id, basis_points in configured_profiles.items()
        ):
            raise ValueError("Technique transfer profiles must use basis points from 0 to 10000")
        self._transfer_profiles = dict(configured_profiles)

    async def current_life_snapshot(self, account_id: UUID) -> CultivationSnapshotResponse:
        async with self._uow_factory() as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=False)
            if life is None:
                raise PlayerLifecycleError()
            state = await uow.cultivation.get_or_create_state(life.life_id, for_update=False)
            group_investments = await uow.cultivation.get_group_investments(life.life_id)
            chain = await uow.cultivation.get_active_realm_chain(life.life_id, for_update=False)
            chain = valid_active_chain(chain, group_investments)
            snapshot = project_progress(
                catalog=self._realm_catalog,
                current_level=state.current_level,
                group_investments=group_investments,
                active_entry=chain[-1] if chain else None,
                unrefined_reserve=state.unrefined_cultivation,
                revision=state.revision,
            )
            await uow.commit()
        return CultivationSnapshotResponse(**asdict(snapshot))

    async def list_techniques(
        self, account_id: UUID
    ) -> tuple[TechniqueSnapshotResponse, ...]:
        async with self._uow_factory() as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=False)
            if life is None:
                raise PlayerLifecycleError()
            techniques = await uow.cultivation.get_techniques(
                life.life_id, for_update=False
            )
            await uow.rollback()
        snapshots: list[TechniqueSnapshotResponse] = []
        for technique in techniques:
            definition = self._technique_catalog.techniques.get(
                technique.technique_id
            )
            snapshots.append(
                TechniqueSnapshotResponse(
                    life_technique_id=technique.life_technique_id,
                    technique_id=technique.technique_id,
                    display_name=(
                        technique.technique_id
                        if definition is None
                        else definition.name
                    ),
                    definition_version=technique.definition_version,
                    group_code=technique.group_code,
                    major_realm=technique.major_realm,
                    attribute_codes=(
                        () if definition is None else definition.required_elements
                    ),
                    invested_amount=technique.invested_amount,
                    max_investment=technique.max_investment,
                    current_layer=technique.current_layer,
                    status=technique.status,
                )
            )
        return tuple(snapshots)

    async def abandon_technique(
        self,
        *,
        account_id: UUID,
        life_technique_id: UUID,
        idempotency_key: UUID,
    ) -> TechniqueMutationResponse:
        return await self._mutate_technique(
            account_id=account_id,
            source_technique_id=life_technique_id,
            target_technique_id=None,
            transfer_profile_id=None,
            idempotency_key=idempotency_key,
        )

    async def transfer_technique(
        self,
        *,
        account_id: UUID,
        source_technique_id: UUID,
        target_technique_id: UUID,
        transfer_profile_id: str,
        idempotency_key: UUID,
    ) -> TechniqueMutationResponse:
        if source_technique_id == target_technique_id:
            raise CultivationTechniqueRuleError("Source and target techniques must differ")
        if transfer_profile_id not in self._transfer_profiles:
            raise CultivationTechniqueRuleError("Unknown technique transfer profile")
        return await self._mutate_technique(
            account_id=account_id,
            source_technique_id=source_technique_id,
            target_technique_id=target_technique_id,
            transfer_profile_id=transfer_profile_id,
            idempotency_key=idempotency_key,
        )

    async def _mutate_technique(
        self,
        *,
        account_id: UUID,
        source_technique_id: UUID,
        target_technique_id: UUID | None,
        transfer_profile_id: str | None,
        idempotency_key: UUID,
    ) -> TechniqueMutationResponse:
        operation_kind = "transfer" if target_technique_id is not None else "abandonment"
        request_payload = {
            "operation_kind": operation_kind,
            "source_technique_id": str(source_technique_id),
            "target_technique_id": (
                None if target_technique_id is None else str(target_technique_id)
            ),
            "transfer_profile_id": transfer_profile_id,
        }
        request_fingerprint = _request_fingerprint(request_payload)
        now = self._clock()
        async with self._uow_factory() as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=True)
            if life is None:
                raise PlayerLifecycleError()
            replay = await uow.cultivation.get_session_by_idempotency(
                life.life_id, idempotency_key
            )
            if replay is not None:
                if (
                    replay.session_kind != "technique_mutation"
                    or replay.request_fingerprint != request_fingerprint
                ):
                    raise CultivationMutationConflictError(
                        "Technique mutation idempotency key was reused"
                    )
                frozen_response = replay.frozen_snapshot.get("response")
                if not isinstance(frozen_response, dict):
                    raise RuntimeError("Technique mutation replay has no frozen response")
                await uow.rollback()
                return TechniqueMutationResponse.model_validate(frozen_response)

            state = await uow.cultivation.get_or_create_state(life.life_id, for_update=True)
            if state.active_session_id is not None:
                active_session = await uow.cultivation.get_session(
                    state.active_session_id, for_update=True
                )
                if active_session is None:
                    raise RuntimeError("Cultivation state points to an unknown active session")
                if active_session.status in {"pending", "active"}:
                    session_label = (
                        "breakthrough"
                        if active_session.session_kind == "breakthrough"
                        else "seclusion"
                    )
                    raise CultivationMutationConflictError(
                        f"Technique mutation is blocked by an active {session_label}"
                    )

            requested_ids = (
                (source_technique_id,)
                if target_technique_id is None
                else (source_technique_id, target_technique_id)
            )
            techniques = await uow.cultivation.get_techniques(
                life.life_id, requested_ids, for_update=True
            )
            by_id = {item.life_technique_id: item for item in techniques}
            source = by_id.get(source_technique_id)
            if source is None:
                raise CultivationTechniqueNotFoundError("Source life technique was not found")
            if source.status != "active":
                raise CultivationTechniqueRuleError("Source life technique is not active")
            target = None
            if target_technique_id is not None:
                target = by_id.get(target_technique_id)
                if target is None:
                    raise CultivationTechniqueNotFoundError(
                        "Target life technique was not found"
                    )
                if target.status != "active":
                    raise CultivationTechniqueRuleError("Target life technique is not active")

            operation_id = uuid4()
            operation_session = CultivationSession(
                session_id=operation_id,
                life_id=life.life_id,
                session_kind="technique_mutation",
                status="completed",
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                area_id=None,
                content_version=TECHNIQUE_MUTATION_CONTENT_VERSION,
                source_level=state.current_level,
                target_level=None,
                frozen_snapshot={"request": request_payload},
                cumulative_elapsed_seconds=0,
                cumulative_generated=0,
                cumulative_reserve_consumed=0,
                cumulative_retained=0,
                started_at=now,
                completes_at=now,
                settled_at=now,
                revision=1,
            )
            await uow.cultivation.insert_session(operation_session)

            removed_amount = source.invested_amount
            transferred_amount = 0
            changes: list[TechniqueInvestmentChange] = []
            if removed_amount > 0:
                changes.append(
                    TechniqueInvestmentChange(
                        source_technique_id,
                        -removed_amount,
                        "transfer_out" if target is not None else "abandonment",
                    )
                )
            if target is not None:
                assert transfer_profile_id is not None
                preserved = (
                    removed_amount * self._transfer_profiles[transfer_profile_id] // 10_000
                )
                transferred_amount = min(
                    preserved,
                    target.max_investment - target.invested_amount,
                )
                if transferred_amount > 0:
                    changes.append(
                        TechniqueInvestmentChange(
                            target.life_technique_id,
                            transferred_amount,
                            "transfer_in",
                        )
                    )
            if changes:
                state = await uow.cultivation.apply_technique_investments(
                    life_id=life.life_id,
                    operation_id=operation_id,
                    session_id=operation_id,
                    changes=tuple(changes),
                    occurred_at=now,
                )
            state = await uow.cultivation.abandon_technique(
                life_id=life.life_id,
                life_technique_id=source_technique_id,
            )

            group_investments = await uow.cultivation.get_group_investments(life.life_id)
            active_chain = await uow.cultivation.get_active_realm_chain(
                life.life_id, for_update=True
            )
            valid_chain = valid_active_chain(active_chain, group_investments)
            if len(valid_chain) != len(active_chain):
                current_level = valid_chain[-1].target_level if valid_chain else 1
                state = await uow.cultivation.invalidate_realm_suffix(
                    life_id=life.life_id,
                    retained_entry_ids=tuple(
                        entry.realm_entry_id for entry in valid_chain
                    ),
                    current_level=current_level,
                    invalidated_at=now,
                )
            snapshot = project_progress(
                catalog=self._realm_catalog,
                current_level=state.current_level,
                group_investments=group_investments,
                active_entry=valid_chain[-1] if valid_chain else None,
                unrefined_reserve=state.unrefined_cultivation,
                revision=state.revision,
            )
            response = TechniqueMutationResponse(
                operation_id=operation_id,
                operation_kind=operation_kind,
                source_technique_id=source_technique_id,
                target_technique_id=target_technique_id,
                removed_amount=removed_amount,
                transferred_amount=transferred_amount,
                destroyed_amount=removed_amount - transferred_amount,
                cultivation=CultivationSnapshotResponse(**asdict(snapshot)),
            )
            await uow.cultivation.update_session_frozen_snapshot(
                session_id=operation_id,
                frozen_snapshot={
                    "request": request_payload,
                    "response": response.model_dump(mode="json"),
                },
            )
            await uow.commit()
        return response

    async def adjust_item(
        self,
        *,
        account_id: UUID,
        item_code: str,
        delta_quantity: int,
        idempotency_key: UUID,
    ) -> ItemAdjustmentResponse:
        if item_code != "foundation_pill":
            raise CultivationTechniqueRuleError("Unsupported administrative item")
        if delta_quantity <= 0:
            raise CultivationTechniqueRuleError("Item adjustment must be positive")
        async with self._uow_factory() as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=True)
            if life is None:
                raise PlayerLifecycleError()
            try:
                entry = await uow.items.adjust(
                    life_id=life.life_id,
                    item_code=item_code,
                    delta_quantity=delta_quantity,
                    operation_id=idempotency_key,
                    occurred_at=self._clock(),
                )
            except ItemOperationConflict as error:
                raise CultivationMutationConflictError(
                    "Item adjustment idempotency key was reused"
                ) from error
            if entry.delta_quantity != delta_quantity:
                raise CultivationMutationConflictError(
                    "Item adjustment idempotency key was reused"
                )
            await uow.commit()
        return ItemAdjustmentResponse(
            item_code=item_code,
            delta_quantity=delta_quantity,
            balance_after=entry.balance_after,
        )

    async def start_breakthrough(
        self,
        *,
        account_id: UUID,
        pill_count: int,
        idempotency_key: UUID,
    ) -> BreakthroughSnapshotResponse:
        request_fingerprint = _request_fingerprint(
            {"rule_id": "qi_to_foundation", "pill_count": pill_count}
        )
        now = self._clock()
        async with self._uow_factory() as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            facts = await uow.players.get_current_life_facts(account_id, for_update=True)
            if facts is None:
                raise PlayerLifecycleError()
            replay = await uow.cultivation.get_session_by_idempotency(
                facts.life_id, idempotency_key
            )
            if replay is not None:
                if (
                    replay.session_kind != "breakthrough"
                    or replay.request_fingerprint != request_fingerprint
                ):
                    raise CultivationBreakthroughConflictError(
                        "Breakthrough idempotency key was reused"
                    )
                await uow.rollback()
                return _breakthrough_snapshot(replay)

            state = await uow.cultivation.get_or_create_state(
                facts.life_id, for_update=True
            )
            if state.active_session_id is not None:
                raise CultivationBreakthroughConflictError(
                    "Another cultivation session is already active"
                )
            rule = self._breakthrough_catalog.rule("qi_to_foundation")
            if state.current_level not in rule.source_levels:
                raise CultivationBreakthroughRuleError(
                    "Current realm is not eligible for foundation breakthrough"
                )
            if facts.spirit_root is None:
                raise CultivationBreakthroughRuleError(
                    "Spirit root must be detected before breakthrough"
                )
            group_investments = await uow.cultivation.get_group_investments(
                facts.life_id
            )
            chain = await uow.cultivation.get_active_realm_chain(
                facts.life_id, for_update=True
            )
            valid_chain = valid_active_chain(chain, group_investments)
            progress = project_progress(
                catalog=self._realm_catalog,
                current_level=state.current_level,
                group_investments=group_investments,
                active_entry=valid_chain[-1] if valid_chain else None,
                unrefined_reserve=state.unrefined_cultivation,
                revision=state.revision,
            )
            if not progress.progress_full:
                raise CultivationBreakthroughRuleError(
                    "Current realm cultivation must be full"
                )
            primary_roll = self._basis_point_roll()
            secondary_roll = self._basis_point_roll()
            try:
                decision = resolve_breakthrough_decision(
                    catalog=self._breakthrough_catalog,
                    rule=rule,
                    source_level=state.current_level,
                    root_count=len(facts.spirit_root.base_element_codes),
                    pill_count=pill_count,
                    primary_roll=primary_roll,
                    secondary_roll=secondary_roll,
                )
            except (KeyError, ValueError) as error:
                raise CultivationBreakthroughRuleError(str(error)) from error

            techniques = tuple(
                technique
                for technique in await uow.cultivation.get_techniques(
                    facts.life_id, for_update=True
                )
                if technique.status == "active"
                and technique.group_code == group_for_level(state.current_level)
                and technique.invested_amount > 0
            )
            if not techniques:
                raise CultivationBreakthroughRuleError(
                    "Breakthrough requires invested backing techniques"
                )
            source_max_exp = self._realm_catalog.level(state.current_level).max_exp
            penalty_total = breakthrough_penalty(source_max_exp)
            entropy = self._entropy_source()
            allocations = allocate_breakthrough_penalty(
                total=penalty_total,
                investments={
                    technique.life_technique_id: technique.invested_amount
                    for technique in techniques
                },
                entropy=entropy,
            )
            session_id = uuid4()
            source_floor = (
                self._realm_catalog.qi_cumulative_totals()[state.current_level]
                if state.current_level <= 13
                else progress.current_progress
            )
            frozen_snapshot: dict[str, object] = {
                "rule_id": decision.rule_id,
                "profile_id": decision.profile_id,
                "pill_count": decision.pill_count,
                "success_basis_points": decision.success_basis_points,
                "primary_roll": decision.primary_roll,
                "secondary_roll": decision.secondary_roll,
                "outcome": decision.outcome,
                "failure_target_level": decision.failure_target_level,
                "root_quality": facts.spirit_root.quality_code,
                "root_count": len(facts.spirit_root.base_element_codes),
                "source_max_exp": source_max_exp,
                "source_floor": source_floor,
                "source_group": group_for_level(state.current_level),
                "penalty_total": penalty_total,
                "penalty_strategy": "hmac_sha256_v1",
                "penalty_entropy": entropy.hex(),
                "technique_debits": {
                    str(technique_id): amount
                    for technique_id, amount in allocations.items()
                },
            }
            session = CultivationSession(
                session_id=session_id,
                life_id=facts.life_id,
                session_kind="breakthrough",
                status="pending",
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                area_id=None,
                content_version=BREAKTHROUGH_CONTENT_VERSION,
                source_level=state.current_level,
                target_level=rule.target_level,
                frozen_snapshot=frozen_snapshot,
                cumulative_elapsed_seconds=0,
                cumulative_generated=0,
                cumulative_reserve_consumed=0,
                cumulative_retained=0,
                started_at=now,
                completes_at=now + timedelta(seconds=rule.duration_seconds),
                settled_at=None,
                revision=1,
            )
            try:
                await uow.cultivation.start_session(session, ())
            except ActiveCultivationSessionExists as error:
                raise CultivationBreakthroughConflictError(
                    "Another cultivation session is already active"
                ) from error
            await uow.cultivation.store_breakthrough_debits(
                tuple(
                    BreakthroughTechniqueDebit(
                        session_id=session_id,
                        life_id=facts.life_id,
                        life_technique_id=technique.life_technique_id,
                        allocated_amount=allocations[technique.life_technique_id],
                        balance_before=technique.invested_amount,
                        balance_after=(
                            technique.invested_amount
                            - allocations[technique.life_technique_id]
                        ),
                    )
                    for technique in techniques
                )
            )
            try:
                await uow.items.consume(
                    life_id=facts.life_id,
                    item_code=rule.required_item_id,
                    quantity=pill_count,
                    operation_id=session_id,
                    entry_type=ItemConsumptionType.BREAKTHROUGH,
                    session_id=session_id,
                    occurred_at=now,
                )
            except InsufficientItemQuantity as error:
                raise ItemInsufficientQuantityError() from error
            except ItemOperationConflict as error:
                raise CultivationBreakthroughConflictError(
                    "Breakthrough item operation identity conflicts with existing history"
                ) from error
            await uow.commit()
        return _breakthrough_snapshot(session)

    async def breakthrough_status(
        self, *, account_id: UUID, session_id: UUID
    ) -> BreakthroughSnapshotResponse:
        async with self._uow_factory() as uow:
            life = await uow.players.get_current_life(account_id, for_update=False)
            if life is None:
                raise PlayerLifecycleError()
            session = await uow.cultivation.get_session(session_id, for_update=False)
            if (
                session is None
                or session.life_id != life.life_id
                or session.session_kind != "breakthrough"
            ):
                raise CultivationTechniqueNotFoundError(
                    "Breakthrough session was not found"
                )
            await uow.rollback()
        return _breakthrough_snapshot(session)

    async def settle_breakthrough(
        self, *, account_id: UUID, session_id: UUID
    ) -> BreakthroughSnapshotResponse:
        now = self._clock()
        async with self._uow_factory() as uow:
            life = await uow.players.get_current_life(account_id, for_update=True)
            if life is None:
                raise PlayerLifecycleError()
            session = await uow.cultivation.get_session(session_id, for_update=True)
            if (
                session is None
                or session.life_id != life.life_id
                or session.session_kind != "breakthrough"
            ):
                raise CultivationTechniqueNotFoundError(
                    "Breakthrough session was not found"
                )
            if session.status not in {"pending", "active"}:
                await uow.rollback()
                return _breakthrough_snapshot(session)
            if now < session.completes_at:
                raise CultivationBreakthroughRuleError(
                    "Breakthrough session has not completed"
                )
            outcome = str(session.frozen_snapshot["outcome"])
            group_investments = await uow.cultivation.get_group_investments(life.life_id)
            active_chain = await uow.cultivation.get_active_realm_chain(
                life.life_id, for_update=True
            )
            parent = active_chain[-1] if active_chain else None
            if outcome in {"success", "failure_advance"}:
                target_level = (
                    int(session.target_level)
                    if outcome == "success"
                    else int(session.frozen_snapshot["failure_target_level"])
                )
                target_group = group_for_level(target_level)
                reentry = await uow.cultivation.has_realm_transition_history(
                    life.life_id,
                    source_level=session.source_level,
                    target_level=target_level,
                )
                entry = RealmEntry(
                    realm_entry_id=uuid4(),
                    life_id=life.life_id,
                    generation=(
                        await uow.cultivation.get_latest_realm_generation(life.life_id)
                    )
                    + 1,
                    parent_entry_id=None if parent is None else parent.realm_entry_id,
                    source_level=session.source_level,
                    target_level=target_level,
                    source_group=str(session.frozen_snapshot["source_group"]),
                    target_group=target_group,
                    source_floor=int(session.frozen_snapshot["source_floor"]),
                    target_baseline=group_investments.get(target_group, 0),
                    transition_kind=(
                        "reentry"
                        if outcome == "success" and reentry
                        else "breakthrough"
                        if outcome == "success"
                        else "failure_advance"
                    ),
                    transition_session_id=session_id,
                    status="active",
                    invalidated_at=None,
                )
                await uow.cultivation.append_realm_entry(entry)
            else:
                debits = await uow.cultivation.get_breakthrough_debits(session_id)
                changes = tuple(
                    TechniqueInvestmentChange(
                        debit.life_technique_id,
                        -debit.allocated_amount,
                        "breakthrough_penalty",
                    )
                    for debit in debits
                    if debit.allocated_amount > 0
                )
                if changes:
                    await uow.cultivation.apply_technique_investments(
                        life_id=life.life_id,
                        operation_id=session_id,
                        session_id=session_id,
                        changes=changes,
                        occurred_at=now,
                    )
                group_investments = await uow.cultivation.get_group_investments(
                    life.life_id
                )
                valid_chain = valid_active_chain(active_chain, group_investments)
                if len(valid_chain) != len(active_chain):
                    await uow.cultivation.invalidate_realm_suffix(
                        life_id=life.life_id,
                        retained_entry_ids=tuple(
                            entry.realm_entry_id for entry in valid_chain
                        ),
                        current_level=(
                            valid_chain[-1].target_level if valid_chain else 1
                        ),
                        invalidated_at=now,
                    )
            updated = await uow.cultivation.update_session_settlement(
                session_id=session_id,
                cumulative_elapsed_seconds=int(
                    max((now - session.started_at).total_seconds(), 0)
                ),
                cumulative_generated=session.cumulative_generated,
                cumulative_reserve_consumed=session.cumulative_reserve_consumed,
                cumulative_retained=session.cumulative_retained,
                status="completed" if outcome == "success" else "failed",
                settled_at=now,
            )
            await uow.commit()
        return _breakthrough_snapshot(updated)

    async def start_seclusion(
        self,
        *,
        account_id: UUID,
        area_id: str,
        technique_ids: tuple[UUID, ...],
        idempotency_key: UUID,
    ) -> SeclusionSnapshotResponse:
        if not 1 <= len(technique_ids) <= 5 or len(set(technique_ids)) != len(technique_ids):
            raise CultivationSeclusionRuleError(
                "Seclusion requires one to five unique techniques"
            )
        now = self._clock()
        request_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "area_id": area_id,
                    "technique_ids": sorted(str(value) for value in technique_ids),
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        async with self._uow_factory() as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=True)
            if life is None:
                raise PlayerLifecycleError()
            existing = await uow.cultivation.get_session_by_idempotency(
                life.life_id, idempotency_key
            )
            if existing is not None:
                if (
                    existing.session_kind != "ordinary"
                    or existing.request_fingerprint != request_fingerprint
                ):
                    raise CultivationSeclusionConflictError(
                        "Seclusion idempotency key was reused"
                    )
                await uow.rollback()
                return _seclusion_snapshot(existing)
            state = await uow.cultivation.get_or_create_state(
                life.life_id, for_update=True
            )
            if state.active_session_id is not None:
                raise CultivationSeclusionConflictError(
                    "Another cultivation session is already active"
                )
            try:
                area = self._area_catalog.area(area_id)
            except KeyError as error:
                raise CultivationSeclusionRuleError(str(error)) from error
            techniques = await uow.cultivation.get_techniques(
                life.life_id, technique_ids, for_update=True
            )
            if len(techniques) != len(technique_ids):
                raise CultivationSeclusionRuleError("Unknown selected technique")
            if len({item.group_code for item in techniques}) != 1:
                raise CultivationSeclusionRuleError(
                    "Selected techniques must share the same technique group"
                )
            if len({item.max_investment for item in techniques}) != 1:
                raise CultivationSeclusionRuleError(
                    "Selected techniques must share the same capacity"
                )
            if len({item.major_realm for item in techniques}) != 1:
                raise CultivationSeclusionRuleError(
                    "Selected technique group has inconsistent major realms"
                )
            if any(
                item.status != "active" or item.invested_amount >= item.max_investment
                for item in techniques
            ):
                raise CultivationSeclusionRuleError(
                    "Selected technique is not eligible for seclusion"
                )
            technique_group = techniques[0].group_code
            technique_capacity = techniques[0].max_investment
            technique_major_realm = techniques[0].major_realm
            player_major_realm = self._realm_catalog.level(state.current_level).major_realm
            try:
                full_seconds = full_mastery_seconds_for_major_realm(
                    technique_major_realm
                )
                player_speed_weight = speed_weight_for_major_realm(player_major_realm)
                technique_speed_weight = speed_weight_for_major_realm(
                    technique_major_realm
                )
            except ValueError as error:
                raise CultivationSeclusionRuleError(
                    "Seclusion uses an unsupported major realm"
                ) from error
            base_rate = base_cycle_rate(
                technique_capacity=technique_capacity,
                full_mastery_seconds=full_seconds,
            )
            cultivation_per_cycle = scaled_cycle_rate(
                base_rate=base_rate,
                player_speed_weight=player_speed_weight,
                technique_speed_weight=technique_speed_weight,
                area_speed_basis_points=area.speed_basis_points,
            )
            session_id = uuid4()
            session = CultivationSession(
                session_id=session_id,
                life_id=life.life_id,
                session_kind="ordinary",
                status="active",
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                area_id=area.area_id,
                content_version=self._area_catalog.revision,
                source_level=state.current_level,
                target_level=None,
                frozen_snapshot={
                    "area_version": area.version,
                    "cycle_seconds": CULTIVATION_CYCLE_SECONDS,
                    "technique_group": technique_group,
                    "technique_capacity": technique_capacity,
                    "full_mastery_seconds": full_seconds,
                    "base_cultivation_per_cycle": base_rate,
                    "player_major_realm": player_major_realm,
                    "player_speed_weight": player_speed_weight,
                    "technique_major_realm": technique_major_realm,
                    "technique_speed_weight": technique_speed_weight,
                    "speed_basis_points": area.speed_basis_points,
                    "yield_basis_points": area.yield_basis_points,
                    "cultivation_per_cycle": cultivation_per_cycle,
                },
                cumulative_elapsed_seconds=0,
                cumulative_generated=0,
                cumulative_reserve_consumed=0,
                cumulative_retained=0,
                started_at=now,
                completes_at=now + timedelta(seconds=CULTIVATION_CYCLE_SECONDS),
                settled_at=None,
                revision=1,
            )
            selections = tuple(
                SessionTechnique(
                    session_id=session_id,
                    life_id=life.life_id,
                    life_technique_id=item.life_technique_id,
                    definition_version=item.definition_version,
                    group_code=item.group_code,
                    major_realm=item.major_realm,
                    frozen_capacity=item.max_investment,
                    frozen_invested=item.invested_amount,
                )
                for item in techniques
            )
            try:
                await uow.cultivation.start_session(session, selections)
            except ActiveCultivationSessionExists as error:
                raise CultivationSeclusionConflictError(
                    "Another cultivation session is already active"
                ) from error
            await uow.commit()
        return _seclusion_snapshot(session)

    async def settle_seclusion(
        self, *, account_id: UUID, session_id: UUID
    ) -> SeclusionSnapshotResponse:
        now = self._clock()
        async with self._uow_factory() as uow:
            life = await uow.players.get_current_life(account_id, for_update=True)
            if life is None:
                raise PlayerLifecycleError()
            session = await uow.cultivation.get_session(session_id, for_update=True)
            if (
                session is None
                or session.life_id != life.life_id
                or session.session_kind != "ordinary"
            ):
                raise CultivationSeclusionNotFoundError()
            if session.status not in {"active", "pending"}:
                await uow.rollback()
                return _seclusion_snapshot(session)
            selections = await uow.cultivation.get_session_techniques(session_id)
            if not selections:
                raise CultivationSeclusionConflictError(
                    "Seclusion session has no selected techniques"
                )
            techniques = await uow.cultivation.get_techniques(
                life.life_id,
                tuple(item.life_technique_id for item in selections),
                for_update=True,
            )
            if len(techniques) != len(selections):
                raise CultivationSeclusionConflictError(
                    "Seclusion selected techniques are unavailable"
                )
            elapsed = max(int((now - session.started_at).total_seconds()), 0)
            if elapsed <= session.cumulative_elapsed_seconds:
                raise CultivationSeclusionConflictError(
                    "Seclusion has no new elapsed time to settle"
                )
            yield_points = int(session.frozen_snapshot["yield_basis_points"])
            cumulative_generated = cumulative_cycle_budget(
                elapsed_seconds=elapsed,
                cultivation_per_cycle=int(
                    session.frozen_snapshot["cultivation_per_cycle"]
                ),
                cycle_seconds=int(session.frozen_snapshot["cycle_seconds"]),
            )
            if cumulative_generated <= session.cumulative_generated:
                raise CultivationSeclusionConflictError(
                    "Seclusion has not generated new cultivation to settle"
                )
            selections_by_id = {item.life_technique_id: item for item in selections}
            initial_remaining: dict[UUID, int] = {}
            prior_allocations: dict[UUID, int] = {}
            for technique in techniques:
                selection = selections_by_id[technique.life_technique_id]
                if (
                    technique.max_investment != selection.frozen_capacity
                    or technique.invested_amount < selection.frozen_invested
                    or technique.invested_amount > selection.frozen_capacity
                ):
                    raise CultivationSeclusionConflictError(
                        "Seclusion technique state no longer matches its frozen snapshot"
                    )
                initial_remaining[technique.life_technique_id] = (
                    selection.frozen_capacity - selection.frozen_invested
                )
                prior_allocations[technique.life_technique_id] = (
                    technique.invested_amount - selection.frozen_invested
                )
            if sum(prior_allocations.values()) != session.cumulative_retained:
                raise CultivationSeclusionConflictError(
                    "Seclusion retained total does not match technique investments"
                )

            cumulative_capacity_budget = min(
                cumulative_generated,
                sum(initial_remaining.values()),
            )
            state = await uow.cultivation.get_or_create_state(life.life_id, for_update=True)
            total_available_reserve = (
                session.cumulative_reserve_consumed + state.unrefined_cultivation
            )
            target_reserve_consumed = min(
                total_available_reserve,
                reserve_required_for_retained(cumulative_capacity_budget, yield_points),
            )
            target_retained = min(
                target_reserve_consumed * yield_points // 10_000,
                cumulative_capacity_budget,
            )
            target_allocations = allocate_equal(target_retained, initial_remaining)
            investment_changes = {
                technique_id: target_amount - prior_allocations[technique_id]
                for technique_id, target_amount in target_allocations.items()
            }
            if any(amount < 0 for amount in investment_changes.values()):
                raise CultivationSeclusionConflictError(
                    "Seclusion allocation would reduce a technique investment"
                )
            reserve_consumed = (
                target_reserve_consumed - session.cumulative_reserve_consumed
            )
            retained = target_retained - session.cumulative_retained
            if reserve_consumed < 0 or retained < 0 or sum(investment_changes.values()) != retained:
                raise CultivationSeclusionConflictError(
                    "Seclusion cumulative settlement snapshot is inconsistent"
                )
            if reserve_consumed > 0 or retained > 0:
                operation_id = uuid4()
                if retained > 0:
                    state = await uow.cultivation.apply_technique_investments(
                        life_id=life.life_id,
                        operation_id=operation_id,
                        session_id=session_id,
                        changes=tuple(
                            TechniqueInvestmentChange(
                                technique_id,
                                amount,
                                "seclusion_realization",
                            )
                            for technique_id, amount in investment_changes.items()
                            if amount > 0
                        ),
                        occurred_at=now,
                    )
                if reserve_consumed > 0:
                    state = await uow.cultivation.consume_unrefined(
                        life_id=life.life_id,
                        session_id=session_id,
                        operation_id=operation_id,
                        amount=reserve_consumed,
                        occurred_at=now,
                    )
            active_chain = await uow.cultivation.get_active_realm_chain(
                life.life_id, for_update=True
            )
            group_investments = await uow.cultivation.get_group_investments(life.life_id)
            current_level = state.current_level
            parent_entry = active_chain[-1] if active_chain else None
            generation = await uow.cultivation.get_latest_realm_generation(life.life_id)
            qi_totals = self._realm_catalog.qi_cumulative_totals()
            while (
                selections[0].group_code == "qi"
                and current_level < 10
                and group_investments.get("qi", 0) >= qi_totals[current_level]
            ):
                generation += 1
                source_floor = qi_totals[current_level]
                reentry = await uow.cultivation.has_realm_transition_history(
                    life.life_id,
                    source_level=current_level,
                    target_level=current_level + 1,
                )
                realm_entry = RealmEntry(
                    realm_entry_id=uuid4(),
                    life_id=life.life_id,
                    generation=generation,
                    parent_entry_id=(
                        None if parent_entry is None else parent_entry.realm_entry_id
                    ),
                    source_level=current_level,
                    target_level=current_level + 1,
                    source_group="qi",
                    target_group="qi",
                    source_floor=source_floor,
                    target_baseline=source_floor,
                    transition_kind="reentry" if reentry else "adjacent",
                    transition_session_id=session_id,
                    status="active",
                    invalidated_at=None,
                )
                state = await uow.cultivation.append_realm_entry(realm_entry)
                parent_entry = realm_entry
                current_level = state.current_level
            progress = project_progress(
                catalog=self._realm_catalog,
                current_level=current_level,
                group_investments=group_investments,
                active_entry=parent_entry,
                unrefined_reserve=state.unrefined_cultivation,
                revision=state.revision,
            )
            selected_mastered = target_retained == sum(initial_remaining.values()) and bool(
                initial_remaining
            )
            progress_group = group_for_level(current_level)
            explicit_barrier_full = (
                selections[0].group_code == progress_group
                and progress.progress_full
                and (current_level >= 10 or progress_group != "qi")
            )
            terminal = selected_mastered or explicit_barrier_full
            updated = await uow.cultivation.update_session_settlement(
                session_id=session_id,
                cumulative_elapsed_seconds=elapsed,
                cumulative_generated=cumulative_generated,
                cumulative_reserve_consumed=target_reserve_consumed,
                cumulative_retained=target_retained,
                status="completed" if terminal else "active",
                settled_at=now if terminal else None,
            )
            await uow.commit()
        return _seclusion_snapshot(updated)

    async def seclusion_status(
        self, *, account_id: UUID, session_id: UUID
    ) -> SeclusionSnapshotResponse:
        async with self._uow_factory() as uow:
            life = await uow.players.get_current_life(account_id, for_update=False)
            if life is None:
                raise PlayerLifecycleError()
            session = await uow.cultivation.get_session(session_id, for_update=False)
            if (
                session is None
                or session.life_id != life.life_id
                or session.session_kind != "ordinary"
            ):
                raise CultivationSeclusionNotFoundError()
            await uow.rollback()
        return _seclusion_snapshot(session)


def _seclusion_snapshot(session: CultivationSession) -> SeclusionSnapshotResponse:
    return SeclusionSnapshotResponse(
        session_id=session.session_id,
        status=session.status,
        started_at=session.started_at,
        completes_at=session.completes_at,
        cumulative_generated=session.cumulative_generated,
        cumulative_reserve_consumed=session.cumulative_reserve_consumed,
        cumulative_retained=session.cumulative_retained,
    )


def _breakthrough_snapshot(session: CultivationSession) -> BreakthroughSnapshotResponse:
    if session.target_level is None:
        raise RuntimeError("Breakthrough session has no target level")
    frozen = session.frozen_snapshot
    return BreakthroughSnapshotResponse(
        session_id=session.session_id,
        status=session.status,
        source_level=session.source_level,
        target_level=session.target_level,
        pill_count=int(frozen["pill_count"]),
        success_basis_points=int(frozen["success_basis_points"]),
        primary_roll=int(frozen["primary_roll"]),
        secondary_roll=(
            None if frozen.get("secondary_roll") is None else int(frozen["secondary_roll"])
        ),
        outcome=str(frozen["outcome"]),
        started_at=session.started_at,
        completes_at=session.completes_at,
        settled_at=session.settled_at,
    )


def _request_fingerprint(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
