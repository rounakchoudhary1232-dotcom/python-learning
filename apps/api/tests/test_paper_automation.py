from app.services.paper_automation import PositionSnapshot, monitor_position

def test_buy_and_sell_sl_tp_and_pnl_are_deterministic():
    buy=PositionSnapshot("BUY",100,99,102,10); sell=PositionSnapshot("SELL",100,101,98,10)
    assert monitor_position(buy,102).payload()=={"action":"CLOSE","exit_price":102,"exit_reason":"EXIT_TP","pnl":20,"paper_only":True}
    assert monitor_position(buy,99).pnl==-10 and monitor_position(sell,98).pnl==20 and monitor_position(sell,101).pnl==-10
def test_hold_invalid_and_closed_positions_are_safe():
    position=PositionSnapshot("BUY",100,99,102,10)
    assert monitor_position(position,100).action=="HOLD"
    assert monitor_position(PositionSnapshot("BUY",100,99,102,10,"CLOSED"),102).action=="REJECT"
