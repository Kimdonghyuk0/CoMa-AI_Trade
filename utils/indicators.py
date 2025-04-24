def compute_indicators(df):
    """
    MA, RSI, MACD, Bollinger Bands, Stochastic, OBV 등 주요 지표 계산
    :param df: 가격 DataFrame. 'close', 'high', 'low', 'volume' 컬럼 필요
    :return: 계산된 지표가 포함된 DataFrame (dropna() 적용)
    """
    # --- Moving Averages ---
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()

    # --- RSI (14) ---
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(alpha=1/14).mean()
    ma_down = down.ewm(alpha=1/14).mean()
    df['rsi'] = 100 - (100 / (1 + ma_up/ma_down))

    # --- MACD (12,26,9) ---
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['signal_line'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['hist'] = df['macd'] - df['signal_line']

    # --- Bollinger Bands (20,2) ---
    df['bb_mid'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']

    # --- Stochastic (14,3) ---
    low14 = df['low'].rolling(14).min()
    high14 = df['high'].rolling(14).max()
    df['stoch_k'] = (df['close'] - low14) / (high14 - low14) * 100
    df['stoch_d'] = df['stoch_k'].rolling(3).mean()

    # --- OBV (On-Balance Volume) ---
    signal = df['close'].diff().gt(0).astype(int).replace({0: -1})
    df['obv'] = (df['volume'] * signal).cumsum()

    return df.dropna()
