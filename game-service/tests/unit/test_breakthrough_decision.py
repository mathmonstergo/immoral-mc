from pathlib import Path

import pytest

from immortal_mmo.cultivation.breakthrough import resolve_breakthrough_decision
from immortal_mmo.cultivation.breakthrough_catalog import load_breakthrough_catalog

ROOT = Path(__file__).resolve().parents[2] / "src/immortal_mmo/cultivation"
CATALOG = load_breakthrough_catalog(ROOT / "breakthrough_rules.json")
RULE = CATALOG.rule("qi_to_foundation")


@pytest.mark.parametrize("root_count", [1, 2, 3])
def test_one_to_three_roots_use_same_guaranteed_profile(root_count: int) -> None:
    decision = resolve_breakthrough_decision(
        catalog=CATALOG,
        rule=RULE,
        source_level=10,
        root_count=root_count,
        pill_count=1,
        primary_roll=10_000,
        secondary_roll=10_000,
    )

    assert decision.profile_id == "one_to_three_root"
    assert decision.success_basis_points == 10_000
    assert decision.outcome == "success"
    assert decision.secondary_roll is None


def test_four_and_five_root_tables_remain_independent() -> None:
    four = resolve_breakthrough_decision(
        catalog=CATALOG,
        rule=RULE,
        source_level=10,
        root_count=4,
        pill_count=10,
        primary_roll=7_500,
        secondary_roll=9_999,
    )
    five = resolve_breakthrough_decision(
        catalog=CATALOG,
        rule=RULE,
        source_level=10,
        root_count=5,
        pill_count=10,
        primary_roll=7_500,
        secondary_roll=1,
    )

    assert (four.success_basis_points, four.outcome) == (10_000, "success")
    assert (five.success_basis_points, five.outcome) == (5_000, "failure_advance")


@pytest.mark.parametrize(
    ("source_level", "secondary_roll", "expected"),
    [(10, 5_000, "failure_advance"), (10, 5_001, "failure_loss"), (13, 1, "failure_loss")],
)
def test_failure_policy_is_resolved_from_catalog(
    source_level: int,
    secondary_roll: int,
    expected: str,
) -> None:
    decision = resolve_breakthrough_decision(
        catalog=CATALOG,
        rule=RULE,
        source_level=source_level,
        root_count=5,
        pill_count=1,
        primary_roll=10_000,
        secondary_roll=secondary_roll,
    )

    assert decision.outcome == expected
    assert decision.failure_target_level == (
        source_level + 1 if expected == "failure_advance" else None
    )


def test_profile_owns_pill_count_validation() -> None:
    with pytest.raises(KeyError, match="Unsupported pill count"):
        resolve_breakthrough_decision(
            catalog=CATALOG,
            rule=RULE,
            source_level=10,
            root_count=3,
            pill_count=2,
            primary_roll=1,
            secondary_roll=1,
        )
