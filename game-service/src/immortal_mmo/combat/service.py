from pathlib import Path
from uuid import UUID, uuid4

from immortal_mmo.combat.catalog import CombatRewardCatalog
from immortal_mmo.combat.models import CombatKillEvent, StoredCombatKillOutcome
from immortal_mmo.combat.schemas import (
    CombatKillBatchRequest,
    CombatKillBatchResponse,
    CombatKillEventRequest,
    CombatKillResult,
)
from immortal_mmo.core.errors import ConflictError
from immortal_mmo.core.uow import UnitOfWork, UnitOfWorkFactory
from immortal_mmo.cultivation.realm_catalog import RealmCatalog, load_realm_catalog
from immortal_mmo.player.models import Account, Life
from immortal_mmo.quest.progression import QuestEventProgressionService


class CombatIdempotencyConflictError(ConflictError):
    code = "combat.kill_idempotency_conflict"
    message = "Combat kill event ID was reused with different immutable facts."


class CombatRewardService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        catalog: CombatRewardCatalog,
        realm_catalog: RealmCatalog | None = None,
        quest_progression: QuestEventProgressionService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._catalog = catalog
        self._realm_catalog = realm_catalog or load_realm_catalog(
            Path(__file__).resolve().parents[1] / "cultivation" / "realm_catalog.json"
        )
        self._quest_progression = quest_progression or QuestEventProgressionService()

    async def process_batch(
        self,
        batch: CombatKillBatchRequest,
    ) -> CombatKillBatchResponse:
        results = []
        for event in batch.events:
            results.append(await self._process_event(event))
        return CombatKillBatchResponse(results=results)

    async def _process_event(self, request: CombatKillEventRequest) -> CombatKillResult:
        async with self._uow_factory() as uow:
            existing = await uow.combat.get_event(request.event_id)
            if existing is not None:
                return await self._duplicate_result(uow, request, existing)

            reward = self._catalog.resolve(request.mob_internal_name, request.mob_level)
            if reward is None:
                event = self._build_event(
                    request,
                    outcome="not_rewardable",
                    telemetry="compact",
                )
                return await self._insert_terminal(uow, request, event)

            account = await uow.players.lock_account_by_minecraft_uuid(request.killer_uuid)
            if account is None:
                event = self._build_event(
                    request,
                    outcome="account_not_found",
                    telemetry=reward.telemetry,
                )
                return await self._insert_terminal(uow, request, event)

            life = await uow.players.get_current_life(account.account_id, for_update=True)
            if (
                life is None
                or request.source_life_id is None
                or request.source_life_id != life.life_id
            ):
                event = self._build_event(
                    request,
                    outcome="current_life_unavailable",
                    telemetry=reward.telemetry,
                    account=account,
                )
                return await self._insert_terminal(uow, request, event)

            event = self._build_event(
                request,
                outcome="rewarded",
                telemetry=reward.telemetry,
                account=account,
                life=life,
                configured_reward_amount=reward.amount,
            )
            inserted = await uow.combat.insert_event_if_absent(event)
            if not inserted:
                existing = await self._require_existing(uow, request.event_id)
                return await self._duplicate_result(uow, request, existing)
            await self._quest_progression.record_mythicmob_kill(
                uow,
                life_id=life.life_id,
                mob_internal_name=request.mob_internal_name,
                occurred_at=request.occurred_at,
            )
            await uow.combat.increment_mob_counter(
                life.life_id,
                request.mob_internal_name,
                request.occurred_at,
            )
            credit = await uow.cultivation.credit_combat_reward(
                life_id=life.life_id,
                kill_event_id=event.kill_event_id,
                amount=reward.amount,
                cap=self._realm_catalog.level(
                    (
                        await uow.cultivation.get_or_create_state(life.life_id, for_update=False)
                    ).current_level
                ).max_exp,
                occurred_at=request.occurred_at,
            )
            await uow.combat.finalize_reward_result(
                event.kill_event_id,
                credited_cultivation_amount=credit.amount,
                unrefined_balance_after=credit.balance_after,
            )
            await uow.commit()
            return CombatKillResult(
                event_id=request.event_id,
                outcome="accepted",
                kill_event_id=event.kill_event_id,
                life_id=life.life_id,
                configured_reward_amount=reward.amount,
                credited_cultivation_amount=credit.amount,
                unrefined_balance=credit.balance_after,
            )

    async def _insert_terminal(
        self,
        uow: UnitOfWork,
        request: CombatKillEventRequest,
        event: CombatKillEvent,
    ) -> CombatKillResult:
        inserted = await uow.combat.insert_event_if_absent(event)
        if not inserted:
            existing = await self._require_existing(uow, request.event_id)
            return await self._duplicate_result(uow, request, existing)
        await uow.commit()
        return CombatKillResult(
            event_id=request.event_id,
            outcome=_wire_terminal_outcome(event.outcome),
            kill_event_id=event.kill_event_id,
            life_id=event.life_id,
        )

    async def _duplicate_result(
        self,
        uow: UnitOfWork,
        request: CombatKillEventRequest,
        existing: CombatKillEvent,
    ) -> CombatKillResult:
        if existing.request_fingerprint != request.request_fingerprint():
            raise CombatIdempotencyConflictError
        configured_reward_amount = existing.configured_reward_amount
        credited_amount = existing.credited_cultivation_amount
        balance = existing.unrefined_balance_after
        if existing.outcome == "rewarded":
            if (
                existing.life_id is None
                or configured_reward_amount is None
                or credited_amount is None
                or balance is None
            ):
                raise RuntimeError("Rewarded combat event is missing recipient facts")
        await uow.rollback()
        return CombatKillResult(
            event_id=request.event_id,
            outcome="duplicate",
            kill_event_id=existing.kill_event_id,
            life_id=existing.life_id,
            configured_reward_amount=configured_reward_amount,
            credited_cultivation_amount=credited_amount,
            unrefined_balance=balance,
        )

    async def _require_existing(
        self,
        uow: UnitOfWork,
        source_event_id: UUID,
    ) -> CombatKillEvent:
        existing = await uow.combat.get_event(source_event_id)
        if existing is None:
            raise RuntimeError("Combat source conflict resolved without a stored event")
        return existing

    @staticmethod
    def _build_event(
        request: CombatKillEventRequest,
        *,
        outcome: StoredCombatKillOutcome,
        telemetry: str,
        account: Account | None = None,
        life: Life | None = None,
        configured_reward_amount: int | None = None,
    ) -> CombatKillEvent:
        detail_payload = None
        if telemetry == "detailed":
            detail_payload = {"x": request.x, "y": request.y, "z": request.z}
        return CombatKillEvent(
            kill_event_id=uuid4(),
            source_event_id=request.event_id,
            request_fingerprint=request.request_fingerprint(),
            server_id=request.server_id,
            entity_uuid=request.entity_uuid,
            mob_internal_name=request.mob_internal_name,
            mob_level=request.mob_level,
            killer_minecraft_uuid=request.killer_uuid,
            source_life_id=request.source_life_id,
            attribution_kind=request.attribution_kind,
            technique_id=request.technique_id,
            cast_id=request.cast_id,
            account_id=account.account_id if account is not None else None,
            life_id=life.life_id if life is not None else None,
            world_key=request.world,
            occurred_at=request.occurred_at,
            outcome=outcome,
            telemetry=telemetry,
            detail_payload=detail_payload,
            configured_reward_amount=configured_reward_amount,
            credited_cultivation_amount=(0 if configured_reward_amount is not None else None),
            unrefined_balance_after=(0 if configured_reward_amount is not None else None),
        )


def _wire_terminal_outcome(outcome: StoredCombatKillOutcome):
    if outcome == "not_rewardable":
        return "not_rewardable"
    if outcome == "account_not_found":
        return "account_not_found"
    if outcome == "current_life_unavailable":
        return "current_life_unavailable"
    raise RuntimeError("Rewarded outcome is not terminal")
