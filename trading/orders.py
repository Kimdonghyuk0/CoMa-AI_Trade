from binance.exceptions import BinanceAPIException
from config.api_client import get_client
from config.settings import set_info, SYMBOL, LEVERAGE
import time

def place_order(data, leverage):
    client = get_client()
    """
    진입 신호에 따라 선물 주문 및 OCO 설정
    """
    try:
        # 레버리지 & balance 조회
        client.futures_change_leverage(symbol=SYMBOL, leverage=LEVERAGE)
        balance = float(client.futures_account_balance()[0]["balance"])
        qty = round(balance * LEVERAGE / data["entry"], 6)

        # Info: 진입 정보 출력
        log = (
            f"📌 진입 정보\n"
            f"  🕒 시각: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"  종목: {SYMBOL}\n"
            f"  방향: {data['signal']}\n"
            f"  진입가: {data['entry']} USDT  SL: {data['sl']}  TP: {data['tp']}\n"
            f"  레버리지: {LEVERAGE}x  사용금액: {balance:.2f} USDT  수량: {qty} {SYMBOL[:-4]}\n"
        )
        set_info(log)
        # 레버리지 설정
        client.futures_change_leverage(symbol=SYMBOL, leverage=leverage)
        side = 'BUY' if data['signal']=='롱' else 'SELL'
        # 잔고 기준 수량 계산
        qty = round(float(client.futures_account_balance()[0]['balance']) * leverage / data['entry'], 6)
        # 진입 주문
        client.futures_create_order(
            symbol=SYMBOL, side=side, type='LIMIT', price=data['entry'], quantity=qty, timeInForce='GTC'
        )
        # 익절/손절 OCO 설정
        client.futures_create_oco_order(
            symbol=SYMBOL,
            side=('SELL' if side=='BUY' else 'BUY'),
            quantity=qty,
            price=data['tp'],
            stopPrice=data['sl'],
            stopLimitPrice=data['sl'],
            stopLimitTimeInForce='GTC'
        )
    except BinanceAPIException as e:
        print("Order error:", e) 