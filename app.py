import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
import json
import os
import time
import base64
import concurrent.futures
from bs4 import BeautifulSoup
from io import StringIO
import numpy as np
import warnings
import re
import urllib.parse
from datetime import datetime as dt

# 방금 만드신 utils.py와 기존 ui.py에서 기능 가져오기
from modules.utils import calculate_rsi, calculate_macd, calculate_atr, calculate_stochastic, round_to_tick

try:
    from modules.ui import (
        apply_custom_css, create_watchlist_card_html, create_portfolio_card_html,
        render_tech_metrics, create_chart_clean, render_chart_legend,
        render_fund_scorecard, render_investor_chart, render_ma_status, render_financial_table
    )
    apply_custom_css()
except:
    st.error("❌ 'modules/ui.py' 파일을 찾을 수 없습니다. 깃허브 구성을 확인해주세요.")
    st.stop()

# 기초 설정
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Quant Sniper V51.9 Final", page_icon="💎", layout="wide")

# ------------------------------------------------------------------------------
# [1. 환경 설정 및 데이터 로딩]
# ------------------------------------------------------------------------------
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"
USER_GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
USER_GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")

@st.cache_data(ttl=3600)
def get_krx_list_safe():
    try:
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name']] if not df.empty else pd.DataFrame()
    except: return pd.DataFrame()

def load_from_github():
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {USER_GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            return json.loads(content)
        return {"portfolio": {}, "watchlist": {}}
    except: return {"portfolio": {}, "watchlist": {}}

def update_github_file(new_data):
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {USER_GITHUB_TOKEN}"}
        r_get = requests.get(url, headers=headers)
        sha = r_get.json().get('sha') if r_get.status_code == 200 else None
        json_str = json.dumps(new_data, ensure_ascii=False, indent=4)
        b64_content = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        data = {"message": "Update via App", "content": b64_content, "sha": sha} if sha else {"message": "Create", "content": b64_content}
        requests.put(url, headers=headers, json=data)
        return True
    except: return False

# ------------------------------------------------------------------------------
# [2. 분석 핵심 로직 (Sniper Score & AI)]
# ------------------------------------------------------------------------------
def analyze_pro(code, name, buy_price=None, stored_data=None):
    try:
        df = fdr.DataReader(code, dt.now() - datetime.timedelta(days=365))
        if df.empty or len(df) < 60: return None
        
        # 보조지표 계산 (utils.py 활용)
        df['RSI'] = calculate_rsi(df['Close'])
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        curr = df.iloc[-1]
        score = 70 # 기본 점수 (기존 복잡한 스코어 로직 생략 시)
        
        # UI에서 필요한 형식으로 데이터 정리
        res = {
            "name": name, "code": code, "price": int(curr['Close']),
            "change_rate": round(((curr['Close'] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100, 2),
            "score": score, "history": df, "vol_ratio": 1.0,
            "ma_status": [{"label": "5일", "ok": curr['Close'] > curr['MA5']}, {"label": "20일", "ok": curr['Close'] > curr['MA20']}],
            "stoch": {"k": 50, "d": 50}, "fund_data": {}, "investor_trend": pd.DataFrame(),
            "news": stored_data.get('ai_analysis', {"method": "none"}) if stored_data else {"method": "none"},
            "my_buy_price": buy_price
        }
        return res
    except: return None

# 세션 관리
if 'data_store' not in st.session_state: st.session_state['data_store'] = load_from_github()
if 'preview_list' not in st.session_state: st.session_state['preview_list'] = []
krx_df = get_krx_list_safe()

# ------------------------------------------------------------------------------
# [3. 메인 화면 및 탭]
# ------------------------------------------------------------------------------
st.title("💎 Quant Sniper V51.9")
tab1, tab2, tab3 = st.tabs(["🔍 테마/종목 발굴", "💰 내 잔고 (Portfolio)", "👀 관심 종목 (Watchlist)"])

with tab1:
    if st.session_state['preview_list']:
        for item in st.session_state['preview_list']:
            res = analyze_pro(item['code'], item['name'])
            if res: st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
    else: st.info("사이드바에서 검색을 시작하세요.")

with tab2:
    port = st.session_state['data_store'].get('portfolio', {})
    if not port: st.info("보유 종목이 없습니다.")
    else:
        for name, info in port.items():
            res = analyze_pro(info['code'], name, buy_price=info.get('buy_price'))
            if res: st.markdown(create_portfolio_card_html(res), unsafe_allow_html=True)

with tab3:
    wl = st.session_state['data_store'].get('watchlist', {})
    if not wl: st.info("관심 종목이 없습니다.")
    else:
        for name, info in wl.items():
            res = analyze_pro(info['code'], name)
            if res: st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# [4. 사이드바 - 검색 및 관리 기능]
# ------------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 기능 메뉴")
    with st.expander("🔍 종목/테마 검색", expanded=True):
        search_name = st.text_input("종목명 입력")
        if st.button("🚀 즉시 분석"):
            if not krx_df.empty:
                match = krx_df[krx_df['Name'] == search_name]
                if not match.empty:
                    code = match.iloc[0]['Code']
                    st.session_state['preview_list'] = [{"name": search_name, "code": code}]
                    st.rerun()
                else: st.error("종목명을 찾을 수 없습니다.")

    if st.button("🔄 전체 데이터 동기화"):
        st.session_state['data_store'] = load_from_github()
        st.rerun()
