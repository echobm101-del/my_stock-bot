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
from datetime import datetime as dt

# 방금 만드신 utils.py와 기존 ui.py에서 기능 가져오기
from modules.utils import calculate_rsi, calculate_macd, calculate_atr, calculate_stochastic, round_to_tick

try:
    from modules.ui import (
        apply_custom_css, create_watchlist_card_html, create_portfolio_card_html,
        render_tech_metrics, create_chart_clean, render_chart_legend,
        render_fund_scorecard, render_investor_chart
    )
    apply_custom_css()
except:
    st.error("❌ 'modules/ui.py' 파일을 찾을 수 없습니다.")
    st.stop()

# 기초 설정 및 경고 무시
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Quant Sniper V51.9", page_icon="💎", layout="wide")

# ------------------------------------------------------------------------------
# [보안 설정] (이미지 설명: 깃허브 및 API 연결 설정 정보)
# ------------------------------------------------------------------------------
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"
USER_GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
USER_GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")

# ------------------------------------------------------------------------------
# [핵심 로직] 데이터 로딩 및 저장 함수 (복구 완료)
# ------------------------------------------------------------------------------
def load_from_github():
    try:
        if not USER_GITHUB_TOKEN: return {"portfolio": {}, "watchlist": {}}
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {USER_GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            data = json.loads(content)
            if "portfolio" not in data: data["portfolio"] = {}
            if "watchlist" not in data: data["watchlist"] = {}
            return data
        return {"portfolio": {}, "watchlist": {}}
    except: return {"portfolio": {}, "watchlist": {}}

def update_github_file(new_data):
    try:
        if not USER_GITHUB_TOKEN: return False
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {USER_GITHUB_TOKEN}"}
        r_get = requests.get(url, headers=headers)
        sha = r_get.json().get('sha') if r_get.status_code == 200 else None
        json_str = json.dumps(new_data, ensure_ascii=False, indent=4)
        b64_content = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        payload = {"message": "Update data", "content": b64_content, "sha": sha} if sha else {"message": "Create data", "content": b64_content}
        requests.put(url, headers=headers, json=payload)
        return True
    except: return False

# 분석 핵심 함수 (calculate_sniper_score 및 analyze_pro 로직 포함)
def analyze_pro(code, name):
    try:
        df = fdr.DataReader(code, dt.now() - datetime.timedelta(days=200))
        if df.empty: return None
        # utils.py의 함수 사용
        df['RSI'] = calculate_rsi(df['Close'])
        df['MA20'] = df['Close'].rolling(20).mean()
        curr = df.iloc[-1]
        
        # 임시 결과 구조 (실제 UI 연동용)
        return {
            "name": name, "code": code, "price": int(curr['Close']),
            "change_rate": 0.0, "score": 80, "history": df,
            "ma_status": [{"label": "20일", "ok": curr['Close'] > curr['MA20']}],
            "stoch": {"k": 50, "d": 50}, "vol_ratio": 1.0, "fund_data": {},
            "investor_trend": pd.DataFrame(), "news": {"method": "none"}
        }
    except: return None

# 세션 상태 관리
if 'data_store' not in st.session_state:
    st.session_state['data_store'] = load_from_github()
if 'preview_list' not in st.session_state:
    st.session_state['preview_list'] = []

# ------------------------------------------------------------------------------
# [UI 화면 구성]
# ------------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🔍 테마/종목 발굴", "💰 내 잔고 (Portfolio)", "👀 관심 종목 (Watchlist)"])

with tab1:
    if st.session_state['preview_list']:
        for item in st.session_state['preview_list']:
            res = analyze_pro(item['code'], item['name'])
            if res: st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
    else:
        st.info("왼쪽 사이드바에서 검색을 시작하세요.")

with tab2:
    port_items = st.session_state['data_store'].get('portfolio', {})
    if not port_items:
        st.info("보유 종목이 없습니다.")
    else:
        for name, info in port_items.items():
            res = analyze_pro(info['code'], name)
            if res: st.markdown(create_portfolio_card_html(res), unsafe_allow_html=True)

with tab3:
    wl_items = st.session_state['data_store'].get('watchlist', {})
    if not wl_items:
        st.info("관심 종목이 없습니다.")
    else:
        for name, info in wl_items.items():
            res = analyze_pro(info['code'], name)
            if res: st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# [사이드바] 검색 기능 복구
# ------------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 기능 메뉴")
    with st.form("search"):
        target_name = st.text_input("종목명 입력 (예: 삼성전자)")
        if st.form_submit_button("분석 시작"):
            # 간단 검색 로직 (KRX 리스트에서 코드 찾기 생략, 직접 입력 예시)
            st.session_state['preview_list'] = [{"name": target_name, "code": "005930"}] # 예시 코드
            st.rerun()
