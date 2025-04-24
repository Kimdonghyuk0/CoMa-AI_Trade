import tkinter as tk
from tkinter import messagebox
from binance.client import Client
import threading
import time
from utils.data import fetch_klines
from datetime import datetime, UTC

# 전역 Info 박스와 set_info 함수 선언
info_box = None

def set_info(msg: str):
    """Info 박스에 메시지 추가 출력하고 자동 스크롤."""
    if info_box:
        info_box.insert(tk.END, msg + "\n")
        info_box.see(tk.END)

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
    set_info("⏳ 대기중... 최대 15분 이내에 실행됩니다.")
    last_open = None
    symbol   = config["SYMBOL"]
    interval = Client.KLINE_INTERVAL_15MINUTE

    while True:
        
        
            from trading.state import is_in_position_or_waiting
            
            # 1) 가장 최근 15분봉 한 개만 가져오기
            df15 = fetch_klines(symbol, interval, limit=1)
            current_open = df15['open_time'].iloc[-1]
            current_open_diff = current_open.replace(tzinfo=UTC)
            now_utc = datetime.now(UTC)
            elapsed = abs((now_utc - current_open_diff).total_seconds())
            
            # 🧠 [추가] 예약 주문이 존재하면 취소 처리
            if current_open != last_open:
              open_orders = config["client"].futures_get_open_orders(symbol=symbol)
              if open_orders:
                  set_info("⛔️ 포착된 진입 타점과 실제 흐름 불일치 — 예약 주문 전부 취소하고 새 전략을 계산합니다.")
                  for order in open_orders:
                    config["client"].futures_cancel_order(symbol=symbol, orderId=order['orderId'])
            

            # 2) 새 봉이 떴을 때만 전략 사이클 실행
            if current_open != last_open and not is_in_position_or_waiting() and elapsed < 65:
                last_open = current_open
                set_info(" ")
                set_info(f"📊 최신 차트 수신 완료...")
                time.sleep(0.2)
                set_info(f"UTC: {current_open}")
                set_info(f"🤖 전략 최적화 중... 시장 움직임에 가장 적합한 진입 타점 추출 중...")
                run_trading_cycle()

            # 10초마다 폴링
            time.sleep(10)
        

        

def get_user_settings():
    """
    GUI를 띄워 사용자 설정을 받고,
    설정 완료 시 자동으로 run_trading_after_config 스레드를 띄웁니다.
    """
    global info_box
    config = {}

    def on_submit():
        
        # 1) 입력값 수집
        b_key    = entry_binance_key.get().strip()
        b_secret = entry_binance_secret.get().strip()
        o_key    = entry_openai_key.get().strip()
        sym = symbol_var.get()
        lev      = int(leverage_var.get())
        rr_txt   = entry_rr.get().strip()
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
        # 2) 유효성 검사
        if not (b_key and b_secret and o_key and rr_txt):
            messagebox.showerror("입력 오류", "모든 값을 입력해주세요.")
            return
        try:
            target_rr = float(rr_txt)
            if target_rr <= 0:
                raise ValueError
        except:
            messagebox.showerror("입력 오류", "유효한 손익비(RR)를 입력하세요.")
            return

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
            "OPENAI_API_KEY": o_key,
            "LEVERAGE": lev,
            "SYMBOL": sym,
            "TARGET_RR": target_rr,
            "set_info": set_info,
            "AMOUNT_VALUE": amount_value,
            "AMOUNT_MODE": amount_mode

        })
        from config.settings import configure
        configure(config)
        

        # 5) Info 출력 및 폼 비활성화
        set_info("✅ 설정 저장 완료")
        for w in form.winfo_children():
            try: w.configure(state="disabled")
            except: pass

        # 6) 자동매매 루프 스레드 시작
        set_info("✅ 자동매매 루프 시작")
        threading.Thread(
            target=run_trading_after_config,
            args=(config,),
            daemon=True
        ).start()

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

    tk.Label(form, text="🟢 Binance API Key").pack(pady=(10,0))
    entry_binance_key = tk.Entry(form, width=50)
    entry_binance_key.pack()

    tk.Label(form, text="🟢 Binance API Secret").pack(pady=(10,0))
    entry_binance_secret = tk.Entry(form, width=50, show="*")
    entry_binance_secret.pack()

    tk.Label(form, text="🔵 OpenAI API Key").pack(pady=(10,0))
    entry_openai_key = tk.Entry(form, width=50, show="*")
    entry_openai_key.pack()

    tk.Label(form, text="📊 거래 종목 선택").pack(pady=(10,0))
    symbol_var = tk.StringVar(value="BTCUSDT")
    tk.OptionMenu(form, symbol_var, "BTCUSDT", "ETHUSDT", "XRPUSDT").pack()


    tk.Label(form, text="⚙️ 레버리지 (1,2,3,4,5,6,7)").pack(pady=(10,0))
    leverage_var = tk.StringVar(value="1")
    tk.OptionMenu(form, leverage_var, "1","2","3","4","5","6","7").pack()
    def on_edit():
        # 폼 안의 모든 위젯을 활성화
        for w in form.winfo_children():
            try:
                w.configure(state="normal")
            except:
                pass
        set_info(" ")
        set_info("✏️ 설정 수정 모드로 전환되었습니다. 값을 변경하고 ‘설정 저장 및 시작’을 눌러주세요.")

    def on_amount_mode_change(selection):
        if selection == "전액":
            entry_amount.configure(state="disabled")
        else:
            entry_amount.configure(state="normal")
    tk.Label(form, text="💰 매매당 진입 금액").pack(pady=(10,0))
    amount_mode_var = tk.StringVar(value="전액")
    tk.OptionMenu(
        form,
        amount_mode_var,
        "전액", "사용자 입력($)", "전액의(%)",
        command=on_amount_mode_change
    ).pack()

    tk.Label(form, text="💵 금액(달러$) or % 입력 (예: 100 or 25)").pack(pady=(5,0))
    entry_amount = tk.Entry(form, width=20)
    entry_amount.insert(0, "100")
    entry_amount.pack()
    entry_amount.configure(state="disabled")

    tk.Label(form, text="📈 목표 손익비 (예:1.5)").pack(pady=(10,0))
    entry_rr = tk.Entry(form, width=20)
    entry_rr.insert(0, "1.5")
    entry_rr.pack()

    btns = tk.Frame(form)
    btns.pack(pady=20)
    tk.Button(
        btns,
        text="✅ 설정 저장 및 시작",
        command=on_submit,
        bg="#4CAF50",
        fg="white",
        width=15
    ).pack(side="left", padx=5)
    tk.Button(
        btns,
        text="✏️ 설정 수정",
        command=on_edit,
        bg="#FFA500",
        fg="white",
        width=15
    ).pack(side="left", padx=5)
    tk.Button(
        btns,
        text="❌ 종료",
        command=on_cancel,
        bg="#f44336",
        fg="white",
        width=10
    ).pack(side="left", padx=5)

    # 오른쪽: Info 박스
    info_frame = tk.LabelFrame(root, text="📋 실시간 정보", padx=5, pady=5)
    info_frame.place(x=420, y=10, width=570, height=580)
    info_box = tk.Text(info_frame, bg="#f5f5f5")
    info_box.pack(fill="both", expand=True)

    root.mainloop()
    return config
