"""Authoritative, deterministic paper-trade risk assessment; no execution side effects."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import math

@dataclass(frozen=True)
class RiskLimits:
    max_risk_per_trade: float; min_risk_reward: float; max_daily_loss: float
    max_trades_per_day: int; max_drawdown: float; max_exposure: float = 1.0
    max_consecutive_losses: int = 3; stale_data_seconds: int = 900

@dataclass(frozen=True)
class AccountRiskState:
    balance: float; equity: float; daily_loss: float = 0; trade_count_today: int = 0
    exposure: float = 0; consecutive_losses: int = 0; kill_switch: bool = False
    mode: str = "PAPER"; open_same_position: bool = False

@dataclass(frozen=True)
class RiskAssessment:
    allowed: bool; reasons: list[str]; risk_per_trade: float; calculated_position_size: float
    entry_price: float | None; stop_loss: float | None; take_profit: float | None
    expected_risk_reward: float | None; max_allowed_risk: float; current_daily_loss: float
    current_drawdown: float; current_exposure: float; trade_count_today: int
    consecutive_losses: int; kill_switch: bool; paper_only: bool = True
    def payload(self) -> dict: return asdict(self)

def assess(action: str, entry: float | None, stop: float | None, target: float | None, timestamp: datetime | None, state: AccountRiskState, limits: RiskLimits) -> RiskAssessment:
    reasons: list[str] = []; max_risk = state.equity * limits.max_risk_per_trade
    drawdown = max(0.0, (state.balance - state.equity) / state.balance) if state.balance > 0 else 1.0
    values = (entry, stop, target)
    if action not in {"BUY", "SELL"}: reasons.append("decision is not an executable BUY or SELL")
    if state.mode != "PAPER": reasons.append("PAPER mode required")
    if state.kill_switch: reasons.append("paper trading kill switch is enabled")
    if not all(isinstance(value, (int, float)) and math.isfinite(value) and value > 0 for value in values): reasons.append("entry, stop loss, and take profit must be positive finite values")
    elif (action == "BUY" and not (stop < entry < target)) or (action == "SELL" and not (target < entry < stop)): reasons.append("stop loss/take profit are invalid for trade direction")
    if timestamp and (datetime.now(UTC) - timestamp.astimezone(UTC)).total_seconds() > limits.stale_data_seconds: reasons.append("market data is stale")
    risk = abs(entry - stop) if not reasons or all("entry" not in item and "direction" not in item for item in reasons) else 0.0
    reward = abs(target - entry) if risk else 0.0; rr = reward / risk if risk else None
    quantity = max_risk / risk if risk else 0.0
    if rr is not None and rr < limits.min_risk_reward: reasons.append("expected R:R below minimum")
    if state.daily_loss >= state.balance * limits.max_daily_loss: reasons.append("max daily loss reached")
    if state.trade_count_today >= limits.max_trades_per_day: reasons.append("max trades per day reached")
    if drawdown >= limits.max_drawdown: reasons.append("max drawdown reached")
    if state.exposure + max_risk > state.equity * limits.max_exposure: reasons.append("max exposure reached")
    if state.consecutive_losses >= limits.max_consecutive_losses: reasons.append("max consecutive losses reached")
    if state.open_same_position: reasons.append("duplicate open paper position")
    if quantity <= 0 or not math.isfinite(quantity): reasons.append("invalid position size")
    return RiskAssessment(not reasons, reasons, max_risk, quantity, entry, stop, target, rr, max_risk, state.daily_loss, drawdown, state.exposure, state.trade_count_today, state.consecutive_losses, state.kill_switch)
