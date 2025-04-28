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
        # 데이터 수집
        logger.info("차트 데이터 수집 중...")
        df15 = compute_indicators(fetch_klines(settings.SYMBOL, Client.KLINE_INTERVAL_15MINUTE, 60))
        df1h = compute_indicators(fetch_klines(settings.SYMBOL, Client.KLINE_INTERVAL_1HOUR, 120))
        logger.info("차트 데이터 수집 완료")

        # 시장 상태 분석
        state = detect_market_state(df1h)
        log_market_info({
            "trend": state
        })
        

        # 지표 계산
        last15 = df15.iloc[-1]
        avg_vol15 = df15['volume'].rolling(20).mean().iloc[-1]
        ind15m = last15.to_dict()
        ind15m['vol_avg15'] = avg_vol15

        last1h = df1h.iloc[-1]
        avg_vol1h = df1h['volume'].rolling(10).mean().iloc[-1]
        ind1h = last1h.to_dict()
        ind1h['vol_avg1h'] = avg_vol1h

        logger.info("기술적 지표 분석 중...")
        
        # 트렌드 신호 확인
        prompt = build_prompt(state, ind1h, ind15m, df1h, df15, mode='trend')
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
            settings.set_info("📉 리스크 대비 리워드 비율(RR) 미달 → 진입 보류하고 관망 유지 중입니다.")
            settings.set_info(f"🧠 판단 근거: {trend_signal['reason']}")
        
        logger.info("트레이딩 사이클 완료")
        return df15['open_time'].iloc[-1]

    except Exception as e:
        logger.error(f"트레이딩 사이클 실행 중 에러 발생: {str(e)}", exc_info=True)
        raise 