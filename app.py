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
st.set_page_config(page_title="Quant Sniper V27.0", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    
    /* 지표 스타일 */
    .metric-container { background: #F9FAFB; padding: 12px; border-radius: 12px; text-align: center; border: 1px solid #E5E8EB; height: 100%; }
    .metric-label { font-size: 13px; color: #6B7684; font-weight: 600; margin-bottom: 4px; }
    .metric-value { font-size: 20px; font-weight: 800; color: #333D4B; }
    .metric-status { font-size: 12px; font-weight: 700; margin-top: 4px; }
    .status-good { color: #F04452; background-color: rgba(240, 68, 82, 0.1); padding: 2px 6px; border-radius: 4px; }
    .status-bad { color: #3182F6; background-color: rgba(49, 130, 246, 0.1); padding: 2px 6px; border-radius: 4px; }
    
    /* 뉴스 및 분석 스타일 */
    .news-ai { background: #F9FAFB; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #E5E8EB; color: #333; }
    .news-fallback { background: #FFF4E6; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #FFD8A8; color: #D9480F; font-weight: 600; }
    .news-box { padding: 8px 0; border-bottom: 1px solid #F2F4F6; font-size: 13px; }
    .news-link { color: #333; text-decoration: none; font-weight: 500; display: block; margin-bottom: 2px;}
    .news-link:hover { color: #3182F6; text-decoration: underline; }
    
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# --- [2. 통합 데이터베이스] ---
SECTOR_DB = {
    "반도체": {"삼성전자":"005930", "SK하이닉스":"000660", "한미반도체":"042700", "DB하이텍":"000990", "리노공업":"058470", "HPSP":"403870", "이수페타시스":"007660"},
    "배터리(2차전지)": {"LG에너지솔루션":"373220", "POSCO홀딩스":"005490", "삼성SDI":"006400", "에코프로비엠":"247540", "LG화학":"051910", "포스코퓨처엠":"003670", "에코프로":"086520"},
    "자동차/부품": {"현대차":"005380", "기아":"000270", "현대모비스":"012330", "HL만도":"204320", "현대위아":"011210"},
    "바이오/제약": {"삼성바이오로직스":"207940", "셀트리온":"068270", "유한양행":"000100", "SK바이오팜":"326030", "알테오젠":"196170", "HLB":"028300"},
    "IT/플랫폼": {"NAVER":"035420", "카카오":"035720", "삼성SDS":"018260", "크래프톤":"259960", "카카오뱅크":"323410"},
    "방위산업": {"한화에어로스페이스":"012450", "한국항공우주":"047810", "현대로템":"064350", "LIG넥스원":"079550", "한화시스템":"272210"},
    "조선/해운": {"HD현대중공업":"329180", "삼성중공업":"010140", "한화오션":"042660", "HMM":"011200", "HD한국조선해양":"009540"},
    "전력/에너지": {"한국전력":"015760", "두산에너빌리티":"034020", "HD현대일렉트릭":"267260", "LS ELECTRIC":"010120"},
    "금융/지주": {"KB금융":"105560", "신한지주":"055550", "하나금융지주":"086790", "메리츠금융지주":"138040", "우리금융지주":"316140", "기업은행":"024110"},
    "엔터/게임": {"하이브":"352820", "JYP Ent.":"035900", "엔씨소프트":"036570", "넷마블":"251270", "펄어비스":"263750", "에스엠":"041510"}
}

THEME_DB = {
    "주도주(시총상위)": {"삼성전자":"005930", "SK하이닉스":"000660", "LG에너지솔루션":"373220", "삼성바이오로직스":"207940", "현대차":"005380"},
    "저PBR(밸류업)": {"현대차":"005380", "기아":"000270", "KB금융":"105560", "하나금융지주":"086790", "기업은행":"024110"}
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
        now = datetime.datetime.now(); start = now - datetime.timedelta(days=10)
        
        # 1. KOSPI
        kospi = fdr.DataReader('KS11', start).iloc[-1]
        # 2. USD/KRW (환율)
        usd = fdr.DataReader('USD/KRW', start).iloc[-1]
        # 3. US 10Y Treasury (미국 국채 10년물 - 금리 대용)
        us10y = fdr.DataReader('US10YT', start).iloc[-1]
        # 4. Crude Oil (WTI 유가) - FRED 심볼 'DCOILWTICO' 대신 fdr의 'CL=F' (선물) 사용 권장되나 단순화
        # fdr에서 유가/금 데이터는 종종 티커가 변경됨. 안정적인 'CL=F'(WTI), 'GC=F'(Gold) 사용
        oil = fdr.DataReader('CL=F', start).iloc[-1] # WTI Crude Oil
        # 5. Gold (금)
        gold = fdr.DataReader('GC=F', start).iloc[-1] 

        def analyze_index(name, curr, open_price):
            diff = curr - open_price
            sign = "▲" if diff > 0 else "▼"
            
            # 상태 판단 (환율, 금리, 유가는 오르면 주식에 보통 부정적)
            if name in ["USD/KRW", "미국채10년", "WTI유가"]:
                status = "하락(긍정)" if diff < 0 else "상승(부정)"
                css = "status-good" if diff < 0 else "status-bad"
            else:
                status = "상승(긍정)" if diff > 0 else "하락(부정)"
                css = "status-good" if diff > 0 else "status-bad"
            
            # 소수점 처리
            fmt = "{:,.2f}"
            
            return {"v": curr, "d": diff, "s": sign, "st": status, "css": css, "fmt": fmt}

        return {
            "KOSPI": analyze_index("KOSPI", kospi['Close'], kospi['Open']),
            "USD/KRW": analyze_index("USD/KRW", usd['Close'], usd['Open']),
            "미국채10년": analyze_index("미국채10년", us10y['Close'], us10y['Open']),
            "WTI유가": analyze_index("WTI유가", oil['Close'], oil['Open']),
            "금(Gold)": analyze_index("금(Gold)", gold['Close'], gold['Open']),
        }
    except Exception as e:
        # 에러 시 None 반환하여 UI에서 처리
        return None

# [GitHub 연동 복구] - 이 부분이 포트폴리오를 살려냅니다.
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

# 세션 상태 초기화 시 GitHub 데이터 로드
if 'watchlist' not in st.session_state or not st.session_state['watchlist']:
    st.session_state['watchlist'] = load_from_github()

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
    return min(max(score, -10), 10), f"키워드 감지: 긍정({score if score>0 else 0}), 부정({abs(score) if score<0 else 0})"

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
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=365))
        if df.empty or len(df) < 60: return None
        
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        curr = df.iloc[-1]
        
        is_good_tech = curr['Close'] >= curr['MA20']
        
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

        fund_score, fund_data = get_fundamental_score(code)
        
        is_my_stock = name in st.session_state['watchlist']
        if is_good_tech or is_my_stock:
             news = get_news_sentiment(name)
        else:
             news = {"score": 0, "headline": "기술적 지표 부진으로 AI 분석 생략", "raw_news": [], "method": "skip"}

        final_score = int((tech_score * 0.4) + fund_score + news['score'])
        final_score = min(max(final_score, 0), 100)
        
        return {
            "name": name, "code": code, "price": int(curr['Close']),
            "score": final_score, "trend": trend,
            "fund": fund_data, "news": news, "history": df
        }
    except: return None

def send_telegram_msg(token, chat_id, msg):
    try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": msg})
    except: pass

def get_target_list(mode, sub_category=None):
    targets = {}
    if mode == "전체":
        try:
            top50 = fdr.StockListing('KRX').head(50)
            for _, r in top50.iterrows(): targets[r['Code']] = r['Name']
        except: pass
        for cat in SECTOR_DB:
            for n, c in SECTOR_DB[cat].items(): targets[c] = n
        for cat in THEME_DB:
            for n, c in THEME_DB[cat].items(): targets[c] = n
    elif mode == "업종별" and sub_category:
        for n, c in SECTOR_DB.get(sub_category, {}).items(): targets[c] = n
    elif mode == "테마별" and sub_category:
        for n, c in THEME_DB.get(sub_category, {}).items(): targets[c] = n
    return targets

# --- [5. 메인 화면 구성] ---
st.title("💎 Quant Sniper V27.0 (Final)")

# (1) 시장 지표 (5종: 코스피, 환율, 금리, 유가, 금)
indices = get_market_indices()
if indices:
    st.markdown("### 🌍 글로벌 주요 지표 (실시간)")
    cols = st.columns(5)
    keys = ["KOSPI", "USD/KRW", "미국채10년", "WTI유가", "금(Gold)"]
    for i, k in enumerate(keys):
        idx = indices.get(k)
        if idx:
            with cols[i]:
                st.markdown(f"""
                <div class='metric-container'>
                    <div class='metric-label'>{k}</div>
                    <div class='metric-value'>{idx['v']:,.2f}</div>
                    <div class='metric-status {idx['css']}'>{idx['s']} {idx['d']:.2f} ({idx['st']})</div>
                </div>
                """, unsafe_allow_html=True)
else: st.warning("시장 지표 데이터를 불러오는 중 오류가 발생했거나 장 운영 시간이 아닙니다.")

with st.expander("ℹ️ 지표 해석 가이드"):
    st.markdown("""
    * **USD/KRW (환율):** 하락(▼)해야 외국인 수급에 유리합니다.
    * **미국채10년 (금리):** 하락(▼)해야 성장주(기술주)에 유리합니다.
    * **WTI유가:** 너무 오르면 물가 상승 압박으로 악재가 됩니다.
    """)

st.markdown("---")

# (2) 탭 구성
tab_pf, tab_scan = st.tabs(["💼 내 포트폴리오 (복구완료)", "🔭 통합 종목 스캔"])

# --- TAB 1: 내 포트폴리오 ---
with tab_pf:
    st.subheader("📌 나의 관심 종목")
    
    if not st.session_state['watchlist']:
        st.warning("저장된 종목이 없습니다. (GitHub 파일이 비어있거나 연동 실패)")
    else:
        if st.button("🔄 포트폴리오 새로고침 및 분석", type="primary"):
            with st.spinner("내 종목들 정밀 진단 중..."):
                items = list(st.session_state['watchlist'].items())
                results = []
                with concurrent.futures.ThreadPoolExecutor() as exe:
                    futures = [exe.submit(analyze_stock, i['code'], n) for n, i in items]
                    for f in concurrent.futures.as_completed(futures):
                        if f.result(): results.append(f.result())
                st.session_state['pf_results'] = sorted(results, key=lambda x: x['score'], reverse=True)

        if 'pf_results' in st.session_state:
            for r in st.session_state['pf_results']:
                c = "#F04452" if r['score']>=60 else "#3182F6"
                st.markdown(f"""
                <div class='toss-card'>
                    <div style='display:flex; justify-content:space-between;'>
                        <div><span style='font-size:18px; font-weight:700;'>{r['name']}</span> <span style='color:#888; font-size:12px;'>{r['code']}</span></div>
                        <div style='text-align:right;'>
                            <div style='font-size:24px; font-weight:800; color:{c};'>{r['score']}점</div>
                            <div style='font-size:12px; font-weight:bold; color:{c};'>{r['trend']}</div>
                        </div>
                    </div>
                    <div style='font-size:20px; font-weight:800; margin-top:5px;'>{r['price']:,}원</div>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander(f"📊 {r['name']} 상세 리포트"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("📋 **펀더멘탈**")
                        st.write(f"PER: {r['fund']['per']:.1f} | PBR: {r['fund']['pbr']:.1f} | 배당: {r['fund']['div']:.1f}%")
                    with c2:
                        st.write("📰 **뉴스 요약**")
                        if r['news']['method'] == 'ai': st.success(r['news']['headline'])
                        elif r['news']['method'] == 'keyword': st.warning(r['news']['headline'])
                        else: st.caption("분석 생략")
                    
                    chart = alt.Chart(r['history'].reset_index().tail(100)).encode(x='Date:T', y=alt.Y('Close:Q', scale=alt.Scale(zero=False))).mark_line()
                    st.altair_chart(chart, use_container_width=True)

# --- TAB 2: 통합 스캔 ---
with tab_scan:
    st.subheader("🕵️‍♂️ 시장 주도주 발굴")
    scan_type = st.radio("스캔 대상", ["전체 통합 스캔 (약 150개)", "카테고리별 스캔"], horizontal=True)
    
    target_dict = {}
    scan_title = ""
    
    if scan_type == "전체 통합 스캔 (약 150개)":
        target_dict = get_target_list("전체")
        scan_title = "전체 통합"
    else:
        cat_type = st.selectbox("대분류", ["업종별", "테마별"])
        if cat_type == "업종별":
            sub = st.selectbox("세부 업종", list(SECTOR_DB.keys()))
            target_dict = get_target_list("업종별", sub)
            scan_title = sub
        else:
            sub = st.selectbox("세부 테마", list(THEME_DB.keys()))
            target_dict = get_target_list("테마별", sub)
            scan_title = sub
            
    if st.button("⚡ 스캔 시작 (텔레그램 전송)", type="primary"):
        token = st.secrets.get("TELEGRAM_TOKEN"); chat_id = st.secrets.get("CHAT_ID")
        
        if not token or not chat_id: st.error("Secrets 설정 필요")
        else:
            bar = st.progress(0, text="데이터 수집 중...")
            found = []
            cnt = 0
            total = len(target_dict)
            
            for code, name in target_dict.items():
                cnt += 1
                bar.progress(cnt/total, text=f"[{cnt}/{total}] {name} 분석 중...")
                res = analyze_stock(code, name)
                if res and res['score'] >= 60:
                    found.append(res)
                    time.sleep(0.5)
            
            bar.progress(100, text="완료!")
            
            if found:
                found.sort(key=lambda x: x['score'], reverse=True)
                msg = f"💎 [Quant Sniper] {scan_title} 발굴 ({datetime.datetime.now().strftime('%m/%d %H:%M')})\n\n"
                for i, r in enumerate(found[:10]):
                    msg += f"{i+1}. {r['name']} ({r['score']}점)\n   가격: {r['price']:,}원 ({r['trend']})\n   요약: {r['news']['headline'][:30]}..\n\n"
                
                send_telegram_msg(token, chat_id, msg)
                st.success(f"✅ {len(found)}개 발견! 텔레그램 전송 완료.")
                
                st.write("### 🎯 발굴된 종목")
                for r in found[:10]:
                    c1, c2 = st.columns([4, 1])
                    with c1: st.write(f"**{r['name']}** ({r['score']}점)")
                    with c2: 
                        if st.button(f"추가", key=f"add_{r['code']}"):
                            st.session_state['watchlist'][r['name']] = {"code": r['code']}
                            st.toast(f"추가됨!")
            else:
                st.warning("조건에 맞는 종목이 없습니다.")
