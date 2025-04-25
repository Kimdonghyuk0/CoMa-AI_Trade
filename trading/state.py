# trading/state.py
import time
import requests
from config.api_client import get_client
import config.settings as settings

client = get_client()

def safe_get_open_orders(retries: int = 3, backoff: float = 1.0):
    """예약 주문 조회—타임아웃 시 재시도, 모두 실패하면 빈 리스트 반환"""
    for attempt in range(1, retries + 1):
        try:
            return client.futures_get_open_orders(symbol=settings.SYMBOL)
        except requests.exceptions.ReadTimeout:
            settings.set_info(f"⚠️ 예약 주문 조회 타임아웃 ({attempt}/{retries}) – {backoff}s 후 재시도")
            time.sleep(backoff)
    settings.set_info("❌ 예약 주문 조회 실패, 빈 리스트 반환")
    return []

def is_in_waiting() -> bool:
    open_orders = safe_get_open_orders()
    return bool(open_orders)

def safe_get_position_info(retries: int = 3, backoff: float = 1.0):
    """포지션 정보 조회—타임아웃 시 재시도, 모두 실패하면 빈 리스트 반환"""
    for attempt in range(1, retries + 1):
        try:
            return client.futures_position_information(symbol=settings.SYMBOL)
        except requests.exceptions.ReadTimeout:
            settings.set_info(f"⚠️ 포지션 조회 타임아웃 ({attempt}/{retries}) – {backoff}s 후 재시도")
            time.sleep(backoff)
    settings.set_info("❌ 포지션 조회 실패, 빈 리스트 반환")
    return []

def is_in_position() -> bool:
    position_info = safe_get_position_info()
    for pos in position_info:
        if float(pos.get("positionAmt", 0)) != 0:
            return True
    return False
