from dataclasses import dataclass
from typing import Literal

from immortal_mmo.cultivation.breakthrough_catalog import (
    BreakthroughCatalog,
    BreakthroughProfile,
    BreakthroughRule,
)

BreakthroughOutcome = Literal["success", "failure_advance", "failure_loss"]


@dataclass(frozen=True, slots=True)
class BreakthroughDecision:
    rule_id: str
    profile_id: str
    source_level: int
    target_level: int
    pill_count: int
    success_basis_points: int
    primary_roll: int
    secondary_roll: int | None
    outcome: BreakthroughOutcome
    failure_target_level: int | None


def resolve_breakthrough_decision(
    *,
    catalog: BreakthroughCatalog,
    rule: BreakthroughRule,
    source_level: int,
    root_count: int,
    pill_count: int,
    primary_roll: int,
    secondary_roll: int,
) -> BreakthroughDecision:
    if source_level not in rule.source_levels:
        raise ValueError("Source level is not eligible for this breakthrough rule")
    for roll, label in (
        (primary_roll, "primary_roll"),
        (secondary_roll, "secondary_roll"),
    ):
        if isinstance(roll, bool) or not isinstance(roll, int) or not 1 <= roll <= 10_000:
            raise ValueError(f"Breakthrough {label} must be from 1 through 10000")

    profile = _profile_for_root_count(catalog, rule, root_count)
    success_basis_points = profile.success_basis_points(pill_count)
    if primary_roll <= success_basis_points:
        return BreakthroughDecision(
            rule.rule_id,
            profile.profile_id,
            source_level,
            rule.target_level,
            pill_count,
            success_basis_points,
            primary_roll,
            None,
            "success",
            None,
        )

    policy = rule.failure_policies[source_level]
    if (
        policy.mode == "secondary_50_50"
        and secondary_roll <= policy.secondary_basis_points
    ):
        outcome: BreakthroughOutcome = "failure_advance"
        failure_target_level = policy.advance_target_level
    else:
        outcome = "failure_loss"
        failure_target_level = None
    return BreakthroughDecision(
        rule.rule_id,
        profile.profile_id,
        source_level,
        rule.target_level,
        pill_count,
        success_basis_points,
        primary_roll,
        secondary_roll if policy.mode == "secondary_50_50" else None,
        outcome,
        failure_target_level,
    )


def _profile_for_root_count(
    catalog: BreakthroughCatalog,
    rule: BreakthroughRule,
    root_count: int,
) -> BreakthroughProfile:
    if isinstance(root_count, bool) or not isinstance(root_count, int):
        raise ValueError("Spirit-root count must be an integer")
    matches = tuple(
        catalog.profile(profile_id)
        for profile_id in rule.profile_ids.values()
        if root_count in catalog.profile(profile_id).root_counts
    )
    if len(matches) != 1:
        raise ValueError("Spirit-root count does not resolve one breakthrough profile")
    return matches[0]
