# config/settings.py
try:
    from .keys import OPENAI_API_KEY, BINANCE_API_KEY as b_key
except ImportError:
    raise ImportError("keys.py 파일이 없습니다. keys.py.example을 참고하여 생성해주세요.")

# GUI 에서 입력받은 설정을 전역 변수로 보관합니다.
client = None
LEVERAGE = None
SYMBOL = None
TARGET_RR = None
set_info = None
AMOUNT_VALUE = None
AMOUNT_MODE = None  

def configure(config_dict):
    """
    get_user_settings()에서 받은 설정 dict를 그대로 전역 변수에 할당.
    """
    global client, OPENAI_API_KEY, b_key, LEVERAGE, SYMBOL, TARGET_RR, set_info, AMOUNT_VALUE, AMOUNT_MODE, add_profit
    client = config_dict["client"]
    LEVERAGE = config_dict["LEVERAGE"]
    SYMBOL = config_dict["SYMBOL"]
    set_info = config_dict["set_info"]
    AMOUNT_VALUE = config_dict["AMOUNT_VALUE"]
    AMOUNT_MODE = config_dict["AMOUNT_MODE"]
    add_profit = config_dict["add_profit"]

