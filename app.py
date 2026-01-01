import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
import json
import os
import time
import base64
from pykrx import stock
import concurrent.futures

# --- [1. 설정 및 UI 스타일링] ---
st.set_page_config(page_title="Pro Quant V13.3", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #F0F2F6; font-family: 'Pretendard', sans-serif; }
    .glass-card { background: rgba(38, 39, 48, 0.6); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px; padding: 24px; margin-bottom: 20px; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3); }
    .border-buy { border-left: 5px solid #00E676 !important; }
    .border-sell { border-left: 5px solid #FF5252 !important; }
    .text-up { color: #00E676; }
    .text-down { color: #FF5252; }
    .text-gray { color: #888; }
    .big-price { font-size: 32px; font-weight: 800; letter-spacing: -1px; }
    .stock-name { font-size: 22px; font-weight: 700; color: #FFFFFF; }
    .stock-code { font-size: 14px; color: #888; margin-left: 8px; font-weight: 400; }
    .macro-box { background: #1A1C24; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #333; height: 100%; }
    .macro-label { font-size: 11px; color: #888; text-transform: uppercase; margin-bottom: 8px; font-weight: bold; }
    .macro-val { font-size: 20px; font-weight: 800; color: #fff; margin-bottom: 8px; }
    .status-badge { font-size: 12px; font-weight: bold; padding: 4px 8px; border-radius: 6px; display: inline-block; width: 100%; }
    .status-good { background-color: rgba(0, 230, 118, 0.15); color: #00E676; border: 1px solid rgba(0, 230, 118, 0.3); }
    .status-bad { background-color: rgba(255, 82, 82, 0.15); color: #FF5252; border: 1px solid rgba(255, 82, 82, 0.3); }
    .status-neutral { background-color: rgba(136, 136, 136, 0.15); color: #aaa; border: 1px solid rgba(136, 136, 136, 0.3); }
    .check-item { font-size: 13px; margin-bottom: 4px; display: flex; align-items: center; color: #ddd; }
    .score-bg { background: #333; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 8px; }
    .score-fill { height: 100%; border-radius: 3px; }
    .strategy-badge { font-size: 14px; font-weight: bold; padding: 6px 12px; border-radius: 8px; display: inline-block; margin-top: 5px; text-align: center; width: 100%; }
    .streamlit-expanderContent { background-color: #1A1C24 !important; color: #F0F2F6 !important; border-radius: 10px; }
    .legend-table { width: 100%; font-size: 14px; border-collapse: collapse; margin-top: 5px; }
    .legend-table td { padding: 12px; border-bottom: 1px solid #444; color: #ddd; vertical-align: middle; line-height: 1.5; }
    .legend-header { font-weight: bold; color: #FFD700; background-color: #262730; text-align: center; padding: 10px; border-radius: 5px; }
    .legend-title { font-weight: bold; color: #fff; width: 150px; background-color: #222; padding-left: 10px; border-radius: 4px; }
    .badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; display: inline-block; margin-right: 5px; }
    .badge-sector { background: #333; color: #ccc; border: 1px solid #444; }
    .badge-buy { background: rgba(0, 230, 118, 0.2); color: #00E676; border: 1px solid #00E676; }
    div.stButton > button { width: 100%; border-radius: 10px; font-weight: bold; border: 1px solid #444; background: #1E222D; color: white; }
    div.stButton > button:hover { border-color: #00E676; color: #00E676; }
</style>
""", unsafe_allow_html=True)

# --- [2. 데이터 및 GitHub 연동] ---
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

@st.cache_data
def get_krx_list():
    try:
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name', 'Sector']]
    except:
        return pd.DataFrame()

krx_df = get_krx_list()

def get_sector_info(code):
    try:
        row = krx_df[krx_df['Code'] == code]
        if not row.empty:
            return row.iloc[0]['Sector']
        return "기타"
    except:
        return "기타"

def load_local_json():
    # [수정] 줄바꿈을 넣어 문법 오류 방지
    if os.path.exists(FILE_PATH):
        try:
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_local_json(data):
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_from_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return load_local_json()
        
        token = st.secrets["GITHUB_TOKEN"]
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            return json.loads(content)
        return load_local_json()
    except:
        return load_local_json()

def save_to_github(data):
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            save_local_json(data)
            return False, "GitHub 토큰이 설정되지 않았습니다. (로컬에만 저장됨)"
            
        token = st.secrets["GITHUB_TOKEN"]
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        
        r = requests.get(url, headers=headers)
        sha = r.json().get('sha') if r.status_code == 200 else None
        
        json_str = json.dumps(data, indent=4, ensure_ascii=False)
        b64_content = base64.b64encode(json_str.encode()).decode()
        
        payload = {
            "message": "Update watchlist from Pro Quant UI",
            "content": b64_content,
            "sha": sha
        }
        
        put_r = requests.put(url, headers=headers, json=payload)
        if put_r.status_code in [200, 201]:
            return True, "GitHub 서버 동기화 완료!"
        else:
            save_local_json(data)
            return False, f"GitHub 저장 실패: {put_r.status_code} (로컬에 저장됨)"
    except Exception as e:
        save_local_json(data)
        return False, f"에러 발생: {e} (로컬에 저장됨)"

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

# --- [3. 분석 및 UI 로직] ---

def create_card_html(item, sector, is_recomm=False):
    if not item: return ""
    
    score = item['score']
    
    # 테두리, 색상, 뱃지 설정
    if score >= 75:
        border_cls = "border-buy"
        score_color = "#00E676"
        p_color = "text-up"
        badge_text = "🚀 강력 매수"
        badge_bg = "rgba(0, 230, 118, 0.2)"
        badge_border = "#00E676"
        badge_font = "#00E676"
    elif score <= 25:
        border_cls = "border-sell"
        score_color = "#FF5252"
        p_color = "text-down"
        badge_text = "📉 매도 권장"
        badge_bg = "rgba(255, 82, 82, 0.2)"
        badge_border = "#FF5252"
        badge_font = "#FF5252"
    else:
        border_cls = ""
        score_color = "#FFD700"
        p_color = "text-gray"
        badge_text = "👀 관망 (중립)"
        badge_bg = "rgba(255, 215, 0, 0.15)"
        badge_border = "#FFD700"
        badge_font = "#FFD700"
    
    if is_recomm: 
        border_cls = "border-buy"
        p_color = "text-up"
    
    checks_html = "".join([f"<div class='check-item'>{c}</div>" for c in item['checks']])
    
    supply_f = format(int(item['supply']['f']), ',')
    supply_i = format(int(item['supply']['i']), ',')
    supply_f_col = '#00E676' if item['supply']['f']>0 else '#FF5252'
    supply_i_col = '#00E676' if item['supply']['i']>0 else '#FF5252'
    price_fmt = format(item['price'], ',')
    
    sector_badge = f"<span class='badge badge-sector'>{sector}</span>"
    if is_recomm: sector_badge = "<span class='badge badge-buy'>STRONG BUY</span>" + sector_badge
    
    html = f"""
    <div class='glass-card {border_cls}'>
        <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
            <div>
                {sector_badge}
                <div style='margin-top:8px;'>
                    <span class='stock-name'>{item.get('name', 'Unknown')}</span>
                    <span class='stock-code'>{item['code']}</span>
                </div>
                <div class='big-price {p_color}'>{price_fmt}원</div>
            </div>
            <div style='text-align:right; width: 130px;'>
                <div style='font-size:12px; color:#888; margin-bottom:5px;'>AI SCORE</div>
                <div style='font-size:28px; font-weight:800; color:{score_color}; line-height:1;'>{score}</div>
                <div class='strategy-badge' style='background:{badge_bg}; border:1px solid {badge_border}; color:{badge_font};'>
                    {badge_text}
                </div>
            </div>
        </div>
        <div class='score-bg' style='margin-top:10px; margin-bottom:15px;'><div class='score-fill' style='width:{score}%; background:{score_color};'></div></div>
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

@st.cache_data(ttl=3600)
def get_global_macro():
    try:
        indices = {"USD/KRW": "USD/KRW", "WTI": "CL=F", "S&P500": "US500", "US 10Y": "^TNX", "VIX": "^VIX"}
        res = {}; score = 0
        for n, c in indices.items():
            df = fdr.DataReader(c, datetime.datetime.now() - datetime.timedelta(days=10))
            if not df.empty:
                now = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
                chg = ((now - prev) / prev) * 100
                res[n] = {"p": now, "c": chg}
                if n == "S&P500": score += 1 if chg > 0 else -1
                elif n == "USD/KRW": score += -1 if chg > 0.5 else (1 if chg < -0.5 else 0)
                elif n == "US 10Y": score += -1 if chg > 1.0 else (1 if chg < -1.0 else 0)
                elif n == "VIX": score += -2 if now > 20 else (1 if now < 15 else 0)
        return {"data": res, "score": score}
    except: return None

@st.cache_data(ttl=1800)
def get_supply_demand(code):
    try:
        e = datetime.datetime.now().strftime("%Y%m%d")
        s = (datetime.datetime.now()-datetime.timedelta(days=7)).strftime("%Y%m%d")
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
        curr = df.iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        std = df['Close'].rolling(20).std().iloc[-1]
        upper = ma20 + (std*2); lower = ma20 - (std*2)
        delta = df['Close'].diff(1)
        rsi = 100 - (100/(1 + (delta.where(delta>0,0).rolling(14).mean().iloc[-1] / -delta.where(delta<0,0).rolling(14).mean().iloc[-1])))
        
        checks = []; pass_cnt = 0
        if sup['f']>0 or sup['i']>0: checks.append("✅ 메이저 수급 유입"); pass_cnt+=1
        else: checks.append("❌ 수급 이탈")
        if curr['Close']>=ma20: checks.append("✅ 20일선 위"); pass_cnt+=1
        else: checks.append("❌ 추세 하락세")
        bb_status = "중립"
        if curr['Close']<=lower*1.02: checks.append("✅ 볼린저 하단(기회)"); pass_cnt+=1; bb_status = "하단 지지"
        elif curr['Close']>=upper*0.98: checks.append("⚠️ 볼린저 상단(과열)"); pass_cnt-=0.5; bb_status = "상단 저항"
        else: checks.append("✅ 밴드 내"); pass_cnt+=0.5; bb_status = "밴드 내"
        if rsi<=70: checks.append("✅ RSI 안정"); pass_cnt+=1
        else: checks.append("❌ RSI 과열")
        
        return {"name": name_override, "code": code, "price": curr['Close'], "checks": checks, "pass": pass_cnt, "score": min(pass_cnt*25, 100), "supply": sup, "rsi": rsi, "bb_status": bb_status}
    except: return None

def analyze_portfolio_parallel(watchlist):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(analyze_precision, info['code'], name): name for name, info in watchlist.items()}
        for future in concurrent.futures.as_completed(futures):
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
            futures = {executor.submit(analyze_precision, c, stock.get_market_ticker_name(c)): c for c in candidates}
            for future in concurrent.futures.as_completed(futures):
                try:
                    a = future.result()
                    if a and a['pass'] >= 3:
                        a['sector'] = get_sector_info(a['code'])
                        res_list.append(a)
                except: continue
        return sorted(res_list, key=lambda x: x['score'], reverse=True)
    except: return []

# --- [5. UI 렌더링] ---
with st.sidebar:
    st.header("⚡ CONTROL PANEL")
    
    auto_mode = st.checkbox("🔴 실시간 자동 감시 및 루틴 알림", value=False)
    
    st.divider()
    with st.expander("➕ 종목 추가 (자동 동기화)", expanded=True):
        n_name = st.text_input("종목명")
        n_code = st.text_input("코드")
        if st.button("추가"):
            clean_name = n_name.strip()
            clean_code = n_code.strip()
            existing_codes = [v['code'] for v in st.session_state['watchlist'].values()]
            if clean_code in existing_codes: st.error("이미 존재하는 종목입니다.")
            elif clean_name and clean_code:
                st.session_state['watchlist'][clean_name] = {"code": clean_code}
                with st.spinner("☁️ GitHub 서버에 저장 중..."):
                    success, msg = save_to_github(st.session_state['watchlist'])
                    if success: st.success(msg); time.sleep(1); st.rerun()
                    else: st.warning(msg)

    if st.session_state['watchlist']:
        st.caption(f"WATCHLIST ({len(st.session_state['watchlist'])}개)")
        for name in list(st.session_state['watchlist'].keys()):
            c1, c2 = st.columns([3,1])
            c1.markdown(f"<span style='color:#ddd'>{name}</span>", unsafe_allow_html=True)
            if c2.button("✕", key=f"del_{name}"):
                del st.session_state['watchlist'][name]
                with st.spinner("☁️ GitHub 서버 동기화 중..."):
                    save_to_github(st.session_state['watchlist'])
                    st.rerun()
                
    st.divider()
    if st.button("🗑️ 데이터 초기화"):
        st.session_state['watchlist'] = {}
        save_to_github({})
        st.rerun()

st.title("🚀 QUANT SNIPER V13.3")
st.caption(f"Fully Automated AI System | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

with st.expander("📘 범례 및 용어 설명 (모든 지표 포함)", expanded=False):
    st.markdown("<table class='legend-table'><tr><td colspan='2' class='legend-header'>🌍 글로벌 시장 지표 (상단 5개 박스)</td></tr><tr><td class='legend-title'>MARKET SCORE</td><td>시장 종합 점수. <br><b>+1 이상:</b> 투자 적기 (Risk On) / <b>-1 이하:</b> 보수적 대응 필요 (Risk Off)</td></tr><tr><td class='legend-title'>🇺🇸 S&P 500</td><td>미국 증시 지수. 한국 시장의 선행 지표 (상승 시 호재).</td></tr><tr><td class='legend-title'>🇰🇷 USD/KRW</td><td>원/달러 환율. <b>상승 시:</b> 외국인 이탈 우려 (주가에 악재).</td></tr><tr><td class='legend-title'>🛢️ WTI CRUDE</td><td>국제 유가. <b>상승 시:</b> 인플레이션 및 기업 비용 증가 (주가에 악재).</td></tr><tr><td class='legend-title' style='color:#FF5252;'>😱 VIX (공포지수)</td><td>월가 공포 지수. <b>20 이상:</b> 공포(하락장), <b>15 이하:</b> 안정(상승장).</td></tr><tr><td class='legend-title'>🇺🇸 US 10Y</td><td>미국채 10년물 금리. <b>급등 시:</b> 기술주/성장주 하락 압력 (악재).</td></tr><tr><td colspan='2' class='legend-header' style='padding-top:15px;'>📊 정밀 진단 지표</td></tr><tr><td class='legend-title'>볼린저 밴드</td><td><b>하단 터치:</b> 과매도(매수 기회), <b>상단 돌파:</b> 과열(매도 검토).</td></tr><tr><td class='legend-title'>AI SCORE</td><td><b>75점 이상:</b> 강력 매수 / <b>25점 이하:</b> 매도 권장.</td></tr></table>", unsafe_allow_html=True)

macro = get_global_macro()
if macro:
    col1, col2, col3, col4, col5 = st.columns(5)
    m_data = macro['data']; score = macro['score']
    if score >= 1: m_state = "🚀 적극 투자"; m_cls = "status-good"; m_col = "text-up"
    elif score <= -1: m_state = "🐻 위험 관리"; m_cls = "status-bad"; m_col = "text-down"
    else: m_state = "👀 관망"; m_cls = "status-neutral"; m_col = "text-gray"
    
    with col1: st.markdown(f"<div class='macro-box'><div class='macro-label'>MARKET SCORE</div><div class='macro-val {m_col}'>{score}</div><div class='status-badge {m_cls}'>{m_state}</div></div>", unsafe_allow_html=True)
    
    cols = [col2, col3, col4, col5]
    keys = ['S&P500', 'VIX', 'WTI', 'US 10Y']
    labels = ['🇺🇸 S&P 500', '😱 VIX (공포)', '🛢️ WTI CRUDE', '🇺🇸 US 10Y']
    for i, k in enumerate(keys):
        val = m_data[k]['p']; chg = m_data[k]['c']
        if k == 'VIX': 
            stt = "😱 공포" if val>=20 else ("😊 안정" if val<=15 else "😐 보통")
            cls = "status-bad" if val>=20 else ("status-good" if val<=15 else "status-neutral")
            col = "text-down" if val>=20 else "text-up"
            txt = f"{val:.2f}"
        else:
            good = (chg>0) if k=='S&P500' else (chg<0)
            stt = "📈 호재" if good else "📉 악재"
            cls = "status-good" if good else "status-bad"
            col = "text-up" if good else "text-down"
            txt = f"{val:.2f}%" if k!='WTI' else f"${val:.1f}"
        with cols[i]:
            st.markdown(f"<div class='macro-box'><div class='macro-label'>{labels[i]}</div><div class='macro-val {col}'>{txt}</div><div class='status-badge {cls}'>{stt}</div></div>", unsafe_allow_html=True)

st.write("")
tab1, tab2 = st.tabs(["📂 내 포트폴리오 (고속)", "🚀 AI 스나이퍼 발굴"])

with tab1:
    if not st.session_state['watchlist']: st.info("사이드바에서 종목을 추가하세요. (GitHub 자동 동기화)")
    else:
        with st.spinner("⚡ AI 엔진 가동 중..."): results = analyze_portfolio_parallel(st.session_state['watchlist'])
        for res in results:
            st.markdown(create_card_html(res, get_sector_info(res['code']), False), unsafe_allow_html=True)
            if auto_mode:
                today = datetime.datetime.now().strftime("%Y%m%d")
                msg_key = f"{res['code']}_{today}"
                if res['score'] >= 75 and st.session_state['sent_alerts'].get(msg_key+"_buy") != "sent":
                    send_telegram_msg(f"🚀 [AI 매수 포착] {res['name']} ({res['score']}점)\n가격: {format(res['price'],',')}원")
                    st.session_state['sent_alerts'][msg_key+"_buy"] = "sent"
                elif res['score'] <= 25 and st.session_state['sent_alerts'].get(msg_key+"_sell") != "sent":
                    send_telegram_msg(f"📉 [AI 매도 경고] {res['name']} ({res['score']}점)\n가격: {format(res['price'],',')}원")
                    st.session_state['sent_alerts'][msg_key+"_sell"] = "sent"

with tab2:
    if st.button("🔭 START SCANNING", use_container_width=True):
        with st.spinner("⚡ 전체 시장 스캔 중..."): recs = get_recommendations()
        if not recs: st.warning("조건을 만족하는 종목이 없습니다.")
        else:
            st.success(f"{len(recs)}개의 타겟 발견!")
            for item in recs: st.markdown(create_card_html(item, item['sector'], True), unsafe_allow_html=True)

if auto_mode:
    st.markdown("---")
    st.empty().markdown(f"⏳ **AI 비서 가동 중... (PC가 켜져있을 때만 작동합니다)**")
    time.sleep(60)
    st.rerun()
