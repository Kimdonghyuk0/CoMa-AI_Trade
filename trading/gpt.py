import json
from openai import OpenAI
from config.settings import OPENAI_API_KEY, TARGET_RR, SYMBOL
from config.settings import set_info  # GUI Info 로그용
import re
# OpenAI API 키 설정
client = OpenAI(api_key=OPENAI_API_KEY)
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
    # 모드별 설명 추가 (1시간봉 기준)
    if mode == 'trend':
        header = (
            f"시장상태: {state}\n"
            "=> 트렌드 추종 전략: 현재 1시간봉의 추세를 그대로 따라가는 진입 기회를 분석합니다.\n"
            "상승장에서는 롱 진입, 하락장에서는 숏 진입을 우선 고려합니다."
        )
    else:
        header = (
            f"시장상태: {state}\n"
            "=> 역추세 반전 전략: 현재 추세와 반대로 눌림목이나 반등 구간에서의 진입 기회를 분석합니다.\n"
            "상승장에서는 고점 눌림에서 숏 진입, 하락장에서는 기술적 반등에서의 롱 진입을 고려합니다."
        )
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
당신은 {SYMBOL} 선물 트레이딩 전문가입니다.

{header}
아래 JSON 형식의 지표 데이터를 참고하여,  '롱' 또는 '숏' 또는 '관망' 시그널을 제안하고,
진입가(entry), 익절가(tp), 손절가(sl)를 산출하세요.
리스크-리워드(RR)는 최소 {TARGET_RR} 이상이어야 합니다.

분석 시야:
- 1시간봉 기준
  - 추세 흐름: 상승 / 하락 / 횡보 판단
  - MA 배열: 정배열 / 역배열 / 꼬임 여부 분석
  - 주요 지지·저항: 매물대 + 이평선 겹침 여부 확인
- 15분봉 기준
  - 진입 흐름: 눌림목 / 돌파 / 삼각수렴 분석
  - 캔들패턴: 반전형 / 지속형 존재 여부 확인
  - 볼린저밴드: 수축 후 확장 or 중심선 돌파 여부 판단

 **핵심 진입 조건** :
 - MA 5/20/60 정배열
 - RSI(14) 50선 돌파
 - MACD 히스토그램 전환
 - 볼린저밴드 중심선 돌파

아래는 분석용 전체 캔들 시퀀스와 최신 지표 데이터입니다:
 최근 1시간봉 30개 (1h_candles)
 최근 15분봉 40개 (15m_candles)
 최신 1시간 지표: 1h
 최신 15분 지표: 15m
```json
{prompt_json}
```
  RR ≥ {TARGET_RR} 미만인 경우 혹은 승률이 60%미만이라고 판단될 경우 반드시 '관망'을 반환하세요.

 여러 개의 유효한 진입 기회 중 RR ≥ {TARGET_RR}을 만족하는 옵션이 있다면,
  실제 차트 패턴과 지지·저항 구간을 기준으로 가장 확실하고 높은 RR 값을 제시하세요.

 진입가는 반드시 현재 시장가 기준, **향후 15분 이내에 체결 가능한 수준**이어야 합니다.
  너무 동떨어진 가격을 제시하면 거래가 성사되지 않으므로 반드시 피해야 합니다.

 TP(익절) / SL(손절)은 최근 가격 범위를 벗어나는 **과도한 값은 지양**하며,
  실재 차트상의 지지·저항, 볼린저밴드, 피보나치 수준 등을 기준으로 산출해야 합니다.

응답은 반드시 아래 JSON 형식으로 출력하세요.
그리고 JSON 블록 **바깥에** `<EOF>`만 따로 출력하세요.

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