 # 이미 초기화된 client 사용
from config.api_client import get_client
from config.settings import SYMBOL

client = get_client()

def is_in_position_or_waiting():
    # 1. 미체결 주문 존재?
    open_orders = client.futures_get_open_orders(symbol=SYMBOL)
    if open_orders:
        return True

    # 2. 포지션 수량 존재?
    position_info = client.futures_position_information(symbol=SYMBOL)
    for pos in position_info:
        if float(pos["positionAmt"]) != 0:
            return True

    return False  # 아무 것도 없으면 진입 가능
