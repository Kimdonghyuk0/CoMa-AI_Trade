from binance.client import Client
import time
from binance.client import Client
import time

class SyncedClient(Client):
    def __init__(self, api_key, api_secret):
        super().__init__(api_key, api_secret)
        server_ts = self.get_server_time()['serverTime']
        local_ts  = int(time.time() * 1000)
        self.time_offset = server_ts - local_ts

    def _adjust_timestamp(self):
        return int(time.time() * 1000 + self.time_offset)

    def _request(self, method, uri, signed=False, force_params=False, **kwargs):
        """
        모든 signed 요청에 대해 timestamp를 자동 추가하도록 오버라이드
        """
        if signed:
            kwargs['timestamp'] = self._adjust_timestamp()
        # force_params까지 그대로 전달
        return super()._request(method, uri, signed, force_params, **kwargs)

_client = None

def init_client(api_key: str, api_secret: str):
    """
    사용자가 입력한 API 키/시크릿으로 Binance Client를 초기화.
    settings.py 에서 한 번 호출해 두면, fetch_klines 등
    다른 모듈에서는 get_client()로 받아서 씁니다.
    """
    global _client
    _client = SyncedClient(api_key, api_secret)

def get_client() -> SyncedClient:
    if _client is None:
        raise RuntimeError("Binance client가 아직 초기화되지 않았습니다.")
    return _client