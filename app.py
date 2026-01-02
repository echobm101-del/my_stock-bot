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

# --- [1. 기본 설정 및 스타일] ---
st.set_page_config(page_title="Quant Sniper (Clean Fixed)", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 20px; padding: 20px; border: 1px solid #E5E8EB; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); }
    
    /* 에러 및 뉴스 박스 스타일 */
    .error-box { background-color: #FFF4E6; color: #D9480F; padding: 15px; border-radius: 12px; border: 1px solid #FFD8A8; font-weight: 600; margin-top: 10px; font-size: 14px; }
    .success-box { background-color: #F9FAFB; padding: 15px; border-radius: 12px; border: 1px solid #E5E8EB; margin-top: 10px; font-size: 14px; color: #333; }
    
    /* 재무 정보 그리드 */
    .fund-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 10px; margin-bottom: 10px; }
    .fund-item { padding: 12px; border-radius: 8px; text-align: center; background: #F2F4F6; }
    .fund-label { font-size: 12px; color: #666; }
    .fund-val { font-size: 16px; font-weight: bold; color: #333; }
    
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
    "금융": {"KB금융":"105560", "신한지주":"055550", "하나금융지주":"086790", "메리츠금융지주":"138040"}
}

# --- [3. GitHub 연동] ---
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
        r_get = requests.get(url, headers=headers)
        sha = r_get.json().get('sha') if r_get.status_code == 200 else None
        
        payload = {
            "message": "update",
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False).encode('utf-8')).decode('utf-8')
        }
        if sha: payload['sha'] = sha
        return requests.put(url, headers=headers, json=payload).status_code in [200, 201]
    except: return False

if 'watchlist' not in st.session_state or not st.session_state['watchlist']:
    st.session_state['watchlist'] = get_github_file()

# --- [4. 분석 엔진 (에러 수정됨)] ---
def call_gemini(prompt):
    api_key = st.secrets.get("GOOGLE_API_KEY", "")
    if not api_key: return None, "API Key 없음"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=5)
        if resp.status_code == 200: return resp.json(), None
        else: return None, f"AI 연결 실패: {resp.status_code} {resp.text}"
    except Exception as e: return None, f"통신 에러: {str(e)}"

def get_news_summary(name):
    try:
        q = urllib.parse.quote(f"{name} 주가")
        # f-string syntax error 수정됨
        rss_url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        
        if not feed.entries: return "뉴스 없음", [], None
        
        titles = [e.title for e in feed.entries[:5]]
        links = [{"title": e.title, "link": e.link, "date": e.published[:10]} for e in feed.entries[:5]]
        
        # AI 요약 시도
        res, err = call_gemini(f"뉴스 제목들: {titles}. 이 종목의 현재 분위기를 한 줄로 요약해줘(JSON output: {{'summary':'...'}})")
        if err: return err, links, "error"

        summary = "AI 분석 대기중"
        if res:
            try:
                txt = res['candidates'][0]['content']['parts'][0]['text']
                summary = json.loads(re.search(r"\{.*\}", txt, re.DOTALL).group(0))['summary']
                status = "success"
            except: 
                summary = "응답 형식 오류"
                status = "error"
        else:
            status = "error"
            
        return summary, links, status
    except Exception as e: return f"시스템 오류: {str(e)}", [], "error"

def analyze_stock(code, name):
    try:
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=365))
        if df.empty: return None
        curr = df.iloc[-1]['Close']
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        
        score = 70 if curr >= ma20 else 30
        trend = "🚀 상승 추세" if curr >= ma20 else "📉 하락/조정"
        
        fund = {"per": 0, "pbr": 0, "div": 0}
        try:
            f = stock.get_market_fundamental_by_date(datetime.datetime.now().strftime("%Y%m%d"), datetime.datetime.now().strftime("%Y%m%d"), code)
            if not f.empty: fund = {"per": f.iloc[-1]['PER'], "pbr": f.iloc[-1]['PBR'], "div": f.iloc[-1]['DIV']}
        except: pass
        
        news_txt, news_links, status = get_news_summary(name)

        return {
            "name": name, "code": code, "price": int(curr), 
            "score": score, "trend": trend, "fund": fund, 
            "news_msg": news_txt, "links": news_links, "status": status, "history": df
        }
    except: return None

def send_telegram_msg(token, chat_id, msg):
    try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": msg})
    except: pass

# --- [5. UI 구성] ---
st.title("💎 Quant Sniper (Clean)")

tab1, tab2 = st.tabs(["💼 내 포트폴리오", "🔍 종목 추가/스캔"])

with tab1:
    if not st.session_state['watchlist']:
        st.info("등록된 종목이 없습니다.")
    else:
        if st.button("🔄 전체 분석 실행"):
            with st.spinner("분석 중..."):
                res = {}
                with concurrent.futures.ThreadPoolExecutor() as exe:
                    futures = {exe.submit(analyze_stock, v['code'], k): k for k, v in st.session_state['watchlist'].items()}
                    for f in concurrent.futures.as_completed(futures):
                        nm = futures[f]; r = f.result()
                        if r: res[nm] = r
                st.session_state['results'] = res

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
                    st.markdown("<span style='color:#999;'>분석 대기 중...</span>", unsafe_allow_html=True)
            
            with c2:
                if st.button("삭제", key=f"del_{info['code']}"):
                    del st.session_state['watchlist'][name]
                    save_github_file(st.session_state['watchlist'])
                    st.rerun()

            if r:
                with st.expander("📊 상세 분석 & 차트"):
                    # 재무
                    st.markdown(f"""
                    <div class='fund-grid'>
                        <div class='fund-item'><div class='fund-label'>PER</div><div class='fund-val'>{r['fund']['per']:.2f}</div></div>
                        <div class='fund-item'><div class='fund-label'>PBR</div><div class='fund-val'>{r['fund']['pbr']:.2f}</div></div>
                        <div class='fund-item'><div class='fund-label'>배당률</div><div class='fund-val'>{r['fund']['div']:.1f}%</div></div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 뉴스 (에러 그대로 표시)
                    st.write("📰 **구글 뉴스 AI 요약**")
                    if r['status'] == 'success':
                        st.markdown(f"<div class='success-box'>🤖 {r['news_msg']}</div>", unsafe_allow_html=True)
                    elif r['status'] == 'error':
                        st.markdown(f"<div class='error-box'>⚠️ {r['news_msg']}</div>", unsafe_allow_html=True)
                    else:
                        st.info(r['news_msg'])
                        
                    for l in r['links']:
                        st.markdown(f"<a href='{l['link']}' target='_blank' style='text-decoration:none; color:#333; font-size:13px;'>📄 {l['title']}</a>", unsafe_allow_html=True)
                    
                    st.altair_chart(alt.Chart(r['history'].reset_index().tail(120)).encode(x='Date:T', y=alt.Y('Close:Q', scale=alt.Scale(zero=False))).mark_line(), use_container_width=True)
            
            st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.subheader("종목 검색 및 추가")
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
                if r and r['status'] == 'success' and r['score'] >= 60: found.append(r); time.sleep(0.5)
            
            bar.progress(100, text="완료!")
            
            if found:
                found.sort(key=lambda x: x['score'], reverse=True)
                msg = f"💎 발굴 리포트 ({len(found)}개)\n\n"
                for i, r in enumerate(found[:5]):
                    msg += f"{i+1}. {r['name']} ({r['score']}점)\n   {r['news_msg'][:40]}..\n\n"
                
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
