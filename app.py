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

# --- [1. 시스템 설정] ---
st.set_page_config(page_title="Quant Sniper V29.0 (Final)", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    
    .metric-container { background: #F9FAFB; padding: 12px; border-radius: 12px; text-align: center; border: 1px solid #E5E8EB; height: 100%; }
    .metric-label { font-size: 13px; color: #6B7684; font-weight: 600; margin-bottom: 4px; }
    .metric-value { font-size: 20px; font-weight: 800; color: #333D4B; }
    .metric-status { font-size: 12px; font-weight: 700; margin-top: 4px; }
    .status-good { color: #F04452; background-color: rgba(240, 68, 82, 0.1); padding: 2px 6px; border-radius: 4px; }
    .status-bad { color: #3182F6; background-color: rgba(49, 130, 246, 0.1); padding: 2px 6px; border-radius: 4px; }
    
    .news-ai { background: #F9FAFB; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #E5E8EB; color: #333; }
    .news-fallback { background: #FFF4E6; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #FFD8A8; color: #D9480F; font-weight: 600; }
    .news-box { padding: 8px 0; border-bottom: 1px solid #F2F4F6; font-size: 13px; }
    .news-link { color: #333; text-decoration: none; font-weight: 500; display: block; margin-bottom: 2px;}
    .news-link:hover { color: #3182F6; text-decoration: underline; }
    
    .fund-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 10px; }
    .fund-item { padding: 10px; border-radius: 8px; text-align: center; background: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# --- [2. 통합 데이터베이스] ---
SECTOR_DB = {
    "반도체": {"삼성전자":"005930", "SK하이닉스":"000660", "한미반도체":"042700", "DB하이텍":"000990", "리노공업":"058470", "HPSP":"403870", "이수페타시스":"007660"},
    "배터리": {"LG에너지솔루션":"373220", "POSCO홀딩스":"005490", "삼성SDI":"006400", "에코프로비엠":"247540", "LG화학":"051910", "포스코퓨처엠":"003670", "에코프로":"086520"},
    "자동차": {"현대차":"005380", "기아":"000270", "현대모비스":"012330", "HL만도":"204320", "현대위아":"011210"},
    "바이오": {"삼성바이오로직스":"207940", "셀트리온":"068270", "유한양행":"000100", "SK바이오팜":"326030", "알테오젠":"196170", "HLB":"028300"},
    "IT/플랫폼": {"NAVER":"035420", "카카오":"035720", "삼성SDS":"018260", "크래프톤":"259960", "카카오뱅크":"323410"},
    "방산/조선": {"한화에어로스페이스":"012450", "HD현대중공업":"329180", "한화오션":"042660", "한국항공우주":"047810", "LIG넥스원":"079550"},
    "전력/에너지": {"한국전력":"015760", "두산에너빌리티":"034020", "HD현대일렉트릭":"267260", "LS ELECTRIC":"010120"},
    "금융": {"KB금융":"105560", "신한지주":"055550", "하나금융지주":"086790", "메리츠금융지주":"138040"},
    "엔터/게임": {"하이브":"352820", "JYP Ent.":"035900", "엔씨소프트":"036570", "넷마블":"251270"}
}
THEME_DB = {"주도주": {"삼성전자":"005930", "현대차":"005380", "SK하이닉스":"000660"}, "저PBR": {"기아":"000270", "KB금융":"105560", "기업은행":"024110"}}

# --- [3. GitHub 저장소 연동 (핵심)] ---
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

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

def save_to_github(data):
    try:
        if "GITHUB_TOKEN" not in st.secrets: return False
        token = st.secrets["GITHUB_TOKEN"]
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        r_get = requests.get(url, headers=headers)
        sha = r_get.json().get('sha', '') if r_get.status_code == 200 else None
        
        content_json = json.dumps(data, indent=4, ensure_ascii=False)
        content_base64 = base64.b64encode(content_json.encode('utf-8')).decode('utf-8')
        payload = {"message": "Update watchlist", "content": content_base64}
        if sha: payload["sha"] = sha
        
        r_put = requests.put(url, headers=headers, json=payload)
        return r_put.status_code in [200, 201]
    except: return False

if 'watchlist' not in st.session_state or not st.session_state['watchlist']:
    st.session_state['watchlist'] = load_from_github()

# --- [4. 분석 엔진 (풀버전 복구)] ---

@st.cache_data(ttl=600)
def get_market_indices():
    try:
        start = datetime.datetime.now() - datetime.timedelta(days=10)
        kospi = fdr.DataReader('KS11', start).iloc[-1]
        usd = fdr.DataReader('USD/KRW', start).iloc[-1]
        us10y = fdr.DataReader('US10YT', start).iloc[-1]
        oil = fdr.DataReader('CL=F', start).iloc[-1]
        gold = fdr.DataReader('GC=F', start).iloc[-1]

        def analyze(curr, prev, name):
            diff = curr - prev; sign = "▲" if diff > 0 else "▼"
            bad = diff > 0 if name in ["USD/KRW", "미국채10년", "WTI유가"] else diff < 0
            status = "부정" if bad else "긍정"
            css = "status-bad" if bad else "status-good"
            return {"v": curr, "d": diff, "s": sign, "st": status, "css": css}

        return {
            "KOSPI": analyze(kospi['Close'], kospi['Open'], "KOSPI"),
            "USD/KRW": analyze(usd['Close'], usd['Open'], "USD/KRW"),
            "미국채10년": analyze(us10y['Close'], us10y['Open'], "미국채10년"),
            "WTI유가": analyze(oil['Close'], oil['Open'], "WTI유가"),
            "금(Gold)": analyze(gold['Close'], gold['Open'], "금(Gold)"),
        }
    except: return None

def call_gemini_auto(prompt):
    api_key = st.secrets.get("GOOGLE_API_KEY", "")
    if not api_key: return None, "NO_KEY"
    models = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=6)
            if r.status_code == 200: return r.json(), None
            elif r.status_code == 429: return None, "RATE_LIMIT"
        except: continue
    return None, "ALL_FAILED"

def analyze_news_by_keywords(news_titles):
    pos = ["상승","급등","최고","호재","개선","성장","흑자","수주","기대","매수"]
    neg = ["하락","급락","최저","악재","우려","감소","적자","이탈","매도","공매도"]
    score = 0
    for t in news_titles:
        for w in pos: 
            if w in t: score+=1
        for w in neg:
            if w in t: score-=1
    return min(max(score, -10), 10), f"키워드 분석: 긍정 {score}점"

@st.cache_data(ttl=600)
def get_news_sentiment(company_name):
    try:
        query = urllib.parse.quote(f"{company_name} 주가")
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko")
        titles = []; data = []
        for e in feed.entries[:15]:
            data.append({"title": e.title, "link": e.link, "date": time.strftime("%Y-%m-%d", e.published_parsed) if e.published_parsed else ""})
            titles.append(e.title)
        
        if not titles: return {"score": 0, "headline": "뉴스 없음", "raw_news": [], "method": "none"}

        prompt = f"뉴스: {str(titles)}. 주가 영향 점수(-10~10)와 한줄 요약(JSON): {{'score':0, 'summary':'내용'}}"
        res_data, err = call_gemini_auto(prompt)
        score = 0; headline = ""; method = "ai"
        
        if res_data:
            try:
                txt = res_data['candidates'][0]['content']['parts'][0]['text']
                js = json.loads(re.search(r"\{.*\}", txt, re.DOTALL).group(0))
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
        
        # 기술적 점수
        tech_score = 0
        if curr['Close'] > curr['MA5']: tech_score += 10
        if curr['Close'] > curr['MA20']: tech_score += 15
        if curr['MA5'] > curr['MA20']: tech_score += 10
        
        pass_cnt = 0
        if curr['Close'] >= curr['MA5']: pass_cnt +=1
        if curr['Close'] >= curr['MA20']: pass_cnt +=1
        if curr['Close'] >= curr['MA60']: pass_cnt +=1
        
        trend = "📈 상승" if pass_cnt >= 2 else ("⚖️ 보합" if pass_cnt == 1 else "📉 하락")

        fund_score, fund_data = get_fundamental_score(code)
        
        # 포트폴리오에 있거나 기술적 우위일 때만 뉴스 분석
        is_my_stock = name in st.session_state['watchlist']
        is_good = curr['Close'] >= curr['MA20']
        
        if is_my_stock or is_good:
             news = get_news_sentiment(name)
        else:
             news = {"score": 0, "headline": "기술적 지표 부진으로 AI 생략", "raw_news": [], "method": "skip"}

        final = int((tech_score * 0.4) + fund_score + news['score'])
        final = min(max(final, 0), 100)
        
        return {"name": name, "code": code, "price": int(curr['Close']), "score": final, "trend": trend, "fund": fund_data, "news": news, "history": df}
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
    elif mode == "업종별" and sub_category:
        for n, c in SECTOR_DB.get(sub_category, {}).items(): targets[c] = n
    elif mode == "테마별" and sub_category:
        for n, c in THEME_DB.get(sub_category, {}).items(): targets[c] = n
    return targets

# --- [5. 메인 UI] ---
st.title("💎 Quant Sniper V29.0 (Final)")

# 지표
idx = get_market_indices()
if idx:
    cols = st.columns(5)
    for i, (k, v) in enumerate(idx.items()):
        with cols[i]:
            st.markdown(f"<div class='metric-container'><div class='metric-label'>{k}</div><div class='metric-value'>{v['v']:,.2f}</div><div class='metric-status {v['css']}'>{v['s']} {v['d']:.2f} ({v['st']})</div></div>", unsafe_allow_html=True)
else: st.info("시장 지표 로딩 중... (잠시 후 다시 시도하세요)")

with st.expander("📚 지표/용어 범례"):
    st.write("- **USD/KRW, 금리, 유가**: 상승 시 주식시장에 보통 '부정적'입니다.")
    st.write("- **PER**: 낮을수록 저평가(좋음). **PBR**: 1.0 미만이면 청산가치보다 쌈(좋음).")

st.markdown("---")
tab1, tab2 = st.tabs(["💼 내 포트폴리오", "🔭 통합 종목 스캔"])

with tab1:
    if not st.session_state['watchlist']:
        st.warning("저장된 종목이 없습니다. 옆 탭에서 추가해주세요.")
    else:
        if st.button("🔄 내 종목 정밀 분석"):
            with st.spinner("분석 중..."):
                res = []
                with concurrent.futures.ThreadPoolExecutor() as exe:
                    futures = [exe.submit(analyze_stock, i['code'], n) for n, i in st.session_state['watchlist'].items()]
                    for f in concurrent.futures.as_completed(futures):
                        if f.result(): res.append(f.result())
                st.session_state['pf_results'] = sorted(res, key=lambda x: x['score'], reverse=True)

        if 'pf_results' in st.session_state:
            for r in st.session_state['pf_results']:
                c = "#F04452" if r['score']>=60 else "#3182F6"
                st.markdown(f"<div class='toss-card'><div style='display:flex; justify-content:space-between;'><div><span style='font-size:18px; font-weight:700;'>{r['name']}</span></div><div style='text-align:right;'><div style='font-size:24px; font-weight:800; color:{c};'>{r['score']}점</div><div style='font-size:12px; font-weight:bold; color:{c};'>{r['trend']}</div></div></div><div style='font-size:20px; font-weight:800;'>{r['price']:,}원</div></div>", unsafe_allow_html=True)
                
                with st.expander("상세 보기"):
                    c1, c2 = st.columns(2)
                    with c1: st.write(f"PER: {r['fund']['per']:.1f} | PBR: {r['fund']['pbr']:.1f}"); 
                    with c2:
                        if r['news']['method'] == 'ai': st.success(r['news']['headline'])
                        elif r['news']['method'] == 'keyword': st.warning(r['news']['headline'])
                        else: st.caption("분석 생략")
                    st.altair_chart(alt.Chart(r['history'].reset_index().tail(100)).encode(x='Date:T', y=alt.Y('Close:Q', scale=alt.Scale(zero=False))).mark_line(), use_container_width=True)
                
                if st.button("삭제", key=f"del_{r['code']}"):
                    del st.session_state['watchlist'][r['name']]
                    save_to_github(st.session_state['watchlist'])
                    st.rerun()

with tab2:
    st.subheader("종목 발굴 및 추가 (자동 저장)")
    
    # 1. 검색
    col1, col2 = st.columns([3, 1])
    txt = col1.text_input("종목명 검색")
    if col2.button("검색") and txt:
        krx = fdr.StockListing('KRX')
        for _, r in krx[krx['Name'].str.contains(txt)].iterrows():
            if st.button(f"+ {r['Name']} ({r['Code']})"):
                st.session_state['watchlist'][r['Name']] = {"code": r['Code']}
                if save_to_github(st.session_state['watchlist']): st.toast("저장됨!"); time.sleep(1); st.rerun()

    # 2. 통합 스캔
    st.markdown("---")
    st.write("🔥 **통합 스캔 & 텔레그램 알림**")
    mode = st.radio("범위", ["전체", "업종별", "테마별"], horizontal=True)
    
    sub = None
    if mode == "업종별": sub = st.selectbox("세부 업종", list(SECTOR_DB.keys()))
    elif mode == "테마별": sub = st.selectbox("세부 테마", list(THEME_DB.keys()))
    
    if st.button("⚡ 스캔 시작"):
        token = st.secrets.get("TELEGRAM_TOKEN"); chat_id = st.secrets.get("CHAT_ID")
        if not token: st.error("Secrets 설정 필요")
        else:
            targets = get_target_list(mode, sub)
            bar = st.progress(0, text=f"{len(targets)}개 종목 스캔 중...")
            found = []
            cnt = 0
            for c, n in targets.items():
                cnt += 1
                bar.progress(cnt/len(targets), text=f"{n} 분석 중...")
                r = analyze_stock(c, n)
                if r and r['score'] >= 60: found.append(r); time.sleep(0.5)
            
            bar.progress(100, text="완료!")
            if found:
                found.sort(key=lambda x: x['score'], reverse=True)
                msg = f"💎 발굴 리포트 ({len(found)}개)\n\n"
                for i, r in enumerate(found[:10]):
                    msg += f"{i+1}. {r['name']} ({r['score']}점)\n   {r['news']['headline'][:30]}..\n\n"
                send_telegram_msg(token, chat_id, msg)
                st.success("텔레그램 전송 완료!")
                for r in found[:10]:
                    c1, c2 = st.columns([4, 1])
                    with c1: st.write(f"**{r['name']}** ({r['score']}점)")
                    with c2:
                        if st.button("추가", key=f"add_{r['code']}"):
                            st.session_state['watchlist'][r['name']] = {"code": r['code']}
                            save_to_github(st.session_state['watchlist'])
                            st.toast("저장됨!")
            else: st.warning("조건에 맞는 종목이 없습니다.")
