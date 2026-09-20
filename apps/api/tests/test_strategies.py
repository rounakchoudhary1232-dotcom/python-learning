from dataclasses import replace

from app.services.strategies import REGIME_COMPATIBILITY, StrategyEvaluator, StrategyRegistry
from app.services.trading import SimulatedMarketDataProvider, analyze_market


def market_context(): return analyze_market("SPY", "5m", SimulatedMarketDataProvider().candles("SPY", "5m"))


def test_registry_evaluates_all_five_normalized_strategies_without_side_effects():
    results = StrategyEvaluator().evaluate(market_context())
    assert len(results) == 5
    assert {item.strategy_name for item in results} == set(REGIME_COMPATIBILITY)
    assert all(item.signal in {"BUY", "SELL", "HOLD", "REJECT"} and 0 <= item.score <= 100 for item in results)
    assert all(set(item.payload()) == {"strategy_name", "signal", "score", "evidence", "regime_compatible", "factors"} for item in results)


def test_invalid_context_rejects_all_strategies():
    invalid = analyze_market("SPY", "5m", SimulatedMarketDataProvider().candles("SPY", "5m", 5))
    assert {item.signal for item in StrategyEvaluator().evaluate(invalid)} == {"REJECT"}


def test_trend_following_buy_and_incompatible_regime_reject():
    base = market_context()
    aligned = replace(base, trend="BULLISH", momentum="BULLISH", mtf_summary="ALIGNED_BULLISH", structure={"state": "BULLISH"}, regime={"state": "TRENDING_BULL"}, data_quality={"valid": True})
    assert StrategyEvaluator().evaluate(aligned)[0].signal == "BUY"
    incompatible = replace(aligned, regime={"state": "RANGE"})
    assert StrategyEvaluator().evaluate(incompatible)[0].signal == "REJECT"


def test_registry_compatibility_is_explicit_and_deterministic():
    context = replace(market_context(), regime={"state": "RANGE"})
    assert [item.strategy_name for item in StrategyRegistry().compatible(context)] == ["mean_reversion"]
