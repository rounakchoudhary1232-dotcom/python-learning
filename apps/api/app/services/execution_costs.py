"""Deterministic execution-cost assumptions for research simulations only."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class ExecutionCostConfig:
    fee_rate: float = 0.0
    slippage_bps: float = 0.0
    slippage_price: float = 0.0
    minimum_fee: float = 0.0

    def __post_init__(self) -> None:
        values = (self.fee_rate, self.slippage_bps, self.slippage_price, self.minimum_fee)
        if not all(math.isfinite(value) and value >= 0 for value in values):
            raise ValueError("execution-cost configuration values must be finite and non-negative")


@dataclass(frozen=True)
class ExecutionCost:
    entry_price: float
    exit_price: float
    entry_fee: float
    exit_fee: float
    total_cost: float

    def payload(self) -> dict: return asdict(self)


class ExecutionCostModel:
    def __init__(self, config: ExecutionCostConfig = ExecutionCostConfig()): self.config = config

    def execution_price(self, direction: str, price: float, is_entry: bool) -> float:
        self._validate(direction, price, 1.0)
        adverse_up = (direction == "BUY") == is_entry
        slippage = self.config.slippage_price + price * self.config.slippage_bps / 10_000
        return price + slippage if adverse_up else price - slippage

    def fee(self, executed_price: float, quantity: float) -> float:
        self._validate("BUY", executed_price, quantity)
        if quantity == 0: return 0.0
        return max(self.config.minimum_fee, executed_price * quantity * self.config.fee_rate)

    def round_trip(self, direction: str, entry_price: float, exit_price: float, quantity: float) -> ExecutionCost:
        self._validate(direction, entry_price, quantity); self._validate(direction, exit_price, quantity)
        entry = self.execution_price(direction, entry_price, True); exit_ = self.execution_price(direction, exit_price, False)
        entry_fee, exit_fee = self.fee(entry, quantity), self.fee(exit_, quantity)
        slippage_cost = abs(entry - entry_price) * quantity + abs(exit_ - exit_price) * quantity
        return ExecutionCost(entry, exit_, entry_fee, exit_fee, entry_fee + exit_fee + slippage_cost)

    @staticmethod
    def _validate(direction: str, price: float, quantity: float) -> None:
        if direction not in {"BUY", "SELL"}: raise ValueError("direction must be BUY or SELL")
        if not all(math.isfinite(value) and value >= 0 for value in (price, quantity)):
            raise ValueError("prices and quantity must be finite and non-negative")
