import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
from bs4 import BeautifulSoup
import json
import os
import time
from pykrx import stock

# --- [1. 설정 및 UI 스타일링] ---
st.set_page_config(page_title="Pro Quant V7.4", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #F0F2F6; font-family: 'Pretendard', sans-serif; }
    .glass-card {
        background: rgba(38, 39, 48, 0.6);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    }
    .border-buy { border-left: 5px solid #00E676 !important; }
    .border-sell { border-left: 5px solid #FF5252 !important; }
    .big-price { font-size: 32px; font-weight: 800; letter-spacing: -1px; }
    .stock-name { font-size: 22px; font-weight: 700; color: #FFFFFF; }
    .stock-code { font-size: 14px; color: #888; margin-left: 8px; font-weight: 400; }
    .text-up { color: #00E676; }
    .text-down { color: #FF5252; }
    .text-gray { color: #888; }
    .badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; display: inline-block; margin-right: 5px; }
    .badge-sector { background: #333; color: #ccc; border: 1px solid #444; }
    .badge-buy { background: rgba(0, 230, 118, 0.2); color: #00E676; border: 1px solid #00E676; }
    .macro-box { background: #1A1C24; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #333; }
    .macro-label { font-size: 12px; color: #888; text-transform: uppercase; margin-bottom: 5px; }
    .macro-val { font-size: 20px; font-weight: 700; color: #fff; }
    .analysis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px; background: rgba(0,0,0,0.2); padding: 15px; border-radius: 12px; }
    .check-item { font-size: 13px; margin-bottom: 4px; display: flex; align-items: center; color: #ddd; }
    .score-bg { background: #333; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 8px; }
    .score-fill { height: 100%; border-radius: 3px; }
    div.stButton > button { width: 100%; border-radius: 10px; font-weight: bold; border: 1px solid #444; background: #1E222D; color: white; }
    div.stButton > button:hover { border-color: #00E676; color: #00E676; }
</style>
""", unsafe_allow_html=True)

DATA_FILE = "my_watchlist_v7.json"
SETTINGS_FILE = "my_settings.json"

# --- [2. 데이터 핸들링] ---
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
if 'sent_alerts' not in st.session_state: st.session_state['sent_alerts'] = {}

def send_telegram_msg(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.get(url, params={"chat_id": chat_id, "text": message})
        return True
    except: return False

# --- [3. HTML 생성 헬퍼 함수 (에러 방지용)] ---
def create_card_html(item, sector, is_recomm=False):
    """복잡한 HTML 문자열을 여기서 안전하게 생성합니다."""
    border_cls = "border-buy" if item['pass'] >= 3 else ("border-sell" if item['pass'] <= 1 else "")
    if is_recomm: border_cls = "border-buy"
    
    p_color = "text-up" if item['pass'] >= 3 else ("text-down" if item['pass'] <= 1 else "text-gray")
    if is_recomm: p_color = "text-up"
    
    score_color = "#00E676" if item['score'] >= 75 else ("#FF5252" if item['score'] <= 25 else "#FFD700")
    
    checks_html = "".join([f"<div class='check-item'>{c}</div>" for c in item['checks']])
    
    supply_f = format(int(item['supply']['f']), ',')
    supply_i = format(int(item['supply']['i']), ',')
    supply_f_col = '#00E676' if item['supply']['f']>0 else '#FF5252'
    supply_i_col = '#00E676' if item['supply']['i']>0 else '#FF5252'
    price_fmt = format(item['price'], ',')
    
    badge_html = f"<span class='badge badge-sector'>{sector}</span>"
    if is_recomm: badge_html = "<span class='badge badge-buy'>STRONG BUY</span>" + badge_html
    
    html = f"""
    <div class='glass-card {border_cls}'>
        <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
            <div>
                {badge_html}
                <div style='margin-top:8px;'>
                    <span class='stock-name'>{item.get('name', 'Unknown')}</span>
                    <span class='stock-code'>{item['code']}</span>
                </div>
                <div class='big-price {p_color}'>{price_fmt}원</div>
            </div>
            <div style='text-align:right; width: 120px;'>
                <div style='font-size:12px; color:#888;'>AI SCORE</div>
                <div style='font-size:24px; font-weight:bold; color:{score_color};'>{item['score']}</div>
                <div class='score-bg'><div class='score-fill' style='width:{item['score']}%; background:{score_color};'></div></div>
            </div>
        </div>
        <div class='analysis-grid'>
            <div>
                <div style='color:#888; font-size:12px; margin-bottom:5px;'>CHECK POINTS</div>
                {checks_html}
            </div>
            <div>
                <div style='color:#888; font-size:12px; margin-bottom:5px;'>SUPPLY & TECH</div>
                <div class='check-item'>외국인: <span style='margin-left:auto; color:{supply_f_col}'>{supply_f}</span></div>
                <div class='check-item'>기관: <span style='margin-left:auto; color:{supply_i_col}'>{supply_i}</span></div>
                <div class='check-item'>RSI (14): <span style='margin-left:auto;'>{item['rsi']:.1f}</span></div>
            </div>
        </div>
    </div>
    """
    return html

# --- [4. 분석 로직] ---
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
        if df.empty: return {"score": 0, "f":0, "i":0}
        f=df['외국인'].sum(); i=df['기관합계'].sum(); sc=0
        if f>0: sc+=1
        elif f<0: sc-=1
        if i>0: sc+=0.5
        elif i<0: sc-=0.5
        return {"score": sc, "f":f, "i":i}
    except: return {"score": 0, "f":0, "i":0}

def analyze_precision(code, name_override=None):
    try:
        sup = get_supply_demand(code)
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=120))
        if df.empty: return None
        
        df['MA20'] = df['Close'].rolling(20).mean()
        delta = df['Close'].diff(1)
        rsi = 100 - (100/(1 + (delta.where(delta>0,0).rolling(14).mean() / -delta.where(delta<0,0).rolling(14).mean())))
        curr = df.iloc[-1]
        
        checks = []
        pass_cnt = 0
        
        if sup['f'] > 0 or sup['i'] > 0: checks.append("✅ 메이저 수급 유입"); pass_cnt+=1
        else: checks.append("❌ 수급 이탈");
        
        if curr['Close'] >= curr['MA20']: checks.append("✅ 20일선 위 상승추세"); pass_cnt+=1
        else: checks.append("❌ 추세 하락세");
        
        # 가격 부담 체크 (단순 이격도)
        if curr['Close'] <= df['MA20'].iloc[-1] * 1.15: checks.append("✅ 가격 부담 없음"); pass_cnt+=1
        else: checks.append("❌ 단기 급등 부담");
            
        if rsi.iloc[-1] <= 70: checks.append("✅ RSI 안정권"); pass_cnt+=1
        else: checks.append("❌ 과매수 구간");
        
        score = (pass_cnt * 25)
        
        return {
            "name": name_override,
            "code": code, "price": curr['Close'], "checks": checks, "pass": pass_cnt, 
            "score": score, "supply": sup, "rsi": rsi.iloc[-1]
        }
    except: return None

@st.cache_data(ttl=3600)
def get_recommendations():
    try:
        t = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        f_list = stock.get_market_net_purchases_of_equities_by_ticker(t, t, "KOSPI", "외국인").head(10).index.tolist()
        i_list = stock.get_market_net_purchases_of_equities_by_ticker(t, t, "KOSPI", "기관합계").head(10).index.tolist()
        candidates = list(set(f_list + i_list))
        
        res_list = []
        for c in candidates:
            name = stock.get_market_ticker_name(c)
            a = analyze_precision(c, name_override=name)
            if a and a['pass'] >= 3:
                a['sector'] = get_sector_info(c)
                res_list.append(a)
        res_list.sort(key=lambda x: x['score'], reverse=True)
        return res_list
    except: return []

# --- [5. UI 렌더링] ---
with st.sidebar:
    st.header("⚡ CONTROL")
    
    with st.expander("🔔 알림 설정", expanded=False):
        t_token = st.text_input("Bot Token", value=settings.get("token", ""), type="password")
        t_chat = st.text_input("Chat ID", value=settings.get("chat_id", ""))
        
        if st.button("저장 및 테스트 발송"):
            save_json(SETTINGS_FILE, {"token": t_token, "chat_id": t_chat})
            if t_token and t_chat:
                if send_telegram_msg(t_token, t_chat, "🚀 [PRO QUANT] 알림 봇 정상 작동중!"):
                    st.success("전송 성공!")
                else: st.error("전송 실패")
            else: st.warning("정보를 입력하세요")

    auto_mode = st.checkbox("🔴 실시간 자동 감시", value=False)
    
    st.divider()
    with st.expander("➕ 종목 추가", expanded=True):
        n_name = st.text_input("종목명")
        n_code = st.text_input("코드")
        if st.button("Add"):
            st.session_state['watchlist'][n_name] = {"code": n_code}
            save_json(DATA_FILE, st.session_state['watchlist']); st.rerun()

    if st.session_state['watchlist']:
        st.caption("WATCHLIST")
        for name in list(st.session_state['watchlist'].keys()):
            c1, c2 = st.columns([3,1])
            c1.markdown(f"<span style='color:#ddd'>{name}</span>", unsafe_allow_html=True)
            if c2.button("✕", key=f"del_{name}"):
                del st.session_state['watchlist'][name]
                save_json(DATA_FILE, st.session_state['watchlist']); st.rerun()

st.title("⚡ QUANT SNIPER V7.4")
st.caption(f"Stable High-Precision Dashboard | {datetime.datetime.now().strftime('%Y-%m-%d')}")

# 매크로
macro = get_global_macro()
if macro:
    col1, col2, col3, col4 = st.columns(4)
    m_data = macro['data']
    with col1:
        st.markdown(f"<div class='macro-box'><div class='macro-label'>MARKET SCORE</div><div class='macro-val' style='color:{'#00E676' if macro['score']>=1 else '#FF5252'}'>{macro['score']}</div></div>", unsafe_allow_html=True)
    with col2:
        c_col = "text-up" if m_data['S&P500']['c'] > 0 else "text-down"
        st.markdown(f"<div class='macro-box'><div class='macro-label'>🇺🇸 S&P 500</div><div class='macro-val {c_col}'>{m_data['S&P500']['c']:.2f}%</div></div>", unsafe_allow_html=True)
    with col3:
        c_col = "text-up" if m_data['USD/KRW']['c'] > 0 else "text-down"
        st.markdown(f"<div class='macro-box'><div class='macro-label'>🇰🇷 USD/KRW</div><div class='macro-val {c_col}'>{format(m_data['USD/KRW']['p'], ',.0f')}</div></div>", unsafe_allow_html=True)
    with col4:
        c_col = "text-up" if m_data['WTI']['c'] > 0 else "text-down"
        st.markdown(f"<div class='macro-box'><div class='macro-label'>🛢️ WTI CRUDE</div><div class='macro-val {c_col}'>${m_data['WTI']['p']:.1f}</div></div>", unsafe_allow_html=True)

st.write("")
tab1, tab2 = st.tabs(["📂 포트폴리오", "🚀 AI 스나이퍼 발굴"])

with tab1:
    if not st.session_state['watchlist']: st.info("사이드바에서 종목을 추가하세요.")
    else:
        for name, info in st.session_state['watchlist'].items():
            res = analyze_precision(info['code'], name_override=name)
            if res:
                # 에러 원인이었던 HTML 생성을 함수로 분리하여 호출
                card_html = create_card_html(res, get_sector_info(res['code']), is_recomm=False)
                st.markdown(card_html, unsafe_allow_html=True)
                
                # 자동 알림
                if auto_mode and t_token and t_chat:
                    today = datetime.datetime.now().strftime("%Y%m%d")
                    reasons_txt = "\n".join(res['checks'])
                    price_fmt = format(res['price'], ',')
                    
                    if res['score'] >= 75:
                        msg_key = f"{info['code']}_buy_{today}"
                        if st.session_state['sent_alerts'].get(msg_key) != "sent":
                            msg = f"🚀 [AI 매수] {name}\n가격: {price_fmt}원\n점수: {res['score']}점\n\n[근거]\n{reasons_txt}"
                            if send_telegram_msg(t_token, t_chat, msg):
                                st.session_state['sent_alerts'][msg_key] = "sent"
                                
                    elif res['score'] <= 25:
                        msg_key = f"{info['code']}_sell_{today}"
                        if st.session_state['sent_alerts'].get(msg_key) != "sent":
                            msg = f"📉 [AI 매도] {name}\n가격: {price_fmt}원\n점수: {res['score']}점\n\n[근거]\n{reasons_txt}"
                            if send_telegram_msg(t_token, t_chat, msg):
                                st.session_state['sent_alerts'][msg_key] = "sent"

with tab2:
    if st.button("🔭 START SCANNING", use_container_width=True):
        with st.spinner("AI 분석중..."):
            recs = get_recommendations()
            
        if not recs:
            st.warning("조건을 만족하는 종목이 없습니다.")
        else:
            st.success(f"{len(recs)}개의 타겟 발견!")
            for item in recs:
                # 에러 원인이었던 HTML 생성을 함수로 분리하여 호출
                card_html = create_card_html(item, item['sector'], is_recomm=True)
                st.markdown(card_html, unsafe_allow_html=True)

if auto_mode:
    time.sleep(60)
    st.rerun()
