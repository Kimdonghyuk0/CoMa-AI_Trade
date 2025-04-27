import json
from openai import OpenAI
import config.settings as settings

import re
# OpenAI API 키 설정
client = OpenAI(api_key=settings.OPENAI_API_KEY)
def build_prompt(state, ind1h, ind15m, df1h, df15, mode='trend'):
    """
     시장 상태 및 모드(트렌드/반전)에 따른 프롬프트 템플릿 생성
    :param state: '상승', '하락', '횡보'
    :param ind1h: 1시간봉 지표 딕셔너리 (MA, RSI, MACD, BB, Stoch, OBV, vol_avg1h 포함)
    :param ind15m: 15분봉 지표 딕셔너리 (MA, RSI, MACD, BB, Stoch, OBV, volume, vol_avg15 포함)
    :param df1h: 1시간봉 데이터프레임
    :param df15: 15분봉 데이터프레임
    :param mode: 'trend' 또는 'counter'
    :return: 완성된 프롬프트 문자열
    """
    # # 모드별 설명 추가 (1시간봉 기준)
    # if mode == 'trend':
    #     header = (
    #         f"시장상태: {state}\n"
    #         "=> 트렌드 추종 전략: 현재 1시간봉의 추세를 그대로 따라가는 진입 기회를 분석합니다.\n"
    #         "상승장에서는 롱 진입, 하락장에서는 숏 진입을 우선 고려합니다."
    #     )
    # else:
    #     header = (
    #         f"시장상태: {state}\n"
    #         "=> 역추세 반전 전략: 현재 추세와 반대로 눌림목이나 반등 구간에서의 진입 기회를 분석합니다.\n"
    #         "상승장에서는 고점 눌림에서 숏 진입, 하락장에서는 기술적 반등에서의 롱 진입을 고려합니다."
    #     )
            # 필요한 컬럼만 추출 (프롬프트 크기 절약)
    cols = ["open_time", "open", "high", "low", "close", "volume"]
    df1h_trimmed = df1h[cols].tail(30).to_dict(orient='records')
    df15_trimmed = df15[cols].tail(40).to_dict(orient='records')

    payload = {
        "1h_candles": df1h_trimmed,
        "15m_candles": df15_trimmed,
        "1h": ind1h,
        "15m": ind15m
    }

    prompt_json = json.dumps(payload, ensure_ascii=False, default=str)
    # 환경정보 및 조건 안내
    template = f"""
당신은 {settings.SYMBOL} 선물 트레이딩 전문가입니다.

※ **지표 계산 방식 정의**  
- RSI(14): 최근 14봉 종가 차이의 Wilder’s smoothing (EWMA, span=14) 적용  
- MACD: EMA12(12) – EMA26(26), Signal line은 MACD의 EMA9, Histogram = MACD – Signal  
- Bollinger Bands: 중단선(bb_mid)=20봉 SMA, 상단/하단 = bb_mid ± 2×20봉 표준편차  
- Stochastic(14,3): %K = (종가 – 14봉 저가 최저) / (14봉 고가 최고 – 14봉 저가 최저) ×100, %D는 %K의 3봉 SMA  
- OBV: 전봉 종가 대비 상승 시 +거래량, 하락 시 –거래량 누적  
- ATR(14): True Range(고가-저가, |고가-전종가|, |저가-전종가|) 중 최댓값의 EWMA(span=14)

아래의 지표와 가격 데이터를 기반으로,
 현재 시장 상황을 직접 진단하고 (상승장 / 하락장 / 횡보장),
 그에 맞는 전략 모드를 선택한 후,
 최적의 진입 방향 ("롱", "숏", "관망")과 진입가, 손절가, 익절가를 제시하세요.

 ※ 아래 가이드는 기본 전략이므로,
   시장 상황에 따라 **필요에 따라 조건을 가감하며** 최적의 결정을 내려야 합니다.
---

 1단계: 시장 상태 진단 (GPT가 스스로 분석)

다음을 종합하여 현재 시장을 판단하세요:
- 1시간봉 MA20/60 배열
- RSI > 55: 상승 / < 45: 하락 / 45~55: 횡보
- MACD > Signal: 상승세 / < Signal: 하락세
- 가격이 BB 중단선 위인지 아래인지
- 최근 OBV 방향성 
- 기타 주요 모멘텀 지표
→ 종합해 아래 중 하나 선택: 
  - "상승장"
  - "하락장"
  - "횡보장"

---

 2단계: 전략 모드 분기

*상승장*  
- **trend – 기본 롱**: 15m 눌림 후 반등(또는 1~2틱 조정) 확인 시  
- **trend – 보조 롱(돌파)**: 눌림 없거나 즉시 상승 구간이면 15m 고점 돌파 시  
- **counter – 단기 숏(조정)**: 과매수+둔화+거래량 감소 시  
- **counter 금지**: 강한 추세 구간에서는 숏 금지  

*하락장*  
- **trend – 기본 숏**: 15m 되돌림 후 하락 재개 시  
- **trend – 보조 숏(돌파)**: 되돌림 없거나 즉시 하락 구간이면 15m 저점 이탈 시  
- **counter – 단기 롱(반등)**: 과매도+MACD 반등+거래량 급증 시  
- **counter 금지**: 강한 추세 구간에서는 롱 금지  

*횡보장*  
- **trend – 단기 롱(반등)**:  BB 하단 터치 + 거래량 급등  
- **counter – 단기 숏(조정)**:  BB 상단 터치 + 거래량 급감  
- **counter – 돌파 진입**: 수렴 구간 돌파 확인 시  
- **관망**: 위 조건 외 모든 경우  

---

3단계: 진입 조건

아래 조건들을 충족할 때만 진입하세요:
- RSI, MACD, 거래량, 볼린저밴드, 캔들패턴 등 종합 판단

※ 시장 변동성(가격 범위, ATR, 볼린저밴드 폭 등)을 고려해, 
 TP/SL 거리도 자동으로 조정하세요.

- 변동성이 클 경우: TP/SL 거리를 늘려서 비교적 넉넉히 설정

- 변동성이 작을 경우: TP/SL 거리를 줄여서 빠르게 익절 또는 손절

- 손익비(RR)는 1.0 ≤ RR ≤ 1.3** 범위 내에 있을 것  
  (단, 변동성이 급격히 축소된 구간(BB 수축, ATR 하락 등)에서는 1.2까지만 허용)
   # RR 계산식:
     * 롱: RR = (tp - entry) / (entry - sl)
     * 숏: RR = (entry - tp) / (sl - entry)

- 진입가(entry)는 시장가보다 보수적으로 유리한 가격(롱: 시장가 아래, 숏: 시장가 위)에 설정하되,
  15분 내 체결 가능 구간을 벗어나지 않도록 하세요.

지지/저항, BB 밴드, 피보나치 등을 참고하여 TP/SL 설정

---

아래는 분석용 전체 캔들 시퀀스와 최신 지표 데이터입니다:
 최근 1시간봉 30개 (1h_candles)
 최근 15분봉 40개 (15m_candles)
 최신 1시간 지표: 1h
 최신 15분 지표: 15m
```json
{prompt_json}
```

응답은 오직 JSON 오브젝트만으로 구성하십시오.  
– 최상위에 아래 네 개 필드(“signal”, “entry”, “tp”, “sl”)만 포함  
– 중첩된 객체나 배열, 추가 텍스트, 주석일체 금지  
– JSON 블록 바깥에는 반드시 `<EOF>`만 출력  
예시:
{{
  "signal": "롱" | "숏" | "관망",
  "entry": 진입가격,
  "tp": 익절가,
  "sl": 손절가
}}

<EOF>

""" 
    print(template)

    return template
    
    
def get_signal(prompt):
    """OpenAI ChatCompletion을 사용해 신호(JSON) 받기"""
    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}]
    )
    raw = res.choices[0].message.content
    print(f"GPT 응답: {raw}")
    # <EOF> 기준으로 나눔
    if "<EOF>" in raw:
        json_part = raw.split("<EOF>")[0].strip()
    else:
        raise ValueError("응답에 <EOF> 태그가 없습니다.")

    # 백틱으로 감싸진 JSON 제거 (```json ... ```)
    if "```json" in json_part:
        json_part = json_part.split("```json")[1].strip()
    if "```" in json_part:
        json_part = json_part.split("```")[0].strip()

    # JSON 디코딩
    try:
        return json.loads(json_part)
    except json.JSONDecodeError as e:
        raise ValueError(f"❌ GPT 응답 파싱 실패: {e}\n[GPT 응답 원문]\n{raw}")