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
import feedparser
import urllib.parse

# --- [1. UI 스타일링] ---
st.set_page_config(page_title="Quant Sniper V22.1", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    .text-up { color: #F04452 !important; }
    .text-down { color: #3182F6 !important; }
    
    /* 재무 박스 스타일 */
    .fund-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 10px; }
    .fund-item { padding: 12px; border-radius: 12px; text-align: center; }
    .fund-label { font-size: 12px; color: #6B7684; margin-bottom: 4px; }
    .fund-val { font-size: 16px; font-weight: 800; color: #333D4B; }
    .fund-badge { font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; margin-left: 4px; display:inline-block; }
    
    /* 기술적 분석 스타일 */
    .tech-summary { background: #F2F4F6; padding: 10px; border-radius: 8px; font-size: 13px; color: #4E5968; margin-bottom: 10px; font-weight: 600; }
    .ma-badge { padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; margin-right: 5px; background: #EEE; color: #888; }
    .ma-ok { background: #F04452; color: white; }
    
    /* 뉴스 분석 스타일 구분 (V22.1 핵심) */
    .news-ai { background: #F9FAFB; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #E5E8EB; color: #333; }
    .news-fallback { background: #FFF4E6; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #FFD8A8; color: #D9480F; font-weight: 600; }
    
    .news-scroll-box { max-height: 300px; overflow-y: auto; border: 1px solid #F2F4F6; border-radius: 8px; padding: 10px; }
    .news-box { padding: 8px 0; border-bottom: 1px solid #F2F4F6; font-size: 13px; }
    .news-link { color: #333; text-decoration: none; font-weight: 500; display: block; margin-bottom: 2px;}
    .news-link:hover { color: #3182F6; text-decoration: underline; }
    .news-date { font-size: 11px; color: #999; }
</style>
""", unsafe_allow_html=True)

# --- [2. 데이터 및 설정] ---
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

@st.cache_data
def get_krx_list():
    try: df = fdr.StockListing('KRX'); return df[['Code', 'Name', 'Sector']]
    except: return pd.DataFrame()
krx_df = get_krx_list()

def load_from_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return {}
        token = st.secrets["GITHUB_TOKEN"]
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            return json.loads(content)
        return {}
    except: return {}

if 'watchlist' not in st.session_state: st.session_state['watchlist'] = load_from_github()

# --- [3. 분석 엔진 V22.1 (명확한 모드 구분)] ---

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    try:
        end_str = datetime.datetime.now().strftime("%Y%m%d")
        start_str = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y%m%d")
        df = stock.get_market_fundamental_by_date(start_str, end_str, code)
        if df.empty: return 25, "데이터 없음", {}
        
        recent = df.iloc[-1]
        per = recent['PER']; pbr = recent['PBR']; div = recent['DIV']
        
        pbr_stat = "good" if pbr < 1.0 else ("neu" if pbr < 2.5 else "bad")
        pbr_txt = "저평가" if pbr < 1.0 else ("적정" if pbr < 2.5 else "고평가")
        per_stat = "good" if 0 < per < 10 else ("neu" if 10 <= per < 20 else "bad")
        per_txt = "실적우수" if 0 < per < 10 else ("보통" if 10 <= per < 20 else "고평가/적자")
        div_stat = "good" if div > 3.0 else "neu"
        div_txt = "고배당" if div > 3.0 else "일반"

        score = 20
        if pbr_stat=="good": score+=15
        if per_stat=="good": score+=10
        if div_stat=="good": score+=5
        
        fund_data = {
            "per": {"val": per, "stat": per_stat, "txt": per_txt},
            "pbr": {"val": pbr, "stat": pbr_stat, "txt": pbr_txt},
            "div": {"val": div, "stat": div_stat, "txt": div_txt}
        }
        return min(score, 50), "분석완료", fund_data
    except: return 25, "분석실패", {}

# 비상용 키워드 분석기
def analyze_news_by_keywords(news_titles):
    pos_words = ["상승", "급등", "최고", "호재", "개선", "성장", "흑자", "수주", "돌파", "기대", "매수"]
    neg_words = ["하락", "급락", "최저", "악재", "우려", "감소", "적자", "이탈", "매도", "공매도"]
    
    score = 0
    found_keywords = []
    
    for title in news_titles:
        for w in pos_words:
            if w in title: 
                score += 1
                found_keywords.append(w)
        for w in neg_words:
            if w in title: 
                score -= 1
                found_keywords.append(w)
    
    final_score = min(max(score, -10), 10)
    summary = f"긍정 키워드 {len([w for w in found_keywords if w in pos_words])}개, 부정 키워드 {len([w for w in found_keywords if w in neg_words])}개가 감지되었습니다."
    return final_score, summary

def call_gemini_auto(prompt):
    api_key = st.secrets.get("GOOGLE_API_KEY", "")
    if not api_key: return None, "NO_KEY"
    
    # 모델 자동 탐색
    models_to_try = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            if response.status_code == 200:
                return response.json(), None
            elif response.status_code == 429:
                return None, "RATE_LIMIT"
        except:
            continue
            
    return None, "ALL_FAILED"

@st.cache_data(ttl=600)
def get_news_sentiment(company_name):
    try:
        query = f"{company_name} 주가"
        encoded_query = urllib.parse.quote(query)
        rss_url = f"
