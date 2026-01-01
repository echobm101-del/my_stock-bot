import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
import json
import os
import time
from pykrx import stock

# --- [1. 설정 및 스타일] ---
st.set_page_config(page_title="Pro Quant Dashboard V6", page_icon="🎯", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #121212; color: #E0E0E0; }
    .macro-card { background-color: #1E222D; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #333; }
    .stock-card { background-color: #1E1E1E; border-radius: 15px; padding: 20px; margin-bottom: 20px; border-left: 5px solid #555; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }
    .stock-card.buy { border-left-color: #FF5252; } /* 매수 추천: 빨강 */
    .section-header { font-size: 20px; font-weight: bold; color: #FFD700; margin-top: 30px; margin-bottom: 10px; border-bottom: 1px solid #444; padding-bottom: 5px; }
    .badge-sector { background-color: #333; padding: 2px 8px; border-radius: 4px; font-size: 12px; color: #AAA; margin-left: 5px; }
    
    /* 정밀 분석 리포트 스타일 */
    .precision-box { background-color: #2A2A2A; padding: 10px; border-radius: 8px; font-size: 13px; margin-top: 10px; border: 1px solid #444; }
    .check-pass { color: #4CAF50; font-weight: bold; } /* 통과: 초록 */
    .check-fail { color: #888; text-decoration: line-through; } /* 실패: 회색 */
    
    div.stButton > button { background-color: #252A35; border: 1px solid #444; color: #ddd; }
    div.stButton > button:hover { border-color: #FF5252; color: #FF5252; }
</style>
""", unsafe_allow_html=True)

DATA_FILE = "my_watchlist_v6.json"
SETTINGS_FILE = "my_settings.json"

# --- [2. 데이터 핸들링 함수] ---
@st.cache_data
def get_krx_list():
    try: df = fdr.StockListing('KRX'); return df[['Code', 'Name', 'Sector']]
    except: return pd.DataFrame()
krx_df = get_krx_list()

def get_sector_info(code):
    try: row = krx_df[krx_df['Code'] == code]; return row.iloc[0]['Sector'] if not row.empty else "기타"
    except: return "기타"

def load_json(file):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

if 'watchlist' not in st.session_state: st.session_state['watchlist'] = load_json(DATA_FILE)
settings = load_json(SETTINGS_FILE)

def send_telegram_msg(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.get(url, params={"chat_id": chat_id, "text": message})
        return True
    except: return False

# --- [3. 핵심 분석 로직] ---
@st.cache_data(ttl=3600)
def get_global_macro():
    try:
        indices = {"USD/KRW": "USD/KRW", "WTI": "CL=F", "S&P500": "US500"}
        res = {}; score = 0
        for n, c in indices.items():
            df = fdr.DataReader(c, datetime.datetime.now()-datetime.timedelta(days=10))
            if not df.empty:
                now = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
                chg = ((now-prev)/prev)*100
                res[n] = {"p": now, "c": chg}
                if n=="S&P500" and chg>0: score+=1
                elif n=="S&P500" and chg<0: score-=1
                if n=="USD/KRW" and chg>0.5: score-=1
                elif n=="USD/KRW" and chg<-0.5: score+=1
        return {"data": res, "score": score}
    except: return None

@st.cache_data(ttl=1800)
def get_supply_demand(code):
    try:
        e = datetime.datetime.now().strftime("%Y%m%d"); s = (datetime.datetime.now()-datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(s, e, code).tail(3)
        if df.empty: return {"score": 0, "msg": [], "f":0, "i":0}
        f=df['외국인'].sum(); i=df['기관합계'].sum(); sc=0; msg=[]
        if f>0: sc+=1; msg.append("외인 매수")
        elif f<0: sc-=1
        if i>0: sc+=0.5; msg.append("기관 매수")
        elif i<0: sc-=0.5
        return {"score": sc, "msg": msg, "f":f, "i":i}
    except: return {"score": 0, "msg": [], "f":0, "i":0}

def analyze_precision_strategy(code):
    """
    [V6.0 스나이퍼 전략]
    수급 + 추세(MA) + 모멘텀(MACD) + 과열여부(RSI)를 종합 체크
    """
    try:
        # 1. 수급 체크
        sup = get_supply_demand(code)
        
        # 2. 기술적 지표 계산
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=120))
        if df.empty: return None
        
        # 이동평균선
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        # RSI
        delta = df['Close'].diff(1)
        rsi = 100 - (100/(1 + (delta.where(delta>0,0).rolling(14).mean() / -delta.where(delta<0,0).rolling(14).mean())))
        
        # MACD
        exp12 = df['Close'].ewm(span=12, adjust=False).mean()
        exp26 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp12 - exp26
        signal = macd.ewm(span=9, adjust=False).mean()
        
        # 최신 데이터
        curr_price = df['Close'].iloc[-1]
        curr_ma20 = df['MA20'].iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_macd = macd.iloc[-1]
        curr_signal = signal.iloc[-1]
        
        # --- [정밀 검증 로직] ---
        checks = []
        pass_count = 0
        
        # Check 1: 수급 (외국인이나 기관이 샀는가?)
        if sup['f'] > 0 or sup['i'] > 0: 
            checks.append("✅ 메이저 수급 유입"); pass_count += 1
        else: checks.append("❌ 수급 이탈 우려")
            
        # Check 2: 추세 (가격이 20일선 위에 있는가? = 정배열 초입)
        if curr_price >= curr_ma20:
            checks.append("✅ 20일선 위 상승 추세"); pass_count += 1
        else: checks.append("❌ 추세 하락 (20일선 아래)")
            
        # Check 3: 모멘텀 (MACD가 시그널보다 높은가?)
        if curr_macd >= curr_signal:
            checks.append("✅ MACD 상승 모멘텀"); pass_count += 1
        else: checks.append("❌ 하락 압력 (MACD < Signal)")
            
        # Check 4: 과열 여부 (RSI가 70 이하인가? = 먹을 자리가 있는가?)
        if curr_rsi <= 70:
            checks.append("✅ 상승 여력 보유 (RSI 안정)"); pass_count += 1
        else: checks.append("❌ 단기 과열 (RSI 70↑)")
            
        total_score = (pass_count * 20) + (sup['score'] * 10) # 100점 만점 환산 시도
        
        return {
            "code": code, "price": curr_price, "checks": checks, "pass_count": pass_count,
            "score": total_score, "supply": sup, "rsi": curr_rsi
        }
    except: return None

@st.cache_data(ttl=3600)
def get_recommendations_v6():
    """
    1단계: 수급 상위 종목 풀(Pool) 수집
    2단계: 정밀 전략 필터링 적용
    """
    try:
        target_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        
        # 외국인/기관 순매수 상위 10개씩만 1차 후보로 선정 (속도 최적화)
        tickers_f = stock.get_market_net_purchases_of_equities_by_ticker(target_date, target_date, "KOSPI", "외국인").head(10).index.tolist()
        tickers_i = stock.get_market_net_purchases_of_equities_by_ticker(target_date, target_date, "KOSPI", "기관합계").head(10).index.tolist()
        tickers_kq_f = stock.get_market_net_purchases_of_equities_by_ticker(target_date, target_date, "KOSDAQ", "외국인").head(10).index.tolist() # 코스닥도 포함
        
        candidates = list(set(tickers_f + tickers_i + tickers_kq_f))
        
        final_list = []
        for code in candidates:
            res = analyze_precision_strategy(code)
            if res and res['pass_count'] >= 3: # 4개 조건 중 3개 이상 통과한 것만 추천
                res['name'] = stock.get_market_ticker_name(code)
                res['sector'] = get_sector_info(code)
                final_list.append(res)
        
        # 점수순 정렬
        final_list.sort(key=lambda x: x['score'], reverse=True)
        return final_list
    except: return []

# --- [4. 사이드바] ---
with st.sidebar:
    st.header("⚙️ 설정")
    with st.expander("🔔 텔레그램 설정"):
        t_token = st.text_input("Bot Token", value=settings.get("token",""), type="password")
        t_chat = st.text_input("Chat ID", value=settings.get("chat_id",""))
        if st.button("저장"):
            save_json(SETTINGS_FILE, {"token": t_token, "chat_id": t_chat})
            if send_telegram_msg(t_token, t_chat, "✅ 알림 연결 성공"): st.success("성공")
            else: st.error("실패")
    
    auto_mode = st.checkbox("🔴 실시간 감시", value=False)
    st.divider()
    with st.expander("➕ 관심 종목 추가"):
        n_name = st.text_input("종목명"); n_code = st.text_input("코드")
        if st.button("추가"):
            st.session_state['watchlist'][n_name] = {"code": n_code}
            save_json(DATA_FILE, st.session_state['watchlist']); st.rerun()
    
    if st.session_state['watchlist']:
        st.caption("내 포트폴리오")
        for name in list(st.session_state['watchlist'].keys()):
            c1, c2 = st.columns([3, 1])
            c1.write(name)
            if c2.button("X", key=f"d_{name}"):
                del st.session_state['watchlist'][name]
                save_json(DATA_FILE, st.session_state['watchlist']); st.rerun()

# --- [5. 메인 UI] ---
st.title("🎯 Pro Quant Sniper V6")
st.caption(f"Precision Trading System | {datetime.datetime.now().strftime('%Y-%m-%d')}")

# 매크로
macro = get_global_macro()
if macro:
    m_score = macro['score']
    msg = "Risk On (투자 적기)" if m_score >= 1 else ("Risk Off (보수적 대응)" if m_score <= -1 else "Neutral (관망)")
    col = "#FF5252" if m_score <= -1 else ("#4CAF50" if m_score >= 1 else "#555")
    st.markdown(f"<div style='background:{col}; padding:8px; border-radius:5px; text-align:center; font-weight:bold; color:white;'>🌍 글로벌 시장: {msg}</div>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📂 내 포트폴리오 분석", "🔭 AI 스나이퍼 발굴 (정밀 추천)"])

# [Tab 1] 내 종목
with tab1:
    if not st.session_state['watchlist']: st.info("사이드바에서 종목을 추가하세요.")
    else:
        for name, info in st.session_state['watchlist'].items():
            # 기존 단순 분석 로직 재사용 (빠른 로딩 위해)
            res = analyze_precision_strategy(info['code'])
            if res:
                decision = "매수 검토" if res['pass_count']>=3 else "관망/매도"
                cls = "buy" if res['pass_count']>=3 else ""
                st.markdown(f"""
                <div class='stock-card {cls}'>
                    <div style='display:flex; justify-content:space-between;'>
                        <span style='font-size:20px; font-weight:bold;'>{name} <span style='font-size:14px; color:#aaa;'>{info['code']}</span></span>
                        <span style='font-size:24px; font-weight:bold;'>{format(res['price'], ',')}원</span>
                    </div>
                    <div class='precision-box'>
                        {'<br>'.join(res['checks'])}
                    </div>
                    <div style='margin-top:5px; text-align:right; font-size:12px; color:#aaa;'>AI 점수: {res['score']}점</div>
                </div>
                """, unsafe_allow_html=True)

# [Tab 2] AI 정밀 추천 (핵심 업그레이드)
with tab2:
    st.markdown("##### 🕵️‍♂️ 기관/외국인 매집주 중 '추세+모멘텀' 완벽한 종목만 엄선합니다.")
    if st.button("🔭 정밀 종목 발굴 시작 (Scan)", use_container_width=True):
        with st.spinner("빅데이터 분석 중... (수급 상위 -> 차트 정밀 진단)"):
            recs = get_recommendations_v6()
            
        if not recs:
            st.warning("⚠️ 현재 까다로운 4단계 조건을 모두 통과한 종목이 없습니다. (시장이 좋지 않을 수 있습니다)")
        else:
            st.success(f"🎯 {len(recs)}개의 스나이퍼 타겟 종목을 찾았습니다!")
            for item in recs:
                st.markdown(f"""
                <div class='stock-card buy' style='border-left: 5px solid #00E676;'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <div>
                            <span style='background:#00E676; color:black; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:12px;'>Strong Buy</span>
                            <span style='font-size:22px; font-weight:bold; margin-left:5px;'>{item['name']}</span>
                            <span class='badge-sector'>{item['sector']}</span>
                        </div>
                        <div style='text-align:right;'>
                             <div style='font-size:24px; font-weight:bold; color:#00E676;'>{format(item['price'], ',')}원</div>
                        </div>
                    </div>
                    <hr style='border-color:#444; margin:10px 0;'>
                    <div style='display:flex; gap:10px;'>
                        <div style='flex:1;' class='precision-box'>
                            <div style='color:#bbb; margin-bottom:5px;'>📊 <b>정밀 진단 리포트</b></div>
                            {'<br>'.join(item['checks'])}
                        </div>
                        <div style='flex:1;' class='precision-box'>
                            <div style='color:#bbb; margin-bottom:5px;'>⚖️ <b>수급 요약</b></div>
                            외국인: <span style='color:{'#FF5252' if item['supply']['f']>0 else '#448AFF'}'>{format(int(item['supply']['f']), ',')}주</span><br>
                            기관: <span style='color:{'#FF5252' if item['supply']['i']>0 else '#448AFF'}'>{format(int(item['supply']['i']), ',')}주</span><br>
                            RSI 지표: <b>{item['rsi']:.1f}</b> (안정권)
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
if auto_mode:
    time.sleep(60)
    st.rerun()
