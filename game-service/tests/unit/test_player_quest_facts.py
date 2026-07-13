from uuid import UUID

import pytest

from immortal_mmo.player.schemas import SpiritRoot
from immortal_mmo.player.service import (
    PlayerAccountNotFoundError,
    PlayerService,
    SpiritRootGenerator,
)


def fixed_spirit_root() -> SpiritRoot:
    return SpiritRoot(
        quality="variant",
        label="异灵根",
        elements=["金"],
        mutated_element="金雷",
        variant_element="雷",
    )


def test_current_life_quest_facts_expose_authoritative_player_state() -> None:
    service = PlayerService()
    login = service.login(UUID(int=1), "Facts")

    facts = service.get_current_life_facts(login.account.account_id)

    assert facts.account_id == login.account.account_id
    assert facts.life_id == login.current_life.life_id
    assert facts.generation_no == 1
    assert facts.spirit_root is None
    assert facts.revision == 1


def test_spirit_root_assignment_advances_player_revision_only_once() -> None:
    service = PlayerService(
        spirit_root_generator=SpiritRootGenerator(
            roll=lambda: 0.95,
            choose_mutated_element=lambda: "金雷",
        )
    )
    login = service.login(UUID(int=2), "Revision")

    before = service.get_current_life_facts(login.account.account_id)
    first_detection = service.detect_current_life_spirit_root(login.account.account_id)
    after_first = service.get_current_life_facts(login.account.account_id)
    second_detection = service.detect_current_life_spirit_root(login.account.account_id)
    after_second = service.get_current_life_facts(login.account.account_id)

    assert first_detection.already_detected is False
    assert second_detection.already_detected is True
    assert before.revision == 1
    assert after_first.revision == 2
    assert after_second.revision == 2
    assert after_first.spirit_root == fixed_spirit_root()
    assert after_second.spirit_root == after_first.spirit_root


def test_current_life_quest_facts_preserve_account_not_found_error() -> None:
    service = PlayerService()

    with pytest.raises(PlayerAccountNotFoundError) as error:
        service.get_current_life_facts(UUID(int=999))

    assert error.value.code == "player.account_not_found"
