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
import google.generativeai as genai # [변경] OpenAI 대신 Google Gemini 사용

# --- [1. 설정 및 UI 스타일링] ---
st.set_page_config(page_title="Quant Sniper V19.0 (Gemini)", page_icon="💎", layout="wide")

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
    .macro-box { background: #F9FAFB; border-radius: 16px; padding: 16px; text-align: center; height: 100%; border: 1px solid #F2F4F6; }
    .macro-val { font-size: 20px; font-weight: 800; color: #333D4B; margin-bottom: 8px; }
    .strategy-box { background-color: #F2F4F6; border-radius: 12px; padding: 15px; font-size: 13px; margin-top: 12px; display: flex; justify-content: space-around; text-align: center; }
    .strategy-item { display: flex; flex-direction: column; }
    .strategy-label { color: #8B95A1; font-size: 11px; margin-bottom: 4px; }
    .strategy-val { color: #333D4B; font-weight: 800; font-size: 14px; }
    .rsi-container { width: 100%; background-color: #F2F4F6; height: 10px; border-radius: 5px; margin-top: 8px; overflow: hidden; }
    .rsi-bar { height: 100%; border-radius: 5px; transition: width 0.5s ease-in-out; }
    .legend-table { width: 100%; font-size: 14px; border-collapse: collapse; margin-top: 5px; }
    .legend-table td { padding: 12px; border-bottom: 1px solid #F2F4F6; color: #333D4B; vertical-align: middle; line-height: 1.5; }
    .legend-header { font-weight: 800; color: #191F28; background-color: #F9FAFB; text-align: center; padding: 10px; border-radius: 8px; margin-bottom: 10px; display: block;}
    .legend-title { font-weight: 700; color: #4E5968; width: 140px; background-color: #F2F4F6; padding: 6px 10px; border-radius: 6px; text-align: center; display: inline-block;}
</style>
""", unsafe_allow_html=True)

# --- [2. 데이터 및 GitHub 연동] ---
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

@st.cache_data
def get_krx_list():
    try: df = fdr.StockListing('KRX'); return df[['Code', 'Name', 'Sector']]
    except: return pd.DataFrame()
krx_df = get_krx_list()

def load_local_json():
    if os.path.exists(FILE_PATH):
        try:
            with open(FILE_PATH, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_local_json(data):
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_from_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return load_local_json()
        token = st.secrets["GITHUB_TOKEN"]
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            return json.loads(content)
        return load_local_json()
    except: return load_local_json()

def save_to_github(data):
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            save_local_json(data)
            return False, "GitHub 토큰 미설정 (로컬 저장)"
        token = st.secrets["GITHUB_TOKEN"]
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        sha = r.json().get('sha') if r.status_code == 200 else None
        json_str = json.dumps(data, indent=4, ensure_ascii=False)
        b64_content = base64.b64encode(json_str.encode()).decode()
        payload = {"message": "Update watchlist PRO", "content": b64_content, "sha": sha}
        put_r = requests.put(url, headers=headers, json=payload)
        return (True, "동기화 완료") if put_r.status_code in [200, 201] else (False, f"저장 실패: {put_r.status_code}")
    except Exception as e:
        save_local_json(data)
        return False, f"에러: {e}"

if 'watchlist' not in st.session_state: st.session_state['watchlist'] = load_from_github()
if 'sent_alerts' not in st.session_state: st.session_state['sent_alerts'] = {}

# --- [3. PRO 분석 엔진 (Gemini 탑재)] ---

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    try:
        end_str = datetime.datetime.now().strftime("%Y%m%d")
        start_str = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_fundamental_by_date(start_str, end_str, code)
        if df.empty: return 25, "데이터 확인 불가"
        
        recent_data = df.iloc[-1]
        per = recent_data['PER']; pbr = recent_data['PBR']; div = recent_data['DIV']
        score = 20; reasons = []
        
        if 0 < pbr < 1.0: score += 15; reasons.append("PBR 1배 미만(저평가)")
        elif pbr < 2.0: score += 5
        if 0 < per < 10: score += 10; reasons.append("PER 10배 미만(실적우수)")
        if div > 3.0: score += 5; reasons.append(f"배당수익률 {div}%")
        return min(score, 50), ", ".join(reasons) if reasons else "밸류에이션 적정"
    except: return 25, "분석 보류"

@st.cache_data(ttl=600)
def get_news_sentiment(code):
    """
    [Gemini Version] 구글 Gemini 1.5 Flash를 사용하여 뉴스 심리 분석 (무료 티어 활용)
    """
    try:
        # 1. 뉴스 크롤링
        url = f"https://finance.naver.com/item/news_news.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.content, "html.parser")
        titles = soup.select(".title .tit")
        
        if not titles: return {"score": 0, "headline": "뉴스 없음"}
        
        # 2. 뉴스 텍스트 준비
        news_list = [t.get_text().strip() for t in titles[:8]] # 상위 8개
        news_text = "\n".join(news_list)
        latest_headline = news_list[0]
        
        # 3. Gemini 호출
        if "GOOGLE_API_KEY" not in st.secrets:
            return {"score": 0, "headline": "API키 미설정 (기본값)"}
            
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash') # 빠르고 효율적인 모델
        
        prompt = f"""
        당신은 주식 시장 심리 분석가입니다. 아래 뉴스 제목들을 보고 시장 심리를 -10점(악재/공포)에서 +10점(호재/기대) 사이의 정수로 평가해주세요.
        
        [뉴스 목록]
        {news_text}
        
        [응답 형식]
        반드시 JSON 형식으로만 답하세요:
        {{"score": 점수, "summary": "가장 중요한 이슈 한 줄 요약"}}
        """
        
        response = model.generate_content(prompt)
        
        # 4. 결과 파싱 (마크다운 제거 후 JSON 변환)
        text_res = response.text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text_res)
        
        score = int(result.get("score", 0))
        summary = result.get("summary", latest_headline)
        
        return {"score": min(max(score, -10), 10), "headline": summary}
        
    except Exception as e:
        # Gemini 호출 실패 시 백업 로직 (키워드 매칭)
        backup_score = 0
        good = ["수주", "계약", "최대", "흑자"]; bad = ["적자", "하향", "우려"]
        for t in titles[:5]:
            for g in good: 
                if g in t.get_text(): backup_score += 2
            for b in bad:
                if b in t.get_text(): backup_score -= 3
        return {"score": min(max(backup_score, -10), 10), "headline": f"{latest_headline} (백업분석)"}

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
        fund_score, fund_reason = get_company_guide_score(code)
        news = get_news_sentiment(code)

        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['MA120'] = df['Close'].rolling(120).mean()
        df['MA240'] = df['Close'].rolling(240).mean()
        df['Std'] = df['Close'].rolling(20).std()
        
        delta = df['Close'].diff(1)
        rsi = 100 - (100/(1 + (delta.where(delta>0,0).rolling(14).mean() / -delta.where(delta<0,0).rolling(14).mean())))
        curr = df.iloc[-1]
        
        tech_score = 0; ma_status = []
        mas = [('5일', 'MA5'), ('20일', 'MA20'), ('60일', 'MA60'), ('120일', 'MA120'), ('240일', 'MA240')]
        cnt = 0
        for label, col in mas:
            if curr['Close'] >= curr[col]: cnt += 1; ma_status.append(f"✅ {label}")
            else: ma_status.append(f"❌ {label}")
        tech_score += (cnt * 6)
        if curr['MA5'] > curr['MA20'] > curr['MA60']: tech_score += 10; ma_status.append("🔥 정배열")
        if sup['f'] > 0 or sup['i'] > 0: tech_score += 10
        
        final_score = int((tech_score * 0.5) + fund_score + news['score'])
        final_score = min(max(final_score, 0), 100)
        
        upside = 0.05 + (final_score / 1000)
        target_price = curr['Close'] * (1 + upside)
        buy_price = curr['MA20']
        
        if final_score >= 80: action = "강력 매수"
        elif final_score >= 60: action = "매수 긍정"
        elif final_score <= 40: action = "매도/관망"
        else: action = "중립"
        
        strategy = {
            "action": action, "buy": int(buy_price), "target": int(target_price),
            "fund_detail": f"{fund_reason}",
            "news_detail": f"[{news['score']}점] {news['headline']}",
            "tech_detail": f"이평선 {cnt}개 돌파 / 수급 {'양호' if sup['f']>0 else '보통'}",
            "ma_list": ma_status
        }
        
        return {
            "name": name_override, "code": code, "price": int(curr['Close']),
            "score": final_score, "rsi": rsi.iloc[-1],
            "checks": [fund_reason.split(',')[0], "Gemini 분석중" if news['score']!=0 else "뉴스없음"],
            "strategy": strategy, "supply": sup, "news": news, "history": df
        }
    except: return None

def analyze_portfolio_parallel(watchlist):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(analyze_pro, info['code'], name): name for name, info in watchlist.items()}
        for future in concurrent.futures.as_completed(futures):
            try: res = future.result(); 
            except: continue
            if res: results.append(res)
    return sorted(results, key=lambda x: x['score'], reverse=True)

def clean_html(raw_html):
    return re.sub(r'\s+', ' ', raw_html).strip()

def create_card_html(res):
    score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
    supply_f_col = "#F04452" if res['supply']['f'] > 0 else "#3182F6"
    
    rsi_val = res['rsi']
    rsi_width = min(max(rsi_val, 0), 100)
    if rsi_val <= 30: rsi_grad = "linear-gradient(90deg, #3182F6, #76B1FF)" 
    elif rsi_val >= 70: rsi_grad = "linear-gradient(90deg, #F04452, #FF8A9B)"
    else: rsi_grad = "linear-gradient(90deg, #8B95A1, #B0B8C1)"

    raw_html = f"""
    <div class='toss-card'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <span class='stock-name'>{res['name']}</span>
                <span class='stock-code'>{res['code']}</span>
                <div class='big-price'>{res['price']:,}원</div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:28px; font-weight:800; color:{score_col};'>{res['score']}점</div>
                <div class='badge-clean' style='background-color:{score_col}20; color:{score_col};'>{res['strategy']['action']}</div>
            </div>
        </div>
        <div class='strategy-box'>
            <div class='strategy-item'><span class='strategy-label'>적정 매수가</span><span class='strategy-val'>{res['strategy']['buy']:,}</span></div>
            <div style='width:1px; background:#ddd;'></div>
            <div class='strategy-item'><span class='strategy-label'>목표가</span><span class='strategy-val text-up'>{res['strategy']['target']:,}</span></div>
            <div style='width:1px; background:#ddd;'></div>
            <div class='strategy-item'><span class='strategy-label'>펀더멘탈</span><span class='strategy-val'>{res['checks'][0]}</span></div>
        </div>
        <div style='margin-top:15px; font-size:13px;'>
            <div style='display:flex; justify-content:space-between; margin-bottom:5px;'>
                <span style='color:#888;'>외국인 수급</span>
                <span style='font-weight:bold; color:{supply_f_col}'>{res['supply']['f']:,}</span>
            </div>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <span style='color:#888;'>RSI (14)</span>
                <div style='width:60%; background:#F2F4F6; height:8px; border-radius:4px;'>
                    <div style='width:{rsi_width}%; background:{rsi_grad}; height:100%; border-radius:4px;'></div>
                </div>
                <span style='font-weight:bold; color:#555;'>{res['rsi']:.1f}</span>
            </div>
        </div>
    </div>
    """
    return clean_html(raw_html)

# --- [4. 매크로 및 차트] ---
@st.cache_data(ttl=3600)
def get_global_macro():
    try:
        indices = {"S&P 500": "US500", "VIX (공포)": "^VIX", "WTI 유가": "CL=F", "미국채 10년": "^TNX"}
        res = {}; score = 0
        for n, c in indices.items():
            df = fdr.DataReader(c, datetime.datetime.now() - datetime.timedelta(days=20))
            if not df.empty:
                now = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]; chg = ((now - prev)/prev)*100
                if "VIX" in n: is_good = now < 20
                elif "S&P" in n: is_good = chg > 0
                else: is_good = chg < 0
                res[n] = {"v": now, "c": chg, "good": is_good}
                score += 1 if is_good else -1
        return {"data": res, "score": score}
    except: return None

def create_bollinger_chart(df, name):
    chart_data = df.tail(120).reset_index()
    base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=alt.Axis(format='%m-%d', title=None)))
    line = base.mark_line(color='#333D4B').encode(y=alt.Y('Close:Q', scale=alt.Scale(zero=False)))
    ma20 = base.mark_line(color='#F2A529').encode(y='MA20:Q')
    ma60 = base.mark_line(color='#3182F6').encode(y='MA60:Q')
    return (line + ma20 + ma60).properties(height=250)

# --- [5. 메인 UI 렌더링] ---
st.title("💎 Quant Sniper V19.0 (Gemini)")
st.caption("Hybrid Engine: Fundamental + Technical + Gemini AI Analysis")

with st.expander("📘 PRO 모드 지표 해석 가이드", expanded=True):
    st.markdown("""
    <table class='legend-table'>
        <tr><td colspan='2' class='legend-header'>📊 하이브리드 분석 기준</td></tr>
        <tr><td><span class='legend-title'>AI 점수</span></td><td><b>80점↑:</b> 강력 매수 (실적+추세 완벽)<br><b>60점↑:</b> 매수 긍정</td></tr>
        <tr><td><span class='legend-title'>뉴스 심리</span></td><td><b>Gemini AI</b>가 뉴스를 읽고 -10~+10점 부여</td></tr>
        <tr><td><span class='legend-title'>재무 진단</span></td><td>PBR 1배/PER 10배 미만 시 가산점</td></tr>
    </table>
    """, unsafe_allow_html=True)

macro = get_global_macro()
if macro:
    cols = st.columns(5)
    sc = macro['score']
    if sc >= 1: state="적극 투자"; s_col="text-up"; s_bg="badge-buy"
    elif sc <= -1: state="보수적"; s_col="text-down"; s_bg="badge-sell"
    else: state="관망"; s_col="text-gray"; s_bg="badge-neu"
    
    with cols[0]:
        st.markdown(f"<div class='macro-box'><div class='label-text'>시장 점수</div><div class='macro-val {s_col}'>{sc}</div><div class='badge-clean {s_bg}'>{state}</div></div>", unsafe_allow_html=True)
        
    for i, (k, v) in enumerate(macro['data'].items()):
        col = "text-up" if v['good'] else "text-down"
        bg = "badge-buy" if v['good'] else "badge-sell"
        txt = "긍정" if v['good'] else "부정"
        with cols[i+1]:
             st.markdown(f"<div class='macro-box'><div class='label-text'>{k}</div><div class='macro-val {col}'>{v['v']:.2f}</div><div class='badge-clean {bg}'>{txt}</div></div>", unsafe_allow_html=True)

st.divider()

tab1, tab2 = st.tabs(["💼 내 포트폴리오", "🔭 종목 발굴"])

with tab1:
    if not st.session_state['watchlist']: st.info("왼쪽 사이드바에서 종목을 추가해주세요.")
    else:
        with st.spinner("Gemini AI가 뉴스를 분석하고 있습니다..."):
            results = analyze_portfolio_parallel(st.session_state['watchlist'])
        
        for res in results:
            st.markdown(create_card_html(res), unsafe_allow_html=True)
            
            with st.expander(f"📑 {res['name']} AI 심층 분석 리포트"):
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("📈 기술적 분석")
                    st.info(res['strategy']['tech_detail'])
                    st.write("**이평선 상태:**")
                    for s in res['strategy']['ma_list']: st.write(s)
                with c2:
                    st.subheader("🤖 Gemini 뉴스 분석")
                    if "Gemini" in res['checks'][1]:
                        st.success(res['strategy']['news_detail'])
                    else:
                        st.warning("뉴스 데이터가 부족합니다.")
                    st.subheader("🏢 재무 상태")
                    st.write(res['strategy']['fund_detail'])
                    
                st.altair_chart(create_bollinger_chart(res['history'], res['name']), use_container_width=True)

with st.sidebar:
    st.header("⚡ 제어판")
    auto = st.checkbox("실시간 감시", value=False)
    with st.expander("종목 추가", expanded=True):
        name = st.text_input("종목명")
        code = st.text_input("코드")
        if st.button("추가"):
            st.session_state['watchlist'][name] = {"code": code}
            save_to_github(st.session_state['watchlist'])
            st.rerun()
    if st.button("초기화"):
        st.session_state['watchlist'] = {}
        save_to_github({})
        st.rerun()

if auto:
    time.sleep(30)
    st.rerun()
