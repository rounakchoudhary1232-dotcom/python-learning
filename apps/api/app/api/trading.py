from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..config import get_settings
from ..database import get_db
from ..models import Trade, TradingSession, User
from ..security import current_user
from ..services.trading import CandleRepository, SimulatedMarketDataProvider, analyze_market, backtest, make_decision
from ..services.risk_engine import AccountRiskState, RiskLimits, assess
from ..services.paper_automation import PositionSnapshot, monitor_position

router = APIRouter(prefix="/trading", tags=["trading"])

def session_for(db: Session, user: User) -> TradingSession:
    session = db.query(TradingSession).filter_by(user_id=user.id).first()
    if not session:
        session = TradingSession(user_id=user.id, mode="PAPER", balance=get_settings().trading_initial_balance, equity=get_settings().trading_initial_balance)
        db.add(session); db.commit(); db.refresh(session)
    return session

def rules(session: TradingSession) -> dict:
    settings = get_settings()
    return {"max_risk_per_trade": settings.max_risk_per_trade, "min_confidence": settings.min_confidence, "min_risk_reward": settings.min_risk_reward, "kill_switch": session.kill_switch}

@router.get("/status")
def trading_status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = session_for(db, user); open_positions = db.query(Trade).filter_by(user_id=user.id, status="OPEN").all()
    return {"mode": "PAPER", "data_provider": "SIMULATED", "balance": session.balance, "equity": session.equity, "kill_switch": session.kill_switch, "open_positions": [{"id": item.id, "symbol": item.symbol, "direction": item.direction, "entry": item.entry, "stop_loss": item.stop_loss, "take_profit": item.take_profit} for item in open_positions]}

@router.post("/decision/{symbol}")
def propose(symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = session_for(db, user); candles = SimulatedMarketDataProvider().candles(symbol, "5m")
    return make_decision(symbol, "5m", candles, session.balance, rules(session)).payload() | {"data_provider": "SIMULATED", "paper_only": True}

@router.get("/market-context/{symbol}")
def market_context(symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    provider = SimulatedMarketDataProvider()
    repository = CandleRepository(db)
    for timeframe in ("1m", "5m", "1h"):
        repository.save(provider.candles(symbol, timeframe))
    return analyze_market(symbol, "5m", repository.recent(symbol, "5m"), repository.recent(symbol, "1m"), repository.recent(symbol, "1h")).payload() | {"data_provider": "SIMULATED", "paper_only": True}

@router.post("/paper/execute/{symbol}", status_code=status.HTTP_201_CREATED)
def paper_execute(symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = session_for(db, user); decision = make_decision(symbol, "5m", SimulatedMarketDataProvider().candles(symbol, "5m"), session.balance, rules(session))
    if decision.final_decision == "REJECTED": raise HTTPException(422, {"decision": decision.payload(), "reason": decision.rejected_rules})
    settings = get_settings()
    duplicate = db.query(Trade).filter_by(user_id=user.id, symbol=decision.symbol, direction=decision.direction, status="OPEN").first() is not None
    assessment = assess(decision.direction, decision.entry, decision.stop_loss, decision.take_profit, None, AccountRiskState(session.balance, session.equity, trade_count_today=db.query(Trade).filter_by(user_id=user.id).count(), kill_switch=session.kill_switch, mode=session.mode, open_same_position=duplicate), RiskLimits(settings.max_risk_per_trade, settings.min_risk_reward, settings.max_daily_loss, settings.max_trades_per_day, settings.max_drawdown))
    if not assessment.allowed: raise HTTPException(422, {"decision": decision.payload(), "risk": assessment.payload(), "reason": assessment.reasons})
    trade = Trade(user_id=user.id, session_id=session.id, decision_id=decision.decision_id, symbol=decision.symbol, strategy=decision.strategy, direction=decision.direction, entry=decision.entry, stop_loss=decision.stop_loss, take_profit=decision.take_profit, quantity=assessment.calculated_position_size, rationale="; ".join(decision.supporting_factors))
    db.add(trade); db.commit(); db.refresh(trade)
    return {"mode": "PAPER", "trade_id": trade.id, "decision": decision.payload()}

@router.post("/kill-switch")
def kill_switch(enabled: bool, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = session_for(db, user); session.kill_switch = enabled; db.commit(); return {"mode": "PAPER", "kill_switch": enabled}

@router.post("/paper/monitor/{symbol}")
def paper_monitor(symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Monitor existing PAPER positions only; the kill switch never blocks safety exits."""
    price = SimulatedMarketDataProvider().candles(symbol, "5m")[-1].close
    trades = db.query(Trade).filter_by(user_id=user.id, symbol=symbol.upper(), status="OPEN").all(); closed = []
    for trade in trades:
        result = monitor_position(PositionSnapshot(trade.direction, trade.entry, trade.stop_loss, trade.take_profit, trade.quantity), price)
        if result.action == "CLOSE":
            trade.status, trade.exit_price, trade.pnl = "CLOSED", result.exit_price, result.pnl
            trade.rationale = f"{trade.rationale}; {result.exit_reason}"
            closed.append({"trade_id": trade.id, **result.payload()})
    if closed: db.commit()
    return {"mode": "PAPER", "paper_only": True, "price": price, "closed": closed, "open_positions": len(trades) - len(closed)}

@router.get("/backtest/{symbol}")
def run_backtest(symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = session_for(db, user); return backtest(symbol.upper(), SimulatedMarketDataProvider().candles(symbol, "5m", 200), rules(session))
