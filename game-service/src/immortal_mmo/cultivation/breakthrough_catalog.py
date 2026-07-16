from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any


class BreakthroughCatalogError(ValueError):
    """Raised when versioned breakthrough content fails strict validation."""


_APPROVED_PROFILES = {
    "one_to_three_root": ((1, 2, 3), (1,), (10_000,)),
    "four_root": (
        (4,),
        tuple(range(1, 11)),
        (500, 1000, 1600, 2400, 3200, 4200, 5300, 6700, 8200, 10000),
    ),
    "five_root": (
        (5,),
        tuple(range(1, 11)),
        (200, 400, 700, 1100, 1600, 2200, 2900, 3600, 4300, 5000),
    ),
}


@dataclass(frozen=True, slots=True)
class BreakthroughProfile:
    profile_id: str
    root_counts: tuple[int, ...]
    pill_counts: tuple[int, ...]
    basis_points: tuple[int, ...]

    def success_basis_points(self, pill_count: int) -> int:
        try:
            index = self.pill_counts.index(pill_count)
        except ValueError as error:
            raise KeyError(
                f"Unsupported pill count for profile {self.profile_id}: {pill_count}"
            ) from error
        return self.basis_points[index]


@dataclass(frozen=True, slots=True)
class FailurePolicy:
    mode: str
    advance_target_level: int | None = None
    loss_numerator: int = 1
    loss_denominator: int = 3
    secondary_basis_points: int = 5_000


@dataclass(frozen=True, slots=True, init=False)
class BreakthroughRule:
    rule_id: str
    source_levels: tuple[int, ...]
    target_level: int
    duration_seconds: int
    duration_min_seconds: int
    duration_max_seconds: int
    required_item_id: str
    profile_ids: Mapping[str, str]
    failure_policies: Mapping[int, FailurePolicy]

    def __init__(
        self,
        rule_id: str,
        source_levels: tuple[int, ...],
        target_level: int,
        duration_seconds: int,
        duration_min_seconds: int,
        duration_max_seconds: int,
        required_item_id: str,
        profile_ids: Mapping[str, str],
        failure_policies: Mapping[int, FailurePolicy],
    ) -> None:
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "source_levels", source_levels)
        object.__setattr__(self, "target_level", target_level)
        object.__setattr__(self, "duration_seconds", duration_seconds)
        object.__setattr__(self, "duration_min_seconds", duration_min_seconds)
        object.__setattr__(self, "duration_max_seconds", duration_max_seconds)
        object.__setattr__(self, "required_item_id", required_item_id)
        object.__setattr__(self, "profile_ids", MappingProxyType(dict(profile_ids)))
        object.__setattr__(self, "failure_policies", MappingProxyType(dict(failure_policies)))


@dataclass(frozen=True, slots=True, init=False)
class BreakthroughCatalog:
    _schema_version: int
    _profiles: Mapping[str, BreakthroughProfile]
    _rules: Mapping[str, BreakthroughRule]

    def __init__(
        self,
        *,
        schema_version: int,
        profiles: tuple[BreakthroughProfile, ...],
        rules: tuple[BreakthroughRule, ...],
    ) -> None:
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or schema_version != 1
        ):
            raise BreakthroughCatalogError("Unsupported breakthrough catalog schema_version")
        by_profile: dict[str, BreakthroughProfile] = {}
        for profile in profiles:
            self._validate_profile(profile)
            if profile.profile_id in by_profile:
                raise BreakthroughCatalogError(
                    f"Duplicate breakthrough profile: {profile.profile_id}"
                )
            by_profile[profile.profile_id] = profile
        by_rule: dict[str, BreakthroughRule] = {}
        for rule in rules:
            self._validate_rule(rule, by_profile)
            if rule.rule_id in by_rule:
                raise BreakthroughCatalogError(f"Duplicate breakthrough rule: {rule.rule_id}")
            by_rule[rule.rule_id] = rule
        object.__setattr__(self, "_schema_version", schema_version)
        object.__setattr__(self, "_profiles", MappingProxyType(by_profile))
        object.__setattr__(self, "_rules", MappingProxyType(by_rule))

    @staticmethod
    def _validate_profile(profile: BreakthroughProfile) -> None:
        if not profile.profile_id:
            raise BreakthroughCatalogError("Breakthrough profile ID must not be empty")
        if not profile.root_counts or any(
            isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5
            for value in profile.root_counts
        ):
            raise BreakthroughCatalogError(
                "Breakthrough root_counts must be integers from 1 through 5"
            )
        if tuple(sorted(set(profile.root_counts))) != profile.root_counts:
            raise BreakthroughCatalogError("Breakthrough root_counts must be sorted and unique")
        if len(profile.pill_counts) != len(profile.basis_points) or not profile.pill_counts:
            raise BreakthroughCatalogError(
                "Breakthrough pill and basis tables must have equal nonzero length"
            )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10
            for value in profile.pill_counts
        ):
            raise BreakthroughCatalogError(
                "Breakthrough pill_counts must be integers from 1 through 10"
            )
        if tuple(sorted(set(profile.pill_counts))) != profile.pill_counts:
            raise BreakthroughCatalogError("Breakthrough pill_counts must be sorted and unique")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000
            for value in profile.basis_points
        ):
            raise BreakthroughCatalogError("Breakthrough basis points must be bounded integers")
        if tuple(sorted(profile.basis_points)) != profile.basis_points:
            raise BreakthroughCatalogError("Breakthrough basis points must be monotonic")
        approved = _APPROVED_PROFILES.get(profile.profile_id)
        if approved is not None and (
            profile.root_counts,
            profile.pill_counts,
            profile.basis_points,
        ) != approved:
            raise BreakthroughCatalogError(
                f"Breakthrough profile {profile.profile_id} must match the approved table"
            )

    @staticmethod
    def _validate_rule(rule: BreakthroughRule, profiles: Mapping[str, BreakthroughProfile]) -> None:
        if not rule.rule_id:
            raise BreakthroughCatalogError("Breakthrough rule ID must not be empty")
        if not rule.source_levels or tuple(sorted(set(rule.source_levels))) != rule.source_levels:
            raise BreakthroughCatalogError("Breakthrough source_levels must be sorted and unique")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 22
            for value in rule.source_levels
        ):
            raise BreakthroughCatalogError(
                "Breakthrough source levels must be integers from 1 through 22"
            )
        if (
            isinstance(rule.target_level, bool)
            or not isinstance(rule.target_level, int)
            or not 1 <= rule.target_level <= 22
        ):
            raise BreakthroughCatalogError(
                "Breakthrough target_level must be an integer from 1 through 22"
            )
        if (
            rule.duration_min_seconds < 600
            or rule.duration_max_seconds > 900
            or rule.duration_min_seconds > rule.duration_max_seconds
        ):
            raise BreakthroughCatalogError(
                "Breakthrough duration validation range must be 600 through 900 seconds"
            )
        if not rule.duration_min_seconds <= rule.duration_seconds <= rule.duration_max_seconds:
            raise BreakthroughCatalogError(
                "Breakthrough duration_seconds is outside validation range"
            )
        if not rule.required_item_id:
            raise BreakthroughCatalogError("Breakthrough required_item_id must not be empty")
        if not rule.profile_ids:
            raise BreakthroughCatalogError("Breakthrough rule must define typed profiles")
        for root_kind, profile_id in rule.profile_ids.items():
            if root_kind not in {"one_to_three_root", "four_root", "five_root"}:
                raise BreakthroughCatalogError(
                    f"Unsupported breakthrough root profile: {root_kind}"
                )
            if profile_id not in profiles:
                raise BreakthroughCatalogError(f"Unknown breakthrough profile: {profile_id}")
        if tuple(sorted(rule.failure_policies)) != rule.source_levels:
            raise BreakthroughCatalogError(
                "Breakthrough failure policies must cover every source level"
            )
        for source_level, policy in rule.failure_policies.items():
            if policy.mode not in {"secondary_50_50", "forced_loss"}:
                raise BreakthroughCatalogError(
                    f"Unsupported breakthrough failure mode: {policy.mode}"
                )
            if policy.mode == "secondary_50_50":
                if (
                    policy.advance_target_level != source_level + 1
                    or policy.secondary_basis_points != 5_000
                ):
                    raise BreakthroughCatalogError(
                        "secondary_50_50 failure policy must advance one level at 5000 basis points"
                    )
            elif policy.advance_target_level is not None:
                raise BreakthroughCatalogError("forced_loss failure policy must not advance")
            if (
                isinstance(policy.loss_numerator, bool)
                or not isinstance(policy.loss_numerator, int)
                or isinstance(policy.loss_denominator, bool)
                or not isinstance(policy.loss_denominator, int)
                or isinstance(policy.secondary_basis_points, bool)
                or not isinstance(policy.secondary_basis_points, int)
                or (
                    policy.advance_target_level is not None
                    and (
                        isinstance(policy.advance_target_level, bool)
                        or not isinstance(policy.advance_target_level, int)
                    )
                )
            ):
                raise BreakthroughCatalogError(
                    "Breakthrough failure policy numeric fields must be integers"
                )
            if (
                policy.loss_numerator <= 0
                or policy.loss_denominator <= 0
                or policy.loss_numerator > policy.loss_denominator
            ):
                raise BreakthroughCatalogError(
                    "Breakthrough loss fraction must be positive and bounded"
                )
        if rule.rule_id == "qi_to_foundation":
            expected_profiles = {
                "one_to_three_root": "one_to_three_root",
                "four_root": "four_root",
                "five_root": "five_root",
            }
            expected_policies = {
                10: FailurePolicy("secondary_50_50", 11),
                11: FailurePolicy("secondary_50_50", 12),
                12: FailurePolicy("secondary_50_50", 13),
                13: FailurePolicy("forced_loss"),
            }
            if (
                rule.source_levels != (10, 11, 12, 13)
                or rule.target_level != 14
                or rule.duration_seconds != 600
                or rule.duration_min_seconds != 600
                or rule.duration_max_seconds != 900
                or rule.required_item_id != "foundation_pill"
                or dict(rule.profile_ids) != expected_profiles
                or dict(rule.failure_policies) != expected_policies
            ):
                raise BreakthroughCatalogError(
                    "qi_to_foundation must match the exact initial foundation breakthrough contract"
                )

    @property
    def schema_version(self) -> int:
        return self._schema_version

    @property
    def profiles(self) -> Mapping[str, BreakthroughProfile]:
        return self._profiles

    @property
    def rules(self) -> Mapping[str, BreakthroughRule]:
        return self._rules

    def profile(self, profile_id: str) -> BreakthroughProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as error:
            raise KeyError(f"Unknown breakthrough profile: {profile_id}") from error

    def rule(self, rule_id: str) -> BreakthroughRule:
        try:
            return self._rules[rule_id]
        except KeyError as error:
            raise KeyError(f"Unknown breakthrough rule: {rule_id}") from error


def load_breakthrough_catalog(path: Path) -> BreakthroughCatalog:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BreakthroughCatalogError(f"Invalid breakthrough catalog JSON: {path}") from error
    if not isinstance(document, dict):
        raise BreakthroughCatalogError("Breakthrough catalog must be a JSON object")
    _reject_unknown_fields(
        document, {"schema_version", "profiles", "rules"}, "breakthrough catalog"
    )
    return BreakthroughCatalog(
        schema_version=_required_int(document, "schema_version"),
        profiles=tuple(_parse_profile(item) for item in _required_list(document, "profiles")),
        rules=tuple(_parse_rule(item) for item in _required_list(document, "rules")),
    )


def _parse_profile(document: dict[str, Any]) -> BreakthroughProfile:
    _reject_unknown_fields(
        document,
        {"profile_id", "root_counts", "pill_counts", "basis_points"},
        "breakthrough profile",
    )
    return BreakthroughProfile(
        profile_id=_required_str(document, "profile_id"),
        root_counts=tuple(_required_int_list(document, "root_counts")),
        pill_counts=tuple(_required_int_list(document, "pill_counts")),
        basis_points=tuple(_required_int_list(document, "basis_points")),
    )


def _parse_rule(document: dict[str, Any]) -> BreakthroughRule:
    _reject_unknown_fields(
        document,
        {
            "rule_id",
            "source_levels",
            "target_level",
            "duration_seconds",
            "duration_min_seconds",
            "duration_max_seconds",
            "required_item_id",
            "profiles",
            "failure_policies",
        },
        "breakthrough rule",
    )
    profiles = document.get("profiles")
    if not isinstance(profiles, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in profiles.items()
    ):
        raise BreakthroughCatalogError("Breakthrough rule profiles must be an object of string IDs")
    failure_policies = document.get("failure_policies")
    if not isinstance(failure_policies, dict):
        raise BreakthroughCatalogError("Breakthrough rule failure_policies must be an object")
    parsed_policies: dict[int, FailurePolicy] = {}
    for source_level, policy in failure_policies.items():
        if (
            not isinstance(source_level, str)
            or not source_level.isdigit()
            or not isinstance(policy, dict)
        ):
            raise BreakthroughCatalogError(
                "Breakthrough failure policy keys must be numeric strings and values objects"
            )
        _reject_unknown_fields(
            policy,
            {
                "mode",
                "advance_target_level",
                "loss_numerator",
                "loss_denominator",
                "secondary_basis_points",
            },
            "failure policy",
        )
        parsed_policies[int(source_level)] = FailurePolicy(
            mode=_required_str(policy, "mode"),
            advance_target_level=_optional_int_or_null(policy, "advance_target_level"),
            loss_numerator=_optional_int(policy, "loss_numerator", 1),
            loss_denominator=_optional_int(policy, "loss_denominator", 3),
            secondary_basis_points=_optional_int(policy, "secondary_basis_points", 5_000),
        )
    return BreakthroughRule(
        rule_id=_required_str(document, "rule_id"),
        source_levels=tuple(_required_int_list(document, "source_levels")),
        target_level=_required_int(document, "target_level"),
        duration_seconds=_required_int(document, "duration_seconds"),
        duration_min_seconds=_required_int(document, "duration_min_seconds"),
        duration_max_seconds=_required_int(document, "duration_max_seconds"),
        required_item_id=_required_str(document, "required_item_id"),
        profile_ids=profiles,
        failure_policies=parsed_policies,
    )


def _required_list(document: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise BreakthroughCatalogError(
            f"Breakthrough catalog field {key} must be a list of objects"
        )
    return value


def _required_int_list(document: dict[str, Any], key: str) -> list[int]:
    value = document.get(key)
    if not isinstance(value, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in value
    ):
        raise BreakthroughCatalogError(
            f"Breakthrough catalog field {key} must be a list of integers"
        )
    return value


def _required_str(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise BreakthroughCatalogError(f"Breakthrough catalog field {key} must be a string")
    return value


def _required_int(document: dict[str, Any], key: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise BreakthroughCatalogError(f"Breakthrough catalog field {key} must be an integer")
    return value


def _optional_int(document: dict[str, Any], key: str, default: int) -> int:
    if key not in document:
        return default
    return _required_int(document, key)


def _optional_int_or_null(document: dict[str, Any], key: str) -> int | None:
    if key not in document or document[key] is None:
        return None
    return _required_int(document, key)


def _reject_unknown_fields(document: dict[str, Any], allowed: set[str], label: str) -> None:
    unexpected = sorted(set(document) - allowed)
    if unexpected:
        raise BreakthroughCatalogError(f"Unexpected {label} fields: {', '.join(unexpected)}")
