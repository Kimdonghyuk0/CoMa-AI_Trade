from binance.exceptions import BinanceAPIException
from config.api_client import get_client
import config.settings as settings
import time
import threading
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from requests.exceptions import ConnectionError
from urllib3.exceptions import NewConnectionError

def _order_lifecycle(qty, is_long, filled_price, tp_price, sl_price):
    client = get_client()
    opp_side = 'SELL' if is_long else 'BUY'

    
    # qty를 Decimal로 변환 (안전처리)
    try:
        qty_dec = Decimal(str(qty))
    except (InvalidOperation, ValueError) as e:
        settings.set_info(f"🚨 수량 변환 오류: {qty} ({e})")
        return
    
     # 2) LOT_SIZE 필터에서 수량 단위(step_size) 조회
    info = client.futures_exchange_info()
    step_size = Decimal('0.0001')
    for s in info['symbols']:
        if s['symbol'] == settings.SYMBOL:
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = Decimal(f['stepSize'])
                    break
            break
    
     # 3) TP 레벨 계산 (33%, 66%, 100%)
    distance = (tp_price - filled_price) if is_long else (filled_price - tp_price)
    tp_levels = []
    for r in [Decimal('0.33'), Decimal('0.66'), Decimal('1')]:
        level = (filled_price + distance * r) if is_long else (filled_price - distance * r)
        tp_levels.append(level.quantize(step_size, rounding=ROUND_DOWN))

     # 4) 부분 익절 수량 분할 
    ratios = [Decimal('0.25'), Decimal('0.45')]
    qty_parts = [(qty_dec * r).quantize(step_size, rounding=ROUND_DOWN) for r in ratios]


    # 5) TP1, TP2 주문
    tp_ids = []
    for part_qty, level in zip(qty_parts, tp_levels[:2]):
        if part_qty <= 0:
            continue
        order = client.futures_create_order(
            symbol=settings.SYMBOL,
            side=opp_side,
            type='TAKE_PROFIT_MARKET',
            stopPrice=str(level),
            quantity=float(part_qty),
            reduceOnly=True
        )
        tp_ids.append(order['orderId'])
        settings.set_info(f"▶️ 부분 익절 주문 접수 — 수량 {part_qty} @ {level:.2f}")
    
    # 6) 최종 TP 주문 (남은 전량 청산)
    final_level = tp_levels[2]
    final_order = client.futures_create_order(
        symbol=settings.SYMBOL,
        side=opp_side,
        type='TAKE_PROFIT_MARKET',
        stopPrice=str(final_level),
        closePosition=True
    )
    tp_ids.append(final_order['orderId'])
    settings.set_info(f"▶️ 최종 익절 주문 접수 — 전량 @ {final_level:.2f}")


    # 2) 손절 주문
    sl_order = client.futures_create_order(
        symbol=settings.SYMBOL,
        side=opp_side,
        type='STOP_MARKET',
        stopPrice=str(sl_price),
        closePosition=True
    )
    sl_id = sl_order['orderId']
    settings.set_info(f"▶️ 손절 주문 접수) - 전량 @ {sl_price:.2f}")

   # 8) TP/SL 체결 모니터링
    filled_tps = set()
    while True:
        try:
            time.sleep(15)
            # TP 체결 확인
            for idx, tp_id in enumerate(tp_ids):
                if idx not in filled_tps:
                    info_tp = client.futures_get_order(symbol=settings.SYMBOL, orderId=tp_id)
                    if info_tp['status'] == 'FILLED':
                        tp_fill = Decimal(info_tp['avgPrice'])
                        executed_qty = Decimal(info_tp.get('executedQty', '0'))
                        profit = ((tp_fill - filled_price) * executed_qty
                                if is_long else
                                (filled_price - tp_fill) * executed_qty)
                        settings.set_info(f"🎉 익절 {idx+1}단계 체결 — +{profit:.2f} USDT")
                        settings.add_profit(profit)  
                        filled_tps.add(idx)
            time.sleep(1)
            # SL 체결 확인
            info_sl = client.futures_get_order(symbol=settings.SYMBOL, orderId=sl_id)
            if info_sl['status'] == 'FILLED':
                sl_fill = Decimal(info_sl['avgPrice'])
                loss = (-(filled_price - sl_fill) * qty_dec
                        if is_long else
                        (sl_fill - filled_price) * qty_dec)
                settings.set_info(f"⚠️ 손절 주문 체결 — {loss:.2f} USDT")
                settings.add_profit(loss)
                settings.is_entry_allowed = False   # <-- 전역 스코프(or 설정 dict)에 있는 플래그
                settings.set_info("🚫 다음 1시간봉 나오기기 전까지 진입 금지")  
                return

            # 모든 TP 체결 시 종료
            if len(filled_tps) == len(tp_ids):
                return

        except (ConnectionError, NewConnectionError) as net_err:
            time.sleep(5)  # 5초 정도 기다렸다가 다시 시도
            continue

        except BinanceAPIException as e:
            settings.set_info(f"⛔️ Binance API 오류: {e}")
            return

        except Exception as e:
            settings.set_info(f"⛔️ 알 수 없는 예외 발생: {e}")
            return


def place_order(data, leverage):
    client = get_client()
    try:
        # 1) 레버리지 설정 & USDT 잔고 조회
        client.futures_change_leverage(symbol=settings.SYMBOL, leverage=settings.LEVERAGE)
        balances = client.futures_account_balance()
        balance = next((float(b['balance']) for b in balances if b['asset'] == 'USDT'), 0.0)

        # 2) 마진 타입 설정
        try:
            client.futures_change_margin_type(
            symbol=settings.SYMBOL,
            marginType='ISOLATED'
        )
        except BinanceAPIException:
            pass

       
        # 3) 사용할 금액 계산
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

        # 4) 수량 단위(stepSize) 조회
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

        # 5) 주문 수량 계산
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

        # 6) 롱/숏 분기
        is_long = (data['signal'] == '롱')
        side = 'BUY' if is_long else 'SELL'
        pos_label = '롱 포지션' if is_long else '숏 포지션'

        
        # 7) 진입 주문 접수
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
                    return

        threading.Thread(target=_wait_fill_and_spawn, daemon=True).start()

    except BinanceAPIException as e:
        settings.set_info(f"❌ 주문 오류: {e}")
