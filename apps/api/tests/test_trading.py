from datetime import timedelta
import pytest
from app.database import SessionLocal
from app.services.trading import Candle, CandleRepository, SimulatedMarketDataProvider, analyze_market, atr, backtest, make_decision, market_structure, support_resistance, validate_candles
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


def test_candle_validation_rejects_duplicate_out_of_order_and_invalid_values():
    candles = SimulatedMarketDataProvider().candles("SPY", "5m", 30)
    assert validate_candles(candles)[0]
    assert not validate_candles(candles + [candles[-1]])[0]
    invalid = Candle(candles[-1].timestamp + timedelta(minutes=5), 1, .5, 2, 1, 1)
    assert not validate_candles(candles + [invalid])[0]


def test_structure_support_resistance_and_market_context_are_serializable():
    candles = SimulatedMarketDataProvider().candles("SPY", "5m", 120)
    structure = market_structure(candles)
    levels = support_resistance(candles, structure)
    context = analyze_market("SPY", "5m", candles)
    assert structure["state"] in {"BULLISH", "BEARISH", "RANGING"}
    assert "support" in levels and context.payload()["data_quality"]["valid"]


def test_insufficient_history_returns_safe_context():
    context = analyze_market("SPY", "5m", SimulatedMarketDataProvider().candles("SPY", "5m", 5))
    assert context.data_quality["valid"] is False


def test_candle_repository_persists_deduplicates_and_orders_recent_data():
    db = SessionLocal()
    try:
        symbol = f"T{uuid4().hex[:8]}"
        candles = SimulatedMarketDataProvider().candles(symbol, "5m", 30)
        repository = CandleRepository(db)
        assert repository.save(candles) == 30
        assert repository.save(candles) == 0
        recent = repository.recent(symbol, "5m", 10)
        assert len(recent) == 10
        assert [item.timestamp for item in recent] == sorted(item.timestamp for item in recent)
        assert recent[-1].close == candles[-1].close
    finally:
        db.close()


def test_candle_repository_rejects_invalid_data_before_persistence():
    db = SessionLocal()
    try:
        candle = Candle(SimulatedMarketDataProvider().candles("SPY", "5m", 1)[0].timestamp, 1, .5, 2, 1, 1, "INVALID", "5m")
        with pytest.raises(ValueError, match="invalid OHLC"):
            CandleRepository(db).save([candle])
    finally:
        db.close()


def test_paper_api_is_isolated_and_kill_switch_blocks_execution():
    with TestClient(app) as client:
        client.post("/api/v1/auth/register", json={"email": f"trade-{uuid4().hex}@example.com", "password": "secure-password-123", "display_name": "Trader"})
        status = client.get("/api/v1/trading/status")
        assert status.status_code == 200 and status.json()["mode"] == "PAPER"
        assert client.post("/api/v1/trading/kill-switch?enabled=true").json()["kill_switch"] is True
        response = client.post("/api/v1/trading/paper/execute/SPY")
        assert response.status_code == 422
        assert client.get("/api/v1/trading/market-context/SPY").status_code == 200
        db = SessionLocal()
        try:
            assert len(CandleRepository(db).recent("SPY", "5m")) >= 120
        finally:
            db.close()
