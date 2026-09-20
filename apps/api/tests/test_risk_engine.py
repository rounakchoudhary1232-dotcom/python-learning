from datetime import UTC, datetime
from app.services.risk_engine import AccountRiskState, RiskLimits, assess

def limits(**x): return RiskLimits(.01,1.5,.03,5,.10,**x)
def state(**x): return AccountRiskState(**({"balance":10000,"equity":10000}|x))
def test_valid_buy_and_sell_size_risk():
    buy=assess("BUY",100,99,102,datetime.now(UTC),state(),limits()); sell=assess("SELL",100,101,98,datetime.now(UTC),state(),limits())
    assert buy.allowed and sell.allowed and buy.calculated_position_size==100 and buy.expected_risk_reward==2
def test_invalid_levels_rr_and_hard_limits_reject():
    assert not assess("BUY",100,100,102,datetime.now(UTC),state(),limits()).allowed
    assert not assess("BUY",100,99,100.5,datetime.now(UTC),state(),limits()).allowed
    assert not assess("BUY",100,99,102,datetime.now(UTC),state(kill_switch=True),limits()).allowed
    assert not assess("BUY",100,99,102,datetime.now(UTC),state(trade_count_today=5),limits()).allowed
def test_daily_drawdown_exposure_losses_duplicate_and_paper_are_authoritative():
    for s,l in [(state(daily_loss=300),limits()),(state(equity=9000),limits()),(state(exposure=10000),limits()),(state(consecutive_losses=3),limits()),(state(open_same_position=True),limits()),(state(mode="LIVE"),limits())]: assert not assess("BUY",100,99,102,datetime.now(UTC),s,l).allowed
def test_assessment_is_serializable_and_deterministic():
    a=assess("BUY",100,99,102,None,state(),limits()); b=assess("BUY",100,99,102,None,state(),limits()); assert a.payload()==b.payload() and a.paper_only
