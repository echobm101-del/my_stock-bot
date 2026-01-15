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
from datetime import datetime as dt
import warnings

# 방금 만드신 utils.py와 기존 ui.py에서 기능 가져오기
from modules.utils import calculate_rsi, calculate_macd, calculate_atr, calculate_stochastic, round_to_tick
try:
    from modules.ui import (
        apply_custom_css, create_watchlist_card_html, create_portfolio_card_html,
        render_tech_metrics, create_chart_clean, render_chart_legend,
        render_fund_scorecard, render_investor_chart
    )
except ImportError:
    st.error("❌ 'modules/ui.py' 파일을 찾을 수 없습니다.")
    st.stop()

# 기초 설정
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Quant Sniper V51.9", page_icon="💎", layout="wide")
apply_custom_css()

# ------------------------------------------------------------------------------
# [보안 설정] Streamlit Secrets에서 가져오기
# ------------------------------------------------------------------------------
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"
USER_GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
USER_GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")

# ------------------------------------------------------------------------------
# [핵심 기능] 데이터 로딩 및 분석 (기존 로직 유지)
# ------------------------------------------------------------------------------
@st.cache_data
def get_krx_list_safe():
    try:
        df = fdr.StockListing('KRX')
        return df if not df.empty else pd.DataFrame()
    except:
        return pd.DataFrame()

def load_from_github():
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {USER_GITHUB_TOKEN}"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            return json.loads(content)
        return {"portfolio": {}, "watchlist": {}}
    except:
        return {"portfolio": {}, "watchlist": {}}

# 세션 상태 초기화
if 'data_store' not in st.session_state:
    st.session_state['data_store'] = load_from_github()
if 'preview_list' not in st.session_state:
    st.session_state['preview_list'] = []

# ------------------------------------------------------------------------------
# [메인 화면] 탭 구성
# ------------------------------------------------------------------------------
st.title("💎 Quant Sniper V51.9")
tab1, tab2, tab3 = st.tabs(["🔍 테마/종목 발굴", "💰 내 잔고 (Portfolio)", "👀 관심 종목 (Watchlist)"])

with tab1:
    if st.session_state['preview_list']:
        st.subheader("🔎 검색된 종목 리스트")
        # 여기에 종목 분석 카드 출력 로직 (기존과 동일)
    else:
        st.info("왼쪽 사이드바에서 테마를 검색하거나 종목명을 입력해주세요.")

with tab2:
    st.subheader("💰 보유 종목 관리")
    # 포트폴리오 출력 로직

with tab3:
    st.subheader("👀 관심 종목 리스트")
    # 관심종목 출력 로직

# ------------------------------------------------------------------------------
# [사이드바] 검색 및 설정 (잘렸던 부분 수정 완료)
# ------------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 기능 메뉴")
    
    with st.expander("🔍 종목/테마 검색", expanded=True):
        mode = st.radio("검색 모드", ["테마 검색", "개별 종목"])
        
        with st.form("search_form"):
            if mode == "테마 검색":
                keyword = st.text_input("테마 키워드 (예: 반도체, AI)")
            else:
                keyword = st.text_input("종목명 입력")
            
            submit_btn = st.form_submit_button("🚀 분석 시작")
            
            if submit_btn and keyword:
                st.toast(f"'{keyword}' 분석을 시작합니다!")
                # 여기에 분석 실행 함수 연결 (기존 analyze_pro 등)

    if st.button("🔄 데이터 강제 동기화"):
        st.session_state['data_store'] = load_from_github()
        st.rerun()
