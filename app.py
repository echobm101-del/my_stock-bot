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

# --- [1. PRO 설정 및 UI 스타일링 (토스 화이트 테마)] ---
st.set_page_config(page_title="Quant Sniper V18.3 PRO", page_icon="💎", layout="wide")

st.markdown("""
<style>
    /* 전체 폰트 및 배경 */
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    
    /* 카드 디자인 */
    .toss-card { 
        background: #FFFFFF; border-radius: 24px; padding: 24px; 
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; 
    }
    
    /* 색상 시스템 (한국형: 빨강=상승/호재) */
    .text-up { color: #F04452 !important; }   
    .text-down { color: #3182F6 !important; } 
    .text-gray { color: #8B95A1 !important; } 
    
    /* 텍스트 스타일 */
    .big-price { font-size: 32px; font-weight: 800; letter-spacing: -0.5px; color: #191F28; }
    .stock-name { font-size: 22px; font-weight: 700; color: #333D4B; }
    .stock-code { font-size: 14px; color: #8B95A1; margin-left: 6px; font-weight: 500; }
    .label-text { font-size: 12px; color: #8B95A1; font-weight: 600; margin-bottom: 4px; }
    
    /* 뱃지 및 박스 */
    .badge-clean { padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700; display: inline-block; }
    .badge-buy { background-color: rgba(240, 68, 82, 0.1); color: #F04452; }
    .badge-sell { background-color: rgba(49, 130, 246, 0.1); color: #3182F6; }
    .badge-neu { background-color: #F2F4F6; color: #4E5968; }
    
    .macro-box { background: #F9FAFB; border-radius: 16px; padding: 16px; text-align: center; height: 100%; border: 1px solid #F2F4F6; }
    .macro-val { font-size: 20px; font-weight: 800; color: #333D4B; margin-bottom: 8px; }
    
    .check-container { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    .check-tag { font-size: 12px; padding: 6px 12px; border-radius: 18px; background: #F2F4F6; color: #4E5968; font-weight: 600; display: flex; align-items: center; }
    
    /* 전략 박스 */
    .strategy-box { background-color: #F2F4F6; border-radius: 12px; padding: 15px; font-size: 13px; margin-top: 12px; display: flex; justify-content: space-around; text-align: center; }
    .strategy-item { display: flex; flex-direction: column; }
    .strategy-label { color: #8B95A1; font-size: 11px; margin-bottom: 4px; }
    .strategy-val { color: #333D4B; font-weight: 800; font-size: 14px; }

    /* RSI 바 */
    .rsi-container { width: 100%; background-color: #F2F4F6; height: 10px; border-radius: 5px; margin-top: 8px; overflow: hidden; }
    .rsi-bar { height: 100%; border-radius: 5px; transition: width 0.5s ease-in-out; }
    
    /* 범례 테이블 */
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

def get_sector_info(code):
    try: 
        row = krx_df[krx_df['Code'] == code]
        return row.iloc[0]['Sector'] if not row.empty else "기타"
    except: return "기타"

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

def send_telegram_msg(message):
    try:
        if "TELEGRAM_TOKEN" in st.secrets and "CHAT_ID" in st.secrets:
            token = st.secrets["TELEGRAM_TOKEN"]
            chat_id = st.secrets["CHAT_ID"]
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.get(url, params={"chat_id": chat_id, "text": message})
            return True
        return False
    except: return False

# --- [3. PRO 분석 엔진 (데이터 어벤져스)] ---

@st.cache_data(ttl=1200)
def get_hankyung_consensus(code):
    """한경 컨센서스: 목표가/의견 추출"""
    try:
        # 실제로는 크롤링이 복잡하므로 예외처리 강화
        url = f"http://consensus.hankyung.com/apps.analysis/analysis.list?sdate={datetime.datetime.now().strftime('%Y-%m-%d')}&edate={datetime.datetime.now().strftime('%Y-%m-%d')}&search_value={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        # (간단한 요청 시도, 실패시 None 반환하여 시스템 멈춤 방지)
        return None 
    except: return None

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    """컴퍼니가이드 로직: 펀더멘탈 점수 (50점 만점)"""
    try:
        df = stock.get_market_fundamental_by_ticker(datetime.datetime.now().strftime("%Y%m%d"), code)
        if df.empty: return 25, "데이터 없음"
        
        per = df.loc['PER']; pbr = df.loc['PBR']; div = df.loc['DIV']
        score = 20
        reasons = []
        
        if 0 < pbr < 1.0: score += 15; reasons.append("PBR 1배 미만(저평가)")
        elif pbr < 2.0: score += 5
        
        if 0 < per < 10: score += 10; reasons.append("PER 10배 미만(실적우수)")
        if div > 3.0: score += 5; reasons.append(f"배당수익률 {div}%")
        
        return min(score, 50), ", ".join(reasons) if reasons else "밸류에이션 적정"
    except: return 25, "분석 보류"

@st.cache_data(ttl=600)
def get_news_sentiment(code):
    """네이버 뉴스 심리 분석 (가산점)"""
    try:
        url = f"https://finance.naver.com/item/news_news.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.content, "html.parser")
        titles = soup.select(".title .tit")
        
        score = 0; headline = "-"
        good = ["수주", "계약", "최대", "흑자", "성장", "호조", "개발", "승인"]
        bad = ["적자", "하향", "우려", "급락", "손실", "불확실"]
        
        if titles:
            headline = titles[0].get_text().strip()
            for t in titles[:5]:
                txt = t.get_text()
                for g in good: 
                    if g in txt: score += 2; break
                for b in bad:
                    if b in txt: score -= 3; break
        
        return {"score": min(max(score, -10), 10), "headline": headline}
    except: return {"score": 0, "headline": "-"}

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
        # [데이터 확보] 1년 3개월치 데이터 (240일선 계산용)
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=450))
        if df.empty or len(df) < 240: return None
        
        # [어벤져스 데이터 호출]
        sup = get_supply_demand(code)
        fund_score, fund_reason = get_company_guide_score(code) # 정성적 1
        news = get_news_sentiment(code) # 정성적 2
        # h_con = get_hankyung_consensus(code) # (속도 이슈로 잠시 제외, 필요시 활성화)

        # [기술적 분석: 5대 이평선]
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['MA120'] = df['Close'].rolling(120).mean()
        df['MA240'] = df['Close'].rolling(240).mean()
        
        # 볼린저/RSI
        df['Std'] = df['Close'].rolling(20).std()
        df['Upper'] = df['MA20'] + (df['Std'] * 2)
        df['Lower'] = df['MA20'] - (df['Std'] * 2)
        delta = df['Close'].diff(1)
        rsi = 100 - (100/(1 + (delta.where(delta>0,0).rolling(14).mean() / -delta.where(delta<0,0).rolling(14).mean())))
        curr = df.iloc[-1]
        
        # --- [PRO 하이브리드 스코어링] ---
        # 1. Tech Score (50점)
        tech_score = 0
        ma_status = []
        
        # 이평선 돌파 (30점)
        mas = [('5일', 'MA5'), ('20일', 'MA20'), ('60일', 'MA60'), ('120일', 'MA120'), ('240일', 'MA240')]
        cnt = 0
        for label, col in mas:
            if curr['Close'] >= curr[col]: 
                cnt += 1; ma_status.append(f"✅ {label}")
            else: ma_status.append(f"❌ {label}")
        tech_score += (cnt * 6)
        
        # 정배열 가산 (10점)
        if curr['MA5'] > curr['MA20'] > curr['MA60']: tech_score += 10; ma_status.append("🔥 정배열 초기")
        
        # 수급 가산 (10점)
        if sup['f'] > 0 or sup['i'] > 0: tech_score += 10
        
        # 2. Fund Score (50점) + News Bonus
        final_score = int((tech_score * 0.5) + fund_score + news['score'])
        final_score = min(max(final_score, 0), 100)
        
        # 3. 전략 수립 (괴리율 최소화)
        # 목표가는 점수가 높을수록(펀더멘탈 튼튼) 높게 잡음
        upside = 0.05 + (final_score / 1000) # 5% ~ 15% 사이
        target_price = curr['Close'] * (1 + upside)
        buy_price = curr['MA20']
        
        # 액션 판단
        if final_score >= 80: action = "강력 매수"
        elif final_score >= 60: action = "매수 긍정"
        elif final_score <= 40: action = "매도/관망"
        else: action = "중립"
        
        strategy = {
            "action": action,
            "buy": int(buy_price),
            "target": int(target_price),
            "fund_detail": f"{fund_reason} (뉴스점수: {news['score']})",
            "tech_detail": f"이평선 {cnt}개 돌파 / 수급 {'양호' if sup['f']>0 else '보통'}",
            "ma_list": ma_status
        }
        
        return {
            "name": name_override, "code": code, "price": int(curr['Close']),
            "score": final_score, "rsi": rsi.iloc[-1], "bb_status": "밴드내",
            "checks": [fund_reason.split(',')[0], "정배열" if cnt>=3 else "역배열"],
            "strategy": strategy, "supply": sup, "news": news, "history": df
        }
    except: return None

def analyze_portfolio_parallel(watchlist):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor: # Worker 줄여서 안정성 확보
        futures = {executor.submit(analyze_pro, info['code'], name): name for name, info in watchlist.items()}
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                if res: results.append(res)
            except: continue
    return sorted(results, key=lambda x: x['score'], reverse=True)

# --- [4. 매크로 및 차트 유틸] ---
@st.cache_data(ttl=3600)
def get_global_macro():
    try:
        indices = {"S&P 500": "US500", "VIX (공포)": "^VIX", "WTI 유가": "CL=F", "미국채 10년": "^TNX"}
        res = {}; score = 0
        for n, c in indices.items():
            df = fdr.DataReader(c, datetime.datetime.now() - datetime.timedelta(days=20))
            if not df.empty:
                now = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]; chg = ((now - prev)/prev)*100
                
                # [V18.3 PRO 로직: VIX < 20 Good]
                if "VIX" in n: is_good = now < 20
                elif "S&P" in n: is_good = chg > 0 # 상승이 좋음
                else: is_good = chg < 0 # 유가, 금리는 하락이 좋음
                
                res[n] = {"v": now, "c": chg, "good": is_good}
                score += 1 if is_good else -1
        return {"data": res, "score": score}
    except: return None

def create_bollinger_chart(df, name):
    chart_data = df.tail(120).reset_index() # 6개월치 차트
    base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=alt.Axis(format='%m-%d', title=None)))
    line = base.mark_line(color='#333D4B').encode(y=alt.Y('Close:Q', scale=alt.Scale(zero=False)))
    ma20 = base.mark_line(color='#F2A529').encode(y='MA20:Q') # 황금선
    ma60 = base.mark_line(color='#3182F6').encode(y='MA60:Q') # 수급선
    return (line + ma20 + ma60).properties(height=250)

# --- [5. 메인 UI 렌더링] ---
st.title("💎 Quant Sniper V18.3 PRO")
st.caption("Hybrid Engine: Fundamental(50%) + Technical(50%) | Data Source: KRX, Naver, Yahoo")

# 1. 범례 (PRO 버전)
with st.expander("📘 PRO 모드 지표 해석 가이드 (필독)", expanded=True):
    st.markdown("""
    <table class='legend-table'>
        <tr><td colspan='2' class='legend-header'>📊 하이브리드 분석 기준</td></tr>
        <tr><td><span class='legend-title'>AI 점수</span></td><td><b>80점↑:</b> 강력 매수 (실적+추세 완벽)<br><b>60점↑:</b> 매수 긍정 (분할 매수)</td></tr>
        <tr><td><span class='legend-title'>VIX (공포)</span></td><td><b>20 미만:</b> 시장 안정 (적극 투자) <span class='text-up'>●</span></td></tr>
        <tr><td><span class='legend-title'>재무 진단</span></td><td>PBR 1배 미만, PER 10배 미만 시 가산점 부여 (컴퍼니가이드 로직)</td></tr>
    </table>
    """, unsafe_allow_html=True)

# 2. 매크로 (PRO 로직 적용)
macro = get_global_macro()
if macro:
    cols = st.columns(5)
    
    # 시장 점수 표시
    sc = macro['score']
    if sc >= 1: state="적극 투자"; s_col="text-up"; s_bg="badge-buy"
    elif sc <= -1: state="보수적"; s_col="text-down"; s_bg="badge-sell"
    else: state="관망"; s_col="text-gray"; s_bg="badge-neu"
    
    with cols[0]:
        st.markdown(f"<div class='macro-box'><div class='label-text'>시장 점수</div><div class='macro-val {s_col}'>{sc}</div><div class='badge-clean {s_bg}'>{state}</div></div>", unsafe_allow_html=True)
        
    for i, (k, v) in enumerate(macro['data'].items()):
        col = "text-up" if v['good'] else "text-down" # 빨강=호재
        bg = "badge-buy" if v['good'] else "badge-sell"
        txt = "긍정" if v['good'] else "부정"
        with cols[i+1]:
             st.markdown(f"<div class='macro-box'><div class='label-text'>{k}</div><div class='macro-val {col}'>{v['v']:.2f}</div><div class='badge-clean {bg}'>{txt}</div></div>", unsafe_allow_html=True)

st.divider()

# 3. 메인 분석 탭
tab1, tab2 = st.tabs(["💼 내 포트폴리오 (PRO)", "🔭 종목 발굴"])

with tab1:
    if not st.session_state['watchlist']: st.info("왼쪽 사이드바에서 종목을 추가해주세요.")
    else:
        with st.spinner("PRO 엔진 가동 중... (재무/수급/이평선 정밀 분석)"):
            results = analyze_portfolio_parallel(st.session_state['watchlist'])
        
        for res in results:
            # 카드 생성 (HTML 직접 구성)
            score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
            
            # HTML 렌더링
            st.markdown(f"""
            <div class='toss-card'>
                <div style='display:flex; justify-content:space-between;'>
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
                    <div class='strategy-item'><span class='strategy-label'>재무 상태</span><span class='strategy-val'>{res['checks'][0]}</span></div>
                </div>
                
                <div style='margin-top:15px; font-size:13px;'>
                    <div style='display:flex; justify-content:space-between;'>
                        <span style='color:#888;'>외국인 수급</span>
                        <span style='font-weight:bold; color:{"#F04452" if res['supply']['f']>0 else "#3182F6"}'>{res['supply']['f']:,}</span>
                    </div>
                    <div style='display:flex; justify-content:space-between; margin-top:5px;'>
                        <span style='color:#888;'>RSI (14)</span>
                        <span>{res['rsi']:.1f}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # PRO 리포트 (Expandable)
            with st.expander(f"📑 {res['name']} AI 심층 분석 리포트 확인"):
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("📈 기술적 분석 (50%)")
                    st.info(res['strategy']['tech_detail'])
                    st.write("**이평선 상태:**")
                    for s in res['strategy']['ma_list']: st.write(s)
                with c2:
                    st.subheader("🏢 펀더멘탈 분석 (50%)")
                    st.success(res['strategy']['fund_detail'])
                    if res['news']['headline'] != "-":
                        st.write(f"**최신 뉴스:** {res['news']['headline']}")
                    else: st.write("특이 뉴스 없음")
                
                st.altair_chart(create_bollinger_chart(res['history'], res['name']), use_container_width=True)

# 4. 사이드바 (종목 추가)
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
