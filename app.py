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

# --- [1. 설정 및 UI 스타일링] ---
st.set_page_config(page_title="Quant Sniper V17.3", page_icon="📈", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { 
        background: #FFFFFF; border-radius: 24px; padding: 24px; 
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; 
    }
    .text-up { color: #F04452 !important; }
    .text-down { color: #3182F6 !important; }
    .text-gray { color: #8B95A1 !important; }
    .big-price { font-size: 32px; font-weight: 800; letter-spacing: -0.5px; color: #191F28; }
    .stock-name { font-size: 22px; font-weight: 700; color: #333D4B; }
    .stock-code { font-size: 14px; color: #8B95A1; margin-left: 6px; font-weight: 500; }
    .label-text { font-size: 12px; color: #8B95A1; font-weight: 600; margin-bottom: 4px; }
    .badge-clean { padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 700; display: inline-block; }
    .badge-buy { background-color: rgba(240, 68, 82, 0.1); color: #F04452; }
    .badge-sell { background-color: rgba(49, 130, 246, 0.1); color: #3182F6; }
    .badge-neu { background-color: #F2F4F6; color: #4E5968; }
    .macro-box { background: #F9FAFB; border-radius: 16px; padding: 16px; text-align: center; height: 100%; border: 1px solid #F2F4F6; }
    .macro-val { font-size: 20px; font-weight: 800; color: #333D4B; margin-bottom: 8px; }
    .check-container { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
    .check-tag { font-size: 12px; padding: 6px 12px; border-radius: 18px; background: #F2F4F6; color: #4E5968; font-weight: 600; display: flex; align-items: center; }
    .score-bg { background: #F2F4F6; height: 8px; border-radius: 4px; overflow: hidden; margin-top: 10px; }
    .score-fill { height: 100%; border-radius: 4px; }
    .rsi-container { width: 100%; background-color: #F2F4F6; height: 10px; border-radius: 5px; margin-top: 8px; overflow: hidden; }
    .rsi-bar { height: 100%; border-radius: 5px; transition: width 0.5s ease-in-out; }
    .legend-table { width: 100%; font-size: 14px; border-collapse: collapse; margin-top: 5px; }
    .legend-table td { padding: 12px; border-bottom: 1px solid #F2F4F6; color: #333D4B; vertical-align: middle; line-height: 1.5; }
    .legend-header { font-weight: 800; color: #191F28; background-color: #F9FAFB; text-align: center; padding: 10px; border-radius: 8px; margin-bottom: 10px; display: block;}
    .legend-title { font-weight: 700; color: #4E5968; width: 140px; background-color: #F2F4F6; padding: 6px 10px; border-radius: 6px; text-align: center; display: inline-block;}
    .streamlit-expanderContent { background-color: #FFFFFF !important; border: 1px solid #F2F4F6; border-radius: 12px; }
    div.stButton > button { width: 100%; border-radius: 12px; font-weight: bold; border: none; background: #3182F6; color: white; padding: 12px 0; transition: 0.2s; }
    div.stButton > button:hover { background: #1B64DA; }
    .strategy-box { background-color: #F2F4F6; border-radius: 12px; padding: 12px; font-size: 13px; margin-top: 12px; display: flex; justify-content: space-around; text-align: center; }
    .strategy-item { display: flex; flex-direction: column; }
    .strategy-label { color: #8B95A1; font-size: 11px; margin-bottom: 4px; }
    .strategy-val { color: #333D4B; font-weight: 700; }
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
        if df.empty: return pd.DataFrame()
        if 'Sector' not in df.columns:
            if 'Industry' in df.columns: df['Sector'] = df['Industry']
            else: df['Sector'] = '기타'
        df['Sector'] = df['Sector'].fillna('기타')
        return df[['Code', 'Name', 'Sector']]
    except: 
        return pd.DataFrame()

krx_df = get_krx_list()

def get_sector_info(code):
    try:
        if krx_df.empty: return "기타"
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

# --- [3. 분석 로직 (V17.3 Strategy & Signals)] ---

@st.cache_data(ttl=1200) 
def get_news_sentiment(code):
    try:
        url = f"https://finance.naver.com/item/news_news.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers)
        try: soup = BeautifulSoup(resp.content, "lxml")
        except: soup = BeautifulSoup(resp.content, "html.parser")
        
        titles = soup.select(".title .tit")
        dates = soup.select(".date")
        
        news_score = 0
        latest_headline = "-"
        good_keywords = ["수주", "계약", "체결", "흑자", "최대", "개선", "성장", "호조", "개발", "승인", "공급", "적자 축소", "흑자 전환"]
        bad_keywords = ["횡령", "배임", "구속", "압수수색", "적자 지속", "하향", "불확실", "우려", "급락", "약세", "손실", "어닝 쇼크"]
        
        today = datetime.datetime.now()
        count = 0
        
        for i in range(len(titles)):
            if count >= 10: break
            t_text = titles[i].get_text().strip()
            d_text = dates[i].get_text().strip()
            try:
                news_date = datetime.datetime.strptime(d_text, "%Y.%m.%d %H:%M")
                diff = (today - news_date).days
                if diff > 5: continue 
            except: continue
                
            if count == 0: latest_headline = t_text
            for k in good_keywords:
                if k in t_text: news_score += 1; break
            for k in bad_keywords:
                if k in t_text: news_score -= 2; break
            count += 1
            
        return {"score": news_score, "headline": latest_headline}
    except:
        return {"score": 0, "headline": "-"}

def create_card_html(item, sector, is_recomm=False):
    if not item: return ""
    score = item['score']
    
    if score >= 80:
        score_color = "#F04452"; p_color = "text-up"; badge_cls = "badge-buy"; badge_text = "강력 매수"
    elif score >= 60:
        score_color = "#F04452"; p_color = "text-up"; badge_cls = "badge-buy"; badge_text = "매수 긍정"
    elif score <= 40:
        score_color = "#3182F6"; p_color = "text-down"; badge_cls = "badge-sell"; badge_text = "매도 권장"
    else:
        score_color = "#8B95A1"; p_color = "text-gray"; badge_cls = "badge-neu"; badge_text = "관망 필요"
    
    if is_recomm: p_color = "text-up"; score_color = "#F04452"; badge_cls = "badge-buy"; badge_text = "강력 매수"
    
    checks_html = "".join([f"<div class='check-tag'>{c}</div>" for c in item['checks']])
    supply_f = format(int(item['supply']['f']), ',')
    supply_i = format(int(item['supply']['i']), ',')
    supply_f_col = '#F04452' if item['supply']['f'] > 0 else '#3182F6'
    supply_i_col = '#F04452' if item['supply']['i'] > 0 else '#3182F6'
    price_fmt = format(item['price'], ',')
    
    buy_price = format(int(item['strategy']['buy']), ',')
    target_price = format(int(item['strategy']['target']), ',')
    action_text = item['strategy']['action']
    
    rsi_val = item['rsi']
    rsi_width = min(max(rsi_val, 0), 100)
    if rsi_val <= 30: rsi_text_col = "#3182F6"; rsi_gradient = "linear-gradient(90deg, #3182F6, #76B1FF)" 
    elif rsi_val >= 70: rsi_text_col = "#F04452"; rsi_gradient = "linear-gradient(90deg, #F04452, #FF8A9B)"
    else: rsi_text_col = "#8B95A1"; rsi_gradient = "linear-gradient(90deg, #8B95A1, #B0B8C1)"
    
    news_html = ""
    if item['news']['headline'] != "-":
        n_col = "#F04452" if item['news']['score'] > 0 else ("#3182F6" if item['news']['score'] < 0 else "#8B95A1")
        safe_headline = item['news']['headline'][:28].replace("<", "&lt;").replace(">", "&gt;")
        news_html = f"<div style='margin-top:10px; padding:10px; background:#F9FAFB; border-radius:12px; font-size:12px;'><span style='font-weight:bold; color:{n_col};'>📰 최근 뉴스</span><br><span style='color:#333;'>{safe_headline}...</span></div>"

    html_str = f"<div class='toss-card'><div style='display:flex; justify-content:space-between; align-items:flex-start;'><div><span class='badge-clean badge-neu'>{sector}</span><div style='margin-top:8px;'><span class='stock-name'>{item.get('name', 'Unknown')}</span><span class='stock-code'>{item['code']}</span></div><div class='big-price {p_color}'>{price_fmt}원</div></div><div style='text-align:right;'><div class='label-text'>AI 진단</div><div style='font-size:24px; font-weight:800; color:{score_color};'>{score}점</div><div class='badge-clean {badge_cls}' style='margin-top:4px;'>{badge_text}</div></div></div><div class='score-bg'><div class='score-fill' style='width:{score}%; background:{score_color};'></div></div>"
    html_str += f"<div class='strategy-box'><div class='strategy-item'><span class='strategy-label'>매매 전략</span><span class='strategy-val' style='color:#3182F6;'>{action_text}</span></div><div style='width:1px; background:#DEE2E6;'></div><div class='strategy-item'><span class='strategy-label'>적정 매수가</span><span class='strategy-val'>{buy_price}</span></div><div style='width:1px; background:#DEE2E6;'></div><div class='strategy-item'><span class='strategy-label'>1차 목표가</span><span class='strategy-val' style='color:#F04452;'>{target_price}</span></div></div>"
    html_str += news_html
    html_str += f"<div style='margin-top:20px;'><div class='label-text' style='margin-bottom:8px;'>투자 체크포인트</div><div class='check-container'>{checks_html}</div></div>"
    html_str += f"<div style='margin-top:15px; padding-top:15px; border-top:1px dashed #F2F4F6; display:flex; justify-content:space-between; font-size:13px;'><div style='width:48%;'><div style='display:flex; justify-content:space-between; margin-bottom:4px;'><span style='color:#8B95A1;'>외국인</span><span style='color:{supply_f_col}; font-weight:600;'>{supply_f}</span></div><div style='display:flex; justify-content:space-between;'><span style='color:#8B95A1;'>기관</span><span style='color:{supply_i_col}; font-weight:600;'>{supply_i}</span></div></div><div style='width:48%; border-left:1px solid #F2F4F6; padding-left:15px;'><div style='display:flex; justify-content:space-between; margin-bottom:4px;'><span style='color:#8B95A1;'>RSI (14)</span><span style='color:{rsi_text_col}; font-weight:600;'>{rsi_val:.1f}</span></div><div class='rsi-container'><div class='rsi-bar' style='width:{rsi_width}%; background:{rsi_gradient};'></div></div><div style='display:flex; justify-content:space-between; margin-top:8px;'><span style='color:#8B95A1;'>볼린저</span><span style='color:#4E5968; font-weight:600;'>{item['bb_status']}</span></div></div></div></div>"
    return html_str

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
                is_uptrend = now >= ma20
                res[n] = {"p": now, "c": chg, "uptrend": is_uptrend}
                if n == "S&P500": score += 1 if is_uptrend else -1
                elif n == "USD/KRW": score += -1 if chg > 0.5 else (1 if chg < -0.5 else 0)
                elif n == "US 10Y": score += -1 if is_uptrend else 1
                elif n == "VIX": score += -2 if now > 20 else 1
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
        news = get_news_sentiment(code)
        
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=150))
        if df.empty or len(df) < 60: return None
        
        is_undervalued = False
        try:
            today_str = datetime.datetime.now().strftime("%Y%m%d")
            fund_df = stock.get_market_fundamental_by_ticker(today_str, code)
            pbr = 0
            if not fund_df.empty:
                if 'PBR' in fund_df.index: pbr = fund_df.loc['PBR']
                elif 'PBR' in fund_df.columns: pbr = fund_df['PBR'].iloc[0]
                if 0 < pbr < 1.2: is_undervalued = True
        except: pass

        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Std'] = df['Close'].rolling(20).std()
        df['Upper'] = df['MA20'] + (df['Std'] * 2)
        df['Lower'] = df['MA20'] - (df['Std'] * 2)
        
        delta = df['Close'].diff(1)
        rsi = 100 - (100/(1 + (delta.where(delta>0,0).rolling(14).mean() / -delta.where(delta<0,0).rolling(14).mean())))
        df['RSI'] = rsi.fillna(50)
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        checks = []; pass_cnt = 0
        
        if curr['Close'] > curr['MA20']:
            checks.append("추세 상승세"); pass_cnt += 1
            if curr['MA5'] > curr['MA20']: pass_cnt += 0.5
        elif curr['Close'] > curr['MA5'] and curr['Close'] > prev['Close']:
            checks.append("단기 반등세"); pass_cnt += 0.5
        else:
            checks.append("추세 하락중")

        net_buy = sup['f'] + sup['i']
        if net_buy > 0: checks.append("메이저 순매수"); pass_cnt += 1
        elif sup['f'] > 0: checks.append("외국인 매수중"); pass_cnt += 0.5
        else: checks.append("수급 부재")
            
        bb_status = "밴드 내"
        if curr['RSI'] <= 35: checks.append("과매도(반등기회)"); pass_cnt += 1; bb_status = "바닥권"
        elif curr['RSI'] >= 70:
            if is_undervalued: checks.append("저평가 랠리"); pass_cnt += 1; bb_status = "상승가속"
            else: checks.append("과열 부담"); pass_cnt -= 0.5; bb_status = "과열권"
        else:
            if is_undervalued: checks.append("가치주 메리트"); pass_cnt += 0.5
            else: checks.append("관망세"); bb_status = "중립"

        if news['score'] >= 1:
            if curr['Close'] > curr['MA5']: checks.append("호재 반영중"); pass_cnt += 1.0
            else: checks.append("호재 있으나 약세"); pass_cnt += 0.5
        elif news['score'] < 0: checks.append("악재 발생"); pass_cnt -= 1.0

        if not name_override:
            try: name_override = krx_df[krx_df['Code'] == code]['Name'].values[0]
            except: name_override = code

        final_score = min(max(pass_cnt * 22, 0), 100)
        
        buy_target = curr['MA20'] if curr['Close'] > curr['MA20'] else curr['Lower']
        sell_target = curr['Upper']
        stop_loss = buy_target * 0.97
        
        action = "관망"
        if final_score >= 80: action = "적극 매수"
        elif final_score >= 60: action = "분할 매수"
        elif final_score <= 40: action = "매도/관망"
        else: action = "중립"

        strategy = {"buy": buy_target, "target": sell_target, "stop": stop_loss, "action": action}

        return {
            "name": name_override, "code": code, "sector": sector, "price": curr['Close'], 
            "checks": checks, "pass": pass_cnt, "score": int(final_score), 
            "supply": sup, "rsi": curr['RSI'], "bb_status": bb_status,
            "news": news, "history": df, "strategy": strategy
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
        limited_df = target_df.head(30)
        targets = {row['Name']: {'code': row['Code']} for _, row in limited_df.iterrows()}
        results = analyze_portfolio_parallel(targets)
        high_score_items = [res for res in results if res['score'] >= 60]
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

st.title("📈 Quant Sniper V17.3")
st.caption(f"AI 기반 실시간 분석 시스템 (재무/뉴스/수급) | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

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
            <td><b>60점↑:</b> <span class='badge-clean badge-buy'>매수 긍정</span> (기준 완화)</td>
        </tr>
        <tr>
            <td><span class='legend-title'>매매 전략</span></td>
            <td><b>적정가/목표가/손절가</b>를 차트와 수급 기반으로 자동 계산</td>
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
            if k == 'S&P500':
                is_good = is_uptrend; status_text = "상승추세" if is_good else "하락추세"
            elif k == 'VIX':
                is_good = val <= 20; status_text = "안정권" if is_good else "공포구간"
            else:
                is_good = not is_uptrend; status_text = "하락안정" if is_good else "상승주의"
            
            bg_cls = "badge-buy" if is_good else "badge-sell"
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
                if res['score'] >= 60 and st.session_state['sent_alerts'].get(msg_key+"_buy") != "sent":
                    send_telegram_msg(f"🚀 [매수 긍정] {res['name']} ({res['score']}점)\n현재가: {format(res['price'],',')}원")
                    st.session_state['sent_alerts'][msg_key+"_buy"] = "sent"

with tab2:
    st.subheader("🔭 조건별 유망 종목 스캔")
    st.caption("※ 실전 투자에 맞춘 테마 및 섹터 분류로 유망 종목을 발굴합니다.")
    
    scan_option = st.radio(
        "분석할 카테고리를 선택하세요:", 
        ["🏆 시가총액 상위 30위 (시장주도주)", 
         "1. 🏛️ 정책 및 시장 테마주", 
         "2. 🏭 산업군별 완성업체 (대장주)", 
         "3. 🔩 산업군별 소부장 (소재/부품/장비)"], 
        horizontal=False
    )

    target_df = pd.DataFrame()
    
    if krx_df.empty:
        st.warning("시장 데이터를 불러오는 중입니다. 잠시만 기다려주세요.")
    else:
        # 1. 시가총액 상위 30위
        if "시가총액 상위" in scan_option:
            st.info("💡 한국 주식 시장을 이끄는 최상위 우량주 30개를 분석합니다.")
            target_df = krx_df.head(30)
            
        # 2. 정책 및 시장 테마주
        elif "정책 및 시장 테마주" in scan_option:
            themes = {
                "🤖 AI & 로봇": ["로봇", "AI", "인공지능", "레인보우", "두산로보틱스"],
                "🔋 2차전지 & 전기차": ["에코프로", "엘앤에프", "LG에너지", "포스코퓨처", "삼성SDI", "천보"],
                "🚀 방산 & 우주항공": ["한화에어로", "LIG넥스원", "한국항공우주", "현대로템", "쎄트렉아이"],
                "🧬 비만치료제 & 바이오": ["한미약품", "페트론", "인벤티지랩", "알테오젠", "HLB"],
                "☢️ 원전 & 전력설비": ["두산에너빌리티", "한전기술", "LS ELECTRIC", "효성중공업", "일진전기"],
                "🪙 STO & 가상자산": ["서울옥션", "케이옥션", "갤럭시", "위메이드"]
            }
            selected_theme = st.selectbox("관심있는 테마를 선택하세요:", list(themes.keys()))
            
            if selected_theme:
                keywords = themes[selected_theme]
                mask = krx_df['Name'].str.contains('|'.join(keywords), case=False, na=False)
                target_df = krx_df[mask]
                st.write(f"🔍 '{selected_theme}' 관련 종목 {len(target_df)}개를 찾았습니다.")

        # 3. 산업군별 완성업체
        elif "산업군별 완성업체" in scan_option:
            industries = {
                "반도체/IT 완성": ["삼성전자", "SK하이닉스", "LG전자", "삼성전기", "LG디스플레이"],
                "자동차 완성차": ["현대차", "기아", "KG모빌리티"],
                "제약/바이오 대장": ["삼성바이오로직스", "셀트리온", "유한양행", "SK바이오팜"],
                "인터넷/게임 플랫폼": ["NAVER", "카카오", "크래프톤", "엔씨소프트", "넷마블"],
                "조선/중공업": ["HD현대중공업", "삼성중공업", "한화오션", "한국조선해양"]
            }
            selected_ind = st.selectbox("산업군을 선택하세요:", list(industries.keys()))
            
            if selected_ind:
                target_names = industries[selected_ind]
                target_df = krx_df[krx_df['Name'].isin(target_names)]
                st.write(f"🏭 {selected_ind} 대표 기업 {len(target_df)}개를 분석합니다.")

        # 4. 소부장
        elif "산업군별 소부장" in scan_option:
            sobujang_sectors = {
                "반도체 소부장": ["반도체 제조", "기계", "장비"],
                "2차전지 소재/부품": ["화학", "전자부품"],
                "디스플레이/IT부품": ["전자부품", "광학"],
                "자동차 부품": ["자동차신품부품"]
            }
            selected_sub = st.selectbox("소부장 섹터를 선택하세요:", list(sobujang_sectors.keys()))
            
            if selected_sub:
                clean_df = krx_df.dropna(subset=['Sector'])
                if "반도체" in selected_sub:
                     mask = clean_df['Sector'].str.contains('반도체|기계|장비', na=False) | clean_df['Name'].str.contains('반도체|테크|머티리얼', na=False)
                elif "2차전지" in selected_sub:
                     mask = clean_df['Sector'].str.contains('화학|전기제품', na=False) | clean_df['Name'].str.contains('에코프로|엘앤에프|코스모', na=False)
                elif "자동차" in selected_sub:
                     mask = clean_df['Sector'].str.contains('자동차', na=False) & ~clean_df['Name'].isin(['현대차', '기아'])
                else:
                     mask = clean_df['Sector'].str.contains('부품|장비|기계', na=False)

                target_df = clean_df[mask].head(30)
                st.write(f"🔩 {selected_sub} 관련 유망 종목(최대 30개)을 스캔합니다.")

    if st.button("🚀 AI 스캔 시작", use_container_width=True):
        if target_df.empty:
            st.warning("분석할 종목을 찾지 못했습니다. 다른 카테고리를 선택해주세요.")
        else:
            with st.spinner(f"AI가 선별된 {len(target_df)}개 기업을 정밀 분석 중입니다..."): 
                final_targets = target_df.head(20)
                recs = get_recommendations(final_targets)
            
            if not recs: 
                st.warning("조건에 맞는 매수 긍정(60점 이상) 종목을 찾지 못했습니다. 관망이 필요할 수 있습니다.")
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
