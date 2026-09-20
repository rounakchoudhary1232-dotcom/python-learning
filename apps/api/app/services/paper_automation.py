"""Paper-only position monitoring primitives; no broker or external calls."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import math

@dataclass(frozen=True)
class PositionSnapshot:
    direction: str; entry: float; stop_loss: float; take_profit: float; quantity: float; status: str = "OPEN"

@dataclass(frozen=True)
class MonitoringResult:
    action: str; exit_price: float | None; exit_reason: str | None; pnl: float | None; paper_only: bool = True
    def payload(self) -> dict: return asdict(self)

def monitor_position(position: PositionSnapshot, current_price: float) -> MonitoringResult:
    """Candle-level rule: if SL and TP are both touched, choose SL conservatively."""
    values = (position.entry, position.stop_loss, position.take_profit, position.quantity, current_price)
    if position.status != "OPEN" or position.direction not in {"BUY", "SELL"} or not all(isinstance(x, (int, float)) and math.isfinite(x) and x > 0 for x in values): return MonitoringResult("REJECT", None, "invalid or closed paper position", None)
    if position.direction == "BUY":
        if current_price <= position.stop_loss: exit_price, reason = position.stop_loss, "EXIT_SL"
        elif current_price >= position.take_profit: exit_price, reason = position.take_profit, "EXIT_TP"
        else: return MonitoringResult("HOLD", None, None, None)
        pnl = (exit_price - position.entry) * position.quantity
    else:
        if current_price >= position.stop_loss: exit_price, reason = position.stop_loss, "EXIT_SL"
        elif current_price <= position.take_profit: exit_price, reason = position.take_profit, "EXIT_TP"
        else: return MonitoringResult("HOLD", None, None, None)
        pnl = (position.entry - exit_price) * position.quantity
    return MonitoringResult("CLOSE", exit_price, reason, pnl)
