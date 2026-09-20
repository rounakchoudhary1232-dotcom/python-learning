from dataclasses import replace
from app.services.decision_engine import DecisionConstraints, DecisionEngine
from app.services.strategies import StrategySignal
from app.services.trading import SimulatedMarketDataProvider, analyze_market

def context(): return analyze_market("SPY", "5m", SimulatedMarketDataProvider().candles("SPY", "5m"))
def constraints(**x): return DecisionConstraints(.6, 1.5, **x)
def signal(direction="BUY", score=80): return StrategySignal("test", direction, score, ["deterministic evidence"], True, {})
def test_buy_and_serialization_are_deterministic():
    c=replace(context(), mtf_summary="ALIGNED_BULLISH")
    a=DecisionEngine().decide(c,constraints(),[signal()]); b=DecisionEngine().decide(c,constraints(),[signal()])
    assert a.action=="BUY" and a.confidence==b.confidence and a.paper_only and "action" in a.payload()
def test_sell_hold_conflict_and_no_compatible_signal():
    engine=DecisionEngine(); base=context(); c=replace(base, support_resistance={"support": base.current_price-10, "resistance": base.current_price+1})
    assert engine.decide(c,constraints(),[signal("SELL")]).action=="SELL"
    assert engine.decide(c,constraints(),[signal(),signal("SELL")]).action=="HOLD"
    assert engine.decide(c,constraints(),[StrategySignal("test", "REJECT", 0, [], False, {})]).action=="HOLD"
def test_hard_constraints_invalid_context_and_rr_safety_reject():
    engine=DecisionEngine(); c=context()
    assert engine.decide(c,constraints(kill_switch=True),[signal()]).action=="REJECT"
    assert engine.decide(None,constraints()).action=="REJECT"
    invalid=replace(c, volatility={"atr":0})
    assert engine.decide(invalid,constraints(),[signal()]).action=="REJECT"
def test_mtf_conflict_and_confidence_threshold_reject():
    c=replace(context(), mtf_summary="MIXED")
    assert DecisionEngine().decide(c,constraints(),[signal(score=70)]).action=="REJECT"
