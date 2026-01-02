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
st.set_page_config(page_title="Quant Sniper V20.0", page_icon="💎", layout="wide")

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
    .news-ai { background: #F9FAFB; padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #E5E8EB; }
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

# --- [3. 분석 엔진 V20.0 (멀티 모델 접속기)] ---

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

# [V20.0 핵심] 모든 모델을 순서대로 두드려보는 함수
def call_gemini_direct(prompt):
    api_key = st.secrets.get("GOOGLE_API_KEY", "")
    if not api_key: return None, "API 키가 Secrets에 없습니다."
    
    # 1순위부터 3순위까지 모델 리스트
    models_to_try = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-pro"
    ]
    
    last_error = ""
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=8)
            if response.status_code == 200:
                # 성공하면 바로 리턴
                return response.json(), None
            else:
                # 실패하면 에러 기록하고 다음 모델로 넘어감
                last_error = f"{model_name} 실패({response.status_code})"
                continue 
        except Exception as e:
            last_error = str(e)
            continue
            
    return None, f"모든 모델 연결 실패: {last_error}"

@st.cache_data(ttl=600)
def get_news_sentiment(company_name):
    try:
        query = f"{company_name} 주가"
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        
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
            return {"score": 0, "headline": "관련 뉴스 없음", "raw_news": []}

        # Gemini 호출
        score = 0; headline = news_titles[0]
        
        prompt = f"""
        뉴스 목록: {str(news_titles)}
        위 뉴스를 분석하여 주가 영향 점수(-10~10)와 한줄 요약을 JSON으로 작성하라.
        형식: {{ "score": 0, "summary": "내용" }}
        """
        
        res_data, error_msg = call_gemini_direct(prompt)
        
        if res_data:
            try:
                raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
                res_json = json.loads(raw_text)
                score = res_json.get('score', 0)
                headline = res_json.get('summary', headline)
            except:
                headline = "AI 응답 해석 오류"
        else:
            headline = f"AI 연결 최종 실패: {error_msg}"

        return {"score": score, "headline": headline, "raw_news": news_data}
    except Exception as e:
        return {"score": 0, "headline": f"시스템 오류: {str(e)}", "raw_news": []}

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

        df['MA5'] = df['Close'].rolling(5).mean(); df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean(); df['MA120'] = df['Close'].rolling(120).mean()
        df['MA240'] = df['Close'].rolling(240).mean()
        
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
            "news": news, "history": df, "supply": sup
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
        <div style='margin-top:10px; color:#666; font-size:13px;'>
            {res['trend_txt']}
        </div>
    </div>
    """)

def create_chart(df):
    chart_data = df.tail(120).reset_index()
    base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=alt.Axis(format='%m-%d', title=None)))
    line = base.mark_line(color='#000000').encode(y=alt.Y('Close:Q', scale=alt.Scale(zero=False)))
    ma20 = base.mark_line(color='#F2A529').encode(y='MA20:Q')
    ma60 = base.mark_line(color='#3182F6').encode(y='MA60:Q')
    return (line + ma20 + ma60).properties(height=250)

# --- [4. 메인 화면] ---
st.title("💎 Quant Sniper V20.0")

if not st.session_state['watchlist']: st.info("종목을 추가해주세요.")
else:
    with st.spinner("AI가 여러 모델을 순차적으로 연결 중입니다..."):
        watchlist_items = list(st.session_state['watchlist'].items())
        results = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(analyze_pro, info['code'], name) for name, info in watchlist_items]
            for f in concurrent.futures.as_completed(futures):
                if f.result(): results.append(f.result())
        results.sort(key=lambda x: x['score'], reverse=True)

    for res in results:
        st.markdown(create_card_html(res), unsafe_allow_html=True)
        
        with st.expander(f"📊 {res['name']} 상세 분석"):
            st.write("###### 📈 기술적 분석")
            st.markdown(f"<div class='tech-summary'>{res['trend_txt']}</div>", unsafe_allow_html=True)
            ma_html = ""
            for m in res['ma_status']:
                cls = "ma-ok" if m['ok'] else ""
                ma_html += f"<span class='ma-badge {cls}'>{m['label']}</span>"
            st.markdown(f"<div>{ma_html}</div>", unsafe_allow_html=True)
            
            st.write("###### 🏢 재무 펀더멘탈")
            fd = res['fund_data']
            if fd:
                st.markdown(f"""
                <div class='fund-grid'>
                    <div class='fund-item'>
                        <div class='fund-label'>PER</div><div class='fund-val'>{fd['per']['val']:.1f}배</div><div class='fund-badge' style='color:{'#F04452' if fd['per']['stat']=='good' else '#3182F6'}'>{fd['per']['txt']}</div>
                    </div>
                    <div class='fund-item'>
                        <div class='fund-label'>PBR</div><div class='fund-val'>{fd['pbr']['val']:.1f}배</div><div class='fund-badge' style='color:{'#F04452' if fd['pbr']['stat']=='good' else '#3182F6'}'>{fd['pbr']['txt']}</div>
                    </div>
                    <div class='fund-item'>
                        <div class='fund-label'>배당률</div><div class='fund-val'>{fd['div']['val']:.1f}%</div><div class='fund-badge' style='color:{'#F04452' if fd['div']['stat']=='good' else '#3182F6'}'>{fd['div']['txt']}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.write("###### 📰 구글 뉴스 AI 요약")
            if "실패" in res['news']['headline']:
                 st.error(f"⚠️ {res['news']['headline']}")
            else:
                st.markdown(f"<div class='news-ai'><b>🤖 AI 요약:</b> {res['news']['headline']}</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='news-scroll-box'>", unsafe_allow_html=True)
            for news in res['news']['raw_news']:
                st.markdown(f"<div class='news-box'><a href='{news['link']}' target='_blank' class='news-link'>📄 {news['title']}</a><span class='news-date'>{news['date']}</span></div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.altair_chart(create_chart(res['history']), use_container_width=True)

with st.sidebar:
    with st.expander("종목 추가", expanded=True):
        name = st.text_input("이름"); code = st.text_input("코드")
        if st.button("추가") and name and code:
            st.session_state['watchlist'][name] = {"code": code}
            st.rerun()
    if st.button("초기화"): st.session_state['watchlist'] = {}; st.rerun()
