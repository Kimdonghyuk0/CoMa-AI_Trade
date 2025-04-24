import threading, time

def monitor_position_exit(client, symbol, set_info):
    """
    포지션 종료 감시 (폴링) -> 익절/손절 결과 & 손익 출력
    """
    def poll():
        set_info("⏳ 포지션 종료 감시 중...")
        while True:
            try:
                pos_data = client.futures_position_information(symbol=symbol)
                # 포지션이 남아있으면 계속 대기
                if any(float(p["positionAmt"]) != 0 for p in pos_data):
                    time.sleep(10)
                    continue

                # 포지션 종료됨: 최근 체결 내역에서 realizedPnl 꺼내기
                trades = client.futures_account_trades(symbol=symbol)
                pnl = 0.0
                if trades:
                    pnl = float(trades[-1]["realizedPnl"])
                if pnl >= 0:
                    set_info(f"✅ [익절] 실현 손익: +{pnl:.2f} USDT")
                else:
                    set_info(f"❌ [손절] 실현 손익: {pnl:.2f} USDT")
                break

            except Exception as e:
                set_info(f"[오류] 감시 실패: {e}")
                time.sleep(10)

    t = threading.Thread(target=poll, daemon=True)
    t.start()
