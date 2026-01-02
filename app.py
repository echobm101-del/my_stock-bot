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

# --- [1. UI 스타일링] ---
st.set_page_config(page_title="Quant Sniper V27.1", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    .text-up { color: #F04452 !important; }
    .text-down { color: #3182F6 !important; }
    
    /* 재무 성적표 스타일 */
    .fund-grid-v2 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 10px; background-color: #F9FAFB; padding: 15px; border-radius: 12px; }
    .fund-item-v2 { text-align: center; }
    .fund-title-v2 { font-size: 12px; color: #8B95A1; margin-bottom: 5px; }
    .fund-value-v2 { font-size: 18px; font-weight: 800; color: #333D4B; }
    .fund-desc-v2 { font-size: 11px; font-weight: 600; margin-top: 4px; display: inline-block; padding: 2px 6px; border-radius: 4px;}
    
    /* 기술적 지표 직관적 스타일 */
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
</style>
""", unsafe_allow_html=True)

# --- [2. 데이터 및 설정] ---
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

@st.cache_data
def get_krx_list():
    # [V27.1 수정] 재무 데이터 백업을 위해 전체 컬럼을 다 가져오도록 수정
    try: 
        df = fdr.StockListing('KRX')
        return df # 필요한 컬럼은 나중에 추출
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
if 'temp_search_list' not in st.session_state: st.session_state['temp_search_list'] = [] 

# --- [2-1. 테마/주도주 크롤링] ---
@st.cache_data(ttl=3600)
def search_theme_stocks(keyword):
    try:
        if krx_df.empty: return []
        # Sector 컬럼이 있는지 확인
        if 'Sector' not in krx_df.columns: return []
        
        matched_krx = krx_df[krx_df['Sector'].str.contains(keyword, na=False)]
        
        if not matched_krx.empty:
            # Marcap(시가총액) 기준으로 정렬 (fdr.StockListing에는 Marcap이 보통 있음)
            sort_col = 'Marcap' if 'Marcap' in matched_krx.columns else 'Code'
            top5 = matched_krx.sort_values(by=sort_col, ascending=False).head(5)
            
            result = []
            for _, row in top5.iterrows():
                result.append({"code": row['Code'], "name": row['Name'], "desc": f"{keyword} 대장주"})
            return result
        return []
    except Exception as e:
        return []

# --- [2-2. 거시 경제 데이터] ---
@st.cache_data(ttl=3600)
def get_macro_data():
    # [V27.1 수정] 개별 Try-Except로 변경하여 하나가 실패해도 나머지는 나오도록 개선
    results = {}
    tickers = {
        "KOSPI": "KS11",
        "KOSDAQ": "KQ11",
        "S&P500": "US500",
        "USD/KRW": "USD/KRW",
        "US_10Y": "US10YT"
    }
    
    for name, code in tickers.items():
        try:
            # 최근 10일치 가져와서 마지막 값 사용 (휴장일 고려)
            df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=14))
            if not df.empty:
                curr = df.iloc[-1]
                results[name] = {
                    "val": curr['Close'],
                    "change": (curr['Close'] - curr['Open']) / curr['Open'] * 100
                }
            else:
                results[name] = {"val": 0.0, "change": 0.0} # 데이터 없음
        except:
            results[name] = {"val": 0.0, "change": 0.0} # 에러 발생 시
            
    # 전체가 다 실패했는지 확인 (다 0이면 None 리턴)
    if all(v['val'] == 0.0 for v in results.values()):
        return None
    return results

# --- [3. 분석 엔진 V27.1] ---

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    # [V27.1 수정] 1차 pykrx 실패 시 2차 StockListing 데이터 사용 (Fallback)
    try:
        # 1차 시도: Pykrx (상세 데이터)
        end_str = datetime.datetime.now().strftime("%Y%m%d")
        start_str = (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y%m%d")
        df = stock.get_market_fundamental_by_date(start_str, end_str, code)
        
        per, pbr, div = 0, 0, 0
        
        if not df.empty:
            recent = df.iloc[-1]
            per = recent.get('PER', 0); pbr = recent.get('PBR', 0); div = recent.get('DIV', 0)
        else:
            # 2차 시도: krx_df (백업 데이터)
            if not krx_df.empty and code in krx_df['Code'].values:
                row = krx_df[krx_df['Code'] == code].iloc[0]
                per = row.get('PER', 0)
                pbr = row.get('PBR', 0)
                div = row.get('DividendYield', 0) # fdr에서는 보통 DividendYield로 옴
            else:
                return 25, "데이터 없음", {}

        # 0인 경우 처리 (에러 방지)
        if per is None: per = 0
        if pbr is None: pbr = 0
        if div is None: div = 0

        pbr_stat = "good" if pbr < 1.0 else ("neu" if pbr < 2.5 else "bad")
        pbr_txt = "저평가(좋음)" if pbr < 1.0 else ("적정" if pbr < 2.5 else "고평가(주의)")
        per_stat = "good" if 0 < per < 10 else ("neu" if 10 <= per < 20 else "bad")
        per_txt = "실적우수" if 0 < per < 10 else ("보통" if 10 <= per < 20 else "고평가/적자")
        div_stat = "good" if div > 3.0 else "neu"
        div_txt = "고배당" if div > 3.0 else "일반"

        score = 20
        if pbr_stat=="good": score+=15
        if per_stat=="good": score+=10
        if div_stat=="good": score+=5
        
        fund_data = {
            "per": {"val": float(per), "stat": per_stat, "txt": per_txt},
            "pbr": {"val": float(pbr), "stat": pbr_stat, "txt": pbr_txt},
            "div": {"val": float(div), "stat": div_stat, "txt": div_txt}
        }
        return min(score, 50), "분석완료", fund_data
    except Exception as e:
        return 25, "분석실패", {}

def analyze_news_by_keywords(news_titles):
    pos_words = ["상승", "급등", "최고", "호재", "개선", "성장", "흑자", "수주", "돌파", "기대", "매수"]
    neg_words = ["하락", "급락", "최저", "악재", "우려", "감소", "적자", "이탈", "매도", "공매도"]
    
    score = 0
    found_keywords = []
    
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
    
    models_to_try = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=6)
            if response.status_code == 200:
                return response.json(), None
            elif response.status_code == 429:
                return None, "RATE_LIMIT"
        except: continue
            
    return None, "ALL_FAILED"

@st.cache_data(ttl=600)
def get_news_sentiment(company_name):
    try:
        query = f"{company_name} 주가"
        encoded_query = urllib.parse.quote(query)
        base_url = "https://news.google.com/rss/search"
        params = f"?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        rss_url = base_url + params
        
        feed = feedparser.parse(rss_url)
        news_titles = []
        news_data = []
        
        for entry in feed.entries[:20]: 
            title = entry.title
            link = entry.link
            date = entry.published_parsed
            date_str = time.strftime("%Y-%m-%d", date) if date else ""
            news_data.append({"title": title, "link": link, "date": date_str})
            news_titles.append(title)
            
        if not news_titles:
            return {"score": 0, "headline": "관련 뉴스 없음", "raw_news": [], "method": "none"}

        # AI 호출
        prompt = f"""
        뉴스 목록: {str(news_titles)}
        위 뉴스를 분석하여 주가 영향 점수(-10~10)와 한줄 요약을 JSON으로 작성하라.
        형식: {{ "score": 0, "summary": "내용" }}
        """
        
        res_data, error_code = call_gemini_auto(prompt)
        score = 0; headline = ""; method = "ai"
        
        if res_data:
            try:
                raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
                res_json = json.loads(raw_text)
                score = res_json.get('score', 0)
                headline = res_json.get('summary', "")
            except: error_code = "PARSE_ERROR"
        
        if not res_data or error_code:
            score, headline = analyze_news_by_keywords(news_titles)
            method = "keyword"

        return {"score": score, "headline": headline, "raw_news": news_data, "method": method}
    except Exception as e:
        return {"score": 0, "headline": f"오류: {str(e)}", "raw_news": [], "method": "error"}

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
        
        search_name = name_override if name_override else code
        news = get_news_sentiment(search_name)

        # 이평선
        df['MA5'] = df['Close'].rolling(5).mean(); df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean(); df['MA120'] = df['Close'].rolling(120).mean()
        df['MA240'] = df['Close'].rolling(240).mean()
        
        # 볼린저 밴드
        df['std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['MA20'] + (df['std'] * 2)
        df['BB_Lower'] = df['MA20'] - (df['std'] * 2)

        # 거래량 분석
        df['Vol_MA20'] = df['Volume'].rolling(20).mean()

        # 스토캐스틱
        n = 14; m = 3; t = 3
        df['L14'] = df['Low'].rolling(window=n).min()
        df['H14'] = df['High'].rolling(window=n).max()
        df['%K'] = (df['Close'] - df['L14']) / (df['H14'] - df['L14']) * 100
        df['%D'] = df['%K'].rolling(window=m).mean() 
        df['%J'] = df['%D'].rolling(window=t).mean() 
        
        curr = df.iloc[-1]
        pass_cnt = 0
        ma_status = []
        mas = [('5일', 'MA5'), ('20일', 'MA20'), ('60일', 'MA60'), ('120일', 'MA120'), ('240일', 'MA240')]
        
        for label, col in mas:
            if curr['Close'] >= curr[col]: 
                pass_cnt += 1
                ma_status.append({"label": label, "ok": True})
            else:
                ma_status.append({"label": label, "ok": False})
        
        tech_score = (pass_cnt * 6) + (10 if curr['MA5'] > curr['MA20'] > curr['MA60'] else 0) + (10 if sup['f'] > 0 else 0)
        
        if curr['%K'] < 20: tech_score += 5 
        elif 20 <= curr['%K'] <= 80 and curr['%K'] > curr['%D']: tech_score += 5

        if pass_cnt >= 4: trend_txt = "🚀 강력한 상승 추세"
        elif pass_cnt >= 3: trend_txt = "📈 상승세 (양호)"
        elif pass_cnt >= 1: trend_txt = "📉 하락 중 반등 시도"
        else: trend_txt = "☠️ 완전 역배열"
        
        final_score = int((tech_score * 0.5) + fund_score + news['score'])
        final_score = min(max(final_score, 0), 100)
        
        return {
            "name": name_override, "code": code, "price": int(curr['Close']),
            "score": final_score, 
            "strategy": {"buy": int(curr['MA20']), "target": int(curr['Close']*1.1), "action": "매수" if final_score>=60 else "관망"},
            "fund_data": fund_data, "ma_status": ma_status, "trend_txt": trend_txt,
            "news": news, "history": df, "supply": sup,
            "stoch": {"k": curr['%K'], "d": curr['%J']},
            "vol_ratio": curr['Volume'] / curr['Vol_MA20'] if curr['Vol_MA20'] > 0 else 1.0
        }
    except Exception as e: 
        return None

def create_card_html(res):
    score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
    return textwrap.dedent(f"""
    <div class='toss-card'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div><span class='stock-name'>{res['name']}</span><span class='stock-code'>{res['code']}</span><div class='big-price'>{res['price']:,}원</div></div>
            <div style='text-align:right;'><div style='font-size:28px; font-weight:800; color:{score_col};'>{res['score']}점</div><div class='badge-clean' style='background-color:{score_col}20; color:{score_col};'>{res['strategy']['action']}</div></div>
        </div>
        <div style='margin-top:10px; color:#666; font-size:13px;'>
            {res['trend_txt']}
        </div>
    </div>
    """)

# 차트: 가격 + 볼린저밴드 (깔끔한 버전)
def create_chart_clean(df):
    chart_data = df.tail(120).reset_index()
    
    # 1. Price Chart Base
    base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=alt.Axis(format='%m-%d', title=None)))
    
    # 2. Bollinger Band (Area) - Grey
    band = base.mark_area(opacity=0.15, color='#868E96').encode(
        y=alt.Y('BB_Lower:Q', title='주가/BB'),
        y2='BB_Upper:Q'
    )
    
    # 3. Lines (Price & MA)
    line = base.mark_line(color='#000000').encode(y='Close:Q') # Black: Price
    ma20 = base.mark_line(color='#F2A529').encode(y='MA20:Q') # Yellow: 20MA
    ma60 = base.mark_line(color='#3182F6').encode(y='MA60:Q') # Blue: 60MA
    
    return (band + line + ma20 + ma60).properties(height=250)

# 직관적인 기술적 지표 UI (신호등 방식)
def render_tech_metrics(stoch, vol_ratio):
    k = stoch['k']
    
    # 스토캐스틱 상태 판단
    if k < 20:
        stoch_txt = f"🟢 침체 구간 ({k:.1f}%)"
        stoch_sub = "매수 기회 탐색"
        stoch_cls = "buy"
    elif k > 80:
        stoch_txt = f"🔴 과열 구간 ({k:.1f}%)"
        stoch_sub = "매도/조정 주의"
        stoch_cls = "sell"
    else:
        stoch_txt = f"⚪ 중립 구간 ({k:.1f}%)"
        stoch_sub = "추세 지속"
        stoch_cls = ""

    # 거래량 상태 판단
    if vol_ratio >= 2.0:
        vol_txt = f"🔥 거래량 폭발 ({vol_ratio*100:.0f}%)"
        vol_cls = "vol"
    elif vol_ratio >= 1.2:
        vol_txt = f"📈 거래량 증가 ({vol_ratio*100:.0f}%)"
        vol_cls = "buy"
    else:
        vol_txt = "☁️ 거래량 평이"
        vol_cls = ""

    st.markdown(f"""
    <div class='tech-status-box'>
        <div class='status-badge {stoch_cls}'>
            <div>📊 스토캐스틱</div>
            <div style='font-size:16px; margin-top:4px;'>{stoch_txt}</div>
            <div style='font-size:11px; opacity:0.8;'>{stoch_sub}</div>
        </div>
        <div class='status-badge {vol_cls}'>
            <div>📢 거래강도(전일비)</div>
            <div style='font-size:16px; margin-top:4px;'>{vol_txt}</div>
            <div style='font-size:11px; opacity:0.8;'>평소보다 {vol_ratio:.1f}배 활발</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# 차트 색상 범례 (Legend)
def render_chart_legend():
    return """
    <div style='display:flex; gap:12px; font-size:12px; color:#555; margin-bottom:8px; align-items:center;'>
        <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#000000; margin-right:4px;'></div>현재가(검정)</div>
        <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#F2A529; margin-right:4px;'></div>20일선(황색)</div>
        <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#3182F6; margin-right:4px;'></div>60일선(파랑)</div>
        <div style='display:flex; align-items:center;'><div style='width:12px; height:12px; background:#868E96; opacity:0.3; margin-right:4px;'></div>볼린저밴드(회색)</div>
    </div>
    """

# 재무 펀더멘탈 성적표
def render_fund_scorecard(fund_data):
    if not fund_data: 
        st.info("재무 정보가 없습니다.")
        return

    per_col = "#F04452" if fund_data['per']['stat']=='good' else ("#3182F6" if fund_data['per']['stat']=='bad' else "#333")
    pbr_col = "#F04452" if fund_data['pbr']['stat']=='good' else ("#3182F6" if fund_data['pbr']['stat']=='bad' else "#333")
    div_col = "#F04452" if fund_data['div']['stat']=='good' else "#333"

    st.markdown(f"""
    <div class='fund-grid-v2'>
        <div class='fund-item-v2'>
            <div class='fund-title-v2'>PER (주가수익비율)</div>
            <div class='fund-value-v2' style='color:{per_col}'>{fund_data['per']['val']:.1f}배</div>
            <div class='fund-desc-v2' style='background-color:{per_col}20; color:{per_col}'>{fund_data['per']['txt']}</div>
        </div>
        <div class='fund-item-v2'>
            <div class='fund-title-v2'>PBR (주가순자산비율)</div>
            <div class='fund-value-v2' style='color:{pbr_col}'>{fund_data['pbr']['val']:.1f}배</div>
            <div class='fund-desc-v2' style='background-color:{pbr_col}20; color:{pbr_col}'>{fund_data['pbr']['txt']}</div>
        </div>
        <div class='fund-item-v2'>
            <div class='fund-title-v2'>배당수익률</div>
            <div class='fund-value-v2' style='color:{div_col}'>{fund_data['div']['val']:.1f}%</div>
            <div class='fund-desc-v2' style='background-color:{div_col}20; color:{div_col}'>{fund_data['div']['txt']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def send_telegram_msg(token, chat_id, msg):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": msg}
    requests.post(url, data=data)

# --- [4. 메인 화면] ---
st.title("💎 Quant Sniper V27.1")

# 거시 경제
with st.expander("🌍 글로벌 거시 경제 대시보드 (Click to Open)", expanded=False):
    macro = get_macro_data()
    if macro:
        c1, c2, c3, c4, c5 = st.columns(5)
        cols = [c1, c2, c3, c4, c5]
        keys = ["KOSPI", "KOSDAQ", "S&P500", "USD/KRW", "US_10Y"]
        
        for i, key in enumerate(keys):
            d = macro.get(key, {"val": 0.0, "change": 0.0}) # 안전장치
            color = "#F04452" if d['change'] > 0 else "#3182F6"
            with cols[i]:
                st.markdown(f"""
                <div class='metric-box'>
                    <div class='metric-title'>{key}</div>
                    <div class='metric-value' style='color:{color}'>{d['val']:,.2f}</div>
                    <div style='font-size:12px; color:{color}'>{d['change']:+.2f}%</div>
                </div>
                """, unsafe_allow_html=True)
        st.caption("※ USD/KRW는 수출 경쟁력, US_10Y는 글로벌 유동성 지표")
    else:
        st.warning("거시 경제 데이터를 불러오지 못했습니다.")

# 통합 리스트
combined_watchlist = list(st.session_state['watchlist'].items())

if st.session_state['temp_search_list']:
    st.info(f"🔍 테마/주도주 검색 결과 {len(st.session_state['temp_search_list'])}개를 포함하여 분석합니다.")
    for item in st.session_state['temp_search_list']:
        combined_watchlist.append((item['name'], {"code": item['code']}))

if not combined_watchlist: 
    st.info("종목을 추가하거나, 사이드바에서 '테마/주도주 검색'을 이용하세요.")
else:
    with st.spinner("시장 데이터 및 AI 분석 중... (관심종목 + 추천주)"):
        results = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(analyze_pro, info['code'], name) for name, info in combined_watchlist]
            for f in concurrent.futures.as_completed(futures):
                if f.result(): results.append(f.result())
        results.sort(key=lambda x: x['score'], reverse=True)

    for res in results:
        st.markdown(create_card_html(res), unsafe_allow_html=True)
        
        with st.expander(f"📊 {res['name']} 상세 분석"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write("###### 📈 기술적 분석")
                st.markdown(f"<div class='tech-summary'>{res['trend_txt']}</div>", unsafe_allow_html=True)
                
                # 신호등 UI
                render_tech_metrics(res['stoch'], res['vol_ratio'])
                
                # 차트 범례 표시
                st.markdown(render_chart_legend(), unsafe_allow_html=True)
                
                # 차트 출력
                st.altair_chart(create_chart_clean(res['history']), use_container_width=True)

            with col2:
                st.write("###### 🏢 재무 펀더멘탈")
                # 재무 성적표 UI
                render_fund_scorecard(res['fund_data'])
                
                st.write("###### 🔍 이동평균선 상태")
                ma_html = ""
                for m in res['ma_status']:
                    cls = "ma-ok" if m['ok'] else ""
                    ma_html += f"<span class='ma-badge {cls}'>{m['label']}</span>"
                st.markdown(f"<div>{ma_html}</div>", unsafe_allow_html=True)

            st.write("###### 📰 뉴스 심층 분석 & VIX 체크")
            if res['news']['method'] == "ai":
                 st.markdown(f"<div class='news-ai'><b>🤖 AI 심층 요약:</b> {res['news']['headline']}</div>", unsafe_allow_html=True)
            else:
                 st.markdown(f"<div class='news-fallback'><b>⚠️ 단순 키워드 분석 (AI 연결 실패):</b> {res['news']['headline']}</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='news-scroll-box'>", unsafe_allow_html=True)
            for news in res['news']['raw_news']:
                st.markdown(f"<div class='news-box'><a href='{news['link']}' target='_blank' class='news-link'>📄 {news['title']}</a><span class='news-date'>{news['date']}</span></div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

with st.sidebar:
    st.write("### ⚙️ 기능 메뉴")
    
    with st.expander("🔍 테마/주도주 찾기", expanded=False):
        theme_keyword = st.text_input("업종/테마 (예: 반도체, 2차전지)")
        if st.button("검색 및 분석 추가"):
            if theme_keyword:
                found_stocks = search_theme_stocks(theme_keyword)
                if found_stocks:
                    st.session_state['temp_search_list'] = found_stocks
                    st.success(f"{len(found_stocks)}개 주도주 발견! 메인 화면을 확인하세요.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("검색 결과가 없습니다.")
        
        if st.button("검색 결과 초기화"):
            st.session_state['temp_search_list'] = []
            st.rerun()

    if st.button("🚀 텔레그램으로 리포트 전송"):
        token = st.secrets.get("TELEGRAM_TOKEN", "")
        chat_id = st.secrets.get("CHAT_ID", "")
        
        if token and chat_id and 'results' in locals() and results:
            try:
                msg = f"💎 Quant Sniper V27.1 리포트 ({datetime.date.today()})\n\n"
                
                if macro:
                    msg += f"[시장상황] 코스피 {macro.get('KOSPI', {'val':0})['val']:.0f} / 환율 {macro.get('USD/KRW', {'val':0})['val']:.0f}\n\n"

                for i, r in enumerate(results[:3]): 
                    msg += f"{i+1}. {r['name']} ({r['score']}점)\n"
                    msg += f"   - 현재가: {r['price']:,}원\n"
                    msg += f"   - 전략: {r['strategy']['action']} (목표 {r['strategy']['target']:,})\n"
                    msg += f"   - AI요약: {r['news']['headline'][:50]}...\n\n"
                
                send_telegram_msg(token, chat_id, msg)
                st.success("✅ 전송 완료! 텔레그램을 확인하세요.")
            except Exception as e:
                st.error(f"전송 실패: {e}")
        else:
            st.warning("⚠️ 분석 결과가 없거나 API 키 설정이 필요합니다.")

    with st.expander("개별 종목 추가", expanded=True):
        name = st.text_input("이름"); code = st.text_input("코드")
        if st.button("추가") and name and code:
            st.session_state['watchlist'][name] = {"code": code}
            st.rerun()
    if st.button("초기화"): st.session_state['watchlist'] = {}; st.session_state['temp_search_list'] = []; st.rerun()
