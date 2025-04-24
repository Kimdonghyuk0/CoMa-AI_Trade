# config/settings.py

# GUI 에서 입력받은 설정을 전역 변수로 보관합니다.
client = None
OPENAI_API_KEY = None
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
    global client, OPENAI_API_KEY, LEVERAGE, SYMBOL, TARGET_RR, set_info
    client = config_dict["client"]
    OPENAI_API_KEY = config_dict["OPENAI_API_KEY"]
    LEVERAGE = config_dict["LEVERAGE"]
    SYMBOL = config_dict["SYMBOL"]
    TARGET_RR = config_dict["TARGET_RR"]
    set_info = config_dict["set_info"]
    AMOUNT_VALUE = config_dict["AMOUNT_VALUE"]
    AMOUNT_MODE = config_dict["AMOUNT_MODE"]

