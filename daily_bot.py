import os
import datetime
import requests
import FinanceDataReader as fdr
from pykrx import stock
import sys

# --- [설정: GitHub Secrets에서 가져옴] ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_msg(msg):
    if not TOKEN or not CHAT_ID:
        print("텔레그램 토큰이 없습니다. GitHub Secrets를 확인하세요.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.get(url, params={"chat_id": CHAT_ID, "text": msg})

# --- [분석 로직] ---
def get_market_score():
    try:
        # 미국장, 환율, 유가, 금리, VIX
        indices = {"S&P500": "US500", "USD/KRW": "USD/KRW", "VIX": "^VIX", "US 10Y": "^TNX"}
        score = 0
        summary = ""
        
        for name, code in indices.items():
            df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=10))
            if not df.empty:
                now = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2]
                chg = ((now - prev) / prev) * 100
                summary += f"- {name}: {now:,.2f} ({chg:+.2f}%)\n"
                
                # 점수 계산
                if name == "S&P500" and chg > 0: score += 1
                elif name == "S&P500" and chg < 0: score -= 1
                elif name == "USD/KRW": score += -1 if chg > 0.5 else (1 if chg < -0.5 else 0)
                elif name == "VIX": score += -2 if now > 20 else (1 if now < 15 else 0)
                elif name == "US 10Y": score += -1 if chg > 1.0 else (1 if chg < -1.0 else 0)
                
        return score, summary
    except Exception as e:
        return 0, f"데이터 수집 에러: {e}"

def get_best_stocks():
    try:
        # 어제 날짜 기준 수급 상위
        t = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        # 오늘이 월요일이면 금요일 데이터(3일 전) 사용 등 처리가 필요하나, 간단히 최근 데이터 조회
        # pykrx는 휴일이면 직전 평일 데이터를 줌
        
        candidates = stock.get_market_net_purchases_of_equities_by_ticker(t, t, "KOSPI", "외국인").head(5).index.tolist()
        best_picks = []
        
        for code in candidates:
            # 간단 분석 (RSI + 수급)
            df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=60))
            if df.empty: continue
            
            delta = df['Close'].diff(1)
            rsi = 100 - (100/(1 + (delta.where(delta>0,0).rolling(14).mean() / -delta.where(delta<0,0).rolling(14).mean()))).iloc[-1]
            
            name = stock.get_market_ticker_name(code)
            if rsi <= 70: # 과열 아님
                best_picks.append(f"🚀 {name} (RSI {rsi:.1f})")
        
        return best_picks
    except:
        return []

# --- [메인 실행] ---
if __name__ == "__main__":
    # 한국 시간 기준 현재 시각
    now = datetime.datetime.now() + datetime.timedelta(hours=9) # GitHub 서버는 UTC이므로 +9시간
    print(f"Current KST: {now}")

    # 1. 아침 브리핑 (오전 8시~9시 사이 실행 시)
    if 8 <= now.hour < 10:
        score, summary = get_market_score()
        opinion = "Risk On (투자 적기)" if score >= 1 else ("Risk Off (관망 필요)" if score <= -1 else "중립 (Neutral)")
        msg = f"🌅 [굿모닝 퀀트 브리핑]\n\n📊 시장 점수: {score}점\n💡 의견: {opinion}\n\n[주요 지표]\n{summary}"
        send_msg(msg)
        print("Morning briefing sent.")

    # 2. 마감 추천 (오후 3시~4시 사이 실행 시)
    elif 15 <= now.hour < 17:
        picks = get_best_stocks()
        if picks:
            msg = f"☕ [마감 전 AI 추천]\n오늘의 수급 주도주 Top Picks:\n\n" + "\n".join(picks)
            send_msg(msg)
        else:
            send_msg("☕ [마감 전 AI 추천]\n오늘은 뚜렷한 매수 신호 종목이 없습니다.")
        print("Afternoon briefing sent.")
        
    else:
        print("No scheduled task for this time.")
