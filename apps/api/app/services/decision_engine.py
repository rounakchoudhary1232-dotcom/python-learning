"""Read-only deterministic aggregation of Phase 2 strategy signals."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
from .strategies import StrategyEvaluator, StrategySignal
from .trading import MarketContext

@dataclass(frozen=True)
class DecisionConstraints:
    min_confidence: float
    min_risk_reward: float
    trading_mode: str = "PAPER"
    kill_switch: bool = False

@dataclass(frozen=True)
class IntelligenceDecision:
    symbol: str; action: str; confidence: float; selected_strategies: list[str]
    reasons: list[str]; regime: str; mtf_confirmation: str; entry: float | None
    stop_loss: float | None; take_profit: float | None; expected_risk_reward: float | None
    rejection_reasons: list[str]; timestamp: datetime; paper_only: bool = True
    def payload(self) -> dict: return asdict(self)

def mtf_confirmation(context: MarketContext) -> tuple[str, float]:
    if context.mtf_summary in {"ALIGNED_BULLISH", "ALIGNED_BEARISH"}: return "ALIGNED", .1
    if context.mtf_summary == "MIXED": return "CONFLICT", -.15
    return "INSUFFICIENT", 0.0

def risk_levels(context: MarketContext, action: str) -> tuple[float | None, float | None, float | None, str | None]:
    entry = context.current_price
    atr = context.volatility.get("atr")
    if not isinstance(entry, (int, float)) or entry <= 0 or not isinstance(atr, (int, float)) or atr <= 0: return entry if entry else None, None, None, "R:R unavailable: valid entry and ATR are required"
    support, resistance = context.support_resistance.get("support"), context.support_resistance.get("resistance")
    stop = support if action == "BUY" and isinstance(support, (int, float)) and support < entry else resistance if action == "SELL" and isinstance(resistance, (int, float)) and resistance > entry else entry - atr if action == "BUY" else entry + atr
    target = resistance if action == "BUY" and isinstance(resistance, (int, float)) and resistance > entry else support if action == "SELL" and isinstance(support, (int, float)) and support < entry else entry + 2 * atr if action == "BUY" else entry - 2 * atr
    risk = abs(entry - stop); reward = abs(target - entry)
    if risk <= 0 or reward <= 0: return entry, stop, target, "R:R unavailable: invalid risk distance"
    return entry, stop, target, None

class DecisionEngine:
    def __init__(self, evaluator: StrategyEvaluator | None = None): self.evaluator = evaluator or StrategyEvaluator()
    def decide(self, context: MarketContext | None, constraints: DecisionConstraints, signals: list[StrategySignal] | None = None) -> IntelligenceDecision:
        now = context.timestamp if context else datetime.now()
        if context is None or not context.data_quality.get("valid", False): return self._result(context, "REJECT", 0, [], ["invalid or missing market context"], "INSUFFICIENT", None, None, None, None, ["invalid or missing market context"], now)
        if constraints.trading_mode != "PAPER" or constraints.kill_switch: return self._result(context, "REJECT", 0, [], ["hard trading safety constraint"], "INSUFFICIENT", None, None, None, None, ["PAPER mode required" if constraints.trading_mode != "PAPER" else "paper trading kill switch is enabled"], now)
        usable = [s for s in (signals or self.evaluator.evaluate(context)) if s.regime_compatible and s.signal in {"BUY", "SELL"}]
        buys, sells = [s for s in usable if s.signal == "BUY"], [s for s in usable if s.signal == "SELL"]
        mtf, adjustment = mtf_confirmation(context)
        if not usable: return self._result(context, "HOLD", 0, [], ["no compatible strategy evidence"], mtf, None, None, None, None, [], now)
        if buys and sells: return self._result(context, "HOLD", 0, [], ["conflicting compatible strategy directions"], mtf, None, None, None, None, [], now)
        chosen = buys or sells; action = "BUY" if buys else "SELL"; confidence = max(0.0, min(1.0, sum(s.score for s in chosen) / (100 * len(chosen)) + adjustment))
        entry, stop, target, error = risk_levels(context, action)
        rejection: list[str] = []
        if confidence < constraints.min_confidence: rejection.append("evidence score below minimum confidence")
        if error: rejection.append(error); rr = None
        else:
            rr = abs(target - entry) / abs(entry - stop) if entry is not None and stop is not None and target is not None else None
            if rr is not None and rr < constraints.min_risk_reward: rejection.append("expected R:R below minimum")
        return self._result(context, "REJECT" if rejection else action, confidence, [s.strategy_name for s in chosen], [reason for s in chosen for reason in s.evidence] + [f"MTF: {mtf}"], mtf, entry, stop, target, rr, rejection, now)
    def _result(self, context, action, confidence, selected, reasons, mtf, entry, stop, target, rr, rejected, timestamp): return IntelligenceDecision(context.symbol if context else "UNKNOWN", action, round(confidence, 2), selected, reasons, context.regime.get("state", "UNCLEAR") if context else "UNCLEAR", mtf, entry, stop, target, rr, rejected, timestamp)
