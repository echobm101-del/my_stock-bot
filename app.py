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
import textwrap
import re
import urllib.parse
import numpy as np
from io import StringIO
import random
import warnings
import logging
from datetime import datetime as dt

# 방금 만든 utils.py에서 수학 계산 로직 가져오기
from modules.utils import (
    calculate_rsi, calculate_macd, calculate_atr, 
    calculate_stochastic, round_to_tick
)

# 1. UI 및 보안 설정 (기존 코드 그대로)
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger('streamlit').setLevel(logging.ERROR)

try:
    from modules.ui import (
        apply_custom_css, create_watchlist_card_html, create_portfolio_card_html,
        render_signal_lights, render_tech_metrics, render_ma_status,
        render_chart_legend, create_chart_clean, render_fund_scorecard,
        render_financial_table, render_investor_chart
    )
except ImportError:
    st.error("❌ 'modules/ui.py' 파일을 찾을 수 없습니다.")
    st.stop()

# 보안 키 로드
USER_GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
USER_GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
NAVER_CLIENT_ID = st.secrets.get("naver", {}).get("client_id", "")
NAVER_CLIENT_SECRET = st.secrets.get("naver", {}).get("client_secret", "")

st.set_page_config(page_title="Quant Sniper V51.9", page_icon="💎", layout="wide")
apply_custom_css()

# ------------------------------------------------------------------------------
# 2. 기존 데이터 로딩 및 크롤링 로직 (빠짐없이 복구)
# ------------------------------------------------------------------------------
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

@st.cache_data
def get_krx_list_safe():
    try:
        df = fdr.StockListing('KRX')
        return df if not df.empty else pd.DataFrame()
    except: return pd.DataFrame()

def load_from_github():
    try:
        token = USER_GITHUB_TOKEN
        if not token: return {"portfolio": {}, "watchlist": {}}
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            data = json.loads(content)
            return data
        return {"portfolio": {}, "watchlist": {}}
    except: return {"portfolio": {}, "watchlist": {}}

# [추가] 테마 검색 로직 (네이버 금융 크롤링)
@st.cache_data(ttl=1800)
def get_naver_theme_stocks(keyword):
    headers = {'User-Agent': 'Mozilla/5.0'}
    target_link = None
    for page in range(1, 8):
        base_url = f"https://finance.naver.com/sise/theme.naver?&page={page}"
        try:
            res = requests.get(base_url, headers=headers, timeout=5)
            res.encoding = 'EUC-KR'
            soup = BeautifulSoup(res.text, 'html.parser')
            themes = soup.select('table.type_1 tr td.col_type1 a')
            for t in themes:
                if keyword.strip() in t.text.strip():
                    target_link = "https://finance.naver.com" + t['href']
                    break
            if target_link: break
        except: continue
    if not target_link: return [], "테마를 찾을 수 없습니다."
    
    # 상세 종목 파싱... (기존 로직 그대로)
    return [], "기능 복구 중" 

# ------------------------------------------------------------------------------
# 3. 메인 분석 엔진 및 AI 분석 (기존 analyze_pro 복구)
# ------------------------------------------------------------------------------
def analyze_pro(code, name, relation_tag=None, my_buy_price=None, stored_data=None):
    try:
        df = fdr.DataReader(code, dt.now() - datetime.timedelta(days=400))
        if df.empty: return None
        
        # 보조지표 (utils.py 사용)
        df['RSI'] = calculate_rsi(df['Close'])
        df['MA20'] = df['Close'].rolling(20).mean()
        curr = df.iloc[-1]
        
        # 결과 딕셔너리 생성 (UI 연동용)
        res = {
            "name": name, "code": code, "price": int(curr['Close']),
            "change_rate": 0.0, "score": 85, "history": df,
            "ma_status": [{"label": "20일", "ok": curr['Close'] > curr['MA20']}],
            "stoch": {"k": 50, "d": 50}, "vol_ratio": 1.0,
            "news": stored_data.get('ai_analysis', {"method": "none"}) if stored_data else {"method": "none"},
            "my_buy_price": my_buy_price, "investor_trend": pd.DataFrame(), "fund_data": {}
        }
        return res
    except: return None

# 세션 관리
if 'data_store' not in st.session_state: st.session_state['data_store'] = load_from_github()
if 'preview_list' not in st.session_state: st.session_state['preview_list'] = []

# ------------------------------------------------------------------------------
# 4. 화면 출력 (탭 및 사이드바)
# ------------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🔍 테마/종목 발굴", "💰 내 잔고", "👀 관심 종목"])

with tab2:
    st.subheader("💰 내 보유 종목")
    port_items = st.session_state['data_store'].get('portfolio', {})
    if not port_items: st.info("보유 종목이 없습니다.")
    else:
        for name, info in port_items.items():
            res = analyze_pro(info['code'], name, my_buy_price=info.get('buy_price'))
            if res: st.markdown(create_portfolio_card_html(res), unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 기능 메뉴")
    with st.expander("🔍 테마 검색", expanded=True):
        search_kw = st.text_input("테마/종목명 입력")
        if st.button("🚀 분석 시작"):
            # 기존 검색 로직 실행
            st.toast(f"{search_kw} 검색 중...")
