import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
import json
import os
import time
from pykrx import stock
import concurrent.futures

# --- [1. 설정 및 UI 스타일링] ---
st.set_page_config(page_title="Pro Quant V11.0", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #F0F2F6; font-family: 'Pretendard', sans-serif; }
    .glass-card {
        background: rgba(38, 39, 48, 0.6);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    }
    .border-buy { border-left: 5px solid #00E676 !important; }
    .border-sell { border-left: 5px solid #FF5252 !important; }
    .text-up { color: #00E676; }
    .text-down { color: #FF5252; }
    .text-gray { color: #888; }
    .big-price { font-size: 32px; font-weight: 800; letter-spacing: -1px; }
    .stock-name { font-size: 22px; font-weight: 700; color: #FFFFFF; }
    .stock-code { font-size: 14px; color: #888; margin-left: 8px; font-weight: 400; }
    .badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; display: inline-block; margin-right: 5px; }
    .badge-sector { background: #333; color: #ccc; border: 1px solid #444; }
    .badge-buy { background: rgba(0, 230, 118, 0.2); color: #00E676; border: 1px solid #00E676; }
    .macro-box { background: #1A1C24; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #333; }
    .macro-label { font-size: 11px; color: #888; text-transform: uppercase; margin-bottom: 5px; font-weight: bold; }
    .macro-val { font-size: 18px; font-weight: 700; color: #fff; }
    .analysis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px; background: rgba(0,0,0,0.2); padding: 15px; border-radius: 12px; }
    .check-item { font-size: 13px; margin-bottom: 4px; display: flex; align-items: center; color: #ddd; }
    .score-bg { background: #333; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 8px; }
    .score-fill { height: 100%; border-radius: 3px; }
    .legend-table { width: 100%; font-size: 14px; border-collapse: collapse; margin-top: 5px; }
    .legend-table td { padding: 12px; border-bottom: 1px solid #333; color: #ddd; vertical-align: middle; line-height: 1.5; }
    .legend-header { font-weight: bold; color: #FFD700; background-color: #262730; text-align: center; padding: 10px; }
    .legend-title { font-weight: bold; color: #fff; width: 160px; background-color: #1E1E1E; }
    div.stButton > button { width: 100%; border-radius: 10px; font-weight: bold; border: 1px solid #444; background: #1E222D; color: white; }
    div.stButton > button:hover { border-color: #00E676; color: #00E676; }
</style>
""", unsafe_allow_html=True)

DATA_FILE = "my_watchlist_v7.json"
SETTINGS_FILE = "my_settings.json"

# --- [2. 데이터 핸들링] ---
@st.cache_data
def get_krx_list():
    try: df = fdr.StockListing('KRX'); return df[['Code', 'Name', 'Sector']]
    except: return pd.DataFrame()
krx_df = get_krx_list()

def get_sector_info(code):
    try: row = krx_df[krx_df['Code'] == code]; return row.iloc[0]['Sector'] if not row.empty else "기타"
    except: return "기타"

def load_json(file):
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

if 'watchlist' not in st.session_state: st.session_state['watchlist'] = load_json(DATA_FILE)
settings = load_json(SETTINGS_FILE)
if 'sent_alerts' not in st.session_state: st.session_state['sent_alerts'] = {}
if 'routine_flags' not in st.session_state: st.session_state['routine_flags'] = {}

def send_telegram_msg(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.get(url, params={"chat_id": chat_id, "text": message})
        return True
    except: return False

# --- [3. HTML 생성 헬퍼] ---
def create_card_html(item, sector, is_recomm=False):
    if not item: return ""
    border_cls = "border-buy" if item['pass'] >= 3 else ("border-sell" if item['pass'] <= 1 else "")
    if is_recomm: border_cls = "border-buy"
    
    p_color = "text-up" if item['pass'] >= 3 else ("text-down" if item['pass'] <= 1 else "text-gray")
    if is_recomm: p_color = "text-up"
    
    score_color = "#00E676" if item['score'] >= 75 else ("#FF5252" if item['score'] <= 25 else "#FFD700")
    
    checks_html = "".join([f"<div class='check-item'>{c}</div>" for c in item['checks']])
    
    supply_f = format(int(item['supply']['f']), ',')
    supply_i = format(int(item['supply']['i']), ',')
    supply_f_col = '#00E676' if item['supply']['f']>0 else '#FF5252'
    supply_i_col = '#00E676' if item['supply']['i']>0 else '#FF5252'
    price_fmt = format(item['price'], ',')
    
    badge_html = f"<span class='badge badge-sector'>{sector}</span>"
    if is_recomm: badge_html = "<span class='badge badge-buy'>STRONG BUY</span>" + badge_html
    
    html = f"""
    <div class='glass-card {border_cls}'>
        <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
            <div>
                {badge_html}
                <div style='margin-top:8px;'>
                    <span class='stock-name'>{item.get('name', 'Unknown')}</span>
                    <span class='stock-code'>{item['code']}</span>
                </div>
                <div class='big-price {p_color}'>{price_fmt}원</div>
            </div>
            <div style='text-align:right; width: 120px;'>
                <div style='font-size:12px; color:#888;'>AI SCORE</div>
                <div style='font-size:24px; font-weight:bold; color:{score_color};'>{item['score']}</div>
                <div class='score-bg'><div class='score-fill' style='width:{item['score']}%; background:{score_color};'></div></div>
            </div>
        </div>
        <div class='analysis-grid'>
            <div>
                <div style='color:#888; font-size:12px; margin-bottom:5px;'>CHECK POINTS</div>
                {checks_html}
            </div>
            <div>
                <div style='color:#888; font-size:12px; margin-bottom:5px;'>SUPPLY & TECH</div>
                <div class='check-item'>외국인: <span style='margin-left:auto; color:{supply_f_col}'>{supply_f}</span></div>
                <div class='check-item'>기관: <span style='margin-left:auto; color:{supply_i_col}'>{supply_i}</span></div>
                <div class='check-item'>RSI (14): <span style='margin-left:auto;'>{item['rsi']:.1f}</span></div>
                <div class='check-item'>볼린저: <span style='margin-left:auto;'>{item['bb_status']}</span></div>
            </div>
        </div>
    </div>
    """
    return html

# --- [4. 분석 로직] ---
@st.cache_data(ttl=3600)
def get_global_macro():
    try:
        indices = {
            "USD/KRW": "USD/KRW", 
            "WTI": "CL=F", 
            "S&P500": "US500", 
            "US 10Y": "^TNX",
            "VIX": "^VIX"
        }
        res = {}; score = 0
        
        for n, c in indices.items():
            df = fdr.DataReader(c, datetime.datetime.now()-datetime.timedelta(days=10))
            if not df.empty:
                now = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
                chg = ((now-prev)/prev)*100
                res[n] = {"p": now, "c": chg}
                if n=="S&P500": 
                    if chg>0: score+=1
                    elif chg<0: score-=1
                elif n=="USD/KRW":
                    if chg>0.5: score-=1
                    elif chg<-0.5: score+=1
                elif n=="US 10Y":
                    if chg > 1.0: score -= 1 
                    elif chg < -1.0: score += 1
                elif n=="VIX":
                    if now > 20: score -= 2
                    elif now < 15: score += 1
        return {"data": res, "score": score}
    except: return None

@st.cache_data(ttl=1800)
def get_supply_demand(code):
    try:
        e = datetime.datetime.now().strftime("%Y%m%d"); s = (datetime.datetime.now()-datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(s, e, code).tail(3)
        if df.empty: return {"score": 0, "f":0, "i":0}
        f=df['외국인'].sum(); i=df['기관합계'].sum(); sc=0
        if f>0: sc+=1
        elif f<0: sc-=1
        if i>0: sc+=0.5
        elif i<0: sc-=0.5
        return {"score": sc, "f":f, "i":i}
    except: return {"score": 0, "f":0, "i":0}

def analyze_precision(code, name_override=None):
    try:
        sup = get_supply_demand(code)
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=120))
        if df.empty: return None
        
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Std'] = df['Close'].rolling(20).std()
        df['Upper'] = df['MA20'] + (df['Std'] * 2)
        df['Lower'] = df['MA20'] - (df['Std'] * 2)
        
        delta = df['Close'].diff(1)
        rsi = 100 - (100/(1 + (delta.where(delta>0,0).rolling(14).mean() / -delta.where(delta<0,0).rolling(14).mean())))
        curr = df.iloc[-1]
        
        checks = []
        pass_cnt = 0
        
        if sup['f'] > 0 or sup['i'] > 0: checks.append("✅ 메이저 수급 유입"); pass_cnt+=1
        else: checks.append("❌ 수급 이탈");
        
        if curr['Close'] >= curr['MA20']: checks.append("✅ 20일선 위 상승추세"); pass_cnt+=1
        else: checks.append("❌ 추세 하락세");
        
        bb_status = "중립"
        if curr['Close'] <= curr['Lower'] * 1.02:
            checks.append("✅ 볼린저밴드 하단(과매도)"); pass_cnt+=1; bb_status = "하단 지지"
        elif curr['Close'] >= curr['Upper'] * 0.98:
            checks.append("⚠️ 볼린저밴드 상단(과열)"); pass_cnt-=0.5; bb_status = "상단 저항"
        else:
            checks.append("✅ 밴드 내 안정적 흐름"); pass_cnt+=0.5; bb_status = "밴드 내"
            
        if rsi.iloc[-1] <= 70: checks.append("✅ RSI 안정권"); pass_cnt+=1
        else: checks.append("❌ 과매수 구간 (RSI>70)");
        
        score = min((pass_cnt * 25), 100)
        
        return {
            "name": name_override,
            "code": code, "price": curr['Close'], "checks": checks, "pass": pass_cnt, 
            "score": score, "supply": sup, "rsi": rsi.iloc[-1], "bb_status": bb_status
        }
    except: return None

def analyze_portfolio_parallel(watchlist):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_stock = {
            executor.submit(analyze_precision, info['code'], name): (name, info) 
            for name, info in watchlist.items()
        }
        for future in concurrent.futures.as_completed(future_to_stock):
            try:
                res = future.result()
                if res: results.append(res)
            except: continue
    return results

@st.cache_data(ttl=3600)
def get_recommendations():
    try:
        t = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        f_list = stock.get_market_net_purchases_of_equities_by_ticker(t, t, "KOSPI", "외국인").head(10).index.tolist()
        i_list = stock.get_market_net_purchases_of_equities_by_ticker(t, t, "KOSPI", "기관합계").head(10).index.tolist()
        candidates = list(set(f_list + i_list))
        
        res_list = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_code = {executor.submit(analyze_precision, c, stock.get_market_ticker_name(c)): c for c in candidates}
            for future in concurrent.futures.as_completed(future_to_code):
                try:
                    a = future.result()
                    if a and a['pass'] >= 3:
                        a['sector'] = get_sector_info(a['code'])
                        res_list.append(a)
                except: continue
        res_list.sort(key=lambda x: x['score'], reverse=True)
        return res_list
    except: return []

# --- [5. UI 렌더링] ---
with st.sidebar:
    st.header("⚡ CONTROL PANEL")
    
    with st.expander("🔔 텔레그램 알림 설정"):
        t_token = st.text_input("Bot Token", value=settings.get("token", ""), type="password")
        t_chat = st.text_input("Chat ID", value=settings.get("chat_id", ""))
        if st.button("설정 저장 및 테스트"):
            save_json(SETTINGS_FILE, {"token": t_token, "chat_id": t_chat})
            if send_telegram_msg(t_token, t_chat, "🚀 [SYSTEM] 알림 봇 연결 확인 완료"): st.success("성공")
            else: st.error("실패")

    # 자동 모드 체크박스 (GitHub Actions를 쓰더라도 화면 켜둘 때 유용함)
    auto_mode = st.checkbox("🔴 실시간 자동 감시 및 루틴 알림", value=False)
    
    st.divider()
    with st.expander("➕ 종목 추가 (중복 방지)", expanded=True):
        n_name = st.text_input("종목명")
        n_code = st.text_input("코드")
        if st.button("추가"):
            clean_name = n_name.strip()
            clean_code = n_code.strip()
            existing_codes = [v['code'] for v in st.session_state['watchlist'].values()]
            if clean_code in existing_codes: st.error("이미 존재하는 종목입니다.")
            elif clean_name and clean_code:
                st.session_state['watchlist'][clean_name] = {"code": clean_code}
                save_json(DATA_FILE, st.session_state['watchlist']); st.rerun()

    if st.session_state['watchlist']:
        st.caption(f"WATCHLIST ({len(st.session_state['watchlist'])}개)")
        for name in list(st.session_state['watchlist'].keys()):
            c1, c2 = st.columns([3,1])
            c1.markdown(f"<span style='color:#ddd'>{name}</span>", unsafe_allow_html=True)
            if c2.button("✕", key=f"del_{name}"):
                del st.session_state['watchlist'][name]
                save_json(DATA_FILE, st.session_state['watchlist']); st.rerun()
                
    st.divider()
    if st.button("🗑️ 데이터 초기화"):
        st.session_state['watchlist'] = {}
        save_json(DATA_FILE, {})
        st.rerun()

st.title("🚀 QUANT SNIPER V11.0")
st.caption(f"Full-Stack Market Analysis System | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

legend_html = """
<table class='legend-table'>
    <tr><td colspan="2" class='legend-header'>🌍 글로벌 시장 지표 (상단 5개 박스)</td></tr>
    <tr><td class='legend-title'>MARKET SCORE</td><td>시장 종합 점수. <br><b>+1 이상:</b> 투자 적기 (Risk On) / <b>-1 이하:</b> 보수적 대응 필요 (Risk Off)</td></tr>
    <tr><td class='legend-title' style='color:#FF5252;'>VIX (공포지수)</td><td>월가 공포 지수. <b>20 이상:</b> 공포(하락장), <b>15 이하:</b> 안정(상승장).</td></tr>
    <tr><td class='legend-title'>US 10Y</td><td>미국채 10년물 금리. 급등 시 주식 시장에 악재.</td></tr>
    
    <tr><td colspan="2" class='legend-header' style='padding-top:15px;'>📊 정밀 진단 지표</td></tr>
    <tr><td class='legend-title'>볼린저 밴드</td><td><b>하단 터치:</b> 과매도(매수 기회), <b>상단 돌파:</b> 과열(매도 검토).</td></tr>
    <tr><td class='legend-title'>AI SCORE</td><td><b>75점 이상:</b> 강력 매수 / <b>25점 이하:</b> 매도 권장.</td></tr>
</table>
"""
with st.expander("📘 범례 및 용어 설명 (여기를 눌러 확인하세요)", expanded=False):
    st.markdown(legend_html, unsafe_allow_html=True)

# 매크로
macro = get_global_macro()
if macro:
    col1, col2, col3, col4, col5 = st.columns(5)
    m_data = macro['data']
    with col1:
        st.markdown(f"<div class='macro-box'><div class='macro-label'>MARKET SCORE</div><div class='macro-val' style='color:{'#00E676' if macro['score']>=1 else '#FF5252'}'>{macro['score']}</div></div>", unsafe_allow_html=True)
    with col2:
        c_col = "text-up" if m_data['S&P500']['c'] > 0 else "text-down"
        st.markdown(f"<div class='macro-box'><div class='macro-label'>🇺🇸 S&P 500</div><div class='macro-val {c_col}'>{m_data['S&P500']['c']:.2f}%</div></div>", unsafe_allow_html=True)
    with col3:
        c_col = "text-down" if m_data['VIX']['p'] > 20 else "text-up"
        st.markdown(f"<div class='macro-box'><div class='macro-label'>😱 VIX (공포)</div><div class='macro-val {c_col}'>{m_data['VIX']['p']:.2f}</div></div>", unsafe_allow_html=True)
    with col4:
        c_col = "text-up" if m_data['WTI']['c'] > 0 else "text-down"
        st.markdown(f"<div class='macro-box'><div class='macro-label'>🛢️ WTI CRUDE</div><div class='macro-val {c_col}'>${m_data['WTI']['p']:.1f}</div></div>", unsafe_allow_html=True)
    with col5:
        c_col = "text-down" if m_data['US 10Y']['c'] > 0 else "text-up"
        st.markdown(f"<div class='macro-box'><div class='macro-label'>🇺🇸 US 10Y</div><div class='macro-val {c_col}'>{m_data['US 10Y']['p']:.2f}%</div></div>", unsafe_allow_html=True)

st.write("")
tab1, tab2 = st.tabs(["📂 내 포트폴리오 (고속)", "🚀 AI 스나이퍼 발굴"])

with tab1:
    if not st.session_state['watchlist']: st.info("사이드바에서 종목을 추가하세요.")
    else:
        with st.spinner("⚡ AI 엔진 가동 중..."):
            results = analyze_portfolio_parallel(st.session_state['watchlist'])
        
        for res in results:
            card_html = create_card_html(res, get_sector_info(res['code']), is_recomm=False)
            st.markdown(card_html, unsafe_allow_html=True)
            
            # [화면이 켜져있을 때 알림 로직]
            if auto_mode and t_token and t_chat:
                today = datetime.datetime.now().strftime("%Y%m%d")
                price_fmt = format(res['price'], ',')
                reasons_txt = "\n".join(res['checks'])
                
                if res['score'] >= 75:
                    msg_key = f"{res['code']}_buy_{today}"
                    if st.session_state['sent_alerts'].get(msg_key) != "sent":
                        msg = f"🚀 [AI 매수 포착] {res['name']}\n가격: {price_fmt}원\n점수: {res['score']}점\n\n[이유]\n{reasons_txt}"
                        if send_telegram_msg(t_token, t_chat, msg): st.session_state['sent_alerts'][msg_key] = "sent"
                elif res['score'] <= 25:
                    msg_key = f"{res['code']}_sell_{today}"
                    if st.session_state['sent_alerts'].get(msg_key) != "sent":
                        msg = f"📉 [AI 매도 경고] {res['name']}\n가격: {price_fmt}원\n점수: {res['score']}점\n\n[이유]\n{reasons_txt}"
                        if send_telegram_msg(t_token, t_chat, msg): st.session_state['sent_alerts'][msg_key] = "sent"

with tab2:
    if st.button("🔭 START SCANNING", use_container_width=True):
        with st.spinner("⚡ 전체 시장 스캔 중..."):
            recs = get_recommendations()
        if not recs:
            st.warning("조건을 만족하는 종목이 없습니다.")
        else:
            st.success(f"{len(recs)}개의 타겟 발견!")
            for item in recs:
                card_html = create_card_html(item, item['sector'], is_recomm=True)
                st.markdown(card_html, unsafe_allow_html=True)

# [NEW] 루틴별 자동 알림 시스템 (화면이 켜져있을 때만 작동하는 백업용 루틴)
if auto_mode and t_token and t_chat:
    now = datetime.datetime.now()
    today_str = now.strftime("%Y%m%d")
    
    # 1. 아침 시황 브리핑 (08:50 ~ 08:59 사이)
    if 8 <= now.hour < 9 and now.minute >= 50:
        if st.session_state['routine_flags'].get(f"market_{today_str}") != "sent":
            m_score = macro['score']
            msg = f"🌅 [장전 시황 브리핑]\n\n📊 Market Score: {m_score}\n🇺🇸 S&P500: {macro['data']['S&P500']['c']:.2f}%\n😱 VIX: {macro['data']['VIX']['p']:.2f}\n"
            if send_telegram_msg(t_token, t_chat, msg): st.session_state['routine_flags'][f"market_{today_str}"] = "sent"
    
    # 2. 오후 추천 (14:30 ~ 14:40 사이)
    if now.hour == 14 and 30 <= now.minute <= 40:
        if st.session_state['routine_flags'].get(f"sniper_{today_str}") != "sent":
            recs = get_recommendations()
            if recs:
                msg = f"☕ [마감 전 AI 추천주]\n{recs[0]['name']}"
                if send_telegram_msg(t_token, t_chat, msg): st.session_state['routine_flags'][f"sniper_{today_str}"] = "sent"

if auto_mode:
    st.markdown("---")
    status_text = st.empty()
    status_text.markdown(f"⏳ **AI 비서 가동 중... (PC가 켜져있을 때만 작동합니다)**")
    time.sleep(60)
    st.rerun()
