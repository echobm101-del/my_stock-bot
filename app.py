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
import numpy as np
from io import StringIO

# --- [1. UI 스타일링] ---
st.set_page_config(page_title="Quant Sniper V31.0", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    
    .fund-grid-v2 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 10px; background-color: #F9FAFB; padding: 15px; border-radius: 12px; }
    .fund-item-v2 { text-align: center; }
    .fund-title-v2 { font-size: 12px; color: #8B95A1; margin-bottom: 5px; }
    .fund-value-v2 { font-size: 18px; font-weight: 800; color: #333D4B; }
    .fund-desc-v2 { font-size: 11px; font-weight: 600; margin-top: 4px; display: inline-block; padding: 2px 6px; border-radius: 4px;}
    
    .tech-status-box { display: flex; gap: 10px; margin-bottom: 5px; }
    .status-badge { flex: 1; padding: 10px; border-radius: 8px; text-align: center; font-size: 13px; font-weight: 700; color: #4E5968; background: #F2F4F6; border: 1px solid #E5E8EB; }
    .status-badge.buy { background-color: #E8F3FF; color: #3182F6; border-color: #3182F6; }
    .status-badge.sell { background-color: #FFF1F1; color: #F04452; border-color: #F04452; }
    .status-badge.vol { background-color: #FFF8E1; color: #D9480F; border-color: #FFD8A8; }

    .tech-summary { background: #F2F4F6; padding: 10px; border-radius: 8px; font-size: 13px; color: #4E5968; margin-bottom: 10px; font-weight: 600; }
    .ma-badge { padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; margin-right: 5px; background: #EEE; color: #888; }
    .ma-ok { background: #F04452; color: white; }
    
    .news-ai { background: #F9FAFB; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #E5E8EB; color: #333; }
    .news-fallback { background: #FFF4E6; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #FFD8A8; color: #D9480F; font-weight: 600; }
    
    .news-scroll-box { max-height: 300px; overflow-y: auto; border: 1px solid #F2F4F6; border-radius: 8px; padding: 10px; }
    .news-box { padding: 8px 0; border-bottom: 1px solid #F2F4F6; font-size: 13px; }
    .news-link { color: #333; text-decoration: none; font-weight: 500; display: block; margin-bottom: 2px;}
    .news-link:hover { color: #3182F6; text-decoration: underline; }
    .news-date { font-size: 11px; color: #999; }
    
    .metric-box { background: #F9FAFB; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #E5E8EB; }
    .metric-title { font-size: 12px; color: #666; }
    .metric-value { font-size: 18px; font-weight: bold; color: #333; }

    .sniper-tag { font-size: 10px; padding: 2px 5px; border-radius: 4px; font-weight: 700; margin-right: 4px; }
    .tag-vol { background: #FFF0EB; color: #D9480F; border: 1px solid #FFD8A8; }
    .tag-smart { background: #E8F3FF; color: #3182F6; border: 1px solid #D0EBFF; }
    .tag-pull { background: #E6FCF5; color: #087F5B; border: 1px solid #B2F2BB; }
</style>
""", unsafe_allow_html=True)

# --- [2. 데이터 및 설정] ---
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

@st.cache_data
def get_krx_list():
    try: df = fdr.StockListing('KRX'); return df
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
if 'preview_list' not in st.session_state: st.session_state['preview_list'] = []
if 'current_theme_name' not in st.session_state: st.session_state['current_theme_name'] = ""

# --- [2-1. 네이버 금융 테마 크롤링] ---

@st.cache_data(ttl=1800)
def get_naver_theme_stocks(keyword):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Referer': 'https://finance.naver.com/'}
    target_link = None
    
    for page in range(1, 8):
        base_url = f"https://finance.naver.com/sise/theme.naver?&page={page}"
        try:
            res = requests.get(base_url, headers=headers)
            res.encoding = 'EUC-KR' 
            soup = BeautifulSoup(res.text, 'html.parser')
            themes = soup.select('table.type_1 tr td.col_type1 a')
            for t in themes:
                if keyword.strip() in t.text.strip():
                    target_link = "https://finance.naver.com" + t['href']
                    break
            if target_link: break
        except: continue

    if not target_link: return [], f"네이버 금융 테마에서 '{keyword}'를 찾을 수 없습니다."

    try:
        res_detail = requests.get(target_link, headers=headers)
        res_detail.encoding = 'EUC-KR'
        soup_detail = BeautifulSoup(res_detail.text, 'html.parser')
        stocks = []
        rows = soup_detail.select('div.box_type_l table.type_5 tr')
        for row in rows:
            name_tag = row.select_one('td.name a')
            if name_tag:
                code = name_tag['href'].split('=')[-1]
                name = name_tag.text.strip()
                price_txt = row.select('td.number')[0].text.strip().replace(',', '')
                try: price = int(price_txt)
                except: price = 0
                stocks.append({"code": code, "name": name, "price": price})
        return stocks, f"'{keyword}' 관련 테마 발견: {len(stocks)}개 종목"
    except Exception as e: return [], f"크롤링 오류: {str(e)}"

# [V31.0] 투자자별 매매 동향 데이터 수집 (최근 20일)
@st.cache_data(ttl=3600)
def get_investor_trend(code):
    try:
        end_d = datetime.datetime.now().strftime("%Y%m%d")
        start_d = (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y%m%d") # 여유있게
        df = stock.get_market_investor_net_purchase_by_date(start_d, end_d, code)
        if df.empty: return pd.DataFrame()
        
        # 최근 20일치만
        df = df.tail(20).copy()
        # 누적 순매수 계산 (Trend 확인용)
        df['Cum_Individual'] = df['개인'].cumsum()
        df['Cum_Foreigner'] = df['외국인'].cumsum()
        df['Cum_Institution'] = df['기관합계'].cumsum()
        df['Cum_Pension'] = df['연기금'].cumsum()
        
        return df
    except: return pd.DataFrame()

# [V31.0] 실적/재무 차트용 데이터 수집 (네이버 크롤링)
@st.cache_data(ttl=3600)
def get_financial_history(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        df_list = pd.read_html(StringIO(res.text), encoding='euc-kr')
        
        # 보통 3번째 테이블이 주요재무제표
        for df in df_list:
            if '최근 연간 실적' in str(df.columns) or '매출액' in str(df.iloc[:,0].values):
                df = df.set_index(df.columns[0])
                # 필요한 행만 추출 (매출액, 영업이익, 당기순이익)
                target_rows = ['매출액', '영업이익', '당기순이익']
                
                # 데이터 정제
                fin_data = []
                # 최근 4개 분기 or 연도 데이터 추출 (컬럼 구조가 복잡하므로 단순화)
                # 컬럼 중 날짜 형식이 있는 것만 필터링 필요하나, 여기선 간단히 끝에서 4개 가져옴
                cols = df.columns[-5:-1] # 최근 예상치 제외하고 확정치 위주
                
                for col in cols:
                    try:
                        col_name = col[1] if isinstance(col, tuple) else col
                        val_sales = df.loc['매출액', col] if '매출액' in df.index else 0
                        val_op = df.loc['영업이익', col] if '영업이익' in df.index else 0
                        val_net = df.loc['당기순이익', col] if '당기순이익' in df.index else 0
                        
                        fin_data.append({
                            "Date": str(col_name),
                            "매출액": float(val_sales) if val_sales != '-' else 0,
                            "영업이익": float(val_op) if val_op != '-' else 0,
                            "당기순이익": float(val_net) if val_net != '-' else 0
                        })
                    except: continue
                    
                return pd.DataFrame(fin_data)
        return pd.DataFrame()
    except: return pd.DataFrame()

def calculate_sniper_score(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=90))
        if df.empty or len(df) < 20: return 0, [], 0, 0
        curr = df.iloc[-1]
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
        score = 0; tags = []
        vol_ratio = curr['Volume'] / vol_avg if vol_avg > 0 else 0
        if vol_ratio >= 3.0: score += 40; tags.append("🔥 거래량폭발")
        elif vol_ratio >= 1.5: score += 20; tags.append("📈 거래량증가")
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        if curr['Close'] > ma20 and curr['Close'] <= ma20 * 1.05: score += 30; tags.append("🏹 눌림목")
        
        try:
            end_d = datetime.datetime.now().strftime("%Y%m%d")
            start_d = (datetime.datetime.now() - datetime.timedelta(days=5)).strftime("%Y%m%d")
            inv_df = stock.get_market_investor_net_purchase_by_date(start_d, end_d, code).tail(3)
            if not inv_df.empty and (inv_df['기관합계'].sum() + inv_df['외국인'].sum() > 0): score += 30; tags.append("🏦 메이저매집")
        except: pass
        
        change = (curr['Close'] - df.iloc[-2]['Close']) / df.iloc[-2]['Close'] * 100
        if change > 15: tags.append("🚀 급등주")
        return score, tags, vol_ratio, change
    except: return 0, [], 0, 0

# --- [2-2. 거시 경제 데이터] ---
@st.cache_data(ttl=3600)
def get_macro_data():
    results = {}
    tickers = {"KOSPI": "KS11", "KOSDAQ": "KQ11", "S&P500": "US500", "USD/KRW": "USD/KRW", "US_10Y": "US10YT"}
    for name, code in tickers.items():
        try:
            df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=14))
            if not df.empty:
                curr = df.iloc[-1]
                results[name] = {"val": curr['Close'], "change": (curr['Close'] - curr['Open']) / curr['Open'] * 100}
            else: results[name] = {"val": 0.0, "change": 0.0}
        except: results[name] = {"val": 0.0, "change": 0.0}
    if all(v['val'] == 0.0 for v in results.values()): return None
    return results

# --- [3. 분석 엔진 V31.0] ---

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    per, pbr, div = 0.0, 0.0, 0.0
    
    # [1단계] 네이버 금융 직접 크롤링
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            def get_val_by_id(id_name):
                tag = soup.select_one(f"#{id_name}")
                if tag:
                    txt = tag.text.replace(',', '').replace('%', '').replace('배', '').strip()
                    try: return float(txt)
                    except: return 0.0
                return 0.0
            per = get_val_by_id("_per")
            pbr = get_val_by_id("_pbr")
            div = get_val_by_id("_dvr")
    except: pass

    # [2단계] 백업
    if per == 0 and pbr == 0:
        if not krx_df.empty and code in krx_df['Code'].values:
            try:
                row = krx_df[krx_df['Code'] == code].iloc[0]
                per = float(row.get('PER', 0)) if pd.notnull(row.get('PER')) else 0
                pbr = float(row.get('PBR', 0)) if pd.notnull(row.get('PBR')) else 0
                div = float(row.get('DividendYield', 0)) if pd.notnull(row.get('DividendYield')) else 0
            except: pass

    # [3단계] Pykrx
    if per == 0 and pbr == 0:
        try:
            end_str = datetime.datetime.now().strftime("%Y%m%d")
            start_str = (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y%m%d")
            df = stock.get_market_fundamental_by_date(start_str, end_str, code)
            if not df.empty:
                recent = df.iloc[-1]
                per = float(recent.get('PER', 0))
                pbr = float(recent.get('PBR', 0))
                div = float(recent.get('DIV', 0))
        except: pass

    pbr_stat = "good" if 0 < pbr < 1.0 else ("neu" if 1.0 <= pbr < 2.5 else "bad")
    pbr_txt = "저평가(좋음)" if 0 < pbr < 1.0 else ("적정" if 1.0 <= pbr < 2.5 else "고평가/정보없음")
    per_stat = "good" if 0 < per < 10 else ("neu" if 10 <= per < 20 else "bad")
    per_txt = "실적우수" if 0 < per < 10 else ("보통" if 10 <= per < 20 else "고평가/적자/정보없음")
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

def analyze_news_by_keywords(news_titles):
    pos_words = ["상승", "급등", "최고", "호재", "개선", "성장", "흑자", "수주", "돌파", "기대", "매수"]
    neg_words = ["하락", "급락", "최저", "악재", "우려", "감소", "적자", "이탈", "매도", "공매도"]
    score = 0; found_keywords = []
    for title in news_titles:
        for w in pos_words:
            if w in title: score += 1; found_keywords.append(w)
        for w in neg_words:
            if w in title: score -= 1; found_keywords.append(w)
    final_score = min(max(score, -10), 10)
    summary = f"긍정 키워드 {len([w for w in found_keywords if w in pos_words])}개, 부정 키워드 {len([w for w in found_keywords if w in neg_words])}개 감지."
    return final_score, summary

def call_gemini_auto(prompt):
    api_key = st.secrets.get("GOOGLE_API_KEY", "")
    if not api_key: return None, "NO_KEY"
    models = ["gemini-1.5-flash", "gemini-pro"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"response_mime_type": "application/json"}}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=6)
            if res.status_code == 200: return res.json(), None
        except: continue
    return None, "ALL_FAILED"

@st.cache_data(ttl=600)
def get_news_sentiment(company_name):
    try:
        query = f"{company_name} 주가"
        encoded_query = urllib.parse.quote(query)
        base_url = "https://news.google.com/rss/search"
        rss_url = base_url + f"?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        news_titles = []; news_data = []
        for entry in feed.entries[:20]:
            date_str = time.strftime("%Y-%m-%d", entry.published_parsed) if entry.published_parsed else ""
            news_data.append({"title": entry.title, "link": entry.link, "date": date_str})
            news_titles.append(entry.title)
        
        if not news_titles: return {"score": 0, "headline": "관련 뉴스 없음", "raw_news": [], "method": "none"}
        
        prompt = f"뉴스 목록: {str(news_titles)}\n위 뉴스를 분석하여 주가 영향 점수(-10~10)와 한줄 요약을 JSON으로 작성하라. 형식: {{ \"score\": 0, \"summary\": \"내용\" }}"
        res_data, error_code = call_gemini_auto(prompt)
        score = 0; headline = ""; method = "ai"
        if res_data:
            try:
                raw = res_data['candidates'][0]['content']['parts'][0]['text']
                js = json.loads(raw)
                score = js.get('score', 0); headline = js.get('summary', "")
            except: error_code = "PARSE_ERROR"
        if not res_data or error_code:
            score, headline = analyze_news_by_keywords(news_titles)
            method = "keyword"
        return {"score": score, "headline": headline, "raw_news": news_data, "method": method}
    except Exception as e: return {"score": 0, "headline": f"오류: {str(e)}", "raw_news": [], "method": "error"}

@st.cache_data(ttl=1800)
def get_supply_demand(code):
    try:
        e = datetime.datetime.now().strftime("%Y%m%d")
        s = (datetime.datetime.now()-datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(s, e, code).tail(3)
        if df.empty: return {"f":0, "i":0}
        return {"f": int(df['외국인'].sum()), "i": int(df['기관합계'].sum())}
    except: return {"f":0, "i":0}

def analyze_pro(code, name_override=None):
    try:
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=450))
        if df.empty or len(df) < 240: return None
        
        sup = get_supply_demand(code)
        fund_score, fund_msg, fund_data = get_company_guide_score(code)
        
        # [V31.0] 투자자 추이 및 재무 이력 가져오기
        investor_trend = get_investor_trend(code)
        fin_history = get_financial_history(code)
        
        search_name = name_override if name_override else code
        news = get_news_sentiment(search_name)

        df['MA5'] = df['Close'].rolling(5).mean(); df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean(); df['MA120'] = df['Close'].rolling(120).mean()
        df['MA240'] = df['Close'].rolling(240).mean()
        df['std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['MA20'] + (df['std'] * 2); df['BB_Lower'] = df['MA20'] - (df['std'] * 2)
        df['Vol_MA20'] = df['Volume'].rolling(20).mean()

        n=14; m=3; t=3
        df['L14'] = df['Low'].rolling(window=n).min(); df['H14'] = df['High'].rolling(window=n).max()
        df['%K'] = (df['Close'] - df['L14']) / (df['H14'] - df['L14']) * 100
        df['%D'] = df['%K'].rolling(window=m).mean(); df['%J'] = df['%D'].rolling(window=t).mean()
        
        curr = df.iloc[-1]
        pass_cnt = 0; ma_status = []
        mas = [('5일', 'MA5'), ('20일', 'MA20'), ('60일', 'MA60'), ('120일', 'MA120'), ('240일', 'MA240')]
        for label, col in mas:
            if curr['Close'] >= curr[col]: pass_cnt += 1; ma_status.append({"label": label, "ok": True})
            else: ma_status.append({"label": label, "ok": False})
        
        tech_score = (pass_cnt * 6) + (10 if curr['MA5'] > curr['MA20'] > curr['MA60'] else 0) + (10 if sup['f'] > 0 else 0)
        if curr['%K'] < 20: tech_score += 5 
        elif 20 <= curr['%K'] <= 80 and curr['%K'] > curr['%D']: tech_score += 5
        
        # [V31.0 Score Boost] 실적 및 수급 가산점
        bonus_score = 0
        if not investor_trend.empty:
            # 외국인 또는 기관 누적 순매수 양수일 경우
            if investor_trend['Cum_Foreigner'].iloc[-1] > 0: bonus_score += 5
            if investor_trend['Cum_Institution'].iloc[-1] > 0: bonus_score += 5
            if investor_trend['Cum_Pension'].iloc[-1] > 0: bonus_score += 5 # 연기금
        
        if not fin_history.empty:
            # 영업이익 성장세 (마지막이 그 전보다 크면)
            if len(fin_history) >= 2 and fin_history['영업이익'].iloc[-1] > fin_history['영업이익'].iloc[-2]:
                bonus_score += 5

        if pass_cnt >= 4: trend_txt = "🚀 강력한 상승 추세"
        elif pass_cnt >= 3: trend_txt = "📈 상승세 (양호)"
        elif pass_cnt >= 1: trend_txt = "📉 하락 중 반등 시도"
        else: trend_txt = "☠️ 완전 역배열"
        
        # AI Score 재조정
        final_score = int((tech_score * 0.4) + fund_score + bonus_score + news['score'])
        final_score = min(max(final_score, 0), 100)
        
        vol_ratio = curr['Volume'] / curr['Vol_MA20'] if curr['Vol_MA20'] > 0 else 1.0
        
        return {
            "name": name_override, "code": code, "price": int(curr['Close']),
            "score": final_score, 
            "strategy": {"buy": int(curr['MA20']), "target": int(curr['Close']*1.1), "action": "매수" if final_score>=60 else "관망"},
            "fund_data": fund_data, "ma_status": ma_status, "trend_txt": trend_txt,
            "news": news, "history": df, "supply": sup,
            "stoch": {"k": curr['%K'], "d": curr['%J']},
            "vol_ratio": vol_ratio,
            "investor_trend": investor_trend, # V31.0
            "fin_history": fin_history # V31.0
        }
    except: return None

def create_card_html(res):
    score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
    return textwrap.dedent(f"""
    <div class='toss-card'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div><span class='stock-name'>{res['name']}</span><span class='stock-code'>{res['code']}</span><div class='big-price'>{res['price']:,}원</div></div>
            <div style='text-align:right;'><div style='font-size:28px; font-weight:800; color:{score_col};'>{res['score']}점</div><div class='badge-clean' style='background-color:{score_col}20; color:{score_col};'>{res['strategy']['action']}</div></div>
        </div>
        <div style='margin-top:10px; color:#666; font-size:13px;'>{res['trend_txt']}</div>
    </div>
    """)

def create_chart_clean(df):
    chart_data = df.tail(120).reset_index()
    base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=alt.Axis(format='%m-%d', title=None)))
    band = base.mark_area(opacity=0.15, color='#868E96').encode(y='BB_Lower:Q', y2='BB_Upper:Q')
    line = base.mark_line(color='#000000').encode(y='Close:Q')
    ma20 = base.mark_line(color='#F2A529').encode(y='MA20:Q')
    ma60 = base.mark_line(color='#3182F6').encode(y='MA60:Q')
    return (band + line + ma20 + ma60).properties(height=250)

def render_tech_metrics(stoch, vol_ratio):
    k = stoch['k']
    if k < 20: stoch_txt = f"🟢 침체 구간 ({k:.1f}%)"; stoch_sub = "매수 기회 탐색"; stoch_cls = "buy"
    elif k > 80: stoch_txt = f"🔴 과열 구간 ({k:.1f}%)"; stoch_sub = "매도/조정 주의"; stoch_cls = "sell"
    else: stoch_txt = f"⚪ 중립 구간 ({k:.1f}%)"; stoch_sub = "추세 지속"; stoch_cls = ""

    if vol_ratio >= 2.0: vol_txt = f"🔥 거래량 폭발 ({vol_ratio*100:.0f}%)"; vol_cls = "vol"
    elif vol_ratio >= 1.2: vol_txt = f"📈 거래량 증가 ({vol_ratio*100:.0f}%)"; vol_cls = "buy"
    else: vol_txt = "☁️ 거래량 평이"; vol_cls = ""

    st.markdown(f"""
    <div class='tech-status-box'>
        <div class='status-badge {stoch_cls}'>
            <div>📊 스토캐스틱</div><div style='font-size:16px; margin-top:4px;'>{stoch_txt}</div><div style='font-size:11px; opacity:0.8;'>{stoch_sub}</div>
        </div>
        <div class='status-badge {vol_cls}'>
            <div>📢 거래강도(전일비)</div><div style='font-size:16px; margin-top:4px;'>{vol_txt}</div><div style='font-size:11px; opacity:0.8;'>평소보다 {vol_ratio:.1f}배 활발</div>
        </div>
    </div>""", unsafe_allow_html=True)

def render_chart_legend():
    return """<div style='display:flex; gap:12px; font-size:12px; color:#555; margin-bottom:8px; align-items:center;'>
        <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#000000; margin-right:4px;'></div>현재가(검정)</div>
        <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#F2A529; margin-right:4px;'></div>20일선(황색)</div>
        <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#3182F6; margin-right:4px;'></div>60일선(파랑)</div>
        <div style='display:flex; align-items:center;'><div style='width:12px; height:12px; background:#868E96; opacity:0.3; margin-right:4px;'></div>볼린저밴드(회색)</div>
    </div>"""

def render_fund_scorecard(fund_data):
    if not fund_data: st.info("재무 정보 로딩 실패 (일시적 오류)"); return
    per = fund_data['per']['val']
    pbr = fund_data['pbr']['val']
    div = fund_data['div']['val']
    per_col = "#F04452" if fund_data['per']['stat']=='good' else ("#3182F6" if fund_data['per']['stat']=='bad' else "#333")
    pbr_col = "#F04452" if fund_data['pbr']['stat']=='good' else ("#3182F6" if fund_data['pbr']['stat']=='bad' else "#333")
    div_col = "#F04452" if fund_data['div']['stat']=='good' else "#333"
    st.markdown(f"""
    <div class='fund-grid-v2'>
        <div class='fund-item-v2'><div class='fund-title-v2'>PER</div><div class='fund-value-v2' style='color:{per_col}'>{per:.1f}배</div><div class='fund-desc-v2' style='background-color:{per_col}20; color:{per_col}'>{fund_data['per']['txt']}</div></div>
        <div class='fund-item-v2'><div class='fund-title-v2'>PBR</div><div class='fund-value-v2' style='color:{pbr_col}'>{pbr:.1f}배</div><div class='fund-desc-v2' style='background-color:{pbr_col}20; color:{pbr_col}'>{fund_data['pbr']['txt']}</div></div>
        <div class='fund-item-v2'><div class='fund-title-v2'>배당률</div><div class='fund-value-v2' style='color:{div_col}'>{div:.1f}%</div><div class='fund-desc-v2' style='background-color:{div_col}20; color:{div_col}'>{fund_data['div']['txt']}</div></div>
    </div>""", unsafe_allow_html=True)

# [V31.0] 새로운 차트 렌더링 함수 (재무)
def render_financial_chart(df):
    if df.empty:
        st.caption("재무 데이터가 없습니다.")
        return
    
    base = alt.Chart(df).encode(x=alt.X('Date', axis=alt.Axis(title=None)))
    bar = base.mark_bar(color='#E8F3FF').encode(y=alt.Y('매출액', axis=alt.Axis(title='매출액')))
    line = base.mark_line(color='#F04452').encode(y=alt.Y('영업이익', axis=alt.Axis(title='영업이익')))
    st.altair_chart((bar + line).properties(height=200), use_container_width=True)

# [V31.0] 새로운 차트 렌더링 함수 (수급)
def render_investor_chart(df):
    if df.empty:
        st.caption("수급 데이터가 없습니다.")
        return
    
    # Altair용 데이터 변환 (Long format)
    df_long = df.reset_index().melt('날짜', value_vars=['Cum_Individual', 'Cum_Foreigner', 'Cum_Institution', 'Cum_Pension'], var_name='Type', value_name='Volume')
    
    # 범례 이름 매핑
    type_map = {
        'Cum_Individual': '개인',
        'Cum_Foreigner': '외국인',
        'Cum_Institution': '기관합계',
        'Cum_Pension': '연기금'
    }
    df_long['Type'] = df_long['Type'].map(type_map)
    
    chart = alt.Chart(df_long).mark_line().encode(
        x=alt.X('날짜:T', axis=alt.Axis(format='%m-%d', title=None)),
        y=alt.Y('Volume:Q', axis=alt.Axis(title='누적 순매수')),
        color=alt.Color('Type:N', legend=alt.Legend(title="투자자"))
    ).properties(height=200)
    
    st.altair_chart(chart, use_container_width=True)

def send_telegram_msg(token, chat_id, msg):
    try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": msg})
    except: pass

# --- [4. 메인 화면] ---
st.title("💎 Quant Sniper V31.0")

# 4-1. 거시 경제
with st.expander("🌍 글로벌 거시 경제 대시보드 (Click to Open)", expanded=False):
    macro = get_macro_data()
    if macro:
        cols = st.columns(5)
        keys = ["KOSPI", "KOSDAQ", "S&P500", "USD/KRW", "US_10Y"]
        for i, key in enumerate(keys):
            d = macro.get(key, {"val": 0.0, "change": 0.0})
            color = "#F04452" if d['change'] > 0 else "#3182F6"
            with cols[i]:
                st.markdown(f"<div class='metric-box'><div class='metric-title'>{key}</div><div class='metric-value' style='color:{color}'>{d['val']:,.2f}</div><div style='font-size:12px; color:{color}'>{d['change']:+.2f}%</div></div>", unsafe_allow_html=True)
        st.caption("※ USD/KRW는 수출 경쟁력, US_10Y는 글로벌 유동성 지표")
    else: st.warning("거시 경제 데이터를 불러오지 못했습니다.")

# 4-2. 검색 결과 '즉시 미리보기' 섹션
if st.session_state.get('preview_list'):
    st.markdown(f"### 🔍 '{st.session_state['current_theme_name']}' 주도주 심층 분석 (미리보기)")
    st.info("💡 마음에 드는 종목의 **'📌 관심종목 등록'** 버튼을 누르면 영구 저장됩니다.")
    
    with st.spinner("주도주 심층 분석 데이터 생성 중..."):
        preview_results = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(analyze_pro, item['code'], item['name']) for item in st.session_state['preview_list']]
            for f in concurrent.futures.as_completed(futures):
                if f.result(): preview_results.append(f.result())
        preview_results.sort(key=lambda x: x['score'], reverse=True)

    for res in preview_results:
        st.markdown(create_card_html(res), unsafe_allow_html=True)
        
        with st.expander(f"📊 {res['name']} 상세 분석 및 추가"):
            col_add, col_info = st.columns([1, 5])
            with col_add:
                if st.button(f"📌 {res['name']} 관심종목 등록", key=f"add_{res['code']}"):
                    st.session_state['watchlist'][res['name']] = {'code': res['code']}
                    st.success(f"✅ {res['name']} 추가 완료!")
                    time.sleep(0.5)
                    st.rerun()
            
            # [V31.0] 차트 레이아웃 2x2 그리드 적용
            col1, col2 = st.columns(2)
            with col1:
                st.write("###### 📈 기술적 분석 & 차트")
                st.markdown(f"<div class='tech-summary'>{res['trend_txt']}</div>", unsafe_allow_html=True)
                render_tech_metrics(res['stoch'], res['vol_ratio'])
                st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
            with col2:
                st.write("###### 🏢 재무 펀더멘탈 & 실적")
                render_fund_scorecard(res['fund_data'])
                render_financial_chart(res['fin_history']) # 실적 차트
            
            st.write("###### 🧠 스마트머니 수급 분석 (20일 누적)")
            render_investor_chart(res['investor_trend']) # 수급 차트

            st.write("###### 📰 뉴스 심층 분석")
            if res['news']['method'] == "ai": st.markdown(f"<div class='news-ai'><b>🤖 AI 심층 요약:</b> {res['news']['headline']}</div>", unsafe_allow_html=True)
            else: st.markdown(f"<div class='news-fallback'><b>⚠️ 단순 키워드 분석:</b> {res['news']['headline']}</div>", unsafe_allow_html=True)
    
    st.markdown("---")

# 4-3. 나의 관심종목 (Watchlist)
st.markdown("### 🌟 나의 관심종목 (Watchlist)")
combined_watchlist = list(st.session_state['watchlist'].items())

if not combined_watchlist: 
    st.info("아직 관심종목이 없습니다. 사이드바에서 테마를 검색하여 추가해보세요.")
else:
    with st.spinner("관심종목 데이터 갱신 중..."):
        wl_results = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(analyze_pro, info['code'], name) for name, info in combined_watchlist]
            for f in concurrent.futures.as_completed(futures):
                if f.result(): wl_results.append(f.result())
        wl_results.sort(key=lambda x: x['score'], reverse=True)

    for res in wl_results:
        st.markdown(create_card_html(res), unsafe_allow_html=True)
        with st.expander(f"📊 {res['name']} 상세 분석"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("###### 📈 기술적 분석")
                st.markdown(f"<div class='tech-summary'>{res['trend_txt']}</div>", unsafe_allow_html=True)
                render_tech_metrics(res['stoch'], res['vol_ratio'])
                st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
            with col2:
                st.write("###### 🏢 재무 펀더멘탈")
                render_fund_scorecard(res['fund_data'])
                render_financial_chart(res['fin_history']) # 실적 차트
            
            st.write("###### 🧠 스마트머니 수급 분석 (20일 누적)")
            render_investor_chart(res['investor_trend']) # 수급 차트
            
            st.write("###### 📰 뉴스 심층 분석")
            if res['news']['method'] == "ai": st.markdown(f"<div class='news-ai'><b>🤖 AI 심층 요약:</b> {res['news']['headline']}</div>", unsafe_allow_html=True)
            else: st.markdown(f"<div class='news-fallback'><b>⚠️ 단순 키워드 분석:</b> {res['news']['headline']}</div>", unsafe_allow_html=True)
            st.markdown("<div class='news-scroll-box'>", unsafe_allow_html=True)
            for news in res['news']['raw_news']:
                st.markdown(f"<div class='news-box'><a href='{news['link']}' target='_blank' class='news-link'>📄 {news['title']}</a><span class='news-date'>{news['date']}</span></div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

with st.sidebar:
    st.write("### ⚙️ 기능 메뉴")
    
    with st.expander("🔍 지능형 테마/주도주 찾기", expanded=True):
        THEME_KEYWORDS = {
            "직접 입력": None,
            "반도체": "반도체",
            "2차전지": "2차전지",
            "HBM": "HBM",
            "AI/인공지능": "지능형로봇",
            "로봇": "로봇",
            "제약바이오": "제약업체",
            "자동차/부품": "자동차",
            "방위산업": "방위산업",
            "원자력발전": "원자력발전",
            "초전도체": "초전도체",
            "저PBR": "은행"
        }
        
        selected_preset = st.selectbox("⚡ 인기 테마 선택", list(THEME_KEYWORDS.keys()))
        
        with st.form(key="search_form"):
            user_input = ""
            if selected_preset == "직접 입력":
                user_input = st.text_input("검색할 테마 입력", placeholder="예: 리튬, 화장품, 엔터")
            else:
                st.info(f"✅ 선택된 테마: **{THEME_KEYWORDS[selected_preset]}**")
            
            submit_btn = st.form_submit_button("테마 분석 및 미리보기")
            
        if submit_btn:
            if selected_preset == "직접 입력": target_keyword = user_input
            else: target_keyword = THEME_KEYWORDS[selected_preset]

            if not target_keyword:
                st.warning("⚠️ 검색어를 입력하거나 테마를 선택해주세요!")
            else:
                try:
                    with st.spinner(f"네이버 금융에서 '{target_keyword}' 관련주 찾는 중... (1~7p 스캔)"):
                        raw_stocks, msg = get_naver_theme_stocks(target_keyword)
                    
                    if raw_stocks:
                        st.success(msg)
                        processed_stocks = []
                        
                        progress_text = "주도주 스코어링 분석 중..."
                        my_bar = st.progress(0, text=progress_text)
                        total_items = min(len(raw_stocks), 5) 
                        
                        for i, stock_info in enumerate(raw_stocks[:total_items]):
                            score, tags, vol, chg = calculate_sniper_score(stock_info['code'])
                            stock_info['sniper_score'] = score
                            stock_info['tags'] = tags
                            stock_info['vol_ratio'] = vol
                            stock_info['real_change'] = chg
                            processed_stocks.append(stock_info)
                            my_bar.progress((i + 1) / total_items, text=f"{stock_info['name']} 분석 완료...")
                        
                        my_bar.empty()
                        
                        processed_stocks.sort(key=lambda x: x['sniper_score'], reverse=True)
                        st.session_state['preview_list'] = processed_stocks
                        st.session_state['current_theme_name'] = target_keyword
                        st.rerun()
                    else:
                        st.error(f"❌ 결과 없음: {msg}")
                except Exception as e:
                    st.error(f"🚫 시스템 오류 발생: {str(e)}")

    if st.button("🚀 텔레그램으로 리포트 전송"):
        token = st.secrets.get("TELEGRAM_TOKEN", "")
        chat_id = st.secrets.get("CHAT_ID", "")
        if token and chat_id and 'wl_results' in locals() and wl_results:
            msg = f"💎 Quant Sniper V31.0 리포트 ({datetime.date.today()})\n\n"
            if macro: msg += f"[시장] KOSPI {macro.get('KOSPI',{'val':0})['val']:.0f}\n\n"
            for i, r in enumerate(wl_results[:3]): 
                msg += f"{i+1}. {r['name']} ({r['score']}점)\n   가격: {r['price']:,}원\n   요약: {r['news']['headline'][:50]}...\n\n"
            send_telegram_msg(token, chat_id, msg)
            st.success("전송 완료!")
        else: st.warning("설정 확인 필요")

    with st.expander("개별 종목 추가", expanded=False):
        name = st.text_input("이름"); code = st.text_input("코드")
        if st.button("추가") and name and code:
            st.session_state['watchlist'][name] = {"code": code}
            st.rerun()
    if st.button("초기화"): st.session_state['watchlist'] = {}; st.session_state['preview_list'] = []; st.rerun()
