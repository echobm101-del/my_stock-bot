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

# --- [1. 시스템 설정 및 UI 스타일링] ---
st.set_page_config(page_title="Quant Sniper V24.0", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    
    /* 지표 스타일 */
    .metric-container { background: #F9FAFB; padding: 10px; border-radius: 10px; text-align: center; border: 1px solid #E5E8EB; }
    .metric-label { font-size: 12px; color: #6B7684; font-weight: 600; }
    .metric-value { font-size: 18px; font-weight: 800; color: #333D4B; }
    .metric-up { color: #F04452; font-size: 12px; }
    .metric-down { color: #3182F6; font-size: 12px; }

    /* 뉴스 및 분석 스타일 */
    .news-ai { background: #F9FAFB; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #E5E8EB; color: #333; }
    .news-fallback { background: #FFF4E6; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #FFD8A8; color: #D9480F; font-weight: 600; }
    .news-box { padding: 8px 0; border-bottom: 1px solid #F2F4F6; font-size: 13px; }
    .news-link { color: #333; text-decoration: none; font-weight: 500; display: block; margin-bottom: 2px;}
    .news-link:hover { color: #3182F6; text-decoration: underline; }
    
    /* 버튼 스타일 커스텀 */
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# --- [2. 업종별 대장주 데이터베이스 (DB)] ---
# 팀장님의 요청대로 업종별 구분을 미리 정의해두었습니다.
SECTOR_DB = {
    "반도체": {"삼성전자":"005930", "SK하이닉스":"000660", "한미반도체":"042700", "DB하이텍":"000990", "리노공업":"058470"},
    "배터리(2차전지)": {"LG에너지솔루션":"373220", "POSCO홀딩스":"005490", "삼성SDI":"006400", "에코프로비엠":"247540", "LG화학":"051910"},
    "자동차/부품": {"현대차":"005380", "기아":"000270", "현대모비스":"012330", "HL만도":"204320"},
    "바이오/제약": {"삼성바이오로직스":"207940", "셀트리온":"068270", "유한양행":"000100", "SK바이오팜":"326030", "알테오젠":"196170"},
    "IT/플랫폼": {"NAVER":"035420", "카카오":"035720", "삼성SDS":"018260", "크래프톤":"259960"},
    "방위산업": {"한화에어로스페이스":"012450", "한국항공우주":"047810", "현대로템":"064350", "LIG넥스원":"079550"},
    "조선/해운": {"HD현대중공업":"329180", "삼성중공업":"010140", "한화오션":"042660", "HMM":"011200"},
    "전력/에너지": {"한국전력":"015760", "두산에너빌리티":"034020", "HD현대일렉트릭":"267260", "LS ELECTRIC":"010120"},
    "화학/정유": {"S-Oil":"010950", "SK이노베이션":"096770", "롯데케미칼":"011170", "금호석유":"011780"},
    "기계/건설": {"두산밥캣":"241560", "현대건설":"000720", "삼성엔지니어링":"028050", "GS건설":"006360"},
    "금융/지주": {"KB금융":"105560", "신한지주":"055550", "하나금융지주":"086790", "메리츠금융지주":"138040"},
    "엔터/게임": {"하이브":"352820", "JYP Ent.":"035900", "엔씨소프트":"036570", "넷마블":"251270"},
    "화장품/소비": {"아모레퍼시픽":"090430", "LG생활건강":"051900", "CJ제일제당":"097950", "F&F":"383220"},
    "가스/유틸": {"한국가스공사":"036460", "지역난방공사":"071320", "SK가스":"018670"},
    "디스플레이": {"LG디스플레이":"034220", "삼성전기":"009150", "이녹스첨단소재":"272290"},
    "금속/철강": {"고려아연":"010130", "현대제철":"004020", "풍산":"103140"}
}

THEME_DB = {
    "주도주(시총상위)": {"삼성전자":"005930", "SK하이닉스":"000660", "LG에너지솔루션":"373220", "삼성바이오로직스":"207940", "현대차":"005380"},
    "저PBR(밸류업)": {"현대차":"005380", "기아":"000270", "KB금융":"105560", "하나금융지주":"086790"},
    "AI/반도체 소부장": {"한미반도체":"042700", "HPSP":"403870", "이수페타시스":"007660", "리노공업":"058470"}
}

# --- [3. 데이터 로딩 및 API 설정] ---
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

@st.cache_data
def get_krx_list():
    try: df = fdr.StockListing('KRX'); return df[['Code', 'Name', 'Sector']]
    except: return pd.DataFrame()
krx_df = get_krx_list()

@st.cache_data(ttl=600)
def get_market_indices():
    """시장 지표 5개 (코스피, 코스닥, 환율, 나스닥, S&P500)"""
    try:
        now = datetime.datetime.now()
        start = now - datetime.timedelta(days=7)
        
        # 한국
        kospi = fdr.DataReader('KS11', start).iloc[-1]
        kosdaq = fdr.DataReader('KQ11', start).iloc[-1]
        usd = fdr.DataReader('USD/KRW', start).iloc[-1]
        
        # 미국 (데이터 지연 있을 수 있음)
        nasdaq = fdr.DataReader('IXIC', start).iloc[-1] 
        sp500 = fdr.DataReader('US500', start).iloc[-1]

        def get_diff(curr, prev):
            val = curr - prev
            sign = "▲" if val > 0 else "▼"
            color = "metric-up" if val > 0 else "metric-down"
            return f"{val:.2f}", sign, color

        return {
            "KOSPI": {"v": kospi['Close'], "d": get_diff(kospi['Close'], kospi['Open'])},
            "KOSDAQ": {"v": kosdaq['Close'], "d": get_diff(kosdaq['Close'], kosdaq['Open'])},
            "USD/KRW": {"v": usd['Close'], "d": get_diff(usd['Close'], usd['Open'])},
            "NASDAQ": {"v": nasdaq['Close'], "d": get_diff(nasdaq['Close'], nasdaq['Open'])},
            "S&P500": {"v": sp500['Close'], "d": get_diff(sp500['Close'], sp500['Open'])},
        }
    except: return None

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

# --- [4. 분석 엔진 (안정성 최우선)] ---

def call_gemini_auto(prompt):
    """라이브러리 없이 requests로 구글 API 직접 호출 (버전 자동 탐색)"""
    api_key = st.secrets.get("GOOGLE_API_KEY", "")
    if not api_key: return None, "NO_KEY"
    
    models = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]
    
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=6)
            if resp.status_code == 200: return resp.json(), None
            elif resp.status_code == 429: return None, "RATE_LIMIT"
        except: continue
    return None, "ALL_FAILED"

def analyze_news_by_keywords(news_titles):
    """AI 실패 시 비상용 키워드 분석"""
    pos_words = ["상승", "급등", "최고", "호재", "개선", "성장", "흑자", "수주", "돌파", "기대", "매수", "체결"]
    neg_words = ["하락", "급락", "최저", "악재", "우려", "감소", "적자", "이탈", "매도", "공매도", "지연"]
    score = 0; keywords = []
    for title in news_titles:
        for w in pos_words:
            if w in title: score += 1; keywords.append(w)
        for w in neg_words:
            if w in title: score -= 1; keywords.append(w)
    return min(max(score, -10), 10), f"키워드 감지: 긍정({len([w for w in keywords if w in pos_words])}), 부정({len([w for w in keywords if w in neg_words])})"

@st.cache_data(ttl=600)
def get_news_sentiment(company_name):
    try:
        # 안전한 URL 파싱
        query = f"{company_name} 주가"
        base_url = "https://news.google.com/rss/search"
        params = urllib.parse.urlencode({'q': query, 'hl': 'ko', 'gl': 'KR', 'ceid': 'KR:ko'})
        feed = feedparser.parse(f"{base_url}?{params}")
        
        news_titles = []; news_data = []
        for entry in feed.entries[:15]: # 15개만 분석
            date_str = time.strftime("%Y-%m-%d", entry.published_parsed) if entry.published_parsed else ""
            news_data.append({"title": entry.title, "link": entry.link, "date": date_str})
            news_titles.append(entry.title)
            
        if not news_titles: return {"score": 0, "headline": "뉴스 없음", "raw_news": [], "method": "none"}

        # AI 호출
        prompt = f"뉴스 목록: {str(news_titles)}. 주가 영향 점수(-10~10)와 한줄 요약(JSON): {{'score':0, 'summary':'내용'}}"
        res_data, err = call_gemini_auto(prompt)
        score = 0; headline = ""; method = "ai"
        
        if res_data:
            try:
                txt = res_data['candidates'][0]['content']['parts'][0]['text']
                # JSON 파싱 강화
                match = re.search(r"\{.*\}", txt, re.DOTALL)
                if match:
                    js = json.loads(match.group(0))
                    score = js.get('score', 0); headline = js.get('summary', "")
            except: err = "PARSE_ERROR"
            
        if not res_data or err:
            score, headline = analyze_news_by_keywords(news_titles)
            method = "keyword"
            
        return {"score": score, "headline": headline, "raw_news": news_data, "method": method}
    except Exception as e: return {"score": 0, "headline": f"오류: {str(e)}", "raw_news": [], "method": "error"}

@st.cache_data(ttl=1200)
def get_fundamental_score(code):
    try:
        df = stock.get_market_fundamental_by_date(datetime.datetime.now().strftime("%Y%m%d"), datetime.datetime.now().strftime("%Y%m%d"), code)
        if df.empty: 
            # 휴일이면 최근 데이터 조회
            start = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y%m%d")
            end = datetime.datetime.now().strftime("%Y%m%d")
            df = stock.get_market_fundamental_by_date(start, end, code)
            if df.empty: return 20, {"per":0, "pbr":0, "div":0}
            
        recent = df.iloc[-1]
        per = recent.get('PER', 0); pbr = recent.get('PBR', 0); div = recent.get('DIV', 0)
        
        score = 20
        if 0 < pbr < 1.0: score += 15
        elif pbr < 3.0: score += 5
        if 0 < per < 10: score += 10
        if div > 3.0: score += 5
        
        return score, {"per": per, "pbr": pbr, "div": div}
    except: return 20, {"per":0, "pbr":0, "div":0}

def analyze_stock(code, name):
    """통합 분석 함수"""
    try:
        # 1. 차트 데이터
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=365))
        if df.empty or len(df) < 60: return None
        
        # 2. 이동평균선
        for w in [5, 20, 60, 120]: df[f'MA{w}'] = df['Close'].rolling(w).mean()
        curr = df.iloc[-1]
        
        # 3. 점수 계산
        tech_score = 0
        if curr['Close'] > curr['MA5']: tech_score += 10
        if curr['Close'] > curr['MA20']: tech_score += 15
        if curr['MA5'] > curr['MA20']: tech_score += 10 # 골든크로스 구간
        
        fund_score, fund_data = get_fundamental_score(code)
        news = get_news_sentiment(name)
        
        final_score = int((tech_score * 0.4) + fund_score + news['score'])
        final_score = min(max(final_score, 0), 100)
        
        # 4. 추세 판단
        trend = "횡보/관망"
        if final_score >= 70: trend = "🚀 강력 매수 우위"
        elif final_score >= 50: trend = "📈 상승 추세"
        elif final_score <= 30: trend = "📉 하락 주의"
        
        return {
            "name": name, "code": code, "price": int(curr['Close']),
            "score": final_score,
            "trend": trend,
            "fund": fund_data,
            "news": news,
            "history": df
        }
    except: return None

def send_telegram_msg(token, chat_id, msg):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": msg})
    except: pass

# --- [5. 메인 UI 구성] ---

# (1) 상단 시장 지표 (5개 + 범례)
st.title("💎 Quant Sniper V24.0")

indices = get_market_indices()
if indices:
    st.markdown("### 🌍 글로벌 시장 지표 (실시간)")
    cols = st.columns(5)
    keys = ["KOSPI", "KOSDAQ", "USD/KRW", "NASDAQ", "S&P500"]
    for i, k in enumerate(keys):
        idx = indices[k]
        val, sign, color = idx['d']
        with cols[i]:
            st.markdown(f"""
            <div class='metric-container'>
                <div class='metric-label'>{k}</div>
                <div class='metric-value'>{idx['v']:,.2f}</div>
                <div class='{color}'>{sign} {val}</div>
            </div>
            """, unsafe_allow_html=True)
    with st.expander("ℹ️ 지표 범례 및 설명"):
        st.caption("""
        * **KOSPI/KOSDAQ:** 한국 증시의 전반적인 분위기를 나타냅니다. (상승 시 매수 유리)
        * **USD/KRW:** 환율입니다. 환율 하락(원화 강세)은 외국인 수급에 긍정적입니다.
        * **NASDAQ/S&P500:** 미국 증시입니다. 한국 시장의 선행 지표 역할을 합니다.
        """)
else: st.info("시장 데이터를 불러오는 중...")

st.markdown("---")

# (2) 메인 탭
tab_my, tab_find = st.tabs(["💼 내 포트폴리오 관리", "🔭 종목 발굴 및 검색"])

# --- TAB 1: 내 포트폴리오 ---
with tab_my:
    if not st.session_state['watchlist']:
        st.info("등록된 종목이 없습니다. '종목 발굴' 탭에서 대장주를 추가해보세요!")
    else:
        if st.button("🔄 포트폴리오 분석 실행", type="primary"):
            with st.spinner("보유 종목 정밀 분석 중..."):
                items = list(st.session_state['watchlist'].items())
                results = []
                with concurrent.futures.ThreadPoolExecutor() as exe:
                    futures = [exe.submit(analyze_stock, i['code'], n) for n, i in items]
                    for f in concurrent.futures.as_completed(futures):
                        if f.result(): results.append(f.result())
                results.sort(key=lambda x: x['score'], reverse=True)
                st.session_state['results'] = results # 결과 저장

        if 'results' in st.session_state:
            for res in st.session_state['results']:
                # 카드형 UI
                color = "#F04452" if res['score'] >= 60 else "#3182F6"
                st.markdown(f"""
                <div class='toss-card'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <div><span style='font-size:20px; font-weight:700;'>{res['name']}</span> <span style='color:#888;'>{res['code']}</span></div>
                        <div style='text-align:right;'>
                            <div style='font-size:24px; font-weight:800; color:{color};'>{res['score']}점</div>
                            <div style='font-size:12px; font-weight:bold; color:{color};'>{res['trend']}</div>
                        </div>
                    </div>
                    <div style='font-size:20px; font-weight:800; margin-top:5px;'>{res['price']:,}원</div>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander(f"📊 {res['name']} 상세 분석 보기"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**재무 상태**")
                        st.json(res['fund'])
                    with c2:
                        st.write("**뉴스 요약**")
                        if res['news']['method'] == 'ai':
                            st.success(res['news']['headline'])
                        else:
                            st.warning(res['news']['headline'])
                    
                    chart = alt.Chart(res['history'].reset_index().tail(100)).encode(x='Date:T').mark_line().encode(y=alt.Y('Close:Q', scale=alt.Scale(zero=False)))
                    st.altair_chart(chart, use_container_width=True)

# --- TAB 2: 종목 발굴 및 검색 ---
with tab_find:
    st.markdown("### 🕵️‍♂️ 무엇을 찾으시나요?")
    
    find_mode = st.radio("모드 선택", ["업종별 대장주 보기", "테마/주도주 보기", "직접 검색", "⚡ 실시간 자동 발굴(텔레그램)"], horizontal=True)
    
    if find_mode == "업종별 대장주 보기":
        selected_sector = st.selectbox("업종 선택", list(SECTOR_DB.keys()))
        st.write(f"**{selected_sector}** 대표 종목:")
        
        cols = st.columns(4)
        for i, (name, code) in enumerate(SECTOR_DB[selected_sector].items()):
            with cols[i % 4]:
                if st.button(f"+ {name}", key=f"sec_{code}"):
                    st.session_state['watchlist'][name] = {"code": code}
                    st.toast(f"✅ {name} 추가 완료!")
    
    elif find_mode == "테마/주도주 보기":
        selected_theme = st.selectbox("테마 선택", list(THEME_DB.keys()))
        for name, code in THEME_DB[selected_theme].items():
            if st.button(f"+ {name} ({code}) 추가", key=f"thm_{code}"):
                st.session_state['watchlist'][name] = {"code": code}
                st.toast(f"✅ {name} 추가 완료!")
                
    elif find_mode == "직접 검색":
        keyword = st.text_input("종목명 입력 (예: 현대차)")
        if keyword:
            found = krx_df[krx_df['Name'].str.contains(keyword)]
            if not found.empty:
                for _, row in found.iterrows():
                    if st.button(f"+ {row['Name']} ({row['Code']})", key=f"srch_{row['Code']}"):
                        st.session_state['watchlist'][row['Name']] = {"code": row['Code']}
                        st.toast(f"✅ 추가됨")
            else: st.warning("검색 결과가 없습니다.")
            
    elif find_mode == "⚡ 실시간 자동 발굴(텔레그램)":
        st.info("👉 시장 주도주(시총 상위 50개)를 실시간으로 스캔하여, '상승 추세(골든크로스)' 종목을 찾아 텔레그램으로 보냅니다.")
        if st.button("🚀 스캔 시작 및 전송", type="primary"):
            token = st.secrets.get("TELEGRAM_TOKEN")
            chat_id = st.secrets.get("CHAT_ID")
            
            if not token or not chat_id:
                st.error("Secrets에 텔레그램 토큰 설정이 필요합니다.")
            else:
                status_bar = st.progress(0)
                found_stocks = []
                
                # 시총 상위 50개만 빠르게 스캔 (속도 최적화)
                targets = fdr.StockListing('KRX').head(50)
                
                for idx, row in targets.iterrows():
                    status_bar.progress((idx + 1) / 50, text=f"{row['Name']} 분석 중...")
                    res = analyze_stock(row['Code'], row['Name'])
                    
                    # 발굴 조건: 점수 60점 이상이거나 상승 추세
                    if res and (res['score'] >= 60 or "상승" in res['trend']):
                        found_stocks.append(f"{res['name']}({res['score']}점): {res['trend']}")
                
                status_bar.progress(100, text="분석 완료!")
                
                if found_stocks:
                    msg = f"🔍 [자동 발굴 리포트]\n발견된 유망 종목:\n\n" + "\n".join(found_stocks[:10]) # 너무 길면 잘림 방지
                    send_telegram_msg(token, chat_id, msg)
                    st.success(f"✅ {len(found_stocks)}개 종목 발견! 텔레그램 전송 완료.")
                    st.write(found_stocks)
                else:
                    st.warning("현재 기준 매수 신호가 뜬 대장주가 없습니다.")
