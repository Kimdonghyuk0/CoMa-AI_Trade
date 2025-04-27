from binance.exceptions import BinanceAPIException
from config.api_client import get_client
import config.settings as settings
import time
import threading
from decimal import Decimal, ROUND_DOWN, InvalidOperation

def _order_lifecycle(qty, is_long, filled_price, tp_price, sl_price):
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

    # qty를 Decimal로 변환 (안전처리)
    try:
        qty_dec = Decimal(str(qty))
    except (InvalidOperation, ValueError) as e:
        settings.set_info(f"🚨 수량 변환 오류: {qty} ({e})")
        return

    # 익절·손절 체결 대기 & P&L 계산
    while True:
        try:
            # 1) 익절 체크 (45초 대기)
            time.sleep(45)
            info_tp = client.futures_get_order(symbol=settings.SYMBOL, orderId=tp_id)
            if info_tp['status'] == 'FILLED':
                tp_fill = Decimal(info_tp['avgPrice'])
                profit = (tp_fill - filled_price) * qty_dec if is_long else (filled_price - tp_fill) * qty_dec
                settings.set_info(f"🎉 익절 체결 — +{profit:.2f} USDT  수익\n")
                return

            # 2) 손절 체크 (15초 대기)
            time.sleep(15)
            info_sl = client.futures_get_order(symbol=settings.SYMBOL, orderId=sl_id)
            if info_sl['status'] == 'FILLED':
                sl_fill = Decimal(info_sl['avgPrice'])
                loss = -(filled_price - sl_fill) * qty_dec if is_long else (sl_fill - filled_price) * qty_dec
                settings.set_info(f"⚠️ 손절 체결 — -{loss:.2f} USDT  손실\n")
                return

        except BinanceAPIException as e:
            settings.set_info(f"⛔️ API 오류: {e}")
            return
        except Exception as e:
            settings.set_info(f"⛔️ 예외 발생: {e}")
            return

def place_order(data, leverage):
    client = get_client()
    try:
        # 1) 레버리지 설정 & USDT 잔고 조회
        client.futures_change_leverage(symbol=settings.SYMBOL, leverage=settings.LEVERAGE)
        balances = client.futures_account_balance()
        balance = next((float(b['balance']) for b in balances if b['asset'] == 'USDT'), 0.0)

        # 2) 사용할 금액 계산
        if settings.AMOUNT_MODE == "전액":
            usd_to_use = balance
        elif settings.AMOUNT_MODE == "사용자 입력($)":
            usd_to_use = settings.AMOUNT_VALUE
        elif settings.AMOUNT_MODE == "전액의(%)":
            usd_to_use = balance * (settings.AMOUNT_VALUE / 100)
        else:
            usd_to_use = balance

        # ✅ entry 값 검증
        entry_raw = data.get("entry")
        if entry_raw is None:
            settings.set_info(f"🚨 entry 값 없음")
            return
        try:
            entry_price = Decimal(str(entry_raw))
        except (InvalidOperation, ValueError) as e:
            settings.set_info(f"🚨 entry 변환 오류: {entry_raw} ({e})")
            return

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

        # 4) 주문 수량 계산
        try:
            raw_qty = Decimal(str(usd_to_use)) * Decimal(str(leverage)) / entry_price
        except (InvalidOperation, ZeroDivisionError) as e:
            settings.set_info(f"🚨 수량 계산 오류: usd_to_use={usd_to_use}, leverage={leverage}, entry={entry_price} ({e})")
            return

        qty = float(raw_qty.quantize(quant, rounding=ROUND_DOWN))

        # ✅ qty가 0이면 주문 안되게
        if qty <= 0:
            settings.set_info(f"🚨 주문 수량이 0 이하입니다. (qty={qty})")
            return

        # 5) 롱/숏 분기
        is_long = (data['signal'] == '롱')
        side = 'BUY' if is_long else 'SELL'
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
                time.sleep(10)
                info_e = client.futures_get_order(symbol=settings.SYMBOL, orderId=entry_id)
                status = info_e['status']
                if status == 'FILLED':
                    filled_price = Decimal(info_e['avgPrice'])
                    settings.set_info(f"✅ {pos_label} 체결 — {filled_price:.2f} USDT")
                    # 체결되면 백그라운드로 TP/SL 스레드 시작
                    try:
                        tp_price = Decimal(str(data["tp"]))
                        sl_price = Decimal(str(data["sl"]))
                    except (InvalidOperation, ValueError) as e:
                        settings.set_info(f"🚨 TP/SL 변환 오류: {e}")
                        return

                    threading.Thread(
                        target=_order_lifecycle,
                        args=(qty, is_long, filled_price, tp_price, sl_price),
                        daemon=True
                    ).start()
                    return
                elif status in ('CANCELED', 'REJECTED', 'EXPIRED'):
                    settings.set_info(f"⚠️ {pos_label} 주문 실패(orderId={entry_id}, status={status})")
                    return

        threading.Thread(target=_wait_fill_and_spawn, daemon=True).start()

    except BinanceAPIException as e:
        settings.set_info(f"❌ 주문 오류: {e}")
