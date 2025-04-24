import logging
from datetime import datetime
import sys

def setup_logger():
    # 로거 생성
    logger = logging.getLogger('TradingBot')
    logger.setLevel(logging.DEBUG)
    
    # 콘솔 핸들러 생성
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # 포맷터 생성
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # 핸들러 추가
    logger.addHandler(console_handler)
    
    return logger

# 글로벌 로거 인스턴스 생성
logger = setup_logger()

def log_trade_info(data):
    """거래 정보 로깅"""
    logger.info("=" * 50)
    logger.info("📊 거래 신호 감지")
    logger.info(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"심볼: {data.get('symbol', '-')}")
    logger.info(f"포지션: {data.get('signal', '-')}")
    logger.info(f"진입가: {data.get('entry', '-')}")
    logger.info(f"손절가: {data.get('sl', '-')}")
    logger.info(f"목표가: {data.get('tp', '-')}")
    logger.info("=" * 50)

def log_position_info(position):
    """포지션 정보 로깅"""
    logger.info("-" * 50)
    logger.info("📈 포지션 정보")
    logger.info(f"심볼: {position.get('symbol', '-')}")
    logger.info(f"수량: {position.get('positionAmt', '0')}")
    logger.info(f"진입가: {position.get('entryPrice', '0')}")
    logger.info(f"미실현 손익: {position.get('unrealizedProfit', '0')} USDT")
    logger.info("-" * 50)

def log_error(error_msg, exc_info=None):
    """에러 로깅"""
    logger.error(f"❌ 에러 발생: {error_msg}", exc_info=exc_info)

def log_success(msg):
    """성공 로깅"""
    logger.info(f"✅ {msg}")

def log_warning(msg):
    """경고 로깅"""
    logger.warning(f"⚠️ {msg}")

def log_market_info(data):
    """시장 상태 로깅"""
    logger.info("🌍 시장 상태")
    logger.info(f"추세: {data.get('trend', '-')}")