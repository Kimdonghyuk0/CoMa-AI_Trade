import tkinter as tk
from tkinter import messagebox, ttk
from binance.client import Client
import threading
import time
from utils.data import fetch_klines
from datetime import datetime, timezone
from config.settings import b_key
from decimal import Decimal
from config import settings

# 전역 Info 박스와 set_info 함수 선언
info_box = None
trading_thread: threading.Thread | None = None
stop_event: threading.Event | None = None
total_profit = Decimal('0.00')
profit_var = None 
def add_profit(amount: Decimal):
    global total_profit, profit_var
    total_profit += amount
    profit_var.set(f"총 수익: {total_profit:.2f} USDT")

    
def set_info(msg: str):
    """Info 박스에 메시지 추가 출력하고 자동 스크롤."""
    if info_box:
        info_box.config(state="normal")    # (1) 쓰기 가능 상태로 풀고
        info_box.insert(tk.END, msg + "\n")
        info_box.see(tk.END)
        info_box.config(state="disabled")   # (2) 다시 잠금

def run_trading_after_config(config):
    """
    자동매매 루프 진입점 (스레드용).
    — 매 10초마다 최신 15분봉의 시작 시각을 확인해서
      이전과 다를 때만 run_trading_cycle()을 호출합니다.
    """
    from trading.strategy import run_trading_cycle
    set_info(" ")
    set_info("🔧 시스템 부팅 중... 전략 판단 및 시장 탐색 준비 완료.")
    set_info(" ")
    set_info("⏳ 대기중... 포지션 보유중이 아닐 경우, 최대 15분 이내에 실행됩니다.")
    # last_open = None
    symbol   = config["SYMBOL"]
    interval = Client.KLINE_INTERVAL_15MINUTE
    last_minute = -1
    last_hour   = -1
    settings.is_entry_allowed = True
   
    while not stop_event.is_set():
            now_utc = datetime.now(timezone.utc)
            minute = now_utc.minute
            second = now_utc.second
            hour = now_utc.hour
             # 1️⃣ 1시간봉 변화 감지 → 진입 재허용
            if hour != last_hour:
                last_hour = hour
                settings.is_entry_allowed = True

            from trading.state import is_in_position
            
            # 1) 가장 최근 15분봉 한 개만 가져오기
            if minute % 15 == 0 and minute != last_minute and second < 5:
                last_minute = minute             
                if not is_in_position() and settings.is_entry_allowed:
                  
                    try:
                        time.sleep(2)
                        df15 = fetch_klines(symbol, interval, limit=1)
                        current_open = df15['open_time'].iloc[-1]
                        open_orders = config["client"].futures_get_open_orders(symbol=symbol)
                        #print("open_orders", open_orders)
                        if open_orders:
                            set_info(" ")
                            set_info("⏳ 예약 주문 전부 삭제 중...")
                            config["client"].futures_cancel_all_open_orders(symbol=symbol)
                        print("새 봉이 떴을 때만 전략 사이클 실행")
                        # last_open = current_open
                        set_info(" ")
                        set_info(f"📊 최신 차트 수신 완료...")
                        time.sleep(0.2)
                        set_info(f"UTC: {current_open}")
                        set_info(f"🤖 전략 최적화 중... 시장 움직임에 가장 적합한 진입 타점 추출 중...")
                        run_trading_cycle()
                        time.sleep(4.5)
                    except Exception as e:
                        set_info(f"🚨 에러 발생: {str(e)}")
            # 1초마다 폴링
            time.sleep(1)
    set_info("⏹️ 자동매매 루프 종료")

        
def cancel_all_orders():
    """모든 예약 주문 삭제"""
    try:
        client = settings.client
        symbol = settings.SYMBOL
        client.futures_cancel_all_open_orders(symbol=symbol)
        set_info(f"🧹 {symbol} - 모든 예약 주문 삭제 완료")
    except Exception as e:
        set_info(f"🚨 예약 주문 삭제 에러: {str(e)}")
        
def close_position():
    """현재 포지션 즉시 시장가로 청산"""
    try:
        client = settings.client
        symbol = settings.SYMBOL
        positions = client.futures_position_information(symbol=symbol)
        for pos in positions:
            if Decimal(pos['positionAmt']) != 0:
                side = 'SELL' if Decimal(pos['positionAmt']) > 0 else 'BUY'
                qty = abs(Decimal(pos['positionAmt']))
                client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='MARKET',
                    quantity=float(qty)
                )
                set_info(f"🧹 {symbol} - 포지션 {side} {qty} 청산 완료")
            else:
                set_info(f"⚡️ {symbol} - 현재 포지션이 없습니다.")
    except Exception as e:
        set_info(f"🚨 {symbol} - 포지션 정리 에러: {str(e)}")

def get_user_settings():
    """
    GUI를 띄워 사용자 설정을 받고,
    설정 완료 시 자동으로 run_trading_after_config 스레드를 띄웁니다.
    """
    global info_box,profit_var
    config = {}

    def on_submit():
        global trading_thread, stop_event
        # 1) 입력값 수집
        b_secret = entry_binance_secret.get().strip()
        # o_key    = entry_openai_key.get().strip()
        sym = symbol_var.get()
        lev      = int(leverage_var.get())
        # rr_txt   = entry_rr.get().strip()
        amount_value_str = entry_amount.get().strip()
        amount_mode  = amount_mode_var.get()

        if amount_mode != "전액":
         try:
            amount_value = float(amount_value_str)
         except ValueError:
            messagebox.showerror("입력 오류", "금액 또는 퍼센트를 올바른 숫자로 입력해주세요.")
            return
        else:
          amount_value = None  # 전액 모드일 땐 수치 필요 없음
    

        # 3) Binance client 생성 테스트 (연결 + 선물 계좌 권한 확인)
        try:
            client = Client(b_key, b_secret)
            client.ping()
            _ = client.futures_account_balance()
        except Exception as e:
            messagebox.showerror(
                "API 오류",
                f"Binance 연결 실패 또는 권한 부족:\n{type(e).__name__} – {e}"
            )
            return
        from config.api_client import init_client
        init_client(b_key, b_secret)
  
        config.update({
            "client": client,
            "LEVERAGE": lev,
            "SYMBOL": sym,
            "set_info": set_info,
            "AMOUNT_VALUE": amount_value,
            "AMOUNT_MODE": amount_mode,
            "add_profit": add_profit

        })
        from config.settings import configure
        configure(config)
        

        # 5) Info 출력 및 폼 비활성화
        set_info("✅ 설정 저장 완료")
        for w in form.winfo_children():
            try: w.configure(state="disabled")
            except: pass

        if trading_thread and trading_thread.is_alive():
            stop_event.set()
        stop_event = threading.Event()
        # 6) 자동매매 루프 스레드 시작
        set_info("✅ 자동매매 루프 시작")
        trading_thread =threading.Thread(
            target=run_trading_after_config,
            args=(config,),
            daemon=True
        )
        trading_thread.start()

    def on_cancel():
        messagebox.showinfo("종료", "프로그램을 종료합니다.")
        root.destroy()
        exit()

    # ───────────────────────────────────────────────────────
    # GUI 레이아웃
    root = tk.Tk()
    root.title("💹 거래 봇 설정")
    root.geometry("1020x650")
    root.resizable(False, False)

    # 왼쪽: 입력 폼
    form = tk.Frame(root)
    form.place(x=10, y=10, width=400, height=580)

    # tk.Label(form, text="🟢 Binance API Key").pack(pady=(10,0))
    # entry_binance_key = tk.Entry(form, width=50)
    # entry_binance_key.pack()

    tk.Label(form, text="🟢 Binance API Secret").pack(pady=(10,0))
    entry_binance_secret = tk.Entry(form, width=50, show="*")
    entry_binance_secret.pack()

    # tk.Label(form, text="🔵 OpenAI API Key").pack(pady=(10,0))
    # entry_openai_key = tk.Entry(form, width=50, show="*")
    # entry_openai_key.pack()

    tk.Label(form, text="📊 거래 종목 선택").pack(pady=(10,0))
    symbol_var = tk.StringVar(value="BTCUSDT")
    symbol_combo = ttk.Combobox(
        form,
        textvariable=symbol_var,
        values=["BTCUSDT", "ETHUSDT", "XRPUSDT","SOLUSDT"],  # 기본 목록
    )
    symbol_combo.pack()
    symbol_combo.focus()  # 커서 자동 포커스 (선택 또는 입력 가능)

    tk.Label(form, text="⚙️ 레버리지 (1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20)").pack(pady=(10,0))
    leverage_var = tk.StringVar(value="1")
    tk.OptionMenu(form, leverage_var, "1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19","20").pack()
    def on_edit():
        # 폼 안의 모든 위젯을 활성화
        for w in form.winfo_children():
            try:
                w.configure(state="normal")
            except:
                pass
        if amount_mode_var.get() == "전액":
          entry_amount.configure(state="disabled")
        set_info(" ")
        set_info("✏️ 설정 수정 모드로 전환되었습니다. \n 값을 변경하고 ‘설정 저장 및 시작’을 눌러주세요.")

    def on_amount_mode_change(selection):
        if selection == "전액":
            entry_amount.configure(state="disabled")
        else:
            entry_amount.configure(state="normal")
    tk.Label(form, text="💰 매매당 진입 금액").pack(pady=(10,0))
    amount_mode_var = tk.StringVar(value="사용자 입력($)")
    tk.OptionMenu(
        form,
        amount_mode_var,
        "사용자 입력($)", "전액의(%)",
        command=on_amount_mode_change
    ).pack()

    tk.Label(form, text="💵 금액(달러$) or 비율(%) 입력 (예: 1000 or 25)").pack(pady=(5,0))
    entry_amount = tk.Entry(form, width=20)
    entry_amount.insert(0, "1000")
    entry_amount.pack()

  
    spacer = tk.Frame(form)
    spacer.pack(expand=True, fill="y") 
    
    btns = tk.Frame(form)
    btns.pack(pady=5)
    tk.Button(
        btns,
        text="✅ 설정 저장 및 시작",
        command=on_submit,
        bg="#4CAF50",
        fg="white",
        width=17,
        font=("맑은 고딕", 10, "bold")
    ).pack(side="left", padx=5)
    # tk.Button(
    #     btns,
    #     text="✏️ 설정 수정",
    #     command=on_edit,
    #     bg="#FFA500",
    #     fg="white",
    #     width=15
    # ).pack(side="left", padx=5)
    tk.Button(
        btns,
        text="❌ 종료",
        command=on_cancel,
        bg="#f44336",
        fg="white",
        width=17,
        font=("맑은 고딕", 10, "bold")
    ).pack(side="left", padx=5)
   
    actions = tk.Frame(form)
    actions.pack(pady=(10, 0))  # 약간만 위아래 간격

    tk.Button(
        actions,
        text="포지션 정리",
        command=close_position,
        bg="#f44336",
        fg="white",
        width=17,
        font=("맑은 고딕", 10, "bold")
    ).pack(side="left", padx=5)

    tk.Button(
        actions,
        text="예약 주문 삭제",
        command=cancel_all_orders,
        bg="#f44336",
        fg="white",
        width=17,
        font=("맑은 고딕", 10, "bold")
    ).pack(side="left", padx=5)
    # ── 누적 수익 표시 ──
    profit_var = tk.StringVar(value="총 수익: 0.00 USDT")
    profit_label = tk.Label(
      root,
     textvariable=profit_var,
     font=("맑은 고딕", 12, "bold"),
     bg="#e0e0e0",
     anchor="center"
    )
# 위치: 우측 하단 (예: x=420+..., y=10+580+10)
    profit_label.place(x=790, y=600, width=200, height= 30)

    # 오른쪽: Info 박스
    info_frame = tk.LabelFrame(root, text="📋 실시간 정보", padx=5, pady=5)
    info_frame.place(x=420, y=10, width=570, height=580)
    info_box = tk.Text(info_frame, bg="#f5f5f5", state="disabled")
    info_box.pack(fill="both", expand=True)
    tk.Label(root, text="* 종료 시, 바이낸스에 예약된 모든 주문은 *반드시* 취소해야 합니다. *", fg="red").place(x=10, y=600)
    root.mainloop()
    return config