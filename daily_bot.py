import os
import datetime
import requests
import FinanceDataReader as fdr
from pykrx import stock
import pandas as pd
import time

# --- [사용자 설정: 감시할 종목 리스트] ---
# 여기에 감시하고 싶은 종목 코드와 이름을 적어주세요. (줄바꿈 오류 방지용 예시)
MY_WATCHLIST = {
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "NAVER": "035420",
    "카카오": "035720",
    "현대차": "005380"
}

# --- [설정: GitHub Secrets] ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_msg(msg):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.get(url, params={"chat_id": CHAT_ID, "text": msg})

# --- [분석 로직] ---
def get_stock_score(code):
    try:
        # 1. 수급 (최근 3일)
        today = datetime.datetime.now().strftime("%Y%m%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y%m%d")
        
        # pykrx가 가끔 휴일 데이터를 못 가져오면 에러가 날 수 있어 예외처리
        try:
            df_sup = stock.get_market_investor_net_purchase_by_date(start, today, code)
            if not df_sup.empty:
                last3 = df_sup.tail(3)
                f = last3['외국인'].sum()
                i = last3['기관합계'].sum()
            else: f, i = 0, 0
        except: f, i = 0, 0

        pass_cnt = 0
        checks = []

        if f > 0 or i > 0: pass_cnt += 1; checks.append("수급 유입(외/기)")
        
        # 2. 기술적 분석 (RSI, 이평선, 볼린저)
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=120))
        if df.empty: return 0, 0, []
        
        curr = df.iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        std = df['Close'].rolling(20).std().iloc[-1]
        upper = ma20 + (std * 2)
        lower = ma20 - (std * 2)
        
        # RSI
        delta = df['Close'].diff(1)
        up = delta.where(delta > 0, 0)
        down = -delta.where(delta < 0, 0)
        rsi = 100 - (100 / (1 + (up.rolling(14).mean().iloc[-1] / down.rolling(14).mean().iloc[-1])))
        
        if curr['Close'] >= ma20: pass_cnt += 1; checks.append("20일선 위")
        if curr['Close'] <= lower * 1.02: pass_cnt += 1; checks.append("볼린저 하단(기회)")
        elif curr['Close'] >= upper * 0.98: pass_cnt -= 0.5; checks.append("볼린저 상단(과열)")
        
        if rsi <= 70: pass_cnt += 1; checks.append("RSI 안정")
        else: checks.append("RSI 과열")
        
        score = min(pass_cnt * 25, 100)
        return score, curr['Close'], checks
    except:
        return 0, 0, []

def get_market_summary():
    # 간단 시황 (점수만)
    try:
        df = fdr.DataReader("US500", datetime.datetime.now()-datetime.timedelta(days=5))
        chg = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100
        return f"S&P500 {chg:+.2f}%"
    except: return "시장 데이터 수집중"

# --- [메인 실행] ---
if __name__ == "__main__":
    now = datetime.datetime.now() + datetime.timedelta(hours=9) # KST 변환
    hour = now.hour
    
    print(f"Current KST: {now}")

    # 1. 아침 8시 장전 브리핑
    if 8 <= hour < 9:
        msg = f"🌅 [장전 브리핑] 로봇이 깨어났습니다.\n{get_market_summary()}\n오늘도 30분 간격으로 감시하겠습니다."
        send_msg(msg)

    # 2. 장중 감시 (09:00 ~ 15:30)
    elif 9 <= hour < 16:
        alerts = []
        for name, code in MY_WATCHLIST.items():
            score, price, reasons = get_stock_score(code)
            
            # 알림 조건: 점수가 아주 좋거나(매수), 아주 나쁠 때(매도)
            if score >= 75:
                alerts.append(f"🚀 [매수 포착] {name} ({score}점)\n현재가: {price:,.0f}원\n이유: {', '.join(reasons)}")
            elif score <= 25:
                alerts.append(f"📉 [위험 경고] {name} ({score}점)\n현재가: {price:,.0f}원\n이유: {', '.join(reasons)}")
        
        if alerts:
            final_msg = f"🔔 [장중 밀착 감시] 특이종목 발견!\n\n" + "\n\n".join(alerts)
            send_msg(final_msg)
        else:
            print("특이사항 없음. 알림 생략.")

    # 3. 장 마감 추천 (16시 이후)
    elif hour >= 16:
        send_msg("☕ 오늘 장이 마감되었습니다. 수고하셨습니다!")
