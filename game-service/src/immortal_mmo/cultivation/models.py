from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CombatCultivationCredit:
    entry_id: UUID
    life_id: UUID
    kill_event_id: UUID
    amount: int
    balance_after: int
    revision: int
