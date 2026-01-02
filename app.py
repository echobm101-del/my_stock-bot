import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
import json
import base64
import altair as alt
from pykrx import stock
import concurrent.futures
import time
import feedparser
import urllib.parse
import re

# --- [1. 기본 설정] ---
st.set_page_config(page_title="Quant Sniper Final", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 20px; padding: 20px; border: 1px solid #E5E8EB; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); }
    .metric-box { text-align: center; padding: 10px; background: #F9FAFB; border-radius: 10px; border: 1px solid #E5E8EB; }
    .status-up { color: #F04452; font-weight: bold; }
    .status-down { color: #3182F6; font-weight: bold; }
    .news-box { background-color: #f8f9fa; padding: 10px; border-radius: 10px; margin-top: 10px; font-size: 13px; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# --- [2. 통합 DB] ---
SECTOR_DB = {
    "반도체": {"삼성전자":"005930", "SK하이닉스":"000660", "한미반도체":"042700", "DB하이텍":"000990"},
    "배터리": {"LG에너지솔루션":"373220", "POSCO홀딩스":"005490", "삼성SDI":"006400", "에코프로비엠":"247540"},
    "자동차": {"현대차":"005380", "기아":"000270", "현대모비스":"012330", "HL만도":"204320"},
    "바이오": {"삼성바이오로직스":"207940", "셀트리온":"068270", "유한양행":"000100", "알테오젠":"196170"},
    "IT/플랫폼": {"NAVER":"035420", "카카오":"035720", "크래프톤":"259960"},
    "방산/조선": {"한화에어로스페이스":"012450", "HD현대중공업":"329180", "한화오션":"042660", "LIG넥스원":"079550"},
    "전력/에너지": {"한국전력":"015760", "두산에너빌리티":"034020", "HD현대일렉트릭":"267260", "LS ELECTRIC":"010120"},
    "금융": {"KB금융":"105560", "신한지주":"055550", "메리츠금융지주":"138040", "우리금융지주":"316140"}
}
THEME_DB = {"주도주": {"삼성전자":"005930", "현대차":"005380"}, "저PBR": {"기아":"000270", "KB금융":"105560"}}

# --- [3. GitHub 연동 (저장/불러오기)] ---
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

def get_github_file():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return {}
        headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}"}
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return json.loads(base64.b64decode(r.json()['content']).decode('utf-8'))
    except: pass
    return {}

def save_github_file(data):
    try:
        if "GITHUB_TOKEN" not in st.secrets: return False
        headers = {"Authorization": f"token {st.secrets['GITHUB_TOKEN']}"}
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        
        # SHA 가져오기
        r_get = requests.get(url, headers=headers)
        sha = r_get.json().get('sha') if r_get.status_code == 200 else None
        
        # 업로드
        payload = {
            "message": "update watchlist",
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False).encode('utf-8')).decode('utf-8')
        }
        if sha: payload['sha'] = sha
        
        return requests.put(url, headers=headers, json=payload).status_code in [200, 201]
    except: return False

# 초기화
if 'watchlist' not in st.session_state or not st.session_state['watchlist']:
    st.session_state['watchlist'] = get_github_file()

# --- [4. 분석 엔진] ---
@st.cache_data(ttl=600)
def get_indices():
    try:
        start = datetime.datetime.now() - datetime.timedelta(days=10)
        def get_val(ticker):
            try: return fdr.DataReader(ticker, start).iloc[-1]
            except: return None

        return {
            "KOSPI": get_val('KS11'), "USD/KRW": get_val('USD/KRW'), 
            "미국채10년": get_val('US10YT'), "유가": get_val('CL=F'), "금": get_val('GC=F')
        }
    except: return {}

def call_gemini(prompt):
    try:
        api_key = st.secrets.get("GOOGLE_API_KEY", "")
        if not api_key: return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        resp = requests.post(url, headers={"Content-Type": "application/json"}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=5)
        if resp.status_code == 200: return resp.json()
    except: pass
    return None

def get_news_summary(name):
    try:
        q = urllib.parse.quote(f"{name} 주가")
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko")
        if not feed.entries: return "뉴스 없음", []
        
        titles = [e.title for e in feed.entries[:5]]
        links = [{"title": e.title, "link": e.link, "date": e.published[:10]} for e in feed.entries[:5]]
        
        # AI 요약 시도
        res = call_gemini(f"뉴스 제목들: {titles}. 이 종목의 현재 분위기를 한 줄로 요약해줘(JSON output: {{'summary':'...'}})")
        summary = "AI 분석 대기중"
        if res:
            try:
                txt = res['candidates'][0]['content']['parts'][0]['text']
                summary = json.loads(re.search(r"\{.*\}", txt, re.DOTALL).group(0))['summary']
            except: summary = "키워드 분석: " + ("긍정" if any(x in str(titles) for x in ['상승','호재']) else "중립/부정")
            
        return summary, links
    except: return "뉴스 데이터 연동 실패", []

def analyze_stock(code, name):
    try:
        # 차트
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=365))
        if df.empty: return None
        curr = df.iloc[-1]['Close']
        ma20 = df['Close'].rolling(20).mean().iloc[-1] if len(df) >= 20 else curr
        
        score = 70 if curr >= ma20 else 30
        trend = "📈 상승 추세" if curr >= ma20 else "📉 하락 추세"
        
        # 펀더멘탈
        fund = {"per": 0, "pbr": 0}
        try:
            f = stock.get_market_fundamental_by_date(datetime.datetime.now().strftime("%Y%m%d"), datetime.datetime.now().strftime("%Y%m%d"), code)
            if not f.empty: fund = {"per": f.iloc[-1]['PER'], "pbr": f.iloc[-1]['PBR']}
        except: pass
        
        # 뉴스
        news_txt, news_links = get_news_summary(name)

        return {
            "name": name, "code": code, "price": int(curr), 
            "score": score, "trend": trend, "fund": fund, 
            "news": news_txt, "links": news_links, "history": df
        }
    except: return None

# --- [5. UI 구성] ---
st.title("💎 Quant Sniper Final")

# 1. 지표
indices = get_indices()
if indices:
    cols = st.columns(5)
    for i, (k, v) in enumerate(indices.items()):
        with cols[i]:
            if v is not None:
                diff = v['Close'] - v['Open']
                color = "status-up" if diff > 0 else "status-down"
                if k in ["USD/KRW", "미국채10년", "유가"]: color = "status-down" if diff > 0 else "status-up" # 역상관
                st.markdown(f"<div class='metric-box'><div style='font-size:12px; color:#888;'>{k}</div><div style='font-weight:bold;'>{v['Close']:,.2f}</div><div class='{color}'>{diff:+.2f}</div></div>", unsafe_allow_html=True)

st.markdown("---")

# 2. 메인 탭
tab1, tab2 = st.tabs(["💼 포트폴리오", "🔍 종목 추가/발굴"])

with tab1:
    if not st.session_state['watchlist']:
        st.info("저장된 종목이 없습니다. '종목 추가' 탭을 이용하세요.")
    else:
        if st.button("🔄 전체 분석 실행"):
            with st.spinner("분석 중..."):
                res = {}
                with concurrent.futures.ThreadPoolExecutor() as exe:
                    futures = {exe.submit(analyze_stock, v['code'], k): k for k, v in st.session_state['watchlist'].items()}
                    for f in concurrent.futures.as_completed(futures):
                        if f.result(): res[futures[f]] = f.result()
                st.session_state['results'] = res

        # [핵심] 결과가 없어도 카드는 무조건 출력
        for name, info in st.session_state['watchlist'].items():
            r = st.session_state.get('results', {}).get(name)
            
            st.markdown(f"<div class='toss-card'>", unsafe_allow_html=True)
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{name}** <span style='color:#999; font-size:12px;'>{info['code']}</span>", unsafe_allow_html=True)
                if r:
                    col = "#F04452" if r['score']>=60 else "#3182F6"
                    st.markdown(f"<span style='font-size:24px; font-weight:bold;'>{r['price']:,}원</span> <span style='color:{col}; font-weight:bold;'>{r['trend']}</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color:#999;'>분석 대기 중... (버튼을 눌러주세요)</span>", unsafe_allow_html=True)
            
            with c2:
                if st.button("삭제", key=f"del_{info['code']}"):
                    del st.session_state['watchlist'][name]
                    save_github_file(st.session_state['watchlist'])
                    st.rerun()

            # 상세 정보 (분석된 경우만)
            if r:
                with st.expander("상세 분석 보기"):
                    st.write(f"PER: {r['fund']['per']} | PBR: {r['fund']['pbr']}")
                    st.info(f"뉴스 요약: {r['news']}")
                    st.altair_chart(alt.Chart(r['history'].reset_index().tail(100)).encode(x='Date:T', y=alt.Y('Close:Q', scale=alt.Scale(zero=False))).mark_line(), use_container_width=True)
            
            st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.subheader("종목 검색 및 추가 (자동 저장)")
    c1, c2 = st.columns([3, 1])
    txt = c1.text_input("종목명")
    if c2.button("검색") and txt:
        krx = fdr.StockListing('KRX')
        for _, row in krx[krx['Name'].str.contains(txt)].iterrows():
            if st.button(f"+ {row['Name']} ({row['Code']})"):
                st.session_state['watchlist'][row['Name']] = {"code": row['Code']}
                save_github_file(st.session_state['watchlist'])
                st.toast("저장됨")
                time.sleep(1); st.rerun()

    st.markdown("---")
    st.subheader("🚀 통합 스캔 & 텔레그램 알림")
    
    # 스캔 대상 선정
    scan_mode = st.radio("스캔 범위", ["전체", "업종별"], horizontal=True)
    targets = {}
    
    if scan_mode == "전체":
        for cat in SECTOR_DB: targets.update(SECTOR_DB[cat])
    else:
        cat = st.selectbox("업종 선택", list(SECTOR_DB.keys()))
        targets = SECTOR_DB[cat]
        
    if st.button(f"⚡ {len(targets)}개 종목 스캔 시작"):
        token = st.secrets.get("TELEGRAM_TOKEN"); chat_id = st.secrets.get("CHAT_ID")
        if not token: st.error("텔레그램 토큰이 없습니다.")
        else:
            bar = st.progress(0, text="스캔 중...")
            found = []
            cnt = 0
            for name, code in targets.items():
                cnt += 1
                bar.progress(cnt/len(targets), text=f"{name} 분석 중...")
                r = analyze_stock(code, name)
                if r and r['score'] >= 60: found.append(r); time.sleep(0.5)
            
            bar.progress(100, text="완료!")
            
            if found:
                found.sort(key=lambda x: x['score'], reverse=True)
                msg = f"💎 발굴 리포트 ({len(found)}개)\n\n"
                for i, r in enumerate(found[:5]):
                    msg += f"{i+1}. {r['name']} ({r['score']}점)\n   {r['news'][:40]}..\n\n"
                
                try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": msg})
                except: pass
                
                st.success("텔레그램 전송 완료!")
                for r in found[:5]:
                    if st.button(f"추가: {r['name']}", key=f"add_scan_{r['code']}"):
                        st.session_state['watchlist'][r['name']] = {"code": r['code']}
                        save_github_file(st.session_state['watchlist'])
                        st.toast("저장됨")
            else:
                st.warning("조건에 맞는 종목이 없습니다.")
