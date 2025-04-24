def detect_market_state(df1h):
    """
    1시간봉 기준 추세(상승/하락/횡보) 결정
    :param df1h: 1시간봉 지표 계산된 DataFrame
    :return: '상승', '하락' 또는 '횡보'
    """
    last = df1h.iloc[-1]
    # 상승장: MA5 > MA20 > MA60 + MA20 기울기 양수
    if last['ma5'] > last['ma20'] > last['ma60'] and (df1h['ma20'].iloc[-1] - df1h['ma20'].iloc[-2]) > 0:
        return '상승'
    # 하락장: MA5 < MA20 < MA60 + MA20 기울기 음수
    if last['ma5'] < last['ma20'] < last['ma60'] and (df1h['ma20'].iloc[-1] - df1h['ma20'].iloc[-2]) < 0:
        return '하락'
    # 그 외 횡보장
    return '횡보' 