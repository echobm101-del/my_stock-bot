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

# --- [1. 설정 및 UI 스타일링 (토스 화이트 테마)] ---
st.set_page_config(page_title="Quant Sniper V16.9", page_icon="📈", layout="wide")

st.markdown("""
<style>
    /* 1. 전체 배경 및 폰트 */
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif; }
    
    /* 2. 카드 디자인 */
    .toss-card { 
        background: #FFFFFF; 
        border-radius: 24px; 
        padding: 24px; 
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); 
        border: 1px solid #F2F4F6; 
        margin-bottom: 16px; 
    }
    
    /* 3. 색상 시스템 */
    .text-up { color: #F04452 !important; }   /* 빨강 (상승) */
    .text-down { color: #3182F6 !important; } /* 파랑 (하락) */
    .text-gray { color: #8B95A1 !important; } 
    
    /* 4. 텍스트 스타일 */
    .big-price { font-size: 32px; font-weight: 800; letter-spacing: -0.5px; color: #191F28; }
    .stock-name { font-size: 22px; font-weight: 700; color: #333D4B; }
    .stock-code { font-size: 14px; color: #8B95A1; margin-left: 6px; font-weight: 500; }
    .label-text { font-size: 12px; color: #8B95A1; font-weight: 600; margin-bottom: 4px; }
    
    /* 5. 뱃지 스타일 */
    .badge-clean { padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700; display: inline-block; }
    .badge-buy { background-color: rgba(240, 68, 82, 0.1); color: #F04452; }    /* 긍정 (빨강 배경) */
    .badge-sell { background-color: rgba(49, 130, 246, 0.1); color: #3182F6; }   /* 부정 (파랑 배경) */
    .badge-neu { background-color: #F2F4F6; color: #4E5968; }
    
    /* 6. 매크로 박스 */
    .macro-box { background: #F9FAFB; border-radius: 16px; padding: 16px; text-align: center; height: 100%; border: 1px solid #F2F4F6; }
    .macro-val { font-size: 20px; font-weight: 800; color: #333D4B; margin-bottom: 8px; }
    
    /* 7. 체크포인트 및 바 */
    .check-container { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    .check-tag { font-size: 12px; padding: 6px 12px; border-radius: 18px; background: #F2F4F6; color: #4E5968; font-weight: 600; display: flex; align-items: center; }
    .score-bg { background: #F2F4F6; height: 8px; border-radius: 4px; overflow: hidden; margin-top: 10px; }
    .score-fill { height: 100%; border-radius: 4px; }
    
    /* 8. RSI 그라데이션 컨테이너 */
    .rsi-container { width: 100%; background-color: #F2F4F6; height: 10px; border-radius: 5px; margin-top: 8px; overflow: hidden; }
    .rsi-bar { height: 100%; border-radius: 5px; transition: width 0.5s ease-in-out; }
    
    /* 범례 테이블 스타일 */
    .legend-table { width: 100%; font-size: 14px; border-collapse: collapse; margin-top: 5px; }
    .legend-table td { padding: 12px; border-bottom: 1px solid #F2F4F6; color: #333D4B; vertical-align: middle; line-height: 1.5; }
    .legend-header { font-weight: 800; color: #191F28; background-color: #F9FAFB; text-align: center; padding: 10px; border-radius: 8px; margin-bottom: 10px; display: block;}
    .legend-title { font-weight: 700; color: #4E5968; width: 140px; background-color: #F2F4F6; padding: 6px 10px; border-radius: 6px; text-align: center; display: inline-block;}
    
    .streamlit-expanderContent { background-color: #FFFFFF !important; border: 1px solid #F2F4F6; border-radius: 12px; }
    div.stButton > button { width: 100%; border-radius: 12px; font-weight: bold; border: none; background: #3182F6; color: white; padding: 12px 0; transition: 0.2s; }
    div.stButton > button:hover { background: #1B64DA; }
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
        df['Sector'] = df['Sector'].fillna('기타')
        return df[['Code', 'Name', 'Sector']]
    except: 
        return pd.DataFrame()

krx_df = get_krx_list()

def get_sector_info(code):
    try: 
        row = krx_df[krx_df['Code'] == code]
        return row.iloc[0]['Sector'] if not row.empty else "기타"
    except: 
        return "기타"

def load_local_json():
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
        payload = {"message": "Update watchlist from Pro Quant UI", "content": b64_content, "sha": sha}
        
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

# --- [3. 분석 및 계산 로직] ---

def create_card_html(item, sector, is_recomm=False):
    if not item: return ""
    score = item['score']
    
    if score >= 75:
        score_color = "#F04452"; p_color = "text-up"; badge_cls = "badge-buy"; badge_text = "매수 추천"
    elif score <= 25:
        score_color = "#3182F6"; p_color = "text-down"; badge_cls = "badge-sell"; badge_text = "매도 권장"
    else:
        score_color = "#F2A529" if score >= 50 else "#8B95A1"
        p_color = "text-gray"; badge_cls = "badge-neu"; badge_text = "관망 필요"
    
    if is_recomm: p_color = "text-up"; score_color = "#F04452"; badge_cls = "badge-buy"; badge_text = "강력 매수"
    
    checks_html = "".join([f"<div class='check-tag'>{c}</div>" for c in item['checks']])
    supply_f = format(int(item['supply']['f']), ',')
    supply_i = format(int(item['supply']['i']), ',')
    supply_f_col = '#F04452' if item['supply']['f'] > 0 else '#3182F6'
    supply_i_col = '#F04452' if item['supply']['i'] > 0 else '#3182F6'
    price_fmt = format(item['price'], ',')
    
    rsi_val = item['rsi']
    rsi_width = min(max(rsi_val, 0), 100)
    
    if rsi_val <= 30: 
        rsi_text_col = "#3182F6" 
        rsi_gradient = "linear-gradient(90deg, #3182F6, #76B1FF)" 
    elif rsi_val >= 70: 
        rsi_text_col = "#F04452"
        rsi_gradient = "linear-gradient(90deg, #F04452, #FF8A9B)"
    else: 
        rsi_text_col = "#8B95A1"
        rsi_gradient = "linear-gradient(90deg, #8B95A1, #B0B8C1)"
    
    html = f"""
    <div class='toss-card'>
        <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
            <div>
                <span class='badge-clean badge-neu'>{sector}</span>
                <div style='margin-top:8px;'>
                    <span class='stock-name'>{item.get('name', 'Unknown')}</span>
                    <span class='stock-code'>{item['code']}</span>
                </div>
                <div class='big-price {p_color}'>{price_fmt}원</div>
            </div>
            <div style='text-align:right;'>
                <div class='label-text'>AI 진단</div>
                <div style='font-size:24px; font-weight:800; color:{score_color};'>{score}점</div>
                <div class='badge-clean {badge_cls}' style='margin-top:4px;'>{badge_text}</div>
            </div>
        </div>
        <div class='score-bg'><div class='score-fill' style='width:{score}%; background:{score_color};'></div></div>
        <div style='margin-top:20px;'>
            <div class='label-text' style='margin-bottom:8px;'>투자 체크포인트</div>
            <div class='check-container'>{checks_html}</div>
        </div>
        <div style='margin-top:15px; padding-top:15px; border-top:1px dashed #F2F4F6; display:flex; justify-content:space-between; font-size:13px;'>
             <div style='width:48%;'>
                <div style='display:flex; justify-content:space-between; margin-bottom:4px;'>
                    <span style='color:#8B95A1;'>외국인</span><span style='color:{supply_f_col}; font-weight:600;'>{supply_f}</span>
                </div>
                <div style='display:flex; justify-content:space-between;'>
                    <span style='color:#8B95A1;'>기관</span><span style='color:{supply_i_col}; font-weight:600;'>{supply_i}</span>
                </div>
            </div>
            <div style='width:48%; border-left:1px solid #F2F4F6; padding-left:15px;'>
                 <div style='display:flex; justify-content:space-between; margin-bottom:4px;'>
                    <span style='color:#8B95A1;'>RSI (14)</span><span style='color:{rsi_text_col}; font-weight:600;'>{rsi_val:.1f}</span>
                </div>
                <div class='rsi-container'><div class='rsi-bar' style='width:{rsi_width}%; background:{rsi_gradient};'></div></div>
                <div style='display:flex; justify-content:space-between; margin-top:8px;'>
                    <span style='color:#8B95A1;'>볼린저</span><span style='color:#4E5968; font-weight:600;'>{item['bb_status']}</span>
                </div>
            </div>
        </div>
    </div>
    """
    return html

def create_bollinger_chart(df, name):
    chart_data = df.tail(60).reset_index()
    base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=alt.Axis(format='%m-%d', title=None, grid=False)))
    band = base.mark_area(opacity=0.1, color='#8B95A1').encode(y=alt.Y('Lower:Q', title=None), y2='Upper:Q')
    line = base.mark_line(color='#333D4B', strokeWidth=2).encode(y='Close:Q')
    upper = base.mark_line(color='#F04452', strokeWidth=1, strokeDash=[3,3]).encode(y='Upper:Q')
    lower = base.mark_line(color='#3182F6', strokeWidth=1, strokeDash=[3,3]).encode(y='Lower:Q')
    return (band + upper + lower + line).properties(height=250).configure_view(stroke=None)

@st.cache_data(ttl=3600)
def get_global_macro():
    try:
        indices = {"USD/KRW": "USD/KRW", "WTI": "CL=F", "S&P500": "US500", "US 10Y": "^TNX", "VIX": "^VIX"}
        res = {}; score = 0
        
        for n, c in indices.items():
            df = fdr.DataReader(c, datetime.datetime.now() - datetime.timedelta(days=100))
            if not df.empty and len(df) > 20:
                now = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2]
                chg = ((now - prev) / prev) * 100
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                
                # 추세 판단 (MA20 기준)
                is_uptrend = now >= ma20
                
                res[n] = {"p": now, "c": chg, "uptrend": is_uptrend}
                
                # 점수 계산
                if n == "S&P500": score += 1 if is_uptrend else -1
                elif n == "USD/KRW": score += -1 if chg > 0.5 else (1 if chg < -0.5 else 0)
                elif n == "US 10Y": score += -1 if is_uptrend else 1
                elif n == "VIX": score += -2 if now > 20 else 1 # VIX 절대값 기준
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
        sector = get_sector_info(code)
        sup = get_supply_demand(code)
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=150))
        
        if df.empty or len(df) < 60: return None
        
        # [NEW] 펀더멘탈(PBR) 체크 - 우량주 보호 로직
        is_undervalued = False
        try:
            # 오늘 날짜 기준 PBR 조회
            today_str = datetime.datetime.now().strftime("%Y%m%d")
            # pykrx의 get_market_fundamental_by_ticker 사용
            fund_df = stock.get_market_fundamental_by_ticker(today_str, code)
            
            # PBR 값 확인 (데이터가 있는 경우에만)
            if not fund_df.empty and 'PBR' in fund_df.index:
                pbr = fund_df.loc['PBR']
                # PBR이 1.2 미만이면 저평가로 간주
                if pbr > 0 and pbr < 1.2:
                    is_undervalued = True
            elif not fund_df.empty and 'PBR' in fund_df.columns: # 포맷 대응
                 pbr = fund_df['PBR'].iloc[0]
                 if pbr > 0 and pbr < 1.2:
                    is_undervalued = True
        except:
            pass # 펀더멘탈 데이터 조회 실패 시 무시

        df['MA20'] = df['Close'].rolling(20).mean()
        df['Std'] = df['Close'].rolling(20).std()
        df['Upper'] = df['MA20'] + (df['Std'] * 2)
        df['Lower'] = df['MA20'] - (df['Std'] * 2)
        
        delta = df['Close'].diff(1)
        rsi = 100 - (100/(1 + (delta.where(delta>0,0).rolling(14).mean() / -delta.where(delta<0,0).rolling(14).mean())))
        df['RSI'] = rsi.fillna(50)
        curr = df.iloc[-1]
        
        checks = []; pass_cnt = 0
        if sup['f']>0 or sup['i']>0: checks.append("큰손 유입"); pass_cnt+=1
        else: checks.append("수급 이탈")
        
        if curr['Close']>=curr['MA20']: checks.append("상승 추세"); pass_cnt+=1
        else: checks.append("하락 추세")
        
        bb_status = "중립"
        if curr['Close']<=curr['Lower']*1.05: checks.append("저점 매수기회"); pass_cnt+=1; bb_status = "바닥권"
        elif curr['Close']>=curr['Upper']*0.98: 
            # [수정] 고점이지만 저평가 상태라면?
            if is_undervalued:
                checks.append("고점이나 저평가"); pass_cnt+=0 # 점수 깎지 않음
                bb_status = "과열(보유)"
            else:
                checks.append("고점 주의"); pass_cnt-=0.5; bb_status = "과열권"
        else: checks.append("안정적 흐름"); pass_cnt+=0.5; bb_status = "밴드 내"
        
        if curr['RSI']<=30: checks.append("RSI 침체"); pass_cnt+=1
        elif curr['RSI']>=70: 
            # [수정] RSI 과열이지만 저평가라면?
            if is_undervalued:
                checks.append("과열(실적우수)"); pass_cnt+=0 # 점수 깎지 않음
            else:
                checks.append("RSI 과열"); pass_cnt-=0.5
        else: checks.append("RSI 안정"); pass_cnt+=0.5
        
        if not name_override:
            try: name_override = krx_df[krx_df['Code'] == code]['Name'].values[0]
            except: name_override = code

        return {
            "name": name_override, "code": code, "sector": sector, "price": curr['Close'], 
            "checks": checks, "pass": pass_cnt, "score": min(pass_cnt*25, 100), 
            "supply": sup, "rsi": curr['RSI'], "bb_status": bb_status,
            "history": df
        }
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

def get_recommendations(target_df):
    try:
        if target_df.empty: return []
        # 속도를 위해 최대 50개 제한
        limited_df = target_df.head(50)
        targets = {row['Name']: {'code': row['Code']} for _, row in limited_df.iterrows()}
        
        results = analyze_portfolio_parallel(targets)
        high_score_items = [res for res in results if res['score'] >= 75]
        high_score_items.sort(key=lambda x: x['score'], reverse=True)
        return high_score_items
    except Exception as e:
        st.error(f"검색 중 오류 발생: {e}")
        return []

# --- [4. UI 렌더링] ---
with st.sidebar:
    st.header("⚡ 제어판")
    auto_mode = st.checkbox("🔴 실시간 자동 감시", value=False)
    st.divider()
    with st.expander("➕ 관심 종목 추가", expanded=True):
        n_name = st.text_input("종목명 (예: 삼성전자)")
        n_code = st.text_input("코드 (예: 005930)")
        if st.button("추가하기"):
            clean_name = n_name.strip(); clean_code = n_code.strip()
            existing_codes = [v['code'] for v in st.session_state['watchlist'].values()]
            if clean_code in existing_codes: st.error("이미 추가된 종목입니다.")
            elif clean_name and clean_code:
                st.session_state['watchlist'][clean_name] = {"code": clean_code}
                with st.spinner("저장 중..."):
                    success, msg = save_to_github(st.session_state['watchlist'])
                    if success: st.success("추가 완료!"); time.sleep(0.5); st.rerun()
                    else: st.warning(msg)
    if st.session_state['watchlist']:
        st.caption(f"내 관심 종목 ({len(st.session_state['watchlist'])}개)")
        for name in list(st.session_state['watchlist'].keys()):
            c1, c2 = st.columns([3,1])
            c1.markdown(f"<span style='color:#333; font-weight:600;'>{name}</span>", unsafe_allow_html=True)
            if c2.button("✕", key=f"del_{name}"):
                del st.session_state['watchlist'][name]; save_to_github(st.session_state['watchlist']); st.rerun()
    st.divider()
    if st.button("🗑️ 전체 초기화"):
        st.session_state['watchlist'] = {}; save_to_github({}); st.rerun()

st.title("📈 Quant Sniper V16.9")
st.caption(f"AI 기반 실시간 분석 시스템 | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

with st.expander("📘 지표 해석 가이드 (범례)", expanded=True):
    st.markdown("""
    <table class='legend-table'>
        <tr><td colspan='2' class='legend-header'>🌍 글로벌 시장 지표 (Macro)</td></tr>
        <tr>
            <td width='30%'><span class='legend-title'>시장 점수</span></td>
            <td><b>+1 이상:</b> <span class='text-up'>적극 투자 (상승장)</span><br><b>-1 이하:</b> <span class='text-down'>보수적 대응 (하락장)</span></td>
        </tr>
        <tr>
            <td><span class='legend-title'>S&P 500</span></td>
            <td><b>상승추세(MA20 위)</b>면 긍정. 한국 시장의 선행 지표.</td>
        </tr>
        <tr>
            <td><span class='legend-title'>WTI/금리</span></td>
            <td><b>하락추세(MA20 아래)</b>여야 긍정. (비용/부담 감소)</td>
        </tr>
        <tr>
            <td><span class='legend-title'>VIX (공포)</span></td>
            <td><b>20 이하</b>면 긍정(안정). 20 초과면 부정(공포).</td>
        </tr>
        <tr><td colspan='2' class='legend-header' style='margin-top:10px;'>📊 종목 진단 지표</td></tr>
        <tr>
            <td><span class='legend-title'>AI 점수</span></td>
            <td><b>75점↑:</b> <span class='badge-clean badge-buy'>매수 추천 (빨강)</span> / <b>25점↓:</b> <span class='badge-clean badge-sell'>매도 권장 (파랑)</span></td>
        </tr>
        <tr>
            <td><span class='legend-title'>RSI (14)</span></td>
            <td>
                <b>30이하 (기회):</b> <span style='color:#3182F6; font-weight:bold;'>부드러운 파랑 그라데이션</span> (침체/저점매수)<br>
                <b>70이상 (주의):</b> <span style='color:#F04452; font-weight:bold;'>부드러운 빨강 그라데이션</span> (과열/고점매도)
            </td>
        </tr>
         <tr>
            <td><span class='legend-title'>텍스트 색상</span></td>
            <td><span class='text-up'>빨강 숫자: 상승</span> / <span class='text-down'>파랑 숫자: 하락</span> (전일 대비)</td>
        </tr>
    </table>
    """, unsafe_allow_html=True)

macro = get_global_macro()
if macro:
    col1, col2, col3, col4, col5 = st.columns(5)
    m_data = macro['data']; score = macro['score']
    
    if score >= 1: m_state = "적극 투자"; m_cls = "badge-buy"; m_col = "text-up"
    elif score <= -1: m_state = "위험 관리"; m_cls = "badge-sell"; m_col = "text-down"
    else: m_state = "관망"; m_cls = "badge-neu"; m_col = "text-gray"
    
    with col1: st.markdown(f"<div class='macro-box'><div class='label-text'>시장 점수</div><div class='macro-val {m_col}'>{score}</div><div class='badge-clean {m_cls}'>{m_state}</div></div>", unsafe_allow_html=True)
    
    cols = [col2, col3, col4, col5]
    keys = ['S&P500', 'VIX', 'WTI', 'US 10Y']
    labels = ['S&P 500', 'VIX (공포)', 'WTI 유가', '미국채 10년']
    
    for i, k in enumerate(keys):
        if k in m_data:
            val = m_data[k]['p']; chg = m_data[k]['c']; is_uptrend = m_data[k]['uptrend']
            
            # --- [긍정/부정 판단: 뱃지 색상] ---
            if k == 'S&P500':
                is_good = is_uptrend # S&P는 상승추세여야 긍정
                status_text = "상승추세" if is_good else "하락추세"
            elif k == 'VIX':
                is_good = val <= 20 # VIX는 20 이하여야 긍정
                status_text = "안정권" if is_good else "공포구간"
            else:
                is_good = not is_uptrend # 유가/금리는 하락추세여야 긍정
                status_text = "하락안정" if is_good else "상승주의"
            
            bg_cls = "badge-buy" if is_good else "badge-sell" # 긍정=Red, 부정=Blue
            
            # --- [텍스트 색상: 전일비 등락] ---
            val_col = "text-up" if chg > 0 else "text-down"
            
            txt = f"{val:.2f}"; txt += "%" if k == 'US 10Y' else ""; txt = f"${val:.1f}" if k == 'WTI' else txt
            
            with cols[i]:
                st.markdown(f"<div class='macro-box'><div class='label-text'>{labels[i]}</div><div class='macro-val {val_col}'>{txt}</div><div class='badge-clean {bg_cls}'>{status_text}</div></div>", unsafe_allow_html=True)

st.write("")
tab1, tab2 = st.tabs(["내 주식", "AI 발굴"])

with tab1:
    if not st.session_state['watchlist']: st.info("👈 왼쪽에서 관심 종목을 추가해주세요.")
    else:
        with st.spinner("분석 중..."): results = analyze_portfolio_parallel(st.session_state['watchlist'])
        for res in results:
            sec = res.get('sector', '기타')
            st.markdown(create_card_html(res, sec, False), unsafe_allow_html=True)
            with st.expander(f"📊 {res['name']} 차트 더보기"):
                st.altair_chart(create_bollinger_chart(res['history'], res['name']), use_container_width=True)
            if auto_mode:
                today = datetime.datetime.now().strftime("%Y%m%d")
                msg_key = f"{res['code']}_{today}"
                if res['score'] >= 75 and st.session_state['sent_alerts'].get(msg_key+"_buy") != "sent":
                    send_telegram_msg(f"🚀 [매수 추천] {res['name']} ({res['score']}점)\n현재가: {format(res['price'],',')}원")
                    st.session_state['sent_alerts'][msg_key+"_buy"] = "sent"
                elif res['score'] <= 25 and st.session_state['sent_alerts'].get(msg_key+"_sell") != "sent":
                    send_telegram_msg(f"💧 [매도 권장] {res['name']} ({res['score']}점)\n현재가: {format(res['price'],',')}원")
                    st.session_state['sent_alerts'][msg_key+"_sell"] = "sent"

with tab2:
    st.subheader("🔭 조건별 유망 종목 스캔")
    
    scan_option = st.radio(
        "스캔 방식을 선택하세요:", 
        ["🏆 시가총액 상위 50위", "🏢 특정 섹터(업종)별 보기"],
        horizontal=True
    )
    
    target_df = pd.DataFrame()
    
    if scan_option == "🏆 시가총액 상위 50위":
        st.caption("한국 주식 시장에서 가장 규모가 큰 우량주 50개를 분석합니다.")
        target_df = krx_df.head(50)
        
    elif scan_option == "🏢 특정 섹터(업종)별 보기":
        sectors = sorted(krx_df['Sector'].dropna().unique().tolist())
        selected_sector = st.selectbox("분석할 섹터를 선택해주세요:", sectors)
        
        if selected_sector:
            st.caption(f"'{selected_sector}' 섹터에 속한 종목들을 분석합니다. (최대 50개)")
            target_df = krx_df[krx_df['Sector'] == selected_sector]

    if st.button("🚀 AI 스캔 시작", use_container_width=True):
        if target_df.empty:
            st.warning("분석할 종목이 없습니다.")
        else:
            with st.spinner(f"AI가 {len(target_df.head(50))}개 종목을 정밀 분석 중입니다..."): 
                recs = get_recommendations(target_df)
            
            if not recs: 
                st.warning("조건에 맞는 매수 추천(75점 이상) 종목을 찾지 못했습니다.")
            else:
                st.success(f"💎 {len(recs)}개의 유망 종목을 발견했습니다!")
                for item in recs:
                    st.markdown(create_card_html(item, item.get('sector', '기타'), True), unsafe_allow_html=True)
                    with st.expander(f"📊 {item['name']} 차트"):
                        st.altair_chart(create_bollinger_chart(item['history'], item['name']), use_container_width=True)

if auto_mode:
    st.markdown("---")
    st.empty().markdown(f"⏳ **실시간 감시 중... (30초 주기)**")
    time.sleep(30); st.rerun()
