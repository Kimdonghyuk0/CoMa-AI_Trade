from binance.exceptions import BinanceAPIException
from config.api_client import get_client
from config.settings import set_info, SYMBOL, LEVERAGE, AMOUNT_MODE, AMOUNT_VALUE
import time
from decimal import Decimal, ROUND_DOWN

def place_order(data, leverage):
    client = get_client()
    """
    진입 신호에 따라 선물 주문 및 OCO 설정
    — 롱/숏 직관적 메시지 + 체결 시각·가격·P&L 출력
    """
    try:
        # 1) 레버리지 설정 & USDT 잔고 조회
        client.futures_change_leverage(symbol=SYMBOL, leverage=leverage)
        balances = client.futures_account_balance()
        balance = next((float(b['balance']) for b in balances if b['asset']=='USDT'), 0.0)

        # 2) 사용할 금액 계산
        if AMOUNT_MODE == "전액":
            usd_to_use = balance
        elif AMOUNT_MODE == "사용자 입력($)":
            usd_to_use = AMOUNT_VALUE
        elif AMOUNT_MODE == "전액의(%)":
            usd_to_use = balance * (AMOUNT_VALUE / 100)
        else:
            usd_to_use = balance

        entry_price = Decimal(str(data["entry"]))

        # 3) 수량 단위(stepSize) 조회
        info = client.futures_exchange_info()
        step_size = "0.0001"
        for s in info['symbols']:
            if s['symbol'] == SYMBOL:
                for f in s['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step_size = f['stepSize']
                        break
                break
        quant = Decimal(step_size)

        # 4) 주문 수량 계산 (레버리지 반영)
        raw_qty = Decimal(str(usd_to_use)) * Decimal(str(leverage)) / entry_price
        qty = float(raw_qty.quantize(quant, rounding=ROUND_DOWN))

        # 5) 롱/숏 분기
        is_long = (data['signal'] == '롱')
        side      = 'BUY' if is_long else 'SELL'
        pos_label = '롱 포지션' if is_long else '숏 포지션'

        # 6) 진입 주문 접수
        set_info(" ")
        set_info(f"{pos_label} 주문 접수 — 수량 {qty} {SYMBOL[:-4]} @ {entry_price:.2f} USDT  \n(사용금액 {usd_to_use:.2f} USDT, 레버리지 {leverage}x)")
        entry = client.futures_create_order(
            symbol=SYMBOL, side=side, type='LIMIT',
            price=str(entry_price), quantity=qty, timeInForce='GTC'
        )
        entry_id = entry['orderId']

        # 7) 진입 체결 대기
        while True:
            time.sleep(1)
            st = client.futures_get_order(symbol=SYMBOL, orderId=entry_id)['status']
            if st == 'FILLED':
                filled_price = Decimal(client.futures_get_order(symbol=SYMBOL, orderId=entry_id)['avgPrice'])
                set_info(f"✅ {pos_label} 거래 체결 — {filled_price:.2f} USDT")
                break
            if st in ('CANCELED','REJECTED','EXPIRED'):
                set_info(f"⚠️ {pos_label} 주문 실패(orderId={entry_id}, status={st})")
                return

        # 8) 익절 & 손절 주문
        tp_price = Decimal(str(data["tp"]))
        sl_price = Decimal(str(data["sl"]))
        opp_side = 'SELL' if is_long else 'BUY'
        tp_label = '익절'
        sl_label = '손절'

        # 익절 마켓 주문
        client.futures_create_order(
            symbol=SYMBOL, side=opp_side, type='TAKE_PROFIT_MARKET',
            stopPrice=str(tp_price), closePosition=True
        )
        
        set_info(f"▶️ {tp_label} 주문 접수) @ {tp_price:.2f}")

        # 익절 체결 대기 & P&L 계산
        while True:
            time.sleep(1)
            info_tp = client.futures_get_order(symbol=SYMBOL, orderId=tp_id)
            if info_tp['status'] == 'FILLED':
                tp_fill = Decimal(info_tp['avgPrice'])
                profit = (tp_fill - filled_price) * Decimal(qty) if is_long else (filled_price - tp_fill) * Decimal(qty)
                pnl_pct = profit / (filled_price * Decimal(qty)) * Decimal(100)
                set_info(f"🎉 {tp_label} 체결 — {tp_fill:.2f} USDT  \n수익 {profit:.2f} USDT ({pnl_pct:.2f}%)")
                break

        # 손절 마켓 주문
        client.futures_create_order(
            symbol=SYMBOL, side=opp_side, type='STOP_MARKET',
            stopPrice=str(sl_price), closePosition=True
                 
        )
        
        set_info(f"▶️ {sl_label} ) @ {sl_price:.2f}")

        # 손절 체결 대기 & P&L 계산
        while True:
            time.sleep(1)
            info_sl = client.futures_get_order(symbol=SYMBOL, orderId=sl_id)
            if info_sl['status'] == 'FILLED':
                sl_fill = Decimal(info_sl['avgPrice'])
                loss = (filled_price - sl_fill) * Decimal(qty) if is_long else (sl_fill - filled_price) * Decimal(qty)
                pnl_pct = loss / (filled_price * Decimal(qty)) * Decimal(100)
                set_info(f"⚠️ {sl_label} 체결 — {sl_fill:.2f} USDT  \n손실 {loss:.2f} USDT ({pnl_pct:.2f}%)")
                break

    except BinanceAPIException as e:
        set_info(f"❌ 주문 오류: {e}")
