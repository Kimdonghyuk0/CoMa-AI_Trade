import pandas as pd
import numpy as np
from decimal import Decimal
from typing import Any

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    MA, RSI, MACD, Bollinger Bands, Stochastic, OBV 등 주요 지표 계산
    :param df: 가격 DataFrame. 'open', 'high', 'low', 'close', 'volume' 컬럼 필요
    :return: 계산된 지표가 포함된 DataFrame (dropna() 적용)
    """
    df = df.copy()

    # --- Moving Averages ---
    df['ma5']  = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()

    # --- RSI (14) ---
    delta = df['close'].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    # Wilder’s smoothing (adjust=False)
    avg_gain = gain.ewm(span=14, adjust=False).mean()
    avg_loss = loss.ewm(span=14, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + avg_gain / avg_loss))

    # --- MACD (12,26,9) ---
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd']        = ema12 - ema26
    df['signal_line'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['hist']        = df['macd'] - df['signal_line']

    # --- Bollinger Bands (20,2) ---
    df['bb_mid']  = df['close'].rolling(20).mean()
    df['bb_std']  = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']

    # --- Stochastic (14,3) ---
    low14  = df['low'].rolling(14).min()
    high14 = df['high'].rolling(14).max()
    df['stoch_k'] = (df['close'] - low14) / (high14 - low14) * 100
    df['stoch_d'] = df['stoch_k'].rolling(3).mean()

    # --- OBV (On-Balance Volume) ---
    # +volume when price up, -volume when down, 0 when unchanged
    direction = np.sign(delta).fillna(0)
    df['obv'] = (df['volume'] * direction).cumsum()

    return df.dropna()