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
st.set_page_config(page_title="Quant Sniper V25.0", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    .metric-container { background: #F9FAFB; padding: 10px; border-radius: 10px; text-align: center; border: 1px solid #E5E8EB; }
    .metric-label { font-size: 12px; color: #6B7684; font-weight: 600; }
    .metric-value { font-size: 18px; font-weight: 800; color: #333D4B; }
    .metric-up { color: #F04452; font-size: 12px; }
    .metric-down { color: #3182F6; font-size: 12px; }
    .news-ai { background: #F9FAFB; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #E5E8EB; color: #333; }
    .news-fallback { background: #FFF4E6; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #FFD8A8; color: #D9480F; font-weight: 600; }
    .news-box { padding: 8px 0; border-bottom: 1px solid #F2F4F6; font-size: 13px; }
    .news-link { color: #333; text-decoration: none; font-weight: 500; display: block; margin-bottom: 2px;}
    .news-link:hover { color: #3182F6; text-decoration: underline; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# --- [2. 통합 데이터베이스 (정책/테마/주도주)] ---
SECTOR_DB = {
    "반도체": {"삼성전자":"005930", "SK하이닉스":"000660", "한미반도체":"042700", "DB하이텍":"000990", "리노공업":"058470", "HPSP":"403870"},
    "배터리(2차전지)": {"LG에너지솔루션":"373220", "POSCO홀딩스":"005490", "삼성SDI":"006400", "에코프로비엠":"247540", "LG화학":"051910", "포스코퓨처엠":"003670"},
    "자동차/부품": {"현대차":"005380", "기아":"000270", "현대모비스":"012330", "HL만도":"204320"},
    "바이오/제약": {"삼성바이오로직스":"207940", "셀트리온":"068270", "유한양행":"000100", "SK바이오팜":"326030", "알테오젠":"196170", "HLB":"028300"},
    "IT/플랫폼": {"NAVER":"035420", "카카오":"035720", "삼성SDS":"018260", "크래프톤":"259960"},
    "방위산업": {"한화에어로스페이스":"012450", "한국항공우주":"047810", "현대로템":"064350", "LIG넥스원":"079550", "한화시스템":"272210"},
    "조선/해운": {"HD현대중공업":"329180", "삼성중공업":"010140", "한화오션":"042660", "HMM":"011200"},
    "전력/에너지": {"한국전력":"015760", "두산에너빌리티":"034020", "HD현대일렉트릭":"267260", "LS ELECTRIC":"010120", "효성중공업":"298040"},
    "화학/정유": {"S-Oil":"010950", "SK이노베이션":"096770", "롯데케미칼":"011170", "금호석유":"011780"},
    "기계/건설": {"두산밥캣":"241560", "현대건설":"000720", "삼성엔지니어링":"028050", "GS건설":"006360"},
    "금융/지주": {"KB금융":"105560", "신한지주":"055550", "하나금융지주":"086790", "메리츠금융지주":"138040"},
    "엔터/게임": {"하이브":"352820", "JYP Ent.":"035900", "엔씨소프트":"036570", "넷마블":"251270", "펄어비스":"263750"},
    "화장품/소비": {"아모레퍼시픽":"090430", "LG생활건강":"051900", "CJ제일제당":"097950", "F&F":"383220", "삼양식품":"003230"},
    "가스/유틸": {"한국가스공사":"036460", "지역난방공사":"071320", "SK가스":"018670"},
    "디스플레이": {"LG디스플레이":"034220", "삼성전기":"009150", "이녹스첨단소재":"272290"},
    "금속/철강": {"고려아연":"010130", "현대제철":"004020", "풍산":"103140"}
}

THEME_DB = {
    "주도주(시총상위)": {"삼성전자":"005930", "SK하이닉스":"000660", "LG에너지솔루션":"373220", "삼성바이오로직스":"207940", "현대차":"005380"},
    "저PBR(밸류업)": {"현대차":"005380", "기아":"000270", "KB금융":"105560", "하나금융지주":"086790", "기업은행":"024110"},
    "AI/반도체 소부장": {"한미반도체":"042700", "HPSP":"403870", "이수페타시스":"007660", "리노공업":"058470", "제우스":"079370"}
}

# --- [3. 데이터 및 API 설정] ---
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
    try:
        now = datetime.datetime.now(); start = now - datetime.timedelta(days=7)
        kospi = fdr.DataReader('KS11', start).iloc[-1]
        kosdaq = fdr.DataReader('KQ11', start).iloc[-1]
        usd = fdr.DataReader('USD/KRW', start).iloc[-1]
        nasdaq = fdr.DataReader('IXIC', start).iloc[-1]
        sp500 = fdr.DataReader('US500', start).iloc[-1]

        def get_diff(curr, prev):
            val = curr - prev; sign = "▲" if val > 0 else "▼"; color = "metric-up" if val > 0 else "metric-down"
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

# --- [4. 분석 엔진] ---

def call_gemini_auto(prompt):
    api_key = st.secrets.get("GOOGLE_API_KEY", "")
    if not api_key: return None, "NO_KEY"
    models = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=5)
            if resp.status_code == 200: return resp.json(), None
            elif resp.status_code == 429: return None, "RATE_LIMIT"
        except: continue
    return None, "ALL_FAILED"

def analyze_news_by_keywords(news_titles):
    pos = ["상승","급등","최고","호재","개선","성장","흑자","수주","돌파","기대","매수","체결","양호"]
    neg = ["하락","급락","최저","악재","우려","감소","적자","이탈","매도","공매도","지연","둔화"]
    score = 0
    for t in news_titles:
        for w in pos: 
            if w in t: score+=1
        for w in neg:
            if w in t: score-=1
    return min(max(score, -10), 10), f"키워드: 긍정({score if score>0 else 0}), 부정({abs(score) if score<0 else 0})"

@st.cache_data(ttl=600)
def get_news_sentiment(company_name):
    try:
        query = f"{company_name} 주가"
        encoded_query = urllib.parse.quote(query)
        base_url = "https://news.google.com/rss/search"
        params = f"?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(base_url + params)
        
        titles = []; data = []
        for e in feed.entries[:15]:
            d = time.strftime("%Y-%m-%d", e.published_parsed) if e.published_parsed else ""
            data.append({"title": e.title, "link": e.link, "date": d})
            titles.append(e.title)
            
        if not titles: return {"score": 0, "headline": "뉴스 없음", "raw_news": [], "method": "none"}

        prompt = f"뉴스 목록: {str(titles)}. 주가 영향 점수(-10~10)와 한줄 요약(JSON): {{'score':0, 'summary':'내용'}}"
        res_data, err = call_gemini_auto(prompt)
        score = 0; headline = ""; method = "ai"
        
        if res_data:
            try:
                txt = res_data['candidates'][0]['content']['parts'][0]['text']
                match = re.search(r"\{.*\}", txt, re.DOTALL)
                if match:
                    js = json.loads(match.group(0))
                    score = js.get('score', 0); headline = js.get('summary', "")
            except: err = "PARSE_ERROR"
        
        if not res_data or err:
            score, headline = analyze_news_by_keywords(titles)
            method = "keyword"
            
        return {"score": score, "headline": headline, "raw_news": data, "method": method}
    except: return {"score": 0, "headline": "분석 오류", "raw_news": [], "method": "error"}

@st.cache_data(ttl=1200)
def get_fundamental_score(code):
    try:
        end = datetime.datetime.now().strftime("%Y%m%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_fundamental_by_date(start, end, code)
        if df.empty: return 20, {"per":0, "pbr":0, "div":0}
        rec = df.iloc[-1]
        score = 20
        if 0 < rec['PBR'] < 1.0: score += 15
        elif rec['PBR'] < 3.0: score += 5
        if 0 < rec['PER'] < 10: score += 10
        if rec['DIV'] > 3.0: score += 5
        return score, {"per": rec['PER'], "pbr": rec['PBR'], "div": rec['DIV']}
    except: return 20, {"per":0, "pbr":0, "div":0}

def analyze_stock(code, name):
    try:
        # 1. 기술적 분석 (가장 빠름 - 1차 필터)
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=365))
        if df.empty or len(df) < 60: return None
        
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        curr = df.iloc[-1]
        
        # 2. 필터링: 역배열이거나 급락 중이면 뉴스 분석 생략 (시간/API 절약)
        # 단, 내 포트폴리오에 있는건 무조건 분석
        is_uptrend = curr['Close'] > curr['MA20'] or curr['MA5'] > curr['MA20']
        
        tech_score = 0
        if curr['Close'] > curr['MA5']: tech_score += 10
        if curr['Close'] > curr['MA20']: tech_score += 15
        if curr['MA5'] > curr['MA20']: tech_score += 10
        
        pass_cnt = 0
        if curr['Close'] >= curr['MA5']: pass_cnt +=1
        if curr['Close'] >= curr['MA20']: pass_cnt +=1
        if curr['Close'] >= curr['MA60']: pass_cnt +=1
        
        if pass_cnt >= 2: trend = "📈 상승 추세"
        elif pass_cnt == 1: trend = "⚖️ 보합/전환"
        else: trend = "📉 하락 우세"

        # 3. 펀더멘탈
        fund_score, fund_data = get_fundamental_score(code)
        
        # 4. 뉴스 (가장 느림 - AI)
        # 여기서 '전체 스캔 모드'일 때는 429 방지를 위해 조금 쉼
        news = get_news_sentiment(name)
        
        final_score = int((tech_score * 0.4) + fund_score + news['score'])
        final_score = min(max(final_score, 0), 100)
        
        return {
            "name": name, "code": code, "price": int(curr['Close']),
            "score": final_score, "trend": trend,
            "fund": fund_data, "news": news, "history": df,
            "ma_ok": [curr['Close']>=curr[c] for c in ['MA5','MA20','MA60']]
        }
    except: return None

def send_telegram_msg(token, chat_id, msg):
    try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": msg})
    except: pass

def get_all_target_codes():
    """Top 50 + 섹터 + 테마주 중복 제거하여 리스트 생성"""
    targets = {} # code: name
    
    # 1. Top 50
    try:
        top50 = fdr.StockListing('KRX').head(50)
        for _, r in top50.iterrows(): targets[r['Code']] = r['Name']
    except: pass
    
    # 2. Sector DB
    for cat in SECTOR_DB:
        for name, code in SECTOR_DB[cat].items(): targets[code] = name
            
    # 3. Theme DB
    for cat in THEME_DB:
        for name, code in THEME_DB[cat].items(): targets[code] = name
            
    return targets

# --- [5. 메인 화면] ---
st.title("💎 Quant Sniper V25.0 (Masterpiece)")

indices = get_market_indices()
if indices:
    st.markdown("### 🌍 글로벌 시장 (실시간)")
    cols = st.columns(5)
    keys = ["KOSPI", "KOSDAQ", "USD/KRW", "NASDAQ", "S&P500"]
    for i, k in enumerate(keys):
        idx = indices[k]; val, sign, color = idx['d']
        with cols[i]:
            st.markdown(f"<div class='metric-container'><div class='metric-label'>{k}</div><div class='metric-value'>{idx['v']:,.2f}</div><div class='{color}'>{sign} {val}</div></div>", unsafe_allow_html=True)
else: st.info("시장 지표 로딩 중...")

st.markdown("---")
tab1, tab2 = st.tabs(["💼 포트폴리오", "🔭 통합 스캔 (발굴)"])

with tab1:
    if not st.session_state['watchlist']: st.info("종목이 없습니다. 옆 탭에서 발굴해보세요!")
    else:
        if st.button("🔄 내 종목 분석"):
            with st.spinner("분석 중..."):
                items = list(st.session_state['watchlist'].items())
                res_list = []
                with concurrent.futures.ThreadPoolExecutor() as exe:
                    futures = [exe.submit(analyze_stock, i['code'], n) for n, i in items]
                    for f in concurrent.futures.as_completed(futures):
                        if f.result(): res_list.append(f.result())
                st.session_state['results'] = sorted(res_list, key=lambda x: x['score'], reverse=True)
        
        if 'results' in st.session_state:
            for r in st.session_state['results']:
                c = "#F04452" if r['score']>=60 else "#3182F6"
                st.markdown(f"<div class='toss-card'><div style='display:flex; justify-content:space-between;'><div><span style='font-size:18px; font-weight:700;'>{r['name']}</span></div><div style='text-align:right;'><div style='font-size:24px; font-weight:800; color:{c};'>{r['score']}점</div><div style='font-size:12px; font-weight:bold; color:{c};'>{r['trend']}</div></div></div><div style='font-size:20px; font-weight:800;'>{r['price']:,}원</div></div>", unsafe_allow_html=True)
                with st.expander("상세 보기"):
                    st.write(f"PER: {r['fund']['per']:.1f} | PBR: {r['fund']['pbr']:.1f}"); st.info(r['news']['headline'])
                    st.altair_chart(alt.Chart(r['history'].reset_index().tail(100)).encode(x='Date:T', y=alt.Y('Close:Q', scale=alt.Scale(zero=False))).mark_line(), use_container_width=True)

with tab2:
    st.subheader("🚀 전 종목 통합 스캔 & 텔레그램 리포트")
    st.info("대한민국 상위 50위 + 정책/테마/업종 대표주 등 약 150개 종목을 한 번에 스캔합니다.")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write("옵션: 분석 시간이 1~3분 정도 소요될 수 있습니다.")
    with col2:
        start_scan = st.button("⚡ 통합 스캔 시작", type="primary")

    if start_scan:
        token = st.secrets.get("TELEGRAM_TOKEN"); chat_id = st.secrets.get("CHAT_ID")
        if not token or not chat_id: st.error("Secrets 설정 필요")
        else:
            targets = get_all_target_codes()
            total = len(targets)
            bar = st.progress(0, text=f"대상 종목 수집 완료: {total}개. 분석 시작...")
            
            found = []
            cnt = 0
            
            # 순차 처리 (API 과부하 방지)
            for code, name in targets.items():
                cnt += 1
                bar.progress(cnt/total, text=f"[{cnt}/{total}] {name} 분석 중...")
                
                # 1. 기술적 분석만 먼저 빠르게 확인 (1차 필터)
                try:
                    df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=60))
                    if df.empty: continue
                    curr = df.iloc[-1]['Close']; ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    
                    # 20일선 위에 있는 종목만 정밀 분석 (시간 절약 핵심)
                    if curr >= ma20:
                        # 정밀 분석 수행 (AI 뉴스 등)
                        full_res = analyze_stock(code, name)
                        if full_res and full_res['score'] >= 60:
                            found.append(full_res)
                            time.sleep(1) # API 쉼표
                except: continue
            
            bar.progress(100, text="분석 완료! 결과 정리 중...")
            
            # 결과 정렬 및 전송
            found.sort(key=lambda x: x['score'], reverse=True)
            top_picks = found[:10] # 상위 10개만
            
            msg = f"💎 [Quant Sniper] 통합 발굴 리포트\n({datetime.datetime.now().strftime('%m/%d %H:%M')})\n\n"
            msg += f"🔍 총 {total}개 스캔 -> {len(found)}개 유망주 발견!\n\n"
            
            for rank, r in enumerate(top_picks):
                icon = "🔥" if r['score'] >= 80 else "✅"
                msg += f"{rank+1}. {r['name']} ({r['score']}점) {icon}\n"
                msg += f"   현재가: {r['price']:,}원\n"
                msg += f"   추세: {r['trend']}\n"
                msg += f"   요약: {r['news']['headline'][:30]}..\n\n"
            
            send_telegram_msg(token, chat_id, msg)
            st.success(f"✅ 텔레그램 전송 완료! (발견된 종목: {len(found)}개)")
            
            # 화면에도 표시
            for r in top_picks:
                st.markdown(f"**{r['name']}** ({r['score']}점): {r['news']['headline']}")
