import json
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

from immortal_mmo.combat.models import RewardDecision

MAX_REWARD_AMOUNT = 9_223_372_036_854_775_807


@dataclass(frozen=True, slots=True)
class LevelRewardCurve:
    curve_id: str
    min_level: Decimal
    max_level: Decimal
    reward_per_level: int


@dataclass(frozen=True, slots=True)
class RewardProfile:
    profile_id: str
    base_reward: int
    level_curve_id: str | None


@dataclass(frozen=True, slots=True)
class MobRewardDefinition:
    internal_name: str
    reward_profile_id: str
    telemetry: Literal["compact", "detailed"]


class CombatRewardCatalog:
    def __init__(
        self,
        *,
        schema_version: int,
        curves: tuple[LevelRewardCurve, ...],
        profiles: tuple[RewardProfile, ...],
        mobs: tuple[MobRewardDefinition, ...],
    ) -> None:
        if schema_version != 1:
            raise ValueError("Unsupported combat reward schema_version")

        self._curves = MappingProxyType(self._unique_by_id(curves, "curve_id", "level curve"))
        self._profiles = MappingProxyType(
            self._unique_by_id(profiles, "profile_id", "reward profile")
        )
        self._mobs = MappingProxyType(
            self._unique_by_id(mobs, "internal_name", "Mythic mob internal name")
        )
        self.schema_version = schema_version
        self._validate()

    def resolve(self, internal_name: str, level: Decimal) -> RewardDecision | None:
        mob = self._mobs.get(internal_name)
        if mob is None:
            return None
        profile = self._profiles[mob.reward_profile_id]
        amount = profile.base_reward
        if profile.level_curve_id is not None:
            curve = self._curves[profile.level_curve_id]
            if level < curve.min_level or level > curve.max_level:
                raise ValueError("Mob level is outside curve bounds")
            level_steps = int((level - curve.min_level).to_integral_value(rounding=ROUND_FLOOR))
            amount = self._checked_add(
                profile.base_reward,
                self._checked_multiply(level_steps, curve.reward_per_level),
            )
        return RewardDecision(
            amount=amount,
            telemetry=mob.telemetry,
            profile_id=profile.profile_id,
            mob_level=level,
        )

    def _validate(self) -> None:
        for curve in self._curves.values():
            if not curve.curve_id:
                raise ValueError("Level curve ID must not be empty")
            if not curve.min_level.is_finite() or not curve.max_level.is_finite():
                raise ValueError("Level curve bounds must be finite")
            if curve.min_level < 0 or curve.max_level < curve.min_level:
                raise ValueError("Invalid level curve bounds")
            if curve.reward_per_level < 0:
                raise ValueError("Level reward must be non-negative")

        for profile in self._profiles.values():
            if not profile.profile_id:
                raise ValueError("Reward profile ID must not be empty")
            if profile.base_reward <= 0 or profile.base_reward > MAX_REWARD_AMOUNT:
                raise ValueError("Reward profile base amount is invalid")
            if profile.level_curve_id is None:
                continue
            curve = self._curves.get(profile.level_curve_id)
            if curve is None:
                raise ValueError(f"Unknown level curve: {profile.level_curve_id}")
            max_steps = int(
                (curve.max_level - curve.min_level).to_integral_value(rounding=ROUND_FLOOR)
            )
            self._checked_add(
                profile.base_reward,
                self._checked_multiply(max_steps, curve.reward_per_level),
            )

        for mob in self._mobs.values():
            if not mob.internal_name:
                raise ValueError("Mythic mob internal name must not be empty")
            if mob.reward_profile_id not in self._profiles:
                raise ValueError(f"Unknown reward profile: {mob.reward_profile_id}")
            if mob.telemetry not in ("compact", "detailed"):
                raise ValueError(f"Unsupported telemetry mode: {mob.telemetry}")

    @staticmethod
    def _unique_by_id(items: tuple[object, ...], field: str, label: str) -> dict[str, object]:
        result: dict[str, object] = {}
        for item in items:
            value = getattr(item, field)
            if value in result:
                raise ValueError(f"Duplicate {label}: {value}")
            result[value] = item
        return result

    @staticmethod
    def _checked_multiply(left: int, right: int) -> int:
        result = left * right
        if result > MAX_REWARD_AMOUNT:
            raise ValueError("Combat reward arithmetic overflow")
        return result

    @staticmethod
    def _checked_add(left: int, right: int) -> int:
        result = left + right
        if result > MAX_REWARD_AMOUNT:
            raise ValueError("Combat reward arithmetic overflow")
        return result


def load_combat_reward_catalog(path: Path) -> CombatRewardCatalog:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid combat reward catalog JSON: {path}") from error
    if not isinstance(document, dict):
        raise ValueError("Combat reward catalog must be a JSON object")

    return CombatRewardCatalog(
        schema_version=_required_int(document, "schema_version"),
        curves=tuple(
            LevelRewardCurve(
                curve_id=_required_str(item, "curve_id"),
                min_level=_required_decimal(item, "min_level"),
                max_level=_required_decimal(item, "max_level"),
                reward_per_level=_required_int(item, "reward_per_level"),
            )
            for item in _required_list(document, "level_curves")
        ),
        profiles=tuple(
            RewardProfile(
                profile_id=_required_str(item, "profile_id"),
                base_reward=_required_int(item, "base_reward"),
                level_curve_id=_optional_str(item, "level_curve_id"),
            )
            for item in _required_list(document, "reward_profiles")
        ),
        mobs=tuple(
            MobRewardDefinition(
                internal_name=_required_str(item, "internal_name"),
                reward_profile_id=_required_str(item, "reward_profile_id"),
                telemetry=_required_telemetry(item, "telemetry"),
            )
            for item in _required_list(document, "mobs")
        ),
    )


def _required_list(document: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = document.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Combat reward catalog field {key} must be a list of objects")
    return value


def _required_str(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Combat reward catalog field {key} must be a string")
    return value


def _optional_str(document: dict[str, Any], key: str) -> str | None:
    value = document.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"Combat reward catalog field {key} must be a string or null")
    return value


def _required_int(document: dict[str, Any], key: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Combat reward catalog field {key} must be an integer")
    return value


def _required_decimal(document: dict[str, Any], key: str) -> Decimal:
    value = document.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Combat reward catalog field {key} must be a decimal string")
    try:
        decimal = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Combat reward catalog field {key} must be a decimal string") from error
    return decimal


def _required_telemetry(
    document: dict[str, Any],
    key: str,
) -> Literal["compact", "detailed"]:
    value = _required_str(document, key)
    if value not in ("compact", "detailed"):
        raise ValueError(f"Unsupported telemetry mode: {value}")
    return value
