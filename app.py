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
import google.generativeai as genai

# --- [1. 설정 및 UI 스타일링] ---
st.set_page_config(page_title="Quant Sniper V19.1", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    .text-up { color: #F04452 !important; }   
    .text-down { color: #3182F6 !important; } 
    .text-gray { color: #8B95A1 !important; } 
    .big-price { font-size: 32px; font-weight: 800; letter-spacing: -0.5px; color: #191F28; }
    .stock-name { font-size: 22px; font-weight: 700; color: #333D4B; }
    .stock-code { font-size: 14px; color: #8B95A1; margin-left: 6px; font-weight: 500; }
    .badge-clean { padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700; display: inline-block; }
    .badge-ma { background: #F2F4F6; color: #4E5968; padding: 4px 8px; border-radius: 6px; font-size: 11px; margin-right: 4px; font-weight: 600; display: inline-block; margin-bottom: 4px; }
    .badge-ma-good { background: rgba(240, 68, 82, 0.1); color: #F04452; }
    
    .fund-box { background: #F9FAFB; padding: 12px; border-radius: 12px; text-align: center; border: 1px solid #F2F4F6; }
    .fund-label { font-size: 11px; color: #8B95A1; margin-bottom: 4px; }
    .fund-val { font-size: 14px; font-weight: 700; color: #333D4B; }

    .strategy-box { background-color: #F2F4F6; border-radius: 12px; padding: 15px; font-size: 13px; margin-top: 12px; display: flex; justify-content: space-around; text-align: center; }
    .strategy-item { display: flex; flex-direction: column; }
    .strategy-label { color: #8B95A1; font-size: 11px; margin-bottom: 4px; }
    .strategy-val { color: #333D4B; font-weight: 800; font-size: 14px; }
    
    .news-item { font-size: 13px; padding: 8px 0; border-bottom: 1px solid #F2F4F6; color: #333; }
    .news-time { font-size: 11px; color: #8B95A1; margin-right: 6px; }
    
    .legend-table { width: 100%; font-size: 14px; border-collapse: collapse; margin-top: 5px; }
    .legend-table td { padding: 12px; border-bottom: 1px solid #F2F4F6; color: #333D4B; vertical-align: middle; }
    .legend-header { font-weight: 800; background: #F9FAFB; text-align: center; padding: 10px; border-radius: 8px; display: block;}
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

# --- [3. 분석 엔진 V19.1] ---

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    try:
        end_str = datetime.datetime.now().strftime("%Y%m%d")
        start_str = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_fundamental_by_date(start_str, end_str, code)
        if df.empty: return 25, "데이터 없음", {"per":0, "pbr":0, "div":0}
        
        recent = df.iloc[-1]
        per = recent['PER']; pbr = recent['PBR']; div = recent['DIV']
        
        score = 20; reasons = []
        if 0 < pbr < 1.0: score += 15; reasons.append("저PBR")
        elif pbr < 2.0: score += 5
        if 0 < per < 10: score += 10; reasons.append("저PER")
        if div > 3.0: score += 5; reasons.append("고배당")
        
        return min(score, 50), ", ".join(reasons) if reasons else "평이", {"per":per, "pbr":pbr, "div":div}
    except: return 25, "분석 불가", {"per":0, "pbr":0, "div":0}

@st.cache_data(ttl=600)
def get_news_sentiment(code):
    try:
        url = f"https://finance.naver.com/item/news_news.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.content, "html.parser")
        titles = soup.select(".title .tit")
        
        news_list = []
        if titles:
            for t in titles[:5]: # 상위 5개만 추출
                news_list.append(t.get_text().strip())
        else:
            news_list = ["관련 뉴스 없음"]

        # Gemini 호출
        score = 0; headline = news_list[0]
        try:
            if "GOOGLE_API_KEY" in st.secrets:
                genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"주식뉴스분석: {str(news_list)}. 점수(-10~10)와 한줄요약 JSON으로: {{'score':int, 'summary':str}}"
                response = model.generate_content(prompt)
                res_json = json.loads(response.text.replace("```json","").replace("```","").strip())
                score = res_json.get('score', 0)
                headline = res_json.get('summary', headline)
            else:
                headline = "API키 미설정 (단순수집)"
        except:
            headline = "AI 분석 지연 (단순수집)"

        return {"score": score, "headline": headline, "raw_news": news_list}
    except: return {"score": 0, "headline": "뉴스 수집 실패", "raw_news": []}

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
        fund_score, fund_reason, fund_data = get_company_guide_score(code)
        news = get_news_sentiment(code)

        df['MA5'] = df['Close'].rolling(5).mean(); df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean(); df['MA120'] = df['Close'].rolling(120).mean()
        df['MA240'] = df['Close'].rolling(240).mean()
        
        delta = df['Close'].diff(1)
        rsi = 100 - (100/(1 + (delta.where(delta>0,0).rolling(14).mean() / -delta.where(delta<0,0).rolling(14).mean())))
        curr = df.iloc[-1]
        
        tech_score = 0; ma_badges = []
        mas = [('5일', 'MA5'), ('20일', 'MA20'), ('60일', 'MA60'), ('120일', 'MA120'), ('240일', 'MA240')]
        cnt = 0
        for label, col in mas:
            if curr['Close'] >= curr[col]: 
                cnt += 1
                ma_badges.append(f"<span class='badge-ma badge-ma-good'>✅ {label}</span>")
            else:
                ma_badges.append(f"<span class='badge-ma'>❌ {label}</span>")
                
        tech_score += (cnt * 6)
        if curr['MA5'] > curr['MA20'] > curr['MA60']: tech_score += 10
        if sup['f'] > 0: tech_score += 10
        
        final_score = int((tech_score * 0.5) + fund_score + news['score'])
        final_score = min(max(final_score, 0), 100)
        
        target = curr['Close'] * (1 + (0.05 + final_score/1000))
        
        return {
            "name": name_override, "code": code, "price": int(curr['Close']),
            "score": final_score, "rsi": rsi.iloc[-1],
            "checks": [fund_reason, "AI분석" if news['score']!=0 else "뉴스"],
            "strategy": {"buy": int(curr['MA20']), "target": int(target), "action": "매수" if final_score>=60 else "관망"},
            "fund_data": fund_data, "ma_html": "".join(ma_badges), "news": news, "history": df, "supply": sup
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
        <div class='strategy-box'>
            <div class='strategy-item'><span class='strategy-label'>적정 매수가</span><span class='strategy-val'>{res['strategy']['buy']:,}</span></div>
            <div class='strategy-item'><span class='strategy-label'>목표가</span><span class='strategy-val text-up'>{res['strategy']['target']:,}</span></div>
            <div class='strategy-item'><span class='strategy-label'>핵심 진단</span><span class='strategy-val'>{res['checks'][0]}</span></div>
        </div>
    </div>
    """)

def create_chart(df):
    chart_data = df.tail(120).reset_index()
    base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=alt.Axis(format='%m-%d', title=None)))
    line = base.mark_line(color='#000000').encode(y=alt.Y('Close:Q', scale=alt.Scale(zero=False)))
    ma20 = base.mark_line(color='#F2A529', strokeWidth=2).encode(y='MA20:Q') # 황금선
    ma60 = base.mark_line(color='#3182F6', strokeWidth=2).encode(y='MA60:Q') # 수급선
    return (line + ma20 + ma60).properties(height=250)

# --- [4. 메인 화면] ---
st.title("💎 Quant Sniper V19.1")

tab1, tab2 = st.tabs(["💼 포트폴리오", "🔭 발굴"])

with tab1:
    if not st.session_state['watchlist']: st.info("종목을 추가해주세요.")
    else:
        with st.spinner("분석 중..."):
            # 병렬 처리로 속도 최적화
            watchlist_items = list(st.session_state['watchlist'].items())
            results = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(analyze_pro, info['code'], name) for name, info in watchlist_items]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): results.append(f.result())
            results.sort(key=lambda x: x['score'], reverse=True)

        for res in results:
            st.markdown(create_card_html(res), unsafe_allow_html=True)
            
            with st.expander(f"📊 {res['name']} 상세 분석 리포트"):
                # 1. 기술적 분석 (가로 배치)
                st.write("###### 📈 기술적 추세 (이평선)")
                st.markdown(res['ma_html'], unsafe_allow_html=True)
                
                # 2. 재무 상태 (박스형)
                st.write("###### 🏢 재무 펀더멘탈 (Fundamental)")
                f_cols = st.columns(3)
                fd = res['fund_data']
                with f_cols[0]: st.markdown(f"<div class='fund-box'><div class='fund-label'>PER (주가수익)</div><div class='fund-val'>{fd['per']:.1f}배</div></div>", unsafe_allow_html=True)
                with f_cols[1]: st.markdown(f"<div class='fund-box'><div class='fund-label'>PBR (자산가치)</div><div class='fund-val'>{fd['pbr']:.1f}배</div></div>", unsafe_allow_html=True)
                with f_cols[2]: st.markdown(f"<div class='fund-box'><div class='fund-label'>배당수익률</div><div class='fund-val'>{fd['div']:.1f}%</div></div>", unsafe_allow_html=True)
                
                # 3. 뉴스 리스트 (제미나이 + 원문)
                st.write("###### 📰 주요 뉴스 (Top 5)")
                if "API키" in res['news']['headline'] or "지연" in res['news']['headline']:
                     st.warning(f"⚠️ AI 분석 불가: {res['news']['headline']} (GitHub requirements.txt를 확인하세요)")
                else:
                     st.info(f"🤖 AI 요약: {res['news']['headline']}")
                
                for news_title in res['news']['raw_news']:
                    st.markdown(f"<div class='news-item'>📄 {news_title}</div>", unsafe_allow_html=True)

                # 4. 차트
                st.write("###### 📉 주가 차트 (120일)")
                st.altair_chart(create_chart(res['history']), use_container_width=True)
                st.caption("검은선: 주가 | 황금선: 20일(생명선) | 파란선: 60일(수급선) | 데이터: FinanceDataReader")

with st.sidebar:
    with st.expander("종목 추가", expanded=True):
        name = st.text_input("이름"); code = st.text_input("코드")
        if st.button("추가") and name and code:
            st.session_state['watchlist'][name] = {"code": code}
            st.rerun()
    if st.button("초기화"): st.session_state['watchlist'] = {}; st.rerun()
