import os
import datetime
import requests
import FinanceDataReader as fdr
from pykrx import stock
import pandas as pd
import json
import time

# --- [설정] ---
DATA_FILE = "my_watchlist_v7.json" # 로봇이 읽어야 할 공용 장부 파일명

# --- [GitHub Secrets: 텔레그램 설정 가져오기] ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_msg(msg):
    if not TOKEN or not CHAT_ID:
        print("텔레그램 토큰이 없습니다. (GitHub Secrets 확인 필요)")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.get(url, params={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print(f"전송 실패: {e}")

# --- [핵심: JSON 파일에서 종목 불러오기] ---
def load_watchlist():
    # 1. 같은 폴더에 파일이 있는지 확인
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 데이터 변환: {"삼성전자": "005930", ...} 형태로 만듦
                watchlist = {name: info["code"] for name, info in data.items()}
                return watchlist
        except Exception as e:
            print(f"파일 읽기 에러: {e}")
            
    # 2. 파일이 없거나 에러나면 비상용 기본값 사용
    print("기본 종목 리스트를 사용합니다.")
    return {
        "삼성전자": "005930",
        "SK하이닉스": "000660"
    }

# --- [분석 로직] ---
def get_stock_score(code):
    try:
        # 1. 수급 분석 (최근 1주일)
        today = datetime.datetime.now().strftime("%Y%m%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y%m%d")
        
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
        
        # 2. 기술적 분석 (120일치 데이터)
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=120))
        if df.empty: return 0, 0, []
        
        curr = df.iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        std = df['Close'].rolling(20).std().iloc[-1]
        upper = ma20 + (std * 2)
        lower = ma20 - (std * 2)
        
        # RSI 계산
        delta = df['Close'].diff(1)
        up = delta.where(delta > 0, 0)
        down = -delta.where(delta < 0, 0)
        rsi = 100 - (100 / (1 + (up.rolling(14).mean().iloc[-1] / down.rolling(14).mean().iloc[-1])))
        
        # 채점 로직
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
    try:
        # S&P500 등락률 체크
        df = fdr.DataReader("US500", datetime.datetime.now()-datetime.timedelta(days=5))
        if not df.empty:
            chg = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100
            return f"S&P500 {chg:+.2f}%"
        return "S&P500 데이터 없음"
    except: return "시장 데이터 수집중"

# --- [메인 실행부] ---
if __name__ == "__main__":
    # GitHub 서버는 UTC 시간이므로 한국 시간(KST)으로 변환 (+9시간)
    now = datetime.datetime.now() + datetime.timedelta(hours=9)
    hour = now.hour
    
    # 여기서 파일을 읽어옵니다!
    MY_WATCHLIST = load_watchlist() 
    
    print(f"Current KST: {now}")
    print(f"Watchlist Loaded: {len(MY_WATCHLIST)} items")

    # 1. 아침 8시~9시: 장전 브리핑
    if 8 <= hour < 9:
        summary = get_market_summary()
        target_names = list(MY_WATCHLIST.keys())[:5] # 너무 길면 5개만 표시
        msg = f"🌅 [장전 브리핑] 로봇 가동 시작!\n\n📊 {summary}\n🎯 감시 대상({len(MY_WATCHLIST)}개): {', '.join(target_names)}..."
        send_msg(msg)

    # 2. 장중 (09:00 ~ 15:30): 30분 간격 감시
    elif 9 <= hour < 16:
        alerts = []
        for name, code in MY_WATCHLIST.items():
            score, price, reasons = get_stock_score(code)
            
            # 알림 조건: 75점 이상(매수) 또는 25점 이하(매도/위험)
            if score >= 75:
                alerts.append(f"🚀 [매수 포착] {name} ({score}점)\n현재가: {price:,.0f}원\n이유: {', '.join(reasons)}")
            elif score <= 25:
                alerts.append(f"📉 [위험 경고] {name} ({score}점)\n현재가: {price:,.0f}원\n이유: {', '.join(reasons)}")
        
        # 알림이 있을 때만 보냄 (알림 공해 방지)
        if alerts:
            final_msg = f"🔔 [장중 밀착 감시] 특이종목 발견!\n\n" + "\n\n".join(alerts)
            send_msg(final_msg)
        else:
            print("특이사항 없음. 알림 생략.")

    # 3. 장 마감 (16시 이후)
    elif hour >= 16:
        send_msg("☕ 오늘 장이 마감되었습니다. 수고하셨습니다!")
    
    else:
        print("장 운영 시간이 아닙니다. (새벽/밤)")
