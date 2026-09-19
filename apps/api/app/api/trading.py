from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..config import get_settings
from ..database import get_db
from ..models import Trade, TradingSession, User
from ..security import current_user
from ..services.trading import SimulatedMarketDataProvider, backtest, make_decision

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

@router.post("/paper/execute/{symbol}", status_code=status.HTTP_201_CREATED)
def paper_execute(symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = session_for(db, user); decision = make_decision(symbol, "5m", SimulatedMarketDataProvider().candles(symbol, "5m"), session.balance, rules(session))
    if decision.final_decision == "REJECTED": raise HTTPException(422, {"decision": decision.payload(), "reason": decision.rejected_rules})
    trade = Trade(user_id=user.id, session_id=session.id, decision_id=decision.decision_id, symbol=decision.symbol, strategy=decision.strategy, direction=decision.direction, entry=decision.entry, stop_loss=decision.stop_loss, take_profit=decision.take_profit, quantity=decision.quantity, rationale="; ".join(decision.supporting_factors))
    db.add(trade); db.commit(); db.refresh(trade)
    return {"mode": "PAPER", "trade_id": trade.id, "decision": decision.payload()}

@router.post("/kill-switch")
def kill_switch(enabled: bool, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = session_for(db, user); session.kill_switch = enabled; db.commit(); return {"mode": "PAPER", "kill_switch": enabled}

@router.get("/backtest/{symbol}")
def run_backtest(symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    session = session_for(db, user); return backtest(symbol.upper(), SimulatedMarketDataProvider().candles(symbol, "5m", 200), rules(session))
