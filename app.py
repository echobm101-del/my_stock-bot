import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
import json
import time
import altair as alt
from pykrx import stock
import concurrent.futures
from bs4 import BeautifulSoup
import re
import feedparser
import urllib.parse
from io import StringIO

# ------------------------------------------------------------------------------
# [1] 모듈 가져오기
# ------------------------------------------------------------------------------
try:
    from modules.ui import (
        apply_custom_css, 
        create_watchlist_card_html, 
        create_portfolio_card_html,
        render_signal_lights,
        render_tech_metrics,
        render_ma_status,
        render_chart_legend,
        create_chart_clean,
        render_fund_scorecard,
        render_financial_table,
        render_investor_chart
    )
    from modules.db import load_db, save_db

except ImportError as e:
    st.error(f"❌ 모듈을 찾을 수 없습니다: {str(e)}")
    st.stop()

# ------------------------------------------------------------------------------
# [2] 보안 설정
# ------------------------------------------------------------------------------
try:
    USER_TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
    USER_CHAT_ID = st.secrets.get("CHAT_ID", "")
    USER_GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
except Exception:
    USER_TELEGRAM_TOKEN = ""
    USER_CHAT_ID = ""
    USER_GOOGLE_API_KEY = ""

# ------------------------------------------------------------------------------
# [3] 페이지 설정 및 초기화
# ------------------------------------------------------------------------------
st.set_page_config(page_title="Quant Sniper V50.1 (Cost Saver)", page_icon="💎", layout="wide")
apply_custom_css()

# 데이터 로딩
if 'data_store' not in st.session_state:
    with st.spinner("📂 구글 시트와 연결 중..."):
        st.session_state['data_store'] = load_db()

# [중요] 분석 결과를 임시 저장할 메모리 공간 (새로고침 전까지 유지됨)
if 'analysis_cache' not in st.session_state:
    st.session_state['analysis_cache'] = {}

if 'preview_list' not in st.session_state: st.session_state['preview_list'] = []
if 'current_theme_name' not in st.session_state: st.session_state['current_theme_name'] = ""

# ------------------------------------------------------------------------------
# [4] 핵심 분석 로직 (기존과 동일)
# ------------------------------------------------------------------------------
@st.cache_data
def get_krx_list_safe():
    try:
        df = fdr.StockListing('KRX')
        if not df.empty: return df
    except: pass 
    return pd.DataFrame() 

krx_df = get_krx_list_safe()

@st.cache_data(ttl=1800)
def get_naver_theme_stocks(keyword):
    headers = {'User-Agent': 'Mozilla/5.0'}
    target_link = None
    for page in range(1, 8):
        base_url = f"https://finance.naver.com/sise/theme.naver?&page={page}"
        try:
            res = requests.get(base_url, headers=headers)
            res.encoding = 'EUC-KR' 
            soup = BeautifulSoup(res.text, 'html.parser')
            themes = soup.select('table.type_1 tr td.col_type1 a')
            for t in themes:
                if keyword.strip() in t.text.strip():
                    target_link = "https://finance.naver.com" + t['href']
                    break
            if target_link: break
        except: continue
    if not target_link: return [], f"네이버 금융 테마에서 '{keyword}'를 찾을 수 없습니다."
    try:
        res_detail = requests.get(target_link, headers=headers)
        res_detail.encoding = 'EUC-KR'
        soup_detail = BeautifulSoup(res_detail.text, 'html.parser')
        stocks = []
        rows = soup_detail.select('div.box_type_l table.type_5 tr')
        for row in rows:
            name_tag = row.select_one('td.name a')
            if name_tag:
                code = name_tag['href'].split('=')[-1]
                name = name_tag.text.strip()
                try: price = int(row.select('td.number')[0].text.strip().replace(',', ''))
                except: price = 0
                stocks.append({"code": code, "name": name, "price": price})
        return stocks, f"'{keyword}' 관련 테마 발견: {len(stocks)}개 종목"
    except Exception as e: return [], f"크롤링 오류: {str(e)}"

@st.cache_data(ttl=3600)
def get_investor_trend(code):
    try:
        end_d = datetime.datetime.now().strftime("%Y%m%d")
        start_d = (datetime.datetime.now() - datetime.timedelta(days=60)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(start_d, end_d, code)
        if not df.empty:
            df = df.tail(30).copy()
            df['Cum_Individual'] = df['개인'].cumsum()
            df['Cum_Foreigner'] = df['외국인'].cumsum()
            df['Cum_Institution'] = df['기관합계'].cumsum()
            df['Cum_Pension'] = df['연기금'].cumsum()
            return df
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_financial_history(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        df_list = pd.read_html(StringIO(res.text), encoding='euc-kr')
        for df in df_list:
            if '최근 연간 실적' in str(df.columns) or '매출액' in str(df.iloc[:,0].values):
                df = df.set_index(df.columns[0])
                fin_data = []
                cols = df.columns[-5:-1]
                for col in cols:
                    try:
                        col_name = col[1] if isinstance(col, tuple) else col
                        val_sales = df.loc['매출액', col] if '매출액' in df.index else 0
                        val_op = df.loc['영업이익', col] if '영업이익' in df.index else 0
                        val_net = df.loc['당기순이익', col] if '당기순이익' in df.index else 0
                        fin_data.append({
                            "Date": str(col_name).strip(),
                            "매출액": float(val_sales) if val_sales != '-' and pd.notnull(val_sales) else 0,
                            "영업이익": float(val_op) if val_op != '-' and pd.notnull(val_op) else 0,
                            "당기순이익": float(val_net) if val_net != '-' and pd.notnull(val_net) else 0
                        })
                    except: continue
                return pd.DataFrame(fin_data)
        return pd.DataFrame()
    except: return pd.DataFrame()

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(data, short=12, long=26, signal=9):
    short_ema = data.ewm(span=short, adjust=False).mean()
    long_ema = data.ewm(span=long, adjust=False).mean()
    macd = short_ema - long_ema
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def calculate_atr(data, window=14):
    try:
        high = data['High']; low = data['Low']; close = data['Close']
        prev_close = close.shift(1)
        tr = pd.concat([high-low, (high-prev_close).abs(), (low-prev_close).abs()], axis=1).max(axis=1)
        return tr.rolling(window=window).mean()
    except: return pd.Series(0, index=data.index)

def backtest_strategy(df):
    try:
        sim_df = df.copy()
        sim_df['Signal'] = (sim_df['Close'] > sim_df['MA20']) & (sim_df['RSI'] < 40)
        signals = sim_df[sim_df['Signal']].index
        wins = 0; total = 0
        for date in signals:
            try:
                idx = sim_df.index.get_loc(date)
                future = sim_df.iloc[idx+1:idx+11]
                if len(future) < 1: continue
                if future['High'].max() >= sim_df.loc[date, 'Close'] * 1.03: wins += 1
                total += 1
            except: continue
        return int((wins / total) * 100) if total > 0 else 0
    except: return 0

@st.cache_data(ttl=1800)
def get_market_cycle_status(code):
    try:
        kospi = fdr.DataReader('KS11', datetime.datetime.now()-datetime.timedelta(days=400))
        ma120 = kospi['Close'].rolling(120).mean().iloc[-1]
        return "📈 시장 상승세 (공격적 매수 유효)" if kospi['Close'].iloc[-1] > ma120 else "📉 시장 하락세 (보수적 접근 필요)"
    except: return "시장 분석 중"

def calculate_sniper_score(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty or len(df) < 60: return 0, [], 0, 0, 0, pd.DataFrame(), ""
        
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['MA120'] = df['Close'].rolling(120).mean()
        df['MA240'] = df['Close'].rolling(240).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        df['ATR'] = calculate_atr(df)
        df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
        df['BB_Upper'] = df['MA20'] + (df['Close'].rolling(20).std() * 2)
        df['BB_Lower'] = df['MA20'] - (df['Close'].rolling(20).std() * 2)
        
        curr = df.iloc[-1]; prev = df.iloc[-2]
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
        vol_ratio = curr['Volume'] / vol_avg if vol_avg > 0 else 0
        
        score = 0; tags = []
        main_reason = "관망 필요"

        if vol_ratio >= 3.0: 
            if curr['Close'] >= curr['Open']: score += 40; tags.append("🔥 거래량폭발"); main_reason = "큰손 쓸어담는 중"
            else: score -= 50; tags.append("😱 투매폭탄"); main_reason = "세력 이탈 경고"
        elif vol_ratio >= 1.5:
            if curr['Close'] >= curr['Open']: score += 20; tags.append("📈 거래량증가")
            else: score -= 10; tags.append("📉 매도세출현")
        
        if curr['Close'] > curr['MA20']: score += 20
        if curr['RSI'] < 30: score += 10; tags.append("💎 과매도(기회)"); main_reason = "바닥 잡을 찬스"
        if curr['MACD'] > curr['MACD_Signal']: score += 10; tags.append("🌊 추세전환"); main_reason = "상승 파도타기"
        
        win_rate = backtest_strategy(df)
        if win_rate >= 70: score += 10; tags.append(f"👑 승률{win_rate}%")

        return score, tags, vol_ratio, (curr['Close']-prev['Close'])/prev['Close']*100, win_rate, df, main_reason
    except: return 0, [], 0, 0, 0, pd.DataFrame(), ""

@st.cache_data(ttl=3600)
def get_macro_data():
    results = {}
    tickers = {"KOSPI": "KS11", "KOSDAQ": "KQ11", "USD/KRW": "USD/KRW"} 
    for name, code in tickers.items():
        try:
            df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=14))
            if not df.empty:
                curr = df.iloc[-1]
                results[name] = {"val": curr['Close'], "change": (curr['Close'] - curr['Open']) / curr['Open'] * 100}
            else: results[name] = {"val": 0.0, "change": 0.0}
        except: results[name] = {"val": 0.0, "change": 0.0}
    return results

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        def get_val(id_str):
            t = soup.select_one(f"#{id_str}")
            return float(t.text.replace(',', '').replace('%','').replace('배','').strip()) if t else 0.0
            
        per = get_val("_per"); pbr = get_val("_pbr"); div = get_val("_dvr")
        
        per_stat = "good" if 0 < per < 10 else "neu"
        pbr_stat = "good" if 0 < pbr < 1.0 else "neu"
        
        score = 20 + (15 if pbr_stat=="good" else 0) + (10 if per_stat=="good" else 0)
        fund_data = {
            "per": {"val": per, "stat": per_stat, "txt": "실적우수" if per_stat=="good" else "보통"},
            "pbr": {"val": pbr, "stat": pbr_stat, "txt": "저평가" if pbr_stat=="good" else "적정"},
            "div": {"val": div, "stat": "good" if div > 3.0 else "neu", "txt": "고배당" if div > 3.0 else "일반"}
        }
        return min(score, 50), "분석완료", fund_data
    except: return 0, "데이터 없음", {}

# --- AI 관련 함수 ---
def call_gemini_dynamic(prompt):
    api_key = USER_GOOGLE_API_KEY
    if not api_key: return None, "NO_KEY"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.0}}
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code == 200: return res.json(), None
        return None, f"HTTP Error: {res.status_code}"
    except Exception as e: return None, str(e)

def get_ai_recommended_stocks(keyword):
    prompt = f"""
    당신은 한국 주식 전문가입니다. '{keyword}'와 관련된 한국(KOSPI/KOSDAQ) 주식 5개를 추천해주세요.
    각 종목의 핵심 관계(relation)를 5글자 이내로 포함하여 JSON으로 출력하세요.
    예시: [{{"name": "삼성전자", "code": "005930", "relation": "HBM대장"}}]
    """
    res, err = call_gemini_dynamic(prompt)
    if res:
        try:
            txt = res['candidates'][0]['content']['parts'][0]['text'].replace("```json", "").replace("```", "").strip()
            return json.loads(txt), f"🤖 AI가 '{keyword}' 관련주를 찾았습니다!"
        except: return [], "AI 응답 오류"
    return [], "AI 연결 실패"

@st.cache_data(ttl=600)
def get_news_sentiment_llm(name, context={}):
    titles = []
    try:
        url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(name)}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        titles = [item.get_text().strip() for item in soup.select('.news_tit')][:5]
    except: pass
    
    if not titles: return {"headline": "뉴스 없음", "opinion": "중립", "score": 0, "raw_news": [], "method": "none"}
    
    prompt = f"""
    종목명: {name}
    현재가: {context.get('current_price', 0)}원
    뉴스: {str(titles)}
    
    위 정보를 바탕으로 투자 의견(매수/매도/관망/보유)과 한 줄 요약, 점수(-10~10)를 JSON으로 출력하세요.
    형식: {{"opinion": "...", "summary": "...", "score": 0, "catalyst": "...", "risk": "..."}}
    """
    
    res, err = call_gemini_dynamic(prompt)
    raw_news = [{"title": t, "link": "#", "date": ""} for t in titles]
    
    if res:
        try:
            txt = res['candidates'][0]['content']['parts'][0]['text'].replace("```json", "").replace("```", "").strip()
            js = json.loads(txt)
            return {"headline": js.get('summary'), "opinion": js.get('opinion'), "score": js.get('score', 0), "raw_news": raw_news, "method": "ai", "catalyst": js.get('catalyst'), "risk": js.get('risk')}
        except: pass
        
    return {"headline": "AI 분석 실패 (키워드 모드)", "opinion": "관망", "score": 0, "raw_news": raw_news, "method": "keyword"}

# --- 종합 분석 함수 ---
def analyze_pro(code, name_override=None, relation_tag=None, my_buy_price=None):
    try:
        score, tags, vol_ratio, chg_rate, win_rate, df, main_reason = calculate_sniper_score(code)
        if df.empty: return None
        curr = df.iloc[-1]
    except: return None

    result = {
        "name": name_override if name_override else code, "code": code, 
        "price": int(curr['Close']), "change_rate": chg_rate, "score": 50,
        "strategy": {}, "fund_data": None, "ma_status": [], "trend_txt": "",
        "news": {}, "history": df, "stoch": {"k": curr['RSI'], "d": 0}, "vol_ratio": vol_ratio,
        "investor_trend": pd.DataFrame(), "fin_history": pd.DataFrame(),
        "win_rate": win_rate, "cycle_txt": get_market_cycle_status(code),
        "relation_tag": relation_tag, "my_buy_price": my_buy_price
    }
    
    # 기술적 분석
    mas = [('5일', 'MA5'), ('20일', 'MA20'), ('60일', 'MA60')]
    result['ma_status'] = [{"label": l, "ok": curr['Close'] >= curr.get(c, 0)} for l, c in mas]
    pass_cnt = sum(1 for x in result['ma_status'] if x['ok'])
    result['trend_txt'] = "강력한 상승" if pass_cnt==3 else ("상승세" if pass_cnt==2 else "조정/하락")
    
    # 재무/수급 분석
    fund_score, _, result['fund_data'] = get_company_guide_score(code)
    result['investor_trend'] = get_investor_trend(code)
    result['fin_history'] = get_financial_history(code)
    
    # 점수 합산
    final_score = score + fund_score
    if "상승세" in result['cycle_txt']: final_score += 10
    result['score'] = min(max(final_score, 0), 100)
    
    # 뉴스 AI 분석 (여기가 비용의 핵심)
    context = {"current_price": result['price'], "code": code}
    result['news'] = get_news_sentiment_llm(result['name'], context)
    if result['news']['method'] == 'ai': result['score'] += result['news']['score']
    
    # 전략 수립
    atr = curr.get('ATR', curr['Close']*0.03)
    if my_buy_price: # 보유중
        result['strategy'] = {
            "action": result['news'].get('opinion', '홀딩'),
            "buy": my_buy_price, "buy_basis": "보유중",
            "target": int(my_buy_price*1.10), "stop": int(my_buy_price*0.95)
        }
    else: # 신규
        buy_p = int(curr['Close']) if result['score'] >= 80 else int(curr.get('MA20', curr['Close']))
        result['strategy'] = {
            "action": "매수" if result['score'] >= 60 else "관망",
            "buy": buy_p, "buy_basis": "기술적 분석",
            "target": int(buy_p*1.10), "stop": int(buy_p*0.95)
        }
    
    return result

def send_telegram_msg(token, chat_id, msg):
    try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": msg})
    except: pass

# ------------------------------------------------------------------------------
# [5] 메인 UI 구성
# ------------------------------------------------------------------------------
col_title, col_guide = st.columns([0.7, 0.3])
with col_title:
    st.title("💎 Quant Sniper V50.1")
    st.caption("비용 최적화: ⚡ 버튼을 눌러야 AI가 분석합니다.")

with col_guide:
    st.write("")
    with st.expander("📊 시장 현황"):
        macro = get_macro_data()
        if macro:
            for k, v in macro.items():
                c = "red" if v['change']>0 else "blue"
                st.markdown(f"**{k}**: :{c}[{v['val']:,.0f} ({v['change']:+.2f}%)]")

tab1, tab2, tab3 = st.tabs(["🔍 종목 발굴", "💰 내 잔고", "👀 관심 종목"])

# --- Tab 1: 종목 발굴 (기존 동일) ---
with tab1:
    with st.form("search_form"):
        keyword = st.text_input("테마/종목 검색 (예: 반도체, 005930)")
        if st.form_submit_button("분석 시작"):
            if not keyword: st.warning("검색어를 입력하세요.")
            else:
                st.info(f"🔎 '{keyword}' AI 검색 중... (비용 발생)")
                targets = []
                # 1. 코드로 검색
                if keyword.isdigit() and not krx_df.empty and keyword in krx_df['Code'].values:
                    name = krx_df[krx_df['Code']==keyword].iloc[0]['Name']
                    targets = [{"code": keyword, "name": name, "relation": "직접검색"}]
                # 2. 이름으로 검색
                elif not krx_df.empty and keyword in krx_df['Name'].values:
                    code = krx_df[krx_df['Name']==keyword].iloc[0]['Code']
                    targets = [{"code": code, "name": keyword, "relation": "직접검색"}]
                # 3. AI 추천
                else:
                    ai_list, msg = get_ai_recommended_stocks(keyword)
                    if ai_list: 
                        st.success(msg)
                        targets = ai_list
                    else:
                        st.warning("AI 추천 실패, 네이버 테마 검색 시도...")
                        raw_list, _ = get_naver_theme_stocks(keyword)
                        targets = raw_list

                # 발굴 탭은 사용자가 의도한 것이므로 즉시 분석 실행
                if targets:
                    results = []
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        futures = [executor.submit(analyze_pro, t['code'], t['name'], t.get('relation')) for t in targets]
                        for f in concurrent.futures.as_completed(futures):
                            if f.result(): results.append(f.result())
                    
                    st.session_state['preview_list'] = sorted(results, key=lambda x: x['score'], reverse=True)
                    st.rerun()
                else: st.error("종목을 찾을 수 없습니다.")

    # 분석 결과 출력
    if st.session_state.get('preview_list'):
        for res in st.session_state['preview_list']:
            st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
            with st.expander(f"▼ 상세 분석: {res['name']}"):
                if st.button("📌 관심종목 등록", key=f"add_{res['code']}"):
                    st.session_state['data_store']['watchlist'][res['name']] = {"code": res['code']}
                    if save_db(st.session_state['data_store']):
                        st.success("구글 시트에 저장 완료!")
                        time.sleep(1); st.rerun()
                
                c1, c2 = st.columns(2)
                with c1: st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                with c2: render_fund_scorecard(res['fund_data']); render_investor_chart(res['investor_trend'])
                
                if res['news']['method'] == 'ai':
                    st.info(f"🤖 AI 요약: {res['news']['headline']}")

# --- Tab 2: 내 잔고 (On-Demand 적용) ---
with tab2:
    portfolio = st.session_state['data_store'].get('portfolio', {})
    if not portfolio: st.info("보유 종목이 없습니다.")
    else:
        # 여기서는 자동으로 분석하지 않고, 목록만 보여줍니다.
        for name, info in portfolio.items():
            code = info['code']
            
            # 1. 이미 분석된 결과가 있는지 확인
            if code in st.session_state['analysis_cache']:
                res = st.session_state['analysis_cache'][code]
                st.markdown(create_portfolio_card_html(res), unsafe_allow_html=True)
                
                with st.expander(f"▼ 관리 옵션: {name}"):
                    if st.button("🗑️ 삭제 (매도)", key=f"del_port_{code}"):
                        del st.session_state['data_store']['portfolio'][name]
                        save_db(st.session_state['data_store'])
                        # 삭제 시 캐시도 지워줌
                        if code in st.session_state['analysis_cache']:
                            del st.session_state['analysis_cache'][code]
                        st.rerun()
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
            
            # 2. 분석되지 않았다면 '심플 카드'와 '분석 버튼' 표시
            else:
                with st.container():
                    st.markdown(f"""
                    <div style='padding:15px; border-radius:12px; background:#fff; border:1px solid #ddd; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;'>
                        <div>
                            <span style='font-size:16px; font-weight:bold;'>{name}</span>
                            <span style='font-size:12px; color:#888; margin-left:5px;'>{code}</span>
                            <div style='font-size:12px; color:#555;'>평단: {info['buy_price']:,}원</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 분석 버튼 (이걸 눌러야 비용 발생)
                    if st.button(f"⚡ {name} AI 분석 실행", key=f"run_port_{code}"):
                        with st.spinner(f"{name} 정밀 분석 중..."):
                            res = analyze_pro(code, name, None, info['buy_price'])
                            if res:
                                # 결과 저장 (캐싱)
                                st.session_state['analysis_cache'][code] = res
                                st.rerun()

# --- Tab 3: 관심 종목 (On-Demand 적용) ---
with tab3:
    watchlist = st.session_state['data_store'].get('watchlist', {})
    if not watchlist: st.info("관심 종목이 없습니다.")
    else:
        for name, info in watchlist.items():
            code = info['code']
            
            # 1. 분석된 결과가 있으면 보여줌
            if code in st.session_state['analysis_cache']:
                res = st.session_state['analysis_cache'][code]
                st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
                
                with st.expander(f"▼ 매수 및 관리: {name}"):
                    c1, c2 = st.columns([0.6, 0.4])
                    with c1:
                        price = st.number_input("매수 단가", value=res['price'], step=100, key=f"p_{code}")
                    with c2:
                        st.write("")
                        st.write("")
                        if st.button("📥 매수 체결", key=f"buy_{code}"):
                            st.session_state['data_store']['portfolio'][name] = {"code": code, "buy_price": price}
                            if name in st.session_state['data_store']['watchlist']:
                                del st.session_state['data_store']['watchlist'][name]
                            save_db(st.session_state['data_store'])
                            st.success("매수 완료! 잔고 탭으로 이동했습니다.")
                            if code in st.session_state['analysis_cache']:
                                del st.session_state['analysis_cache'][code]
                            time.sleep(1); st.rerun()
                    
                    if st.button("🗑️ 삭제", key=f"del_wl_{code}"):
                        del st.session_state['data_store']['watchlist'][name]
                        save_db(st.session_state['data_store'])
                        if code in st.session_state['analysis_cache']:
                            del st.session_state['analysis_cache'][code]
                        st.rerun()
            
            # 2. 분석 전: 심플 카드 표시
            else:
                with st.container():
                    st.markdown(f"""
                    <div style='padding:15px; border-radius:12px; background:#fff; border:1px solid #ddd; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;'>
                        <div>
                            <span style='font-size:16px; font-weight:bold;'>{name}</span>
                            <span style='font-size:12px; color:#888; margin-left:5px;'>{code}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"⚡ {name} AI 분석 실행", key=f"run_wl_{code}"):
                        with st.spinner(f"{name} 분석 중..."):
                            res = analyze_pro(code, name)
                            if res:
                                st.session_state['analysis_cache'][code] = res
                                st.rerun()
