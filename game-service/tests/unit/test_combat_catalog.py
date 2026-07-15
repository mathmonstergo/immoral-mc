from decimal import Decimal

import pytest

from immortal_mmo.combat.catalog import (
    MAX_REWARD_AMOUNT,
    CombatRewardCatalog,
    LevelRewardCurve,
    MobRewardDefinition,
    RewardProfile,
    load_combat_reward_catalog,
)


def catalog() -> CombatRewardCatalog:
    return CombatRewardCatalog(
        schema_version=1,
        curves=(
            LevelRewardCurve(
                curve_id="linear-low",
                min_level=Decimal("1.000"),
                max_level=Decimal("100.000"),
                reward_per_level=2,
            ),
        ),
        profiles=(
            RewardProfile(
                profile_id="ordinary-wolf",
                base_reward=10,
                level_curve_id="linear-low",
            ),
            RewardProfile(
                profile_id="boss-flat",
                base_reward=500,
                level_curve_id=None,
            ),
        ),
        mobs=(
            MobRewardDefinition(
                internal_name="AzureWolf",
                reward_profile_id="ordinary-wolf",
                telemetry="compact",
            ),
            MobRewardDefinition(
                internal_name="AzureDragon",
                reward_profile_id="boss-flat",
                telemetry="detailed",
            ),
        ),
    )


def test_catalog_uses_exact_mythic_internal_name() -> None:
    rewards = catalog()

    assert rewards.resolve("AzureWolf", Decimal("3.900")).amount == 14
    assert rewards.resolve("AzureWolf", Decimal("3.900")).telemetry == "compact"
    assert rewards.resolve("AzureDragon", Decimal("50.000")).amount == 500
    assert rewards.resolve("AzureDragon", Decimal("50.000")).telemetry == "detailed"
    assert rewards.resolve("azurewolf", Decimal("3.900")) is None


@pytest.mark.parametrize("level", [Decimal("0.999"), Decimal("100.001")])
def test_catalog_rejects_level_outside_selected_curve(level: Decimal) -> None:
    with pytest.raises(ValueError, match="outside curve bounds"):
        catalog().resolve("AzureWolf", level)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {
                "mobs": (
                    MobRewardDefinition("Same", "boss-flat", "compact"),
                    MobRewardDefinition("Same", "boss-flat", "compact"),
                )
            },
            "Duplicate Mythic mob internal name",
        ),
        (
            {
                "profiles": (
                    RewardProfile("bad", 10, "missing-curve"),
                )
            },
            "Unknown level curve",
        ),
        (
            {
                "profiles": (
                    RewardProfile("overflow", MAX_REWARD_AMOUNT, "overflow-curve"),
                ),
                "curves": (
                    LevelRewardCurve(
                        "overflow-curve",
                        Decimal("1.000"),
                        Decimal("2.000"),
                        1,
                    ),
                ),
                "mobs": (
                    MobRewardDefinition("OverflowMob", "overflow", "compact"),
                ),
            },
            "overflow",
        ),
    ],
)
def test_catalog_rejects_invalid_content(
    kwargs: dict[str, tuple[object, ...]],
    message: str,
) -> None:
    defaults: dict[str, object] = {
        "schema_version": 1,
        "curves": (),
        "profiles": (RewardProfile("boss-flat", 500, None),),
        "mobs": (MobRewardDefinition("Boss", "boss-flat", "compact"),),
    }
    defaults.update(kwargs)

    with pytest.raises(ValueError, match=message):
        CombatRewardCatalog(**defaults)


def test_catalog_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        CombatRewardCatalog(schema_version=2, curves=(), profiles=(), mobs=())


def test_catalog_loads_versioned_json_content(tmp_path) -> None:
    catalog_file = tmp_path / "mythicmob_rewards.json"
    catalog_file.write_text(
        """
        {
          "schema_version": 1,
          "level_curves": [
            {
              "curve_id": "linear-low",
              "min_level": "1.000",
              "max_level": "100.000",
              "reward_per_level": 2
            }
          ],
          "reward_profiles": [
            {
              "profile_id": "ordinary-wolf",
              "base_reward": 10,
              "level_curve_id": "linear-low"
            }
          ],
          "mobs": [
            {
              "internal_name": "AzureWolf",
              "reward_profile_id": "ordinary-wolf",
              "telemetry": "compact"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    loaded = load_combat_reward_catalog(catalog_file)

    assert loaded.resolve("AzureWolf", Decimal("2.000")).amount == 12


def test_catalog_loader_rejects_non_object_json(tmp_path) -> None:
    catalog_file = tmp_path / "mythicmob_rewards.json"
    catalog_file.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_combat_reward_catalog(catalog_file)
