from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.combat.postgres_repository import PostgresCombatRepository
from immortal_mmo.cultivation.db_models import (
    BreakthroughTechniqueDebitRow,
    CultivationResourceEntryRow,
    CultivationSessionRow,
    CultivationSessionTechniqueRow,
    LifeCultivationStateRow,
    LifeRealmEntryRow,
    LifeTechniqueRow,
    TechniqueInvestmentEntryRow,
)
from immortal_mmo.cultivation.postgres_repository import PostgresCultivationRepository
from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory
from immortal_mmo.item.db_models import LifeItemStackRow
from immortal_mmo.item.postgres_repository import PostgresItemRepository
from immortal_mmo.main import create_app
from immortal_mmo.player.db_models import LifeSpiritRootRow
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository
from immortal_mmo.quest.postgres_repository import PostgresQuestRepository


def client(sessions: async_sessionmaker[AsyncSession]) -> httpx.AsyncClient:
    app = create_app(
        uow_factory=SqlAlchemyUnitOfWorkFactory(
            sessions,
            PostgresPlayerRepository,
            PostgresQuestRepository,
            PostgresCombatRepository,
            PostgresCultivationRepository,
            PostgresItemRepository,
        )
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_new_current_life_has_mortal_empty_cultivation_snapshot(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    account_id = UUID(int=500)
    async with client(postgres_sessions) as test_client:
        login = await test_client.post(
            "/api/v1/players/login",
            json={
                "minecraft_uuid": str(account_id),
                "player_name": "Cultivator",
            },
        )
        stored_account_id = login.json()["account"]["account_id"]
        response = await test_client.get(
            f"/api/v1/players/{stored_account_id}/current-life/cultivation"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["current_level"] == 0
    assert body["realm_name"] == "凡人"
    assert body["current_progress"] == 0
    assert body["max_exp"] == 50
    assert body["unrefined_reserve"] == 0
    assert body["reserve_cap"] == 50


@pytest.mark.asyncio
async def test_start_seclusion_persists_unordered_authoritative_selection(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    technique_ids = (UUID(int=902), UUID(int=901))
    async with client(postgres_sessions) as test_client:
        login = await test_client.post(
            "/api/v1/players/login",
            json={"minecraft_uuid": str(UUID(int=501)), "player_name": "Retreater"},
        )
        account_id = login.json()["account"]["account_id"]
        life_id = login.json()["current_life"]["life_id"]
        async with postgres_sessions() as session:
            for index, technique_id in enumerate(technique_ids):
                session.add(
                    LifeTechniqueRow(
                        life_technique_id=technique_id,
                        life_id=UUID(life_id),
                        technique_id=f"GF_Test_{index}",
                        definition_version=1,
                        group_code="qi",
                        major_realm="练气",
                        invested_amount=0,
                        max_investment=109,
                        current_layer=0,
                        status="active",
                    )
                )
            await session.commit()
        response = await test_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/seclusions",
            headers={"Idempotency-Key": str(UUID(int=999))},
            json={
                "area_id": "neutral_training_ground",
                "technique_ids": [str(value) for value in technique_ids],
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    async with postgres_sessions() as session:
        session_count = await session.scalar(
            select(func.count()).select_from(CultivationSessionRow)
        )
        stored_session = await session.scalar(select(CultivationSessionRow))
        selections = (
            await session.scalars(
                select(CultivationSessionTechniqueRow.life_technique_id).order_by(
                    CultivationSessionTechniqueRow.life_technique_id
                )
            )
        ).all()
    assert session_count == 1
    assert stored_session is not None
    assert stored_session.completes_at - stored_session.started_at == timedelta(seconds=10)
    assert stored_session.frozen_snapshot == {
        "area_version": 1,
        "cycle_seconds": 10,
        "technique_group": "qi",
        "technique_capacity": 109,
        "full_mastery_seconds": 36_000,
        "base_cultivation_per_cycle": 1,
        "player_major_realm": "凡人",
        "player_speed_weight": 1,
        "technique_major_realm": "练气",
        "technique_speed_weight": 1,
        "speed_basis_points": 10_000,
        "yield_basis_points": 10_000,
        "cultivation_per_cycle": 1,
    }
    assert tuple(selections) == tuple(sorted(technique_ids))


@pytest.mark.asyncio
async def test_mortal_seclusion_settlement_persists_level_zero_to_one_atomically(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    technique_id = UUID(int=9_001)
    async with client(postgres_sessions) as test_client:
        login = await test_client.post(
            "/api/v1/players/login",
            json={"minecraft_uuid": str(UUID(int=9_000)), "player_name": "Mortal"},
        )
        account_id = login.json()["account"]["account_id"]
        life_id = UUID(login.json()["current_life"]["life_id"])
        async with postgres_sessions() as session:
            session.add_all(
                [
                    LifeCultivationStateRow(
                        life_id=life_id,
                        current_level=0,
                        unrefined_cultivation=50,
                        realized_cultivation=0,
                        revision=1,
                    ),
                    LifeTechniqueRow(
                        life_technique_id=technique_id,
                        life_id=life_id,
                        technique_id="GF_YinqiShu_01",
                        definition_version=1,
                        group_code="qi",
                        major_realm="练气",
                        invested_amount=0,
                        max_investment=3_780,
                        current_layer=0,
                        status="active",
                    ),
                ]
            )
            await session.commit()

        started = await test_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/seclusions",
            headers={"Idempotency-Key": str(UUID(int=9_002))},
            json={
                "area_id": "neutral_training_ground",
                "technique_ids": [str(technique_id)],
            },
        )
        assert started.status_code == 200
        session_id = UUID(started.json()["session_id"])

        async with postgres_sessions() as session:
            seclusion = await session.get(CultivationSessionRow, session_id)
            assert seclusion is not None
            seclusion.started_at -= timedelta(seconds=500)
            await session.commit()

        settled = await test_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/seclusions/"
            f"{session_id}/settle"
        )
        snapshot = await test_client.get(
            f"/api/v1/players/{account_id}/current-life/cultivation"
        )

    assert settled.status_code == 200
    assert settled.json()["status"] == "active"
    assert settled.json()["cumulative_generated"] == 50
    assert settled.json()["cumulative_reserve_consumed"] == 50
    assert settled.json()["cumulative_retained"] == 50
    assert snapshot.status_code == 200
    assert snapshot.json()["current_level"] == 1
    assert snapshot.json()["realm_name"] == "练气一层"
    assert snapshot.json()["current_progress"] == 0
    assert snapshot.json()["max_exp"] == 100
    assert snapshot.json()["realized_total"] == 50
    assert snapshot.json()["unrefined_reserve"] == 0

    async with postgres_sessions() as session:
        state = await session.get(LifeCultivationStateRow, life_id)
        technique = await session.get(LifeTechniqueRow, technique_id)
        seclusion = await session.get(CultivationSessionRow, session_id)
        realm_entries = (
            await session.scalars(
                select(LifeRealmEntryRow).where(LifeRealmEntryRow.life_id == life_id)
            )
        ).all()
        technique_entries = (
            await session.scalars(
                select(TechniqueInvestmentEntryRow).where(
                    TechniqueInvestmentEntryRow.session_id == session_id
                )
            )
        ).all()
        resource_entries = (
            await session.scalars(
                select(CultivationResourceEntryRow).where(
                    CultivationResourceEntryRow.session_id == session_id
                )
            )
        ).all()

    assert state is not None
    assert state.current_level == 1
    assert state.unrefined_cultivation == 0
    assert state.realized_cultivation == 50
    assert state.active_session_id == session_id
    assert technique is not None
    assert technique.invested_amount == 50
    assert seclusion is not None
    assert seclusion.source_level == 0
    assert seclusion.cumulative_generated == 50
    assert seclusion.cumulative_reserve_consumed == 50
    assert seclusion.cumulative_retained == 50

    assert len(realm_entries) == 1
    realm_entry = realm_entries[0]
    assert realm_entry.generation == 1
    assert realm_entry.parent_entry_id is None
    assert realm_entry.source_level == 0
    assert realm_entry.target_level == 1
    assert realm_entry.source_floor == 50
    assert realm_entry.target_baseline == 50
    assert realm_entry.transition_kind == "adjacent"
    assert realm_entry.transition_session_id == session_id
    assert realm_entry.status == "active"

    assert len(technique_entries) == 1
    technique_entry = technique_entries[0]
    assert technique_entry.entry_type == "seclusion_realization"
    assert technique_entry.delta_amount == 50
    assert technique_entry.balance_after == 50
    assert len(resource_entries) == 2
    resource_entries_by_code = {entry.resource_code: entry for entry in resource_entries}
    assert resource_entries_by_code["realized_cultivation"].entry_type == (
        "seclusion_realization"
    )
    assert resource_entries_by_code["realized_cultivation"].delta_amount == 50
    assert resource_entries_by_code["realized_cultivation"].balance_after == 50
    assert resource_entries_by_code["unrefined_cultivation"].entry_type == (
        "seclusion_consumption"
    )
    assert resource_entries_by_code["unrefined_cultivation"].delta_amount == -50
    assert resource_entries_by_code["unrefined_cultivation"].balance_after == 0
    operation_ids = {
        technique_entry.operation_id,
        *(entry.operation_id for entry in resource_entries),
    }
    assert None not in operation_ids
    assert len(operation_ids) == 1


@pytest.mark.asyncio
async def test_abandonment_api_replays_across_app_restart_without_double_debit(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    idempotency_key = UUID(int=9_101)
    abandoned_id = UUID(int=9_111)
    other_id = UUID(int=9_112)
    async with client(postgres_sessions) as first_client:
        login = await first_client.post(
            "/api/v1/players/login",
            json={"minecraft_uuid": str(UUID(int=9_100)), "player_name": "Abandoner"},
        )
        account_id = login.json()["account"]["account_id"]
        life_id = UUID(login.json()["current_life"]["life_id"])
        async with postgres_sessions() as session:
            session.add(
                LifeCultivationStateRow(
                    life_id=life_id,
                    current_level=1,
                    unrefined_cultivation=33,
                    realized_cultivation=80,
                    revision=1,
                )
            )
            for technique_id, invested in ((abandoned_id, 80), (other_id, 0)):
                session.add(
                    LifeTechniqueRow(
                        life_technique_id=technique_id,
                        life_id=life_id,
                        technique_id=f"GF_Test_{technique_id.int}",
                        definition_version=1,
                        group_code="qi",
                        major_realm="练气",
                        invested_amount=invested,
                        max_investment=109,
                        current_layer=12 if invested else 0,
                        status="active",
                    )
                )
            await session.commit()
        first = await first_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/techniques/"
            f"{abandoned_id}/abandon",
            headers={"Idempotency-Key": str(idempotency_key)},
        )

    async with client(postgres_sessions) as restarted_client:
        replay = await restarted_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/techniques/"
            f"{abandoned_id}/abandon",
            headers={"Idempotency-Key": str(idempotency_key)},
        )
        conflict = await restarted_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/techniques/"
            f"{other_id}/abandon",
            headers={"Idempotency-Key": str(idempotency_key)},
        )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert first.json()["removed_amount"] == 80
    assert first.json()["destroyed_amount"] == 80
    assert first.json()["cultivation"]["realized_total"] == 0
    assert first.json()["cultivation"]["unrefined_reserve"] == 33
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "cultivation.technique_mutation_conflict"

    operation_id = UUID(first.json()["operation_id"])
    async with postgres_sessions() as session:
        source = await session.get(LifeTechniqueRow, abandoned_id)
        state = await session.get(LifeCultivationStateRow, life_id)
        mutation = await session.get(CultivationSessionRow, operation_id)
        technique_entries = (
            await session.scalars(
                select(TechniqueInvestmentEntryRow).where(
                    TechniqueInvestmentEntryRow.operation_id == operation_id
                )
            )
        ).all()
        resource_entries = (
            await session.scalars(
                select(CultivationResourceEntryRow).where(
                    CultivationResourceEntryRow.operation_id == operation_id
                )
            )
        ).all()
    assert source is not None
    assert source.status == "abandoned"
    assert source.invested_amount == 0
    assert state is not None
    assert state.realized_cultivation == 0
    assert state.unrefined_cultivation == 33
    assert mutation is not None
    assert mutation.session_kind == "technique_mutation"
    assert mutation.status == "completed"
    assert mutation.frozen_snapshot["response"] == first.json()
    assert len(technique_entries) == 1
    assert technique_entries[0].entry_type == "abandonment"
    assert technique_entries[0].delta_amount == -80
    assert len(resource_entries) == 1
    assert resource_entries[0].entry_type == "technique_abandonment"
    assert resource_entries[0].delta_amount == -80


@pytest.mark.asyncio
async def test_transfer_api_applies_profile_fraction_and_target_capacity(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    source_id = UUID(int=9_211)
    target_id = UUID(int=9_212)
    async with client(postgres_sessions) as test_client:
        login = await test_client.post(
            "/api/v1/players/login",
            json={"minecraft_uuid": str(UUID(int=9_200)), "player_name": "Transferer"},
        )
        account_id = login.json()["account"]["account_id"]
        life_id = UUID(login.json()["current_life"]["life_id"])
        async with postgres_sessions() as session:
            session.add(
                LifeCultivationStateRow(
                    life_id=life_id,
                    current_level=1,
                    unrefined_cultivation=55,
                    realized_cultivation=179,
                    revision=1,
                )
            )
            session.add_all(
                [
                    LifeTechniqueRow(
                        life_technique_id=source_id,
                        life_id=life_id,
                        technique_id="GF_Transfer_Source",
                        definition_version=1,
                        group_code="qi",
                        major_realm="练气",
                        invested_amount=101,
                        max_investment=201,
                        current_layer=11,
                        status="active",
                    ),
                    LifeTechniqueRow(
                        life_technique_id=target_id,
                        life_id=life_id,
                        technique_id="GF_Transfer_Target",
                        definition_version=1,
                        group_code="qi",
                        major_realm="练气",
                        invested_amount=78,
                        max_investment=109,
                        current_layer=12,
                        status="active",
                    ),
                ]
            )
            await session.commit()
        response = await test_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/techniques/"
            f"{source_id}/transfer",
            headers={"Idempotency-Key": str(UUID(int=9_299))},
            json={
                "target_technique_id": str(target_id),
                "transfer_profile_id": "Trans_Gongfa_01",
            },
        )

    assert response.status_code == 200
    assert response.json()["removed_amount"] == 101
    assert response.json()["transferred_amount"] == 31
    assert response.json()["destroyed_amount"] == 70
    assert response.json()["cultivation"]["realized_total"] == 109
    assert response.json()["cultivation"]["unrefined_reserve"] == 55


@pytest.mark.asyncio
async def test_regression_reentry_appends_a_new_postgres_branch(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    abandoned_id = UUID(int=9_311)
    retained_id = UUID(int=9_312)
    mortal_entry_id = UUID(int=9_320)
    first_entry_id = UUID(int=9_321)
    invalidated_entry_id = UUID(int=9_322)
    async with client(postgres_sessions) as test_client:
        login = await test_client.post(
            "/api/v1/players/login",
            json={"minecraft_uuid": str(UUID(int=9_300)), "player_name": "Reentry"},
        )
        account_id = login.json()["account"]["account_id"]
        life_id = UUID(login.json()["current_life"]["life_id"])
        async with postgres_sessions() as session:
            session.add(
                LifeCultivationStateRow(
                    life_id=life_id,
                    current_level=3,
                    unrefined_cultivation=100,
                    realized_cultivation=300,
                    revision=1,
                )
            )
            session.add_all(
                [
                    LifeTechniqueRow(
                        life_technique_id=abandoned_id,
                        life_id=life_id,
                        technique_id="GF_Reentry_Abandoned",
                        definition_version=1,
                        group_code="qi",
                        major_realm="练气",
                        invested_amount=100,
                        max_investment=109,
                        current_layer=12,
                        status="active",
                    ),
                    LifeTechniqueRow(
                        life_technique_id=retained_id,
                        life_id=life_id,
                        technique_id="GF_Reentry_Retained",
                        definition_version=1,
                        group_code="qi",
                        major_realm="练气",
                        invested_amount=200,
                        max_investment=300,
                        current_layer=11,
                        status="active",
                    ),
                    LifeRealmEntryRow(
                        realm_entry_id=mortal_entry_id,
                        life_id=life_id,
                        generation=1,
                        parent_entry_id=None,
                        source_level=0,
                        target_level=1,
                        source_group="qi",
                        target_group="qi",
                        source_floor=50,
                        target_baseline=50,
                        transition_kind="adjacent",
                        transition_session_id=None,
                        status="active",
                        invalidated_at=None,
                    ),
                    LifeRealmEntryRow(
                        realm_entry_id=first_entry_id,
                        life_id=life_id,
                        generation=2,
                        parent_entry_id=mortal_entry_id,
                        source_level=1,
                        target_level=2,
                        source_group="qi",
                        target_group="qi",
                        source_floor=150,
                        target_baseline=150,
                        transition_kind="adjacent",
                        transition_session_id=None,
                        status="active",
                        invalidated_at=None,
                    ),
                    LifeRealmEntryRow(
                        realm_entry_id=invalidated_entry_id,
                        life_id=life_id,
                        generation=3,
                        parent_entry_id=first_entry_id,
                        source_level=2,
                        target_level=3,
                        source_group="qi",
                        target_group="qi",
                        source_floor=300,
                        target_baseline=300,
                        transition_kind="adjacent",
                        transition_session_id=None,
                        status="active",
                        invalidated_at=None,
                    ),
                ]
            )
            await session.commit()

        regressed = await test_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/techniques/"
            f"{abandoned_id}/abandon",
            headers={"Idempotency-Key": str(UUID(int=9_390))},
        )
        assert regressed.status_code == 200
        assert regressed.json()["cultivation"]["current_level"] == 2

        started = await test_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/seclusions",
            headers={"Idempotency-Key": str(UUID(int=9_391))},
            json={
                "area_id": "neutral_training_ground",
                "technique_ids": [str(retained_id)],
            },
        )
        assert started.status_code == 200
        session_id = UUID(started.json()["session_id"])
        async with postgres_sessions() as session:
            seclusion = await session.get(CultivationSessionRow, session_id)
            assert seclusion is not None
            seclusion.started_at -= timedelta(hours=4)
            await session.commit()
        settled = await test_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/seclusions/"
            f"{session_id}/settle"
        )

    assert settled.status_code == 200
    async with postgres_sessions() as session:
        entries = (
            await session.scalars(
                select(LifeRealmEntryRow)
                .where(LifeRealmEntryRow.life_id == life_id)
                .order_by(LifeRealmEntryRow.generation)
            )
        ).all()
        state = await session.get(LifeCultivationStateRow, life_id)
    assert state is not None
    assert state.current_level == 3
    assert [entry.generation for entry in entries] == [1, 2, 3, 4]
    assert entries[0].status == "active"
    assert entries[1].status == "active"
    assert entries[2].status == "invalidated"
    assert entries[3].status == "active"
    assert entries[3].source_level == 2
    assert entries[3].target_level == 3
    assert entries[3].parent_entry_id == first_entry_id
    assert entries[3].transition_kind == "reentry"


@pytest.mark.asyncio
async def test_foundation_breakthrough_replays_and_settles_after_app_restart(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    technique_id = UUID(int=9_411)
    entry_ids = tuple(UUID(int=9_420 + source_level) for source_level in range(10))
    qi_entry_totals = (50, 150, 300, 525, 862, 1_367, 2_124, 3_259, 4_961, 7_514)
    start_key = UUID(int=9_413)
    async with client(postgres_sessions) as first_client:
        login = await first_client.post(
            "/api/v1/players/login",
            json={"minecraft_uuid": str(UUID(int=9_400)), "player_name": "Breaker"},
        )
        account_id = login.json()["account"]["account_id"]
        life_id = UUID(login.json()["current_life"]["life_id"])
        async with postgres_sessions() as session:
            session.add_all(
                [
                    LifeSpiritRootRow(
                        life_id=life_id,
                        quality_code="triple",
                        base_element_codes=["metal", "wood", "water"],
                        variant_element_code=None,
                        generator_version=1,
                    ),
                    LifeCultivationStateRow(
                        life_id=life_id,
                        current_level=10,
                        unrefined_cultivation=777,
                        realized_cultivation=11_343,
                        revision=1,
                    ),
                    LifeTechniqueRow(
                        life_technique_id=technique_id,
                        life_id=life_id,
                        technique_id="GF_Breakthrough_Qi",
                        definition_version=1,
                        group_code="qi",
                        major_realm="练气",
                        invested_amount=11_343,
                        max_investment=20_000,
                        current_layer=13,
                        status="active",
                    ),
                    *(
                        LifeRealmEntryRow(
                            realm_entry_id=entry_ids[source_level],
                            life_id=life_id,
                            generation=source_level + 1,
                            parent_entry_id=(
                                None if source_level == 0 else entry_ids[source_level - 1]
                            ),
                            source_level=source_level,
                            target_level=source_level + 1,
                            source_group="qi",
                            target_group="qi",
                            source_floor=qi_entry_totals[source_level],
                            target_baseline=qi_entry_totals[source_level],
                            transition_kind="adjacent",
                            transition_session_id=None,
                            status="active",
                            invalidated_at=None,
                        )
                        for source_level in range(10)
                    ),
                ]
            )
            await session.commit()
        granted = await first_client.post(
            f"/api/v1/players/{account_id}/current-life/items/adjustments",
            headers={"Idempotency-Key": str(UUID(int=9_414))},
            json={"item_code": "foundation_pill", "delta_quantity": 1},
        )
        started = await first_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/breakthroughs",
            headers={"Idempotency-Key": str(start_key)},
            json={"pill_count": 1},
        )

    assert granted.status_code == 200
    assert started.status_code == 200
    assert started.json()["status"] == "pending"
    assert started.json()["outcome"] == "success"
    breakthrough_id = UUID(started.json()["session_id"])
    async with client(postgres_sessions) as restarted_client:
        replay = await restarted_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/breakthroughs",
            headers={"Idempotency-Key": str(start_key)},
            json={"pill_count": 1},
        )
        async with postgres_sessions() as session:
            breakthrough = await session.get(CultivationSessionRow, breakthrough_id)
            assert breakthrough is not None
            breakthrough.started_at -= timedelta(minutes=11)
            breakthrough.completes_at -= timedelta(minutes=11)
            await session.commit()
        settled = await restarted_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/breakthroughs/"
            f"{breakthrough_id}/settle"
        )
        snapshot = await restarted_client.get(
            f"/api/v1/players/{account_id}/current-life/cultivation"
        )

    assert replay.json() == started.json()
    assert settled.status_code == 200
    assert settled.json()["status"] == "completed"
    assert snapshot.json()["current_level"] == 14
    assert snapshot.json()["current_progress"] == 0
    assert snapshot.json()["unrefined_reserve"] == 777
    async with postgres_sessions() as session:
        stack = await session.get(
            LifeItemStackRow,
            {"life_id": life_id, "item_code": "foundation_pill"},
        )
        debit_count = await session.scalar(
            select(func.count())
            .select_from(BreakthroughTechniqueDebitRow)
            .where(BreakthroughTechniqueDebitRow.session_id == breakthrough_id)
        )
    assert stack is not None and stack.quantity == 0
    assert debit_count == 1
