from binance.client import Client
import config.settings as settings
from utils.data import fetch_klines
from utils.indicators import compute_indicators
from analysis.market import detect_market_state
from analysis.signals import is_pullback_entry, is_rebound_entry,is_breakdown_entry,is_failed_rebound_entry
from trading.gpt import build_prompt, get_signal
from trading.orders import place_order
from utils.logger import logger, log_market_info, log_success, log_warning


def run_trading_cycle():
    """한 번의 트레이딩 사이클 실행"""
    logger.info("=" * 70)
    logger.info("새로운 트레이딩 사이클 시작")
    
    try:
        # 1) 원본 캔들 데이터 수집 (지표용이 아닌 순수 가격·볼륨)
        logger.info("차트 데이터 수집 중...")
        df15_raw = fetch_klines(settings.SYMBOL, Client.KLINE_INTERVAL_15MINUTE, 60)
        df1h_raw = fetch_klines(settings.SYMBOL, Client.KLINE_INTERVAL_1HOUR, 120)
        df4h_raw = fetch_klines(settings.SYMBOL, Client.KLINE_INTERVAL_4HOUR, 200)
        df1d_raw = fetch_klines(settings.SYMBOL, Client.KLINE_INTERVAL_1DAY, 60)
        logger.info("차트 데이터 수집 완료")

        # 2) 원본에서 평균 거래량 계산
        avg_vol15 = df15_raw['volume'].rolling(20).mean().iloc[-1]
        avg_vol1h = df1h_raw['volume'].rolling(10).mean().iloc[-1]
        avg_vol4h = df4h_raw['volume'].rolling(10).mean().iloc[-1]
        avg_vol1d = df1d_raw['volume'].rolling(10).mean().iloc[-1]

        # 3) 지표 계산 (dropna() 적용)
        df15 = compute_indicators(df15_raw)
        df1h = compute_indicators(df1h_raw)
        df4h = compute_indicators(df4h_raw)
        df1d = compute_indicators(df1d_raw)

        # 4) 마지막 지표값 추출 및 dict 변환
        last15 = df15.iloc[-1]
        ind15m = last15.to_dict()
        ind15m['vol_avg15'] = avg_vol15

        last1h = df1h.iloc[-1]
        ind1h = last1h.to_dict()
        ind1h['vol_avg1h'] = avg_vol1h

        last4h = df4h.iloc[-1]
        ind4h = last4h.to_dict()
        ind4h['vol_avg4h'] = avg_vol4h

        last1d = df1d.iloc[-1]
        ind1d = last1d.to_dict()
        ind1d['vol_avg1d'] = avg_vol1d


        logger.info("기술적 지표 분석 중...")
            
        # 트렌드 신호 확인
        prompt = build_prompt(ind1d, ind1h, ind15m, ind4h, df1d, df1h, df15, df4h, mode='trend')
        trend_signal = get_signal(prompt)
        logger.info(f"트렌드 신호: {trend_signal['signal']}")

        # # 카운터 트레이딩 신호 확인
        # pull = is_pullback_entry(state, df15)
        # reb = is_rebound_entry(state, df15)
        # breakdown = is_breakdown_entry(state, df15)
        # fail_rebound = is_failed_rebound_entry(state, df15)
        # counter_signal = None or {'signal': '관망'}
        
        # if pull or reb or breakdown or fail_rebound:
        #     prompt_ct = build_prompt(state, ind1h, ind15m, df1h, df15, mode='counter')
        #     counter_signal = get_signal(prompt_ct)
        #     logger.info(f"카운터 트레이딩 신호: {counter_signal['signal'] if counter_signal else '없음'}")

        # 최종 신호 결정
        # final_signal = trend_signal if trend_signal['signal'] != '관망' else (counter_signal or {'signal':'관망'})
        
        if trend_signal['signal'] != '관망':
            log_success(f"거래 신호 감지: {trend_signal['signal']}")
            place_order(trend_signal, settings.LEVERAGE)
            settings.set_info(f"🧠 판단 근거: {trend_signal['reason']}")
            
        else:
            log_warning("현재 관망 상태입니다.")
            settings.set_info("📉 진입 보류하고 관망 유지 중입니다.")
            settings.set_info(f"🧠 판단 근거: {trend_signal['reason']}")
        
        logger.info("트레이딩 사이클 완료")
        return df15['open_time'].iloc[-1]

    except Exception as e:
        logger.error(f"트레이딩 사이클 실행 중 에러 발생: {str(e)}", exc_info=True)
        raise 