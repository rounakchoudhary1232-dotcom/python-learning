from datetime import UTC, datetime, timedelta
from app.services.trading import Candle, SimulatedMarketDataProvider, atr, backtest, make_decision
from fastapi.testclient import TestClient
from app.main import app
from uuid import uuid4


def rules(**overrides):
    return {"max_risk_per_trade": .01, "min_confidence": .60, "min_risk_reward": 1.5, "kill_switch": False} | overrides


def test_simulated_market_data_is_deterministic_and_complete():
    provider = SimulatedMarketDataProvider()
    assert provider.candles("BTCUSD", "5m", 10) == provider.candles("BTCUSD", "5m", 10)
    assert all(candle.high >= max(candle.open, candle.close) >= candle.low for candle in provider.candles("BTCUSD", "5m", 10))


def test_indicator_and_risk_sized_decision_have_no_invalid_prices():
    candles = SimulatedMarketDataProvider().candles("SPY", "5m")
    decision = make_decision("SPY", "5m", candles, 10000, rules())
    assert atr(candles) > 0
    assert decision.risk_amount == 100
    assert decision.stop_loss > 0 and decision.take_profit > 0


def test_kill_switch_rejects_paper_trade():
    decision = make_decision("SPY", "5m", SimulatedMarketDataProvider().candles("SPY", "5m"), 10000, rules(kill_switch=True))
    assert decision.final_decision == "REJECTED"
    assert "kill switch" in decision.rejected_rules[0]


def test_backtest_is_walk_forward_and_labels_limits():
    result = backtest("SPY", SimulatedMarketDataProvider().candles("SPY", "5m", 100), rules())
    assert result["mode"] == "BACKTEST"
    assert "not evidence" in result["note"]


def test_paper_api_is_isolated_and_kill_switch_blocks_execution():
    with TestClient(app) as client:
        client.post("/api/v1/auth/register", json={"email": f"trade-{uuid4().hex}@example.com", "password": "secure-password-123", "display_name": "Trader"})
        status = client.get("/api/v1/trading/status")
        assert status.status_code == 200 and status.json()["mode"] == "PAPER"
        assert client.post("/api/v1/trading/kill-switch?enabled=true").json()["kill_switch"] is True
        response = client.post("/api/v1/trading/paper/execute/SPY")
        assert response.status_code == 422
