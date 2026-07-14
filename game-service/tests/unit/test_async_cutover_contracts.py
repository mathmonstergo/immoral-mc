import inspect

import pytest

from immortal_mmo.main import create_app
from immortal_mmo.player.api import detect_current_life_spirit_root, login_player
from immortal_mmo.player.service import PlayerService
from immortal_mmo.quest.api import (
    accept_quest,
    get_quest_interaction_state,
    get_quest_provider_catalog,
    turn_in_quest,
)
from immortal_mmo.quest.service import QuestService


def test_application_composition_requires_a_unit_of_work_factory() -> None:
    with pytest.raises(TypeError):
        create_app()


def test_services_require_a_unit_of_work_factory() -> None:
    with pytest.raises(TypeError):
        PlayerService()
    with pytest.raises(TypeError):
        QuestService()


@pytest.mark.parametrize(
    "handler",
    [
        login_player,
        detect_current_life_spirit_root,
        get_quest_provider_catalog,
        get_quest_interaction_state,
        accept_quest,
        turn_in_quest,
    ],
)
def test_player_and_quest_route_handlers_are_coroutines(handler: object) -> None:
    assert inspect.iscoroutinefunction(handler)
