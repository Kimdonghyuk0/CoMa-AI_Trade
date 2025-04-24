# utils/data.py
import pandas as pd
from config.api_client import get_client
from config.settings import LEVERAGE

def fetch_klines(symbol, interval, limit):
    """
    지정된 심볼/인터벌로 Binance에서 kline을 가져와 DataFrame으로 반환
    """
    client = get_client()
    if client is None:
        raise RuntimeError("Binance client가 초기화되지 않았습니다. configure() 를 먼저 호출하세요.")
    
   
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)

    df = pd.DataFrame(klines, columns=[
        'open_time','open','high','low','close','volume',
        'close_time','quote_asset_volume','num_trades',
        'taker_buy_base','taker_buy_quote','ignore'
    ])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df[['open','high','low','close','volume']] = \
        df[['open','high','low','close','volume']].astype(float)
    return df
