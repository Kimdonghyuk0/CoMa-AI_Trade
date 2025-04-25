from binance.exceptions import BinanceAPIException
from config.api_client import get_client
import config.settings as settings
import time
import threading
from decimal import Decimal, ROUND_DOWN

def _order_lifecycle( qty, is_long, filled_price, tp_price, sl_price):
    client = get_client()
    opp_side = 'SELL' if is_long else 'BUY'

    # 1) 익절 주문
    tp_order = client.futures_create_order(
        symbol=settings.SYMBOL,
        side=opp_side,
        type='TAKE_PROFIT_MARKET',
        stopPrice=str(tp_price),
        closePosition=True
    )
    tp_id = tp_order['orderId']
    settings.set_info(f"▶️ 익절 주문 접수) @ {tp_price:.2f}")

    # 2) 손절 주문
    sl_order = client.futures_create_order(
        symbol=settings.SYMBOL,
        side=opp_side,
        type='STOP_MARKET',
        stopPrice=str(sl_price),
        closePosition=True
        )
    sl_id = sl_order['orderId']
    settings.set_info(f"▶️ 손절 주문 접수) @ {sl_price:.2f}")
    # 익절 손절 체결 대기 & P&L 계산
    while True:
        try:
            # 1) 익절 체크 (45초 대기 후)
            time.sleep(45)
            info_tp = client.futures_get_order(symbol=settings.SYMBOL, orderId=tp_id)
            if info_tp['status'] == 'FILLED':
                tp_fill = Decimal(info_tp['avgPrice'])
                profit = (tp_fill - filled_price) * qty if is_long else (filled_price - tp_fill) * qty
                pnl_pct = profit / (filled_price * qty) * Decimal(100)
                settings.set_info(
                    f"🎉 익절 체결 — {tp_fill:.2f} USDT  수익 \n"
                    f"{profit:.2f} USDT ({pnl_pct:.2f}%)"
                )
                return  # 익절되었으면 종료

            # 2) 손절 체크 (15초 대기 후)
            time.sleep(15)
            info_sl = client.futures_get_order(symbol=settings.SYMBOL, orderId=sl_id)
            if info_sl['status'] == 'FILLED':
                sl_fill = Decimal(info_sl['avgPrice'])
                loss = -((filled_price - sl_fill) * qty) if is_long else (sl_fill - filled_price) * qty
                pnl_pct = loss / (filled_price * qty) * Decimal(100)
                settings.set_info(
                    f"⚠️ 손절 체결 — {sl_fill:.2f} USDT  손실 \n"
                    f"{loss:.2f} USDT ({pnl_pct:.2f}%)"
                )
                return  # 손절되었으면 종료

        except Exception:
            # 예외는 모두 무시하고 다음 루프로
            continue



def place_order(data, leverage):
    client = get_client()
    """
    진입 신호에 따라 선물 주문 및 OCO 설정
    — 롱/숏 직관적 메시지 + 체결 시각·가격·P&L 출력
    """
    try:
        # 1) 레버리지 설정 & USDT 잔고 조회
        client.futures_change_leverage(symbol=settings.SYMBOL, leverage=settings.LEVERAGE)
        balances = client.futures_account_balance()
        balance = next((float(b['balance']) for b in balances if b['asset']=='USDT'), 0.0)

        # 2) 사용할 금액 계산
        if settings.AMOUNT_MODE == "전액":
            usd_to_use = balance
        elif settings.AMOUNT_MODE == "사용자 입력($)":
            usd_to_use = settings.AMOUNT_VALUE
        elif settings.AMOUNT_MODE == "전액의(%)":
            usd_to_use = balance * (settings.AMOUNT_VALUE / 100)
        else:
            usd_to_use = balance

        entry_price = Decimal(str(data["entry"]))

        # 3) 수량 단위(stepSize) 조회
        info = client.futures_exchange_info()
        step_size = "0.0001"
        for s in info['symbols']:
            if s['symbol'] == settings.SYMBOL:
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
        settings.set_info(" ")
        settings.set_info(f"{pos_label} 주문 접수 — 수량 {qty} {settings.SYMBOL[:-4]} @ {entry_price:.2f} USDT  \n(사용금액 {usd_to_use:.2f} USDT, 레버리지 {leverage}x)")
        entry = client.futures_create_order(
            symbol=settings.SYMBOL, side=side, type='LIMIT',
            price=str(entry_price), quantity=qty, timeInForce='GTC'
        )
        entry_id = entry['orderId']

        def _wait_fill_and_spawn():
            while True:
                time.sleep(1)
                info_e = client.futures_get_order(symbol=settings.SYMBOL, orderId=entry_id)
                status = info_e['status']
                if status == 'FILLED':
                    filled_price = Decimal(info_e['avgPrice'])
                    settings.set_info(f"✅ {pos_label} 체결 — {filled_price:.2f} USDT")
                    # 체결되면 백그라운드로 TP/SL 스레드 시작
                    tp_price = Decimal(str(data["tp"]))
                    sl_price = Decimal(str(data["sl"]))
                    threading.Thread(
                        target=_order_lifecycle,
                        args=(qty, is_long, filled_price, tp_price, sl_price),
                        daemon=True
                    ).start()
                    return
                elif status in ('CANCELED','REJECTED','EXPIRED'):
                    settings.set_info(f"⚠️ {pos_label} 주문 실패(orderId={entry_id}, status={status})")
                    return

        threading.Thread(target=_wait_fill_and_spawn, daemon=True).start()

    except BinanceAPIException as e:
        settings.set_info(f"❌ 주문 오류: {e}")
