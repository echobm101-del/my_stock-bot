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
st.set_page_config(page_title="Quant Sniper V25.0", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    .text-up { color: #F04452 !important; }
    .text-down { color: #3182F6 !important; }
    
    .fund-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 10px; }
    .fund-item { padding: 12px; border-radius: 12px; text-align: center; }
    .fund-label { font-size: 12px; color: #6B7684; margin-bottom: 4px; }
    .fund-val { font-size: 16px; font-weight: 800; color: #333D4B; }
    .fund-badge { font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; margin-left: 4px; display:inline-block; }
    
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
if 'temp_search_list' not in st.session_state: st.session_state['temp_search_list'] = [] 

# --- [2-1. 테마/주도주 크롤링] ---
@st.cache_data(ttl=3600)
def search_theme_stocks(keyword):
    """네이버 금융 등에서 테마/섹터 주도주 검색"""
    try:
        matched_krx = krx_df[krx_df['Sector'].str.contains(keyword, na=False)]
        
        if not matched_krx.empty:
            end_date = datetime.datetime.now().strftime("%Y%m%d")
            cap_df = stock.get_market_cap(end_date)
            merged = pd.merge(matched_krx, cap_df, left_on='Code', right_index=True)
            top5 = merged.sort_values(by='시가총액', ascending=False).head(5)
            
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
    try:
        ks11 = fdr.DataReader('KS11', datetime.datetime.now()-datetime.timedelta(days=7)).iloc[-1]
        kq11 = fdr.DataReader('KQ11', datetime.datetime.now()-datetime.timedelta(days=7)).iloc[-1]
        us500 = fdr.DataReader('US500', datetime.datetime.now()-datetime.timedelta(days=7)).iloc[-1]
        usd_krw = fdr.DataReader('USD/KRW', datetime.datetime.now()-datetime.timedelta(days=7)).iloc[-1]
        us_10y = fdr.DataReader('US10YT', datetime.datetime.now()-datetime.timedelta(days=7)).iloc[-1]
        
        return {
            "KOSPI": {"val": ks11['Close'], "change": (ks11['Close'] - ks11['Open']) / ks11['Open'] * 100},
            "KOSDAQ": {"val": kq11['Close'], "change": (kq11['Close'] - kq11['Open']) / kq11['Open'] * 100},
            "S&P500": {"val": us500['Close'], "change": (us500['Close'] - us500['Open']) / us500['Open'] * 100},
            "USD/KRW": {"val": usd_krw['Close'], "change": (usd_krw['Close'] - usd_krw['Open']) / usd_krw['Open'] * 100},
            "US_10Y": {"val": us_10y['Close'], "change": (us_10y['Close'] - us_10y['Open']) / us_10y['Open'] * 100},
        }
    except:
        return None

# --- [3. 분석 엔진 V25.0] ---

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
        
        # [V25.0 추가] 볼린저 밴드 계산
        df['std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['MA20'] + (df['std'] * 2)
        df['BB_Lower'] = df['MA20'] - (df['std'] * 2)

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
            "stoch": {"k": curr['%K'], "d": curr['%J']}
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

# [V25.0 수정] 차트: 가격 + 볼린저밴드 + 거래량 + 스토캐스틱
def create_chart_advanced(df):
    chart_data = df.tail(120).reset_index()
    
    # 1. Price Chart Base
    base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=alt.Axis(format='%m-%d', title=None)))
    
    # 2. Bollinger Band (Area)
    band = base.mark_area(opacity=0.15, color='#868E96').encode(
        y=alt.Y('BB_Lower:Q', title='주가/BB'),
        y2='BB_Upper:Q'
    )
    
    # 3. Lines (Price & MA)
    line = base.mark_line(color='#000000').encode(y='Close:Q')
    ma20 = base.mark_line(color='#F2A529').encode(y='MA20:Q')
    ma60 = base.mark_line(color='#3182F6').encode(y='MA60:Q')
    
    # Combine Price Chart
    price_chart = (band + line + ma20 + ma60).properties(height=200)
    
    # 4. Volume Chart
    vol = base.mark_bar(color='#E5E8EB').encode(y=alt.Y('Volume:Q', title="거래량")).properties(height=60)
    
    # 5. Stochastic Chart
    stoch_k = base.mark_line(color='#F04452').encode(y=alt.Y('%K:Q', title="Stoch"))
    stoch_d = base.mark_line(color='#3182F6').encode(y='%J:Q')
    band_low = base.mark_rule(color='gray', strokeDash=[2,2]).encode(y=alt.datum(20))
    band_high = base.mark_rule(color='gray', strokeDash=[2,2]).encode(y=alt.datum(80))
    stoch_chart = (stoch_k + stoch_d + band_low + band_high).properties(height=80)

    return alt.vconcat(price_chart, vol, stoch_chart).resolve_scale(x='shared')

def create_fund_chart(fund_data):
    if not fund_data: return None
    
    data = [
        {"Index": "PER", "Value": min(fund_data['per']['val'], 50), "Label": f"{fund_data['per']['val']:.1f}", "Color": "#F04452" if fund_data['per']['stat']=='good' else "#ADB5BD"},
        {"Index": "PBR", "Value": min(fund_data['pbr']['val'], 5) * 10, "Label": f"{fund_data['pbr']['val']:.1f}", "Color": "#F04452" if fund_data['pbr']['stat']=='good' else "#ADB5BD"},
        {"Index": "배당", "Value": fund_data['div']['val'] * 5, "Label": f"{fund_data['div']['val']:.1f}%", "Color": "#F04452" if fund_data['div']['stat']=='good' else "#ADB5BD"}
    ]
    df = pd.DataFrame(data)
    
    base = alt.Chart(df).encode(
        x=alt.X('Index', title=None),
        y=alt.Y('Value', title=None, axis=None),
        color=alt.Color('Color', scale=None)
    )
    bar = base.mark_bar().properties(height=150)
    text = base.mark_text(dy=-10).encode(text='Label')
    
    return (bar + text)

def send_telegram_msg(token, chat_id, msg):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": msg}
    requests.post(url, data=data)

# --- [4. 메인 화면] ---
st.title("💎 Quant Sniper V25.0")

# 거시 경제
with st.expander("🌍 글로벌 거시 경제 대시보드 (Click to Open)", expanded=False):
    macro = get_macro_data()
    if macro:
        c1, c2, c3, c4, c5 = st.columns(5)
        cols = [c1, c2, c3, c4, c5]
        keys = ["KOSPI", "KOSDAQ", "S&P500", "USD/KRW", "US_10Y"]
        
        for i, key in enumerate(keys):
            d = macro[key]
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
                st.write("###### 📈 기술적 분석 (Price+Bollinger / Vol / Stoch)")
                st.markdown(f"<div class='tech-summary'>{res['trend_txt']}</div>", unsafe_allow_html=True)
                ma_html = ""
                for m in res['ma_status']:
                    cls = "ma-ok" if m['ok'] else ""
                    ma_html += f"<span class='ma-badge {cls}'>{m['label']}</span>"
                st.markdown(f"<div>{ma_html}</div>", unsafe_allow_html=True)
                # 차트 출력
                st.altair_chart(create_chart_advanced(res['history']), use_container_width=True)

            with col2:
                st.write("###### 🏢 재무 펀더멘탈")
                fd = res['fund_data']
                if fd:
                    fund_chart = create_fund_chart(fd)
                    if fund_chart: st.altair_chart(fund_chart, use_container_width=True)
                    
                    st.markdown(f"""
                    <div class='fund-grid'>
                        <div class='fund-item'>
                            <div class='fund-label'>PER</div><div class='fund-val'>{fd['per']['val']:.1f}</div>
                        </div>
                        <div class='fund-item'>
                            <div class='fund-label'>PBR</div><div class='fund-val'>{fd['pbr']['val']:.1f}</div>
                        </div>
                        <div class='fund-item'>
                            <div class='fund-label'>배당률</div><div class='fund-val'>{fd['div']['val']:.1f}%</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

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
                msg = f"💎 Quant Sniper V25.0 리포트 ({datetime.date.today()})\n\n"
                
                if macro:
                    msg += f"[시장상황] 코스피 {macro['KOSPI']['val']:.0f}({macro['KOSPI']['change']:.2f}%) / 환율 {macro['USD/KRW']['val']:.0f}\n\n"

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
