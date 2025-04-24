# project/api_client.py
from binance.client import Client

_client = None

def init_client(api_key: str, api_secret: str):
    """
    사용자가 입력한 API 키/시크릿으로 Binance Client를 초기화.
    settings.py 에서 한 번 호출해 두면, fetch_klines 등
    다른 모듈에서는 get_client()로 받아서 씁니다.
    """
    global _client
    _client = Client(api_key, api_secret)

def get_client() -> Client:
    if _client is None:
        raise RuntimeError("Binance client가 아직 초기화되지 않았습니다.")
    return _client
