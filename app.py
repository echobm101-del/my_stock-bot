import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
import json
import os
import time
from pykrx import stock
import concurrent.futures

# --- [1. 설정 및 UI 스타일링] ---
st.set_page_config(page_title="Pro Quant V11.4", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #F0F2F6; font-family: 'Pretendard', sans-serif; }
    
    /* 카드 스타일 */
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
    
    /* 텍스트 색상 */
    .text-up { color: #00E676; }
    .text-down { color: #FF5252; }
    .text-gray { color: #888; }
    .big-price { font-size: 32px; font-weight: 800; letter-spacing: -1px; }
    .stock-name { font-size: 22px; font-weight: 700; color: #FFFFFF; }
    .stock-code { font-size: 14px; color: #888; margin-left: 8px; font-weight: 400; }
    
    /* 매크로 박스 */
    .macro-box { background: #1A1C24; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #333; height: 100%; }
    .macro-label { font-size: 11px; color: #888; text-transform: uppercase; margin-bottom: 8px; font-weight: bold; }
    .macro-val { font-size: 20px; font-weight: 800; color: #fff; margin-bottom: 8px; }
    
    /* 상태 뱃지 */
    .status-badge { font-size: 12px; font-weight: bold; padding: 4px 8px; border-radius: 6px; display: inline-block; width: 100%; }
    .status-good { background-color: rgba(0, 230, 118, 0.15); color: #00E676; border: 1px solid rgba(0, 230, 118, 0.3); }
    .status-bad { background-color: rgba(255, 82, 82, 0.15); color: #FF5252; border: 1px solid rgba(255, 82, 82, 0.3); }
    .status-neutral { background-color: rgba(136, 136, 136, 0.15); color: #aaa; border: 1px solid rgba(136, 136, 136, 0.3); }

    .check-item { font-size: 13px; margin-bottom: 4px; display: flex; align-items: center; color: #ddd; }
    .score-bg { background: #333; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 8px; }
    .score-fill { height: 100%; border-radius: 3px; }
    
    /* [수정] 범례 테이블 스타일 및 Expander 배경 이슈 해결 */
    .streamlit-expanderContent {
        background-color: #1A1C24 !important;
        color: #F0F2F6 !important;
        border-radius: 10px;
    }
    .legend-table { width: 100%; font-size: 14px; border-collapse: collapse; margin-top: 5px; }
    .legend-table td { padding: 12px; border-bottom: 1px solid #444; color: #ddd; vertical-align: middle; line-height: 1.5; }
    .legend-header { font-weight: bold; color: #FFD700; background-color: #262730; text-align: center; padding: 10px; border-radius: 5px; }
    .legend-title { font-weight: bold; color: #fff; width: 150px; background-color: #222; padding-left: 10px; border-radius: 4px; }
    
    .badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; display: inline-block; margin-right: 5px; }
    .badge-sector { background: #333; color: #ccc; border: 1px solid #444; }
    .badge-buy { background: rgba(0, 230, 118, 0.2); color: #00E676; border: 1px solid #00E676; }
    
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
        try:
            with open(file, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

if 'watchlist' not in st.session_state: st.session_state['watchlist'] = load_json(DATA_FILE)
settings = load_json(SETTINGS_FILE)
if 'sent_alerts' not in st.session_state: st.session_state['sent_alerts'] = {}
if 'routine_flags' not in st.session_state: st.session_state['routine_flags'] = {}

def send_telegram_msg(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.get(url, params={"chat_id": chat_id, "text": message})
        return True
    except: return False

# --- [3. HTML 생성 헬퍼] ---
def create_card_html(item, sector, is_recomm=False):
    if not item: return ""
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
                <div class='check-item'>볼린저: <span style='margin-left:auto;'>{item['bb_status']}</span></div>
            </div>
        </div>
    </div>
    """
    return html

# --- [4. 분석 로직] ---
@st.cache_data(ttl=3600)
def get_global_macro():
    try:
        indices = {
            "USD/KRW": "USD/KRW", 
            "WTI": "CL=F", 
            "S&P500": "US500", 
            "US 10Y": "^TNX",
            "VIX": "^VIX"
        }
        res = {}; score = 0
        
        for n, c in indices.items():
            df = fdr.DataReader(c, datetime.datetime.now()-datetime.timedelta(days=10))
            if not df.empty:
                now = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
                chg = ((now-prev)/prev)*100
                res[n] = {"p": now, "c": chg}
                if n=="S&P500": 
                    if chg>0: score+=1
                    elif chg<0: score-=1
                elif n=="USD/KRW":
                    if chg>0.5: score-=1
                    elif chg<-0.5: score+=1
                elif n=="US 10Y":
                    if chg
