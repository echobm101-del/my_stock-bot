import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
import json
import os
import time
import base64
import altair as alt
from pykrx import stock
import concurrent.futures
from bs4 import BeautifulSoup
import re
import feedparser
import urllib.parse
from io import StringIO
from streamlit_gsheets import GSheetsConnection

# [New] DART 라이브러리 (설치 안됐을 경우 대비)
try:
    import OpenDartReader
except ImportError:
    dart = None

# ==============================================================================
# [0. 초기화 및 세션 설정]
# ==============================================================================
if 'data_store' not in st.session_state: st.session_state['data_store'] = {"portfolio": {}, "watchlist": {}}
if 'preview_list' not in st.session_state: st.session_state['preview_list'] = []
if 'current_theme_name' not in st.session_state: st.session_state['current_theme_name'] = ""
if 'ai_cache' not in st.session_state: st.session_state['ai_cache'] = {}

# [Secrets 가져오기]
try:
    USER_GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
    USER_TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
    USER_CHAT_ID = st.secrets.get("CHAT_ID", "")
    USER_GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
    USER_NAVER_ID = st.secrets.get("NAVER_CLIENT_ID", "")
    USER_NAVER_SECRET = st.secrets.get("NAVER_CLIENT_SECRET", "")
    USER_DART_KEY = st.secrets.get("DART_API_KEY", "")
except:
    USER_GITHUB_TOKEN = ""
    USER_TELEGRAM_TOKEN = ""
    USER_CHAT_ID = ""
    USER_GOOGLE_API_KEY = ""
    USER_NAVER_ID = ""
    USER_NAVER_SECRET = ""
    USER_DART_KEY = ""

# ==============================================================================
# [1. UI 스타일링 및 설정]
# ==============================================================================
st.set_page_config(page_title="Quant Sniper V50 (Reboot)", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    .profit-positive { color: #F04452; font-weight: 800; font-size: 20px; }
    .profit-negative { color: #3182F6; font-weight: 800; font-size: 20px; }
    .status-badge { padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 700; }
    .badge-buy { background-color: #E8F3FF; color: #3182F6; }
    .badge-sell { background-color: #FFF1F1; color: #F04452; }
    .news-box { padding: 10px; border: 1px solid #eee; border-radius: 8px; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# [2. 구글 시트 DB 함수]
# ==============================================================================
def load_data_from_gsheets():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(ttl=0)
        if df.empty or 'Code' not in df.columns:
            return {"portfolio": {}, "watchlist": {}}
        
        data = {"portfolio": {}, "watchlist": {}}
        for _, row in df.iterrows():
            category = row['Type']
            name = row['Name']
            code = str(row['Code']).replace("'", "").zfill(6) # 따옴표 제거 및 6자리 맞춤
            buy_price = row.get('BuyPrice', 0)
            
            if category == "portfolio":
                data[category][name] = {"code": code, "buy_price": float(buy_price)}
            elif category == "watchlist":
                data[category][name] = {"code": code}
        return data
    except Exception as e:
        return {"portfolio": {}, "watchlist": {}}

def save_data_to_gsheets(data_store):
    try:
        rows = []
        for name, info in data_store['portfolio'].items():
            rows.append({"Type": "portfolio", "Name": name, "Code": f"'{info['code']}", "BuyPrice": info.get('buy_price', 0)})
        for name, info in data_store['watchlist'].items():
             rows.append({"Type": "watchlist", "Name": name, "Code": f"'{info['code']}", "BuyPrice": 0})
        
        df = pd.DataFrame(rows)
        conn = st.connection("gsheets", type=GSheetsConnection)
        conn.update(data=df)
        return True
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False

# 데이터 로드
if not st.session_state['data_store']['portfolio']:
    st.session_state['data_store'] = load_data_from_gsheets()

# ==============================================================================
# [3. 핵심 분석 로직 (간소화)]
# ==============================================================================
@st.cache_data(ttl=3600)
def get_stock_price(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=60))
        if df.empty: return 0, 0, pd.DataFrame()
        curr = df.iloc[-1]['Close']
        prev = df.iloc[-2]['Close']
        chg = (curr - prev) / prev * 100
        return int(curr), chg, df
    except:
        return 0, 0, pd.DataFrame()

# ==============================================================================
# [4. UI 구성]
# ==============================================================================
st.title("💎 Quant Sniper V50 (Reboot)")

tab1, tab2 = st.tabs(["💰 내 잔고 (Portfolio)", "🔍 종목 검색"])

# --- TAB 1: 포트폴리오 ---
with tab1:
    portfolio = st.session_state['data_store']['portfolio']
    if not portfolio:
        st.info("보유 종목이 없습니다. '종목 검색' 탭에서 추가해주세요.")
    
    for name, info in portfolio.items():
        price, chg, _ = get_stock_price(info['code'])
        buy_price = info['buy_price']
        profit_rate = (price - buy_price) / buy_price * 100 if buy_price > 0 else 0
        
        # 카드 UI
        p_color = "#F04452" if profit_rate > 0 else "#3182F6"
        st.markdown(f"""
        <div class='toss-card'>
            <div style='display:flex; justify-content:space-between;'>
                <div>
                    <div style='font-size:18px; font-weight:bold;'>{name}</div>
                    <div style='font-size:12px; color:#888;'>{info['code']}</div>
                </div>
                <div style='text-align:right;'>
                    <div style='font-size:18px; font-weight:bold; color:{p_color};'>{profit_rate:.2f}%</div>
                    <div style='font-size:14px;'>현재 {price:,}원</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button(f"🗑️ {name} 삭제", key=f"del_{info['code']}"):
            del st.session_state['data_store']['portfolio'][name]
            save_data_to_gsheets(st.session_state['data_store'])
            st.rerun()

# --- TAB 2: 검색 및 추가 ---
with tab2:
    col1, col2 = st.columns([3, 1])
    with col1:
        search_txt = st.text_input("종목명 또는 코드 입력 (예: 삼성전자)")
    with col2:
        st.write("")
        st.write("")
        search_btn = st.button("검색")
    
    if search_btn and search_txt:
        # KRX 전체 리스트 로딩 (캐싱)
        @st.cache_data
        def get_tickers():
            return fdr.StockListing('KRX')
        
        krx = get_tickers()
        # 종목 찾기
        res = krx[krx['Name'] == search_txt]
        if res.empty:
            res = krx[krx['Code'] == search_txt]
            
        if not res.empty:
            found_name = res.iloc[0]['Name']
            found_code = res.iloc[0]['Code']
            price, chg, _ = get_stock_price(found_code)
            
            st.success(f"🔎 {found_name} ({found_code}) 찾음! 현재가: {price:,}원")
            
            with st.form("add_form"):
                bp = st.number_input("매수 평단가 (보유중이면 입력)", value=price, step=100)
                submitted = st.form_submit_button("📥 내 잔고에 추가")
                if submitted:
                    st.session_state['data_store']['portfolio'][found_name] = {
                        "code": found_code,
                        "buy_price": bp
                    }
                    if save_data_to_gsheets(st.session_state['data_store']):
                        st.success("저장 완료!")
                        time.sleep(1)
                        st.rerun()
        else:
            st.error("종목을 찾을 수 없습니다.")
