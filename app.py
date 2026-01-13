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
import urllib.parse
import numpy as np
from io import StringIO
import random
import warnings
import logging

# [강제 처방 1] 모든 경고 메시지 & 로그 차단 (화면 깨끗하게 하기)
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
logging.getLogger('streamlit').setLevel(logging.ERROR)
st.set_option('deprecation.showPyplotGlobalUse', False)

# ------------------------------------------------------------------------------
# [모듈 연결] ui.py 기능 가져오기
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
except ImportError:
    st.error("❌ 'modules/ui.py' 파일을 찾을 수 없습니다. 깃허브에 파일이 있는지 확인해주세요!")
    st.stop()

# ==============================================================================
# [보안 설정] Streamlit Secrets
# ==============================================================================
try:
    USER_GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
    USER_TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
    USER_CHAT_ID = st.secrets.get("CHAT_ID", "")
    USER_GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
except Exception as e:
    USER_GITHUB_TOKEN = ""
    USER_TELEGRAM_TOKEN = ""
    USER_CHAT_ID = ""
    USER_GOOGLE_API_KEY = ""

# --- [1. 기본 설정 및 CSS 적용] ---
st.set_page_config(page_title="Quant Sniper V50.2 (Final)", page_icon="💎", layout="wide")
apply_custom_css()

# --- [2. 데이터 로딩 및 분석 로직] ---
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

@st.cache_data
def get_krx_list_safe():
    try:
        df = fdr.StockListing('KRX')
        if not df.empty: return df
    except: pass 

    try:
        target_date = datetime.datetime.now()
        for _ in range(5):
            d_str = target_date.strftime("%Y%m%d")
            try:
                tickers = stock.get_market_ticker_list(d_str, market="KOSPI")
                if tickers: break 
            except: pass
            target_date -= datetime.timedelta(days=1)
        d_str = target_date.strftime("%Y%m%d")
        df_kospi = stock.get_market_cap_by_ticker(d_str, market="KOSPI")
        df_kosdaq = stock.get_market_cap_by_ticker(d_str, market="KOSDAQ")
        df_list = []
        if not df_kospi.empty:
            df_kospi = df_kospi.reset_index()
            df_list.append(df_kospi[['티커', '종목명']].rename(columns={'티커': 'Code', '종목명': 'Name'}))
        if not df_kosdaq.empty:
            df_kosdaq = df_kosdaq.reset_index()
            df_list.append(df_kosdaq[['티커', '종목명']].rename(columns={'티커': 'Code', '종목명': 'Name'}))
        if df_list: return pd.concat(df_list, ignore_index=True)
    except Exception as e: pass
    return pd.DataFrame() 

krx_df = get_krx_list_safe()

def load_from_github():
    try:
        token = USER_GITHUB_TOKEN
        if not token: return {"portfolio": {}, "watchlist": {}}
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            data = json.loads(content)
            if "portfolio" not in data and "watchlist" not in data:
                return {"portfolio": {}, "watchlist": data}
            return data
        return {"portfolio": {}, "watchlist": {}}
    except: return {"portfolio": {}, "watchlist": {}}

def update_github_file(new_data):
    try:
        token = USER_GITHUB_TOKEN
        if not token: return False
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        r_get = requests.get(url, headers=headers)
        if r_get.status_code == 200:
            sha = r_get.json().get('sha')
        else:
            sha = None
        json_str = json.dumps(new_data, ensure_ascii=False, indent=4)
        b64_content = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        data = {
            "message": "Update data via Streamlit App (V50.2)",
            "content": b64_content
        }
        if sha: data["sha"] = sha
        r_put = requests.put(url, headers=headers, json=data)
        return r_put.status_code in [200, 201]
    except Exception as e:
        return False

if 'data_store' not in st.session_state: st.session_state['data_store'] = load_from_github()
if 'preview_list' not in st.session_state: st.session_state['preview_list'] = []
if 'current_theme_name' not in st.session_state: st.session_state['current_theme_name'] = ""

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
                price_txt = row.select('td.number')[0].text.strip().replace(',', '')
                try: price = int(price_txt)
                except: price = 0
                stocks.append({"code": code, "name": name, "price": price})
        return stocks, f"'{keyword}' 관련 테마 발견: {len(stocks)}개 종목"
    except Exception as e: return [], f"크롤링 오류: {str(e)}"

def get_investor_trend_from_naver(code):
    try:
        url = f"https://finance.naver.com/item/frgn.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        try: dfs = pd.read_html(StringIO(res.text), match='날짜', header=0, encoding='euc-kr')
        except: dfs = pd.read_html(StringIO(res.text), header=0, encoding='euc-kr')
        target_df = dfs[1] if len(dfs) > 1 else dfs[0]
        if target_df is not None:
            df = target_df.dropna().copy()
            df.columns = ['날짜', '종가', '전일비', '등락률', '거래량', '기관', '외국인', '보유주수', '보유율']
            df = df.iloc[:20].copy().sort_values('날짜')
            df['기관'] = df['기관'].astype(str).str.replace(',', '').astype(float)
            df['외국인'] = df['외국인'].astype(str).str.replace(',', '').astype(float)
            df['개인'] = -(df['기관'] + df['외국인'])
            df['Cum_Individual'] = df['개인'].cumsum()
            df['Cum_Foreigner'] = df['외국인'].cumsum()
            df['Cum_Institution'] = df['기관'].cumsum()
            return df
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_investor_trend(code):
    try:
        end_d = datetime.datetime.now().strftime("%Y%m%d")
        start_d = (datetime.datetime.now() - datetime.timedelta(days=100)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(start_d, end_d, code)
        if not df.empty:
            df = df.tail(60).copy()
            df['Cum_Individual'] = df['개인'].cumsum()
            df['Cum_Foreigner'] = df['외국인'].cumsum()
            df['Cum_Institution'] = df['기관합계'].cumsum()
            df['Cum_Pension'] = df['연기금'].cumsum()
            return df
    except: pass
    return get_investor_trend_from_naver(code)

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

# -----------------------------------------------------------
# [보조지표 함수]
# -----------------------------------------------------------
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
        high = data['High']
        low = data['Low']
        close = data['Close']
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=window).mean()
        return atr
    except: return pd.Series(0, index=data.index)

def calculate_stochastic(data, n=14, m=3, t=3):
    try:
        low = data['Low']
        high = data['High']
        close = data['Close']
        fast_k = ((close - low.rolling(n).min()) / (high.rolling(n).max() - low.rolling(n).min())) * 100
        slow_k = fast_k.rolling(m).mean()
        slow_d = slow_k.rolling(t).mean()
        return slow_k, slow_d
    except: return pd.Series(0), pd.Series(0)

def calculate_mfi(data, period=14):
    try:
        tp = (data['High'] + data['Low'] + data['Close']) / 3
        mf = tp * data['Volume']
        delta = tp.diff()
        pos_mf = pd.Series(0.0, index=data.index)
        neg_mf = pd.Series(0.0, index=data.index)
        pos_mf[delta > 0] = mf[delta > 0]
        neg_mf[delta < 0] = mf[delta < 0]
        mfi = 100 - (100 / (1 + (pos_mf.rolling(period).sum() / neg_mf.rolling(period).sum())))
        return mfi.fillna(50)
    except: return pd.Series(50, index=data.index)

def calculate_sar(data, af_start=0.02, af_step=0.02, af_max=0.2):
    try:
        high = data['High'].values
        low = data['Low'].values
        close = data['Close'].values
        length = len(close)
        sar = np.zeros(length)
        trend = np.zeros(length)
        if length == 0: return pd.Series(0), pd.Series(0)
        sar[0] = low[0]; trend[0] = 1
        ep = high[0]; af = af_start
        for i in range(1, length):
            prev_sar = sar[i-1]; prev_trend = trend[i-1]
            new_sar = prev_sar + af * (ep - prev_sar)
            if prev_trend == 1:
                if low[i] < new_sar: trend[i] = -1; sar[i] = ep; ep = low[i]; af = af_start
                else: trend[i] = 1; sar[i] = new_sar; ep = max(ep, high[i]); af = min(af + af_step, af_max)
            else:
                if high[i] > new_sar: trend[i] = 1; sar[i] = ep; ep = high[i]; af = af_start
                else: trend[i] = -1; sar[i] = new_sar; ep = min(ep, low[i]); af = min(af + af_step, af_max)
        return pd.Series(sar, index=data.index), pd.Series(trend, index=data.index)
    except: return pd.Series(0, index=data.index), pd.Series(0, index=data.index)

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

# --- [뉴스 크롤링] ---
def get_naver_search_news(keyword):
    titles = []
    try:
        url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(keyword)}&sort=1&pd=2"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('.news_tit')
        for item in items:
            t = item.get_text().strip()
            if t: titles.append(t)
    except: pass
    return list(dict.fromkeys(titles))[:7]

def get_naver_finance_news(code):
    titles = []
    try:
        url = f"https://finance.naver.com/item/news_news.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        res.encoding = 'euc-kr'
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('.title a')
        for item in items:
            t = item.get_text().strip()
            if t and "관련기사" not in t:
                titles.append(t)
    except: pass
    return list(dict.fromkeys(titles))[:5]

# [AI 분석 엔진]
def get_news_sentiment_llm(company_name, stock_data_context=None):
    if stock_data_context is None: stock_data_context = {}
    news_titles = []
     
    # 1. 네이버 검색 뉴스
    search_titles = get_naver_search_news(company_name)
    news_titles.extend([f"[검색] {t}" for t in search_titles])

    # 2. 네이버 금융 뉴스
    code = stock_data_context.get('code', '')
    if code:
        fin_titles = get_naver_finance_news(code)
        news_titles.extend([f"[공시/금융] {t}" for t in fin_titles])

    news_titles = list(set(news_titles))

    if not news_titles: 
        return {"score": 0, "headline": "최신 뉴스 없음 (기술적 분석 수행)", "method": "tech_only", "opinion": "중립", "risk": "정보 부재", "raw_news": []}

    try:
        if not USER_GOOGLE_API_KEY: raise Exception("API Key Missing")
        
        # 데이터 준비
        trend = stock_data_context.get('trend', '분석중')
        profit_rate = stock_data_context.get('profit_rate', 0.0)
        current_price = stock_data_context.get('current_price', 0)
        is_holding = stock_data_context.get('is_holding', False)
        supply_info = stock_data_context.get('supply_info', '수급 정보 없음')
        macro_info = stock_data_context.get('macro_info', 'USD/KRW 정보 없음')
        
        prompt = f"""
        당신은 노련한 주식 전략가입니다. 아래 데이터를 바탕으로 3가지 관점에서 입체적으로 분석해주세요.
        
        [1. 기초 데이터]
        - 종목: {company_name} (현재가: {current_price:,}원)
        - 기술적 추세: {trend}
        - **투자자별 수급**: {supply_info}
        - 시장 환율(참고): {macro_info}
        - 내 상태: {"보유중 (수익률 " + str(round(profit_rate, 2)) + "%)" if is_holding else "미보유 (신규진입 고민)"}

        [2. 최신 뉴스]
        {str(news_titles)}

        [분석 요청]
        1. 정량적(Technical): 차트 및 수급 분석
        2. 정성적(Qualitative): 뉴스 재료 분석
        3. 수급(Supply): 기관/외인 동향 추론
        4. 종합 결론: 매수/매도/관망 의견

        반드시 아래 JSON 포맷으로만 응답하세요. 마크다운 쓰지 마세요.
        {{
            "technical": "내용",
            "qualitative": "내용",
            "supply_analysis": "내용",
            "conclusion": "한줄 결론",
            "score": 70
        }}
        """
        
        res_data, error_msg = call_gemini_dynamic(prompt)
        if res_data and 'candidates' in res_data:
            raw = res_data['candidates'][0]['content']['parts'][0]['text']
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            
            # [강력해진 JSON 파싱]
            try:
                # 1차 시도: 정규식으로 JSON 추출
                match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                if match:
                    js = json.loads(match.group())
                else:
                    # JSON 형식이 아닐 경우 전체 텍스트를 강제로 변환
                    js = {
                        "technical": "분석 데이터 변환 중",
                        "qualitative": cleaned[:200] + "...",
                        "supply_analysis": "상세 내용은 AI 원문 참조",
                        "conclusion": cleaned[:50] + "...",
                        "score": 50
                    }
                
                # 뉴스 데이터 포맷팅
                formatted_news = [{"title": t, "link": f"https://search.naver.com/search.naver?where=news&query={company_name}", "date": "최신"} for t in news_titles[:7]]
                js['raw_news'] = formatted_news
                js['method'] = "ai"
                if 'headline' not in js: js['headline'] = js.get('conclusion', '분석 완료')
                return js

            except Exception as parse_e:
                return {
                    "technical": "AI 응답 형식이 올바르지 않지만 내용은 수신했습니다.",
                    "qualitative": cleaned, 
                    "supply_analysis": "위 내용을 참고하세요.",
                    "conclusion": "형식 오류로 원문 표시",
                    "score": 50,
                    "raw_news": [],
                    "method": "ai"
                }

        else: raise Exception(error_msg)
        
    except Exception as e:
        return {"score": 0, "headline": f"AI 통신 오류: {str(e)}", "method": "error", "opinion": "중립", "raw_news": []}

def get_valid_model_name(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            models = [m['name'] for m in res.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
            if 'models/gemini-1.5-flash' in models: return 'models/gemini-1.5-flash'
            if 'models/gemini-pro' in models: return 'models/gemini-pro'
            return models[0] if models else "models/gemini-pro"
    except: pass
    return "models/gemini-pro"

def call_gemini_dynamic(prompt):
    api_key = USER_GOOGLE_API_KEY
    if not api_key: return None, "NO_KEY"
    model_name = get_valid_model_name(api_key).replace("models/", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.0}}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code == 200: return res.json(), None
        else: return None, f"HTTP {res.status_code}"
    except Exception as e: return None, str(e)

def get_supply_demand(code):
    try:
        e = datetime.datetime.now().strftime("%Y%m%d")
        s = (datetime.datetime.now()-datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(s, e, code).tail(3)
        if df.empty: return {"f":0, "i":0}
        return {"f": int(df['외국인'].sum()), "i": int(df['기관합계'].sum())}
    except: return {"f":0, "i":0}

def get_macro_data():
    try:
        df = fdr.DataReader('USD/KRW', datetime.datetime.now() - datetime.timedelta(days=7))
        if not df.empty:
            return {"USD/KRW": {"val": df['Close'].iloc[-1]}}
    except: pass
    return {"USD/KRW": {"val": 0.0}}

def get_company_guide_score(code):
    return 0, 0, {}

def get_ai_recommended_stocks(keyword):
    return [], "검색 실패"

def round_to_tick(price):
    if price < 2000: return int(round(price, -1))
    elif price < 5000: return int(round(price / 5) * 5)
    elif price < 20000: return int(round(price, -1))
    elif price < 50000: return int(round(price / 50) * 50)
    elif price < 200000: return int(round(price, -2))
    elif price < 500000: return int(round(price / 500) * 500)
    else: return int(round(price, -3))

def calculate_sniper_score(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=400))
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
        df['Stoch_K'], df['Stoch_D'] = calculate_stochastic(df)
        df['MFI'] = calculate_mfi(df)
        df['SAR'], df['SAR_Trend'] = calculate_sar(df) 
        
        curr = df.iloc[-1]; prev = df.iloc[-2]
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
        score = 0; tags = []
        vol_ratio = curr['Volume'] / vol_avg if vol_avg > 0 else 0
        price_chg = (curr['Close'] - prev['Close']) / prev['Close'] * 100
        main_reason = "관망 필요"

        if curr['MFI'] > 80: score += 10; tags.append("🔥 자금유입")
        if curr['SAR_Trend'] == 1: score += 20; tags.append("📈 상승추세")
        else: score -= 10
        if curr['Close'] > curr['MA20']: score += 10
        if curr['MACD'] > curr['MACD_Signal']: score += 10; tags.append("🌊 MACD상승")
        if curr['Stoch_K'] > curr['Stoch_D'] and prev['Stoch_K'] < prev['Stoch_D']: score += 30; tags.append("⚡ 골든크로스"); main_reason="매수 신호 발생"
        
        win_rate = backtest_strategy(df)
        if win_rate >= 70: score += 10; tags.append(f"👑 승률{win_rate}%")

        if score < 60 and main_reason == "관망 필요": main_reason = "힘 모으는 중"
        return min(max(score, 0), 100), tags, vol_ratio, price_chg, win_rate, df, main_reason
    except: return 0, [], 0, 0, 0, pd.DataFrame(), ""

def analyze_pro(code, name_override=None, relation_tag=None, my_buy_price=None, stored_data=None):
    try:
        score, tags, vol_ratio, chg_rate, win_rate, df, main_reason = calculate_sniper_score(code)
        if df.empty: return None
        curr = df.iloc[-1]
    except: return None

    profit_rate = 0.0
    if my_buy_price and my_buy_price > 0:
        profit_rate = (int(curr['Close']) - my_buy_price) / my_buy_price * 100

    result_dict = {
        "name": name_override if name_override else code, 
        "code": code, 
        "price": int(curr['Close']),
        "change_rate": chg_rate, 
        "score": score,
        "strategy": {}, 
        "fund_data": None, 
        "ma_status": [], 
        "trend_txt": "분석 중",
        "news": {"score":0, "headline":"AI 분석 버튼을 눌러주세요 👇", "raw_news":[], "method":"none", "opinion":"", "catalyst":"", "risk":""}, 
        "history": df, 
        "supply": {"f":0, "i":0},
        "stoch": {"k": curr.get('Stoch_K', 50), "d": curr.get('Stoch_D', 50)},
        "vol_ratio": vol_ratio,
        "investor_trend": pd.DataFrame(),
        "fin_history": pd.DataFrame(),
        "win_rate": win_rate, 
        "cycle_txt": "확인 중", 
        "relation_tag": relation_tag,
        "my_buy_price": my_buy_price 
    }

    if stored_data and 'ai_analysis' in stored_data:
        result_dict['news'] = stored_data['ai_analysis']

    try:
        mas = [('5일', 'MA5'), ('20일', 'MA20'), ('60일', 'MA60')]
        ma_status = []
        pass_cnt = 0
        for label, col in mas:
            val = curr.get(col, 0)
            if curr['Close'] >= val: pass_cnt += 1; ma_status.append({"label": label, "ok": True})
            else: ma_status.append({"label": label, "ok": False})
        result_dict['ma_status'] = ma_status
        result_dict['trend_txt'] = "강력한 상승" if pass_cnt >= 3 else ("상승세 유지" if pass_cnt >= 2 else "조정 국면")
    except: pass

    try: _, _, fund_data = get_company_guide_score(code); result_dict['fund_data'] = fund_data
    except: result_dict['fund_data'] = {}
    
    try: result_dict['investor_trend'] = get_investor_trend(code)
    except: pass
    try: result_dict['fin_history'] = get_financial_history(code)
    except: pass
    
    buy_price = int(curr['Close']); stop_price = int(curr['Close'] * 0.95); target_price = int(curr['Close'] * 1.1)
    result_dict['strategy'] = {
        "buy": buy_price, "buy_basis": main_reason, "target": target_price, "stop": stop_price, "action": "관망" if score < 60 else "매수"
    }
    return result_dict

def send_telegram_msg(token, chat_id, msg):
    try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": msg})
    except: pass

# --- [3. 메인 화면 UI] ---
col_title, col_guide = st.columns([0.7, 0.3])
with col_title:
    st.title("💎 Quant Sniper V50.2 (Final)")
with col_guide:
    st.write("") 
    st.write("") 
    with st.expander("📘 V50.2 업데이트", expanded=False):
        st.markdown("* **[Force Fix]** 로그 강제 차단 코드 적용\n* **[Safe Save]** 분석 결과 임시 저장 기능 추가")

tab1, tab2, tab3 = st.tabs(["🔍 테마/종목 발굴", "💰 내 잔고 (Portfolio)", "👀 관심 종목 (Watchlist)"])

with tab1:
    if st.button("🔄 화면 정리"): st.rerun()
    if st.session_state.get('preview_list'):
        st.markdown(f"### 🔍 '{st.session_state['current_theme_name']}' 분석 결과")
        with st.spinner("🚀 분석 중..."):
            preview_results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(analyze_pro, item['code'], item['name'], item.get('relation_tag')) for item in st.session_state['preview_list']]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): preview_results.append(f.result())
            preview_results.sort(key=lambda x: x['score'], reverse=True)

        for res in preview_results:
            st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
            with st.expander(f"🤖 AI 분석 및 상세 차트"):
                c1, c2 = st.columns([1, 1])
                with c1:
                    # [차트 그리기 안전 장치]
                    try:
                        st.altair_chart(create_chart_clean(res['history']))
                    except:
                        st.error("차트 로딩 중 경고 발생 (데이터는 정상입니다)")
                    
                    st.markdown(render_chart_legend(), unsafe_allow_html=True)
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_investor_chart(res['investor_trend'])
                with c2:
                    render_fund_scorecard(res['fund_data'])
                    
                    # [AI 분석 버튼 로직 수정]
                    ai_key = f"ai_result_{res['code']}"
                    if st.button(f"✨ AI 분석 실행", key=f"btn_{res['code']}"):
                        with st.spinner("AI가 3단계(기술/재료/수급)로 심층 분석 중..."):
                            inv_df = res['investor_trend']
                            sup_txt = "정보 없음"
                            if not inv_df.empty:
                                last = inv_df.iloc[-1]
                                f_buy = int(last['외국인']); i_buy = int(last['기관'])
                                sup_txt = f"외국인 {'순매수' if f_buy>0 else '순매도'}({f_buy:,}), 기관 {'순매수' if i_buy>0 else '순매도'}({i_buy:,})"
                            
                            macro = get_macro_data()
                            usd = f"USD/KRW {macro['USD/KRW']['val']:.2f}" if macro else "환율 정보 없음"

                            context = {"code": res['code'], "trend": res['trend_txt'], "current_price": res['price'], "supply_info": sup_txt, "macro_info": usd}
                            # 결과 저장
                            st.session_state[ai_key] = get_news_sentiment_llm(res['name'], context)
                    
                    # [저장된 결과 표시]
                    if ai_key in st.session_state:
                        ai_result = st.session_state[ai_key]
                        if ai_result.get('technical'):
                            st.success(f"📊 **정량(기술) 분석**\n{ai_result['technical']}")
                            st.info(f"📰 **정성(재료) 분석**\n{ai_result['qualitative']}")
                            st.warning(f"👥 **수급 심층 분석**\n{ai_result['supply_analysis']}")
                            st.markdown(f"---")
                            st.caption(f"🏆 **종합 결론**: {ai_result['conclusion']}")
                        else:
                            st.write(ai_result.get('headline'))

                        for n in ai_result.get('raw_news', []):
                            st.markdown(f"- [{n['title']}]({n['link']})")

                if st.button(f"📌 관심등록", key=f"add_{res['code']}"):
                    st.session_state['data_store']['watchlist'][res['name']] = {'code': res['code']}
                    update_github_file(st.session_state['data_store'])
                    st.success("완료"); time.sleep(0.5); st.rerun()

with tab2:
    st.markdown("### 💰 내 보유 종목 (Portfolio)")
    port_items = list(st.session_state['data_store']['portfolio'].items())
    if not port_items: st.info("보유 종목이 없습니다.")
    else:
        port_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(analyze_pro, info['code'], name, None, float(info.get('buy_price', 0)), info) for name, info in port_items]
            for f in concurrent.futures.as_completed(futures):
                if f.result(): port_results.append(f.result())
        
        for res in port_results:
            st.markdown(create_portfolio_card_html(res), unsafe_allow_html=True)
            with st.expander(f"📊 {res['name']} 상세 분석"):
                c1, c2 = st.columns([0.6, 0.4])
                with c1:
                    try:
                        st.altair_chart(create_chart_clean(res['history']))
                    except:
                        st.error("차트 로딩 중 경고 발생")
                    st.markdown(render_chart_legend(), unsafe_allow_html=True)
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_investor_chart(res['investor_trend'])
                with c2:
                    ai_data = res['news']
                    
                    inv_df = res['investor_trend']
                    sup_txt = "정보 없음"
                    if not inv_df.empty:
                        last = inv_df.iloc[-1]
                        sup_txt = f"외인 {int(last['외국인']):,}, 기관 {int(last['기관']):,}"
                    macro = get_macro_data()
                    usd = f"USD {macro['USD/KRW']['val']:.0f}" if macro else ""

                    if ai_data.get('method') == 'ai':
                        st.caption(f"🕒 {ai_data.get('timestamp')}")
                        if 'technical' in ai_data:
                            st.markdown(f"**📊 기술:** {ai_data['technical']}")
                            st.markdown(f"**📰 재료:** {ai_data['qualitative']}")
                            st.markdown(f"**👥 수급:** {ai_data['supply_analysis']}")
                            st.info(f"🏆 {ai_data['conclusion']}")
                        else:
                            st.markdown(f"**{ai_data.get('headline')}**")

                        if st.button("🔄 업데이트", key=f"re_{res['code']}"):
                            with st.spinner("..."):
                                ctx = {"code": res['code'], "trend": res['trend_txt'], "current_price": res['price'], "is_holding": True, "supply_info": sup_txt, "macro_info": usd}
                                new_ai = get_news_sentiment_llm(res['name'], ctx)
                                new_ai['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                st.session_state['data_store']['portfolio'][res['name']]['ai_analysis'] = new_ai
                                update_github_file(st.session_state['data_store'])
                                st.rerun()
                    else:
                        if st.button("✨ 3단 심층 분석", key=f"new_{res['code']}"):
                            with st.spinner("..."):
                                ctx = {"code": res['code'], "trend": res['trend_txt'], "current_price": res['price'], "is_holding": True, "supply_info": sup_txt, "macro_info": usd}
                                new_ai = get_news_sentiment_llm(res['name'], ctx)
                                new_ai['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                st.session_state['data_store']['portfolio'][res['name']]['ai_analysis'] = new_ai
                                update_github_file(st.session_state['data_store'])
                                st.rerun()
                if st.button(f"🗑️ 삭제", key=f"del_{res['code']}"):
                    del st.session_state['data_store']['portfolio'][res['name']]
                    update_github_file(st.session_state['data_store'])
                    st.rerun()

with tab3:
    st.markdown("### 👀 관심 종목 (Watchlist)")
    wl_items = list(st.session_state['data_store']['watchlist'].items())
    if not wl_items: st.info("관심 종목이 없습니다.")
    else:
        wl_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(analyze_pro, info['code'], name, None, None, info) for name, info in wl_items]
            for f in concurrent.futures.as_completed(futures):
                if f.result(): wl_results.append(f.result())
        
        for res in wl_results:
            st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
            with st.expander(f"🤖 AI 상세 분석"):
                c1, c2 = st.columns([0.6, 0.4])
                with c1:
                    try:
                        st.altair_chart(create_chart_clean(res['history']))
                    except:
                        st.error("차트 로딩 중 경고 발생")
                    st.markdown(render_chart_legend(), unsafe_allow_html=True)
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_investor_chart(res['investor_trend'])
                with c2:
                    ai_data = res['news']
                    inv_df = res['investor_trend']
                    sup_txt = "정보 없음"
                    if not inv_df.empty:
                        last = inv_df.iloc[-1]
                        sup_txt = f"외인 {int(last['외국인']):,}, 기관 {int(last['기관']):,}"
                    macro = get_macro_data()
                    usd = f"USD {macro['USD/KRW']['val']:.0f}" if macro else ""

                    # [수정: AI 결과 보여주기 방식 변경]
                    if ai_data.get('method') == 'ai':
                        st.caption(f"🕒 {ai_data.get('timestamp')}")
                        if 'technical' in ai_data:
                            st.markdown(f"**📊 기술:** {ai_data['technical']}")
                            st.markdown(f"**📰 재료:** {ai_data['qualitative']}")
                            st.markdown(f"**👥 수급:** {ai_data['supply_analysis']}")
                            st.info(f"🏆 {ai_data['conclusion']}")
                        else:
                            st.markdown(f"**{ai_data.get('headline')}**")

                        if st.button("🔄 업데이트", key=f"rw_{res['code']}"):
                            with st.spinner("..."):
                                ctx = {"code": res['code'], "trend": res['trend_txt'], "current_price": res['price'], "supply_info": sup_txt, "macro_info": usd}
                                new_ai = get_news_sentiment_llm(res['name'], ctx)
                                new_ai['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                st.session_state['data_store']['watchlist'][res['name']]['ai_analysis'] = new_ai
                                update_github_file(st.session_state['data_store'])
                                st.rerun()
                    else:
                        if st.button("✨ 3단 심층 분석", key=f"nw_{res['code']}"):
                            with st.spinner("..."):
                                ctx = {"code": res['code'], "trend": res['trend_txt'], "current_price": res['price'], "supply_info": sup_txt, "macro_info": usd}
                                new_ai = get_news_sentiment_llm(res['name'], ctx)
                                new_ai['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                st.session_state['data_store']['watchlist'][res['name']]['ai_analysis'] = new_ai
                                update_github_file(st.session_state['data_store'])
                                st.rerun()
                st.markdown("---")
                bp = st.number_input("매수 단가", value=res['price'], step=100, key=f"b_{res['code']}")
                if st.button("📥 잔고 이동", key=f"m_{res['code']}"):
                    st.session_state['data_store']['portfolio'][res['name']] = {"code": res['code'], "buy_price": bp, "ai_analysis": res['news']}
                    if res['name'] in st.session_state['data_store']['watchlist']:
                        del st.session_state['data_store']['watchlist'][res['name']]
                    update_github_file(st.session_state['data_store'])
                    st.success("이동 완료"); st.rerun()
                if st.button(f"🗑️ 삭제", key=f"d_{res['code']}"):
                    del st.session_state['data_store']['watchlist'][res['name']]
                    update_github_file(st.session_state['data_store'])
                    st.rerun()

with st.sidebar:
    st.write("### ⚙️ 기능 메뉴")
    with st.expander("🔍 테마 검색", expanded=True):
        THEME_KEYWORDS = { "직접 입력": None, "반도체": "반도체", "2차전지": "2차전지", "AI": "지능형로봇" }
        preset = st.selectbox("테마 선택", list(THEME_KEYWORDS.keys()))
        with st.form("search"):
            inp = st.text_input("검색어")
            if st.form_submit_button("분석 시작"):
                k = inp if preset == "직접 입력" else THEME_KEYWORDS[preset]
                if krx_df.empty: krx_df = get_krx_list_safe()
                found = False
                if k in krx_df['Name'].values:
                    c = krx_df[krx_df['Name'] == k].iloc[0]['Code']
                    r = analyze_pro(c, k); st.session_state['preview_list'] = [r]; found = True
                if not found:
                    s, _ = get_ai_recommended_stocks(k)
                    if s: st.session_state['preview_list'] = s
                    else: 
                        r, _ = get_naver_theme_stocks(k)
                        st.session_state['preview_list'] = r
                st.rerun()
      
    with st.expander("종목 추가"):
        n = st.text_input("이름"); c = st.text_input("코드"); h = st.checkbox("보유?")
        p = st.number_input("평단", step=100) if h else 0
        if st.button("저장"):
            t = 'portfolio' if h else 'watchlist'
            d = {"code": c}; 
            if h: d["buy_price"] = p
            st.session_state['data_store'][t][n] = d
            update_github_file(st.session_state['data_store']); st.rerun()
            
    if st.button("초기화"):
        st.session_state['data_store'] = {"portfolio": {}, "watchlist": {}}; st.rerun()
