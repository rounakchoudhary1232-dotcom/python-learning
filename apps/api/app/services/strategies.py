"""Deterministic, read-only strategy intelligence built on MarketContext."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from .trading import MarketContext


REGIME_COMPATIBILITY: dict[str, frozenset[str]] = {
    "trend_following": frozenset({"TRENDING_BULL", "TRENDING_BEAR"}),
    "momentum": frozenset({"TRENDING_BULL", "TRENDING_BEAR", "HIGH_VOLATILITY"}),
    "breakout": frozenset({"TRENDING_BULL", "TRENDING_BEAR", "HIGH_VOLATILITY", "LOW_VOLATILITY"}),
    "mean_reversion": frozenset({"RANGE", "LOW_VOLATILITY"}),
    "volatility_breakout": frozenset({"HIGH_VOLATILITY", "LOW_VOLATILITY"}),
}


@dataclass(frozen=True)
class StrategySignal:
    """Score is deterministic evidence strength, never a probability."""
    strategy_name: str
    signal: str
    score: int
    evidence: list[str]
    regime_compatible: bool
    factors: dict[str, str]

    def payload(self) -> dict: return asdict(self)


class Strategy(Protocol):
    strategy_name: str
    def evaluate(self, context: MarketContext) -> StrategySignal: ...


def _evaluate(name: str, context: MarketContext, direction: str, checks: list[tuple[bool, str]], factors: dict[str, str]) -> StrategySignal:
    if not context.data_quality.get("valid", False):
        return StrategySignal(name, "REJECT", 0, ["invalid or insufficient market context"], False, factors)
    compatible = context.regime.get("state") in REGIME_COMPATIBILITY[name]
    if not compatible:
        return StrategySignal(name, "REJECT", 0, [f"incompatible regime: {context.regime.get('state', 'UNKNOWN')}"], False, factors)
    evidence = [reason for passed, reason in checks if passed]
    if len(evidence) < 2:
        return StrategySignal(name, "HOLD", len(evidence) * 25, evidence + ["insufficient confluence"], True, factors)
    return StrategySignal(name, direction, min(100, 40 + len(evidence) * 20), evidence, True, factors)


class TrendFollowing:
    strategy_name = "trend_following"
    def evaluate(self, c: MarketContext) -> StrategySignal:
        direction = "BUY" if c.trend == "BULLISH" else "SELL"
        return _evaluate(self.strategy_name, c, direction, [(c.structure.get("state") == c.trend, "trend and structure align"), (c.momentum == c.trend, "momentum aligns with trend"), (c.mtf_summary == f"ALIGNED_{c.trend}", "multi-timeframe alignment")], {"trend": c.trend, "structure": c.structure.get("state", "UNKNOWN"), "momentum": c.momentum, "mtf": c.mtf_summary})


class Momentum:
    strategy_name = "momentum"
    def evaluate(self, c: MarketContext) -> StrategySignal:
        direction = "BUY" if c.momentum == "BULLISH" else "SELL"
        return _evaluate(self.strategy_name, c, direction, [(c.momentum in {"BULLISH", "BEARISH"}, "directional momentum"), (c.trend == c.momentum, "trend confirmation"), (c.volume_state == "EXPANDED", "expanded volume")], {"momentum": c.momentum, "trend": c.trend, "volume": c.volume_state})


class Breakout:
    strategy_name = "breakout"
    def evaluate(self, c: MarketContext) -> StrategySignal:
        state = c.breakout.get("state", "NONE")
        return _evaluate(self.strategy_name, c, "BUY" if "BULLISH" in state else "SELL", [(state in {"BULLISH_BREAKOUT", "BEARISH_BREAKOUT"}, "confirmed breakout"), (c.breakout.get("strength", 0) >= .5, "breakout strength threshold met"), (c.volume_state == "EXPANDED", "volume confirmation")], {"breakout": state, "volume": c.volume_state, "volatility": c.volatility.get("state", "UNKNOWN")})


class MeanReversion:
    strategy_name = "mean_reversion"
    def evaluate(self, c: MarketContext) -> StrategySignal:
        near_support, near_resistance = bool(c.support_resistance.get("near_support")), bool(c.support_resistance.get("near_resistance"))
        return _evaluate(self.strategy_name, c, "BUY" if near_support else "SELL", [(near_support or near_resistance, "price near range boundary"), (c.structure.get("state") == "RANGING", "ranging structure"), (c.reversal.get("state") in {"BULLISH_EVIDENCE", "BEARISH_EVIDENCE"}, "reversal evidence")], {"structure": c.structure.get("state", "UNKNOWN"), "reversal": c.reversal.get("state", "NONE"), "near_support": str(near_support), "near_resistance": str(near_resistance)})


class VolatilityBreakout:
    strategy_name = "volatility_breakout"
    def evaluate(self, c: MarketContext) -> StrategySignal:
        state = c.breakout.get("state", "NONE")
        return _evaluate(self.strategy_name, c, "BUY" if "BULLISH" in state else "SELL", [(c.volatility.get("state") in {"HIGH", "EXTREME"}, "volatility expansion"), (state in {"BULLISH_BREAKOUT", "BEARISH_BREAKOUT"}, "confirmed breakout"), (c.volume_state == "EXPANDED", "expanded volume")], {"volatility": c.volatility.get("state", "UNKNOWN"), "breakout": state, "volume": c.volume_state})


class StrategyRegistry:
    def __init__(self, strategies: tuple[Strategy, ...] = (TrendFollowing(), Momentum(), Breakout(), MeanReversion(), VolatilityBreakout())): self._strategies = strategies
    def all(self) -> tuple[Strategy, ...]: return self._strategies
    def compatible(self, context: MarketContext) -> tuple[Strategy, ...]: return tuple(item for item in self._strategies if context.regime.get("state") in REGIME_COMPATIBILITY[item.strategy_name])


class StrategyEvaluator:
    def __init__(self, registry: StrategyRegistry | None = None): self.registry = registry or StrategyRegistry()
    def evaluate(self, context: MarketContext) -> list[StrategySignal]: return [strategy.evaluate(context) for strategy in self.registry.all()]
