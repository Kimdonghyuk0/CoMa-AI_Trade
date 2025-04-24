def is_pullback_entry(state, df15):
    """
    상승장 내 한시적 눌림 후 반등 타점 탐지
    주요 조건: RSI, MACD, Stochastic 반등 + MA20 근접 + 거래량 급증
    """
    last = df15.iloc[-1]
    prev = df15.iloc[-2]
    # 기본 조건
    cond1 = state == '상승'
    cond2 = abs(last['close'] - last['ma20'])/last['ma20'] < 0.005
    cond3 = prev['rsi'] < 50 and last['rsi'] > 50
    cond4 = prev['hist'] < 0 and last['hist'] > 0
    cond5 = prev['stoch_k'] < 20 and last['stoch_k'] > last['stoch_d']
    # 거래량 급증: 최근 20봉 평균 대비 1.2배 이상
    vol_avg = df15['volume'].rolling(20).mean().iloc[-1]
    cond6 = last['volume'] > vol_avg * 1.2
    return all([cond1, cond2, cond3, cond4, cond5, cond6])


def is_rebound_entry(state, df15):
    """
    하락장 내 한시적 반등 후 재하락 타점 탐지
    주요 조건: RSI, MACD, Stochastic 반전 + MA20 근접 + 거래량 급증
    """
    last = df15.iloc[-1]
    prev = df15.iloc[-2]
    cond1 = state == '하락'
    cond2 = abs(last['close'] - last['ma20'])/last['ma20'] < 0.005
    cond3 = prev['rsi'] > 50 and last['rsi'] < 50
    cond4 = prev['hist'] > 0 and last['hist'] < 0
    cond5 = prev['stoch_k'] > 80 and last['stoch_k'] < last['stoch_d']
    vol_avg = df15['volume'].rolling(20).mean().iloc[-1]
    cond6 = last['volume'] > vol_avg * 1.2
    return all([cond1, cond2, cond3, cond4, cond5, cond6]) 

def is_breakdown_entry(state, df15):
    """
    상승 추세가 붕괴되는 순간 숏 진입
    조건: MA 이탈 + RSI 하향 + MACD 음전환 + 거래량 증가
    """
    last = df15.iloc[-1]
    prev = df15.iloc[-2]
    cond1 = state == '상승'
    cond2 = last['close'] < last['ma20']  # 상승 MA20 이탈
    cond3 = prev['rsi'] > 50 and last['rsi'] < 50
    cond4 = prev['hist'] > 0 and last['hist'] < 0
    cond5 = last['volume'] > df15['volume'].rolling(20).mean().iloc[-1] * 1.2
    return all([cond1, cond2, cond3, cond4, cond5])

def is_failed_rebound_entry(state, df15):
    """
    하락장 중 기술적 반등 실패 후 재하락 진입 (숏)
    조건: 반등 후 MA 저항, MACD 음전환, 거래량 둔화 후 재증가
    """
    last = df15.iloc[-1]
    prev = df15.iloc[-2]
    cond1 = state == '하락'
    cond2 = last['close'] < last['ma20']
    cond3 = prev['hist'] > 0 and last['hist'] < 0
    cond4 = last['stoch_k'] < last['stoch_d']
    cond5 = last['volume'] > df15['volume'].rolling(20).mean().iloc[-1]
    return all([cond1, cond2, cond3, cond4, cond5])