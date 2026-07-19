from pathlib import Path

from fastapi import FastAPI
from starlette.types import Lifespan

from immortal_mmo.api.errors import domain_error_handler
from immortal_mmo.api.v1.health import ReadinessCheck, not_configured_readiness
from immortal_mmo.api.v1.router import api_router
from immortal_mmo.combat.catalog import CombatRewardCatalog, load_combat_reward_catalog
from immortal_mmo.combat.service import CombatRewardService
from immortal_mmo.core.errors import DomainError
from immortal_mmo.core.uow import UnitOfWorkFactory
from immortal_mmo.cultivation.area_catalog import AreaCatalog, load_area_catalog
from immortal_mmo.cultivation.realm_catalog import RealmCatalog, load_realm_catalog
from immortal_mmo.cultivation.service import CultivationService
from immortal_mmo.cultivation.technique_catalog import (
    TechniqueCatalog,
    load_technique_catalog,
)
from immortal_mmo.item.service import ItemService
from immortal_mmo.player.service import PlayerService
from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import (
    MythicMobKillObjectiveDefinition,
    RealmLevelObjectiveDefinition,
    TechniqueLayerObjectiveDefinition,
)
from immortal_mmo.quest.progression import QuestEventProgressionService
from immortal_mmo.quest.service import QuestService
from immortal_mmo.storage.catalog import StorageCatalog, load_storage_catalog
from immortal_mmo.storage.service import StorageService

DEFAULT_COMBAT_CATALOG_PATH = Path(__file__).resolve().parent / "combat" / "mythicmob_rewards.json"
DEFAULT_REALM_CATALOG_PATH = Path(__file__).resolve().parent / "cultivation" / "realm_catalog.json"
DEFAULT_TECHNIQUE_CATALOG_PATH = (
    Path(__file__).resolve().parent / "cultivation" / "techniques.json"
)
DEFAULT_AREA_CATALOG_PATH = Path(__file__).resolve().parent / "cultivation" / "areas.json"
DEFAULT_STORAGE_CATALOG_PATH = Path(__file__).resolve().parent / "storage" / "catalog.json"


def create_app(
    *,
    uow_factory: UnitOfWorkFactory,
    lifespan: Lifespan[FastAPI] | None = None,
    readiness_check: ReadinessCheck | None = None,
    combat_catalog: CombatRewardCatalog | None = None,
    realm_catalog: RealmCatalog | None = None,
    technique_catalog: TechniqueCatalog | None = None,
    quest_catalog: QuestDefinitionCatalog | None = None,
    area_catalog: AreaCatalog | None = None,
    storage_catalog: StorageCatalog | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Immortal MMO Game Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.player_service = PlayerService(uow_factory)
    app.state.item_service = ItemService(uow_factory)
    resolved_quest_catalog = quest_catalog or QUEST_CATALOG
    resolved_combat_catalog = combat_catalog or load_combat_reward_catalog(
        DEFAULT_COMBAT_CATALOG_PATH
    )
    resolved_realm_catalog = realm_catalog or load_realm_catalog(DEFAULT_REALM_CATALOG_PATH)
    resolved_technique_catalog = technique_catalog or load_technique_catalog(
        DEFAULT_TECHNIQUE_CATALOG_PATH
    )
    resolved_area_catalog = area_catalog or load_area_catalog(DEFAULT_AREA_CATALOG_PATH)
    resolved_storage_catalog = storage_catalog or load_storage_catalog(
        DEFAULT_STORAGE_CATALOG_PATH
    )
    if set(resolved_storage_catalog.storages) != set(resolved_area_catalog.areas):
        raise ValueError("Storage catalog must cover exactly the configured area catalog")
    _validate_quest_catalog_references(
        resolved_quest_catalog,
        resolved_combat_catalog,
        resolved_technique_catalog,
        resolved_realm_catalog,
    )
    app.state.quest_service = QuestService(
        uow_factory,
        resolved_quest_catalog,
        realm_catalog=resolved_realm_catalog,
    )
    app.state.combat_service = CombatRewardService(
        uow_factory,
        resolved_combat_catalog,
        realm_catalog=resolved_realm_catalog,
        quest_progression=QuestEventProgressionService(resolved_quest_catalog),
    )
    app.state.cultivation_service = CultivationService(
        uow_factory,
        resolved_realm_catalog,
        area_catalog=resolved_area_catalog,
        technique_catalog=resolved_technique_catalog,
    )
    app.state.storage_service = StorageService(
        uow_factory,
        catalog=resolved_storage_catalog,
    )
    app.state.readiness_check = (
        readiness_check if readiness_check is not None else not_configured_readiness
    )
    app.add_exception_handler(DomainError, domain_error_handler)
    app.include_router(api_router)
    return app


def _validate_quest_catalog_references(
    quest_catalog: QuestDefinitionCatalog,
    combat_catalog: CombatRewardCatalog,
    technique_catalog: TechniqueCatalog,
    realm_catalog: RealmCatalog,
) -> None:
    for quest in quest_catalog.quests:
        for objective in quest.objectives:
            if isinstance(objective, MythicMobKillObjectiveDefinition):
                if objective.mob_internal_name not in combat_catalog.mobs:
                    raise ValueError(
                        f"Quest {quest.quest_id} objective {objective.objective_id} "
                        f"references unknown MythicMob: {objective.mob_internal_name}"
                    )
            elif isinstance(objective, TechniqueLayerObjectiveDefinition):
                technique = technique_catalog.techniques.get(objective.technique_id)
                if technique is None:
                    raise ValueError(
                        f"Quest {quest.quest_id} objective {objective.objective_id} "
                        f"references unknown technique: {objective.technique_id}"
                    )
                if objective.target_layer > technique.max_layer:
                    raise ValueError(
                        f"Quest {quest.quest_id} objective {objective.objective_id} "
                        f"references unavailable technique layer: {objective.target_layer}"
                    )
            elif (
                isinstance(objective, RealmLevelObjectiveDefinition)
                and objective.target_level not in realm_catalog.levels
            ):
                raise ValueError(
                    f"Quest {quest.quest_id} objective {objective.objective_id} "
                    f"references unknown realm level: {objective.target_level}"
                )
        for reward in quest.rewards:
            technique_id = getattr(reward, "technique_id", None)
            if technique_id is not None and technique_id not in technique_catalog.techniques:
                raise ValueError(
                    f"Quest {quest.quest_id} reward {reward.reward_id} "
                    f"references unknown technique: {technique_id}"
                )
