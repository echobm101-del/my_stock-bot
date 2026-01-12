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
import numpy as np
from io import StringIO
import random

# ------------------------------------------------------------------------------
# [모듈 연결] 방금 만든 ui.py 파일에서 디자인 기능들을 가져옵니다.
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
# [보안 설정] Streamlit Secrets에서 키 가져오기
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
st.set_page_config(page_title="Quant Sniper V49.9 (Rescue Mode)", page_icon="💎", layout="wide")

# ui.py에서 가져온 함수로 디자인 적용!
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
            "message": "Update data via Streamlit App (V49.9)",
            "content": b64_content
        }
        if sha: data["sha"] = sha
        r_put = requests.put(url, headers=headers, json=data)
        return r_put.status_code in [200, 201]
    except Exception as e:
        print(f"GitHub Save Error: {e}")
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
        target_df = None
        for df in dfs:
            cols_str = " ".join([str(c) for c in df.columns])
            if '기관' in cols_str and '외국인' in cols_str: target_df = df; break
        if target_df is None and len(dfs) > 1: target_df = dfs[1]
        if target_df is not None:
            df = target_df.dropna().copy()
            first_col = df.columns[0]
            try:
                df[first_col] = pd.to_datetime(df[first_col], format='%Y.%m.%d', errors='coerce')
                df = df.dropna(subset=[first_col])
            except: return pd.DataFrame()
            df = df.rename(columns={first_col: '날짜'})
            inst_col = [c for c in df.columns if '기관' in str(c)][0]
            frgn_col = [c for c in df.columns if '외국인' in str(c)][0]
            df = df.iloc[:20].copy().sort_values('날짜')
            df['기관'] = df[inst_col].astype(str).str.replace(',', '').astype(float)
            df['외국인'] = df[frgn_col].astype(str).str.replace(',', '').astype(float)
            df['개인'] = -(df['기관'] + df['외국인'])
            df['Cum_Individual'] = df['개인'].cumsum()
            df['Cum_Foreigner'] = df['외국인'].cumsum()
            df['Cum_Institution'] = df['기관'].cumsum()
            df['Cum_Pension'] = 0 
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
# [보조지표 계산 함수 - 업그레이드됨!]
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
    """스토캐스틱 슬로우 (Fast%K -> Fast%D(=Slow%K) -> Slow%D)"""
    try:
        low = data['Low']
        high = data['High']
        close = data['Close']
        
        # Fast %K 계산
        fast_k = ((close - low.rolling(n).min()) / (high.rolling(n).max() - low.rolling(n).min())) * 100
        # Slow %K (= Fast %D)
        slow_k = fast_k.rolling(m).mean()
        # Slow %D
        slow_d = slow_k.rolling(t).mean()
        
        return slow_k, slow_d
    except:
        return pd.Series(0), pd.Series(0)

def calculate_mfi(data, period=14):
    """MFI (Money Flow Index) - 자금 흐름 지수"""
    try:
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        money_flow = typical_price * data['Volume']
        
        positive_flow = [0]
        negative_flow = [0]
        
        # 전일 대비 상승/하락 분류 (반복문 최소화)
        delta = typical_price.diff()
        
        # 긍정/부정 자금 흐름 계산
        pos_mf = pd.Series(0.0, index=data.index)
        neg_mf = pd.Series(0.0, index=data.index)
        
        pos_mf[delta > 0] = money_flow[delta > 0]
        neg_mf[delta < 0] = money_flow[delta < 0]
        
        pos_mf_sum = pos_mf.rolling(window=period).sum()
        neg_mf_sum = neg_mf.rolling(window=period).sum()
        
        mfi = 100 - (100 / (1 + (pos_mf_sum / neg_mf_sum)))
        return mfi.fillna(50) # NaN은 중립(50)으로 대체
    except:
        return pd.Series(50, index=data.index)

def calculate_sar(data, af_start=0.02, af_step=0.02, af_max=0.2):
    """파라볼릭 SAR (Parabolic Stop And Reverse)"""
    try:
        high = data['High'].values
        low = data['Low'].values
        close = data['Close'].values
        length = len(close)
        
        sar = np.zeros(length)
        trend = np.zeros(length) # 1: 상승, -1: 하락
        
        if length == 0: return pd.Series(0), pd.Series(0)

        # 초기값 설정
        sar[0] = low[0]
        trend[0] = 1
        ep = high[0] # Extreme Point
        af = af_start # Acceleration Factor
        
        for i in range(1, length):
            prev_sar = sar[i-1]
            prev_trend = trend[i-1]
            
            # SAR 계산
            new_sar = prev_sar + af * (ep - prev_sar)
            
            # 추세 반전 로직
            if prev_trend == 1: # 상승 추세 중
                if low[i] < new_sar: # 저가가 SAR을 깸 -> 하락 반전
                    trend[i] = -1
                    sar[i] = ep # 이전 최고점이 새로운 SAR
                    ep = low[i]
                    af = af_start
                else:
                    trend[i] = 1
                    sar[i] = new_sar
                    if high[i] > ep: # 신고가 갱신
                        ep = high[i]
                        af = min(af + af_step, af_max)
                        
            else: # 하락 추세 중
                if high[i] > new_sar: # 고가가 SAR을 돌파 -> 상승 반전
                    trend[i] = 1
                    sar[i] = ep # 이전 최저점이 새로운 SAR
                    ep = high[i]
                    af = af_start
                else:
                    trend[i] = -1
                    sar[i] = new_sar
                    if low[i] < ep: # 신저가 갱신
                        ep = low[i]
                        af = min(af + af_step, af_max)
                        
        return pd.Series(sar, index=data.index), pd.Series(trend, index=data.index)
    except:
        return pd.Series(0, index=data.index), pd.Series(0, index=data.index)

def backtest_strategy(df):
    try:
        sim_df = df.copy()
        sim_df['Signal'] = (sim_df['Close'] > sim_df['MA20']) & (sim_df['RSI'] < 40)
        signals = sim_df[sim_df['Signal']].index
        wins = 0
        total = 0
        for date in signals:
            try:
                idx = sim_df.index.get_loc(date)
                future = sim_df.iloc[idx+1:idx+11]
                if len(future) < 1: continue
                buy_price = sim_df.loc[date, 'Close']
                max_price = future['High'].max()
                if max_price >= buy_price * 1.03: 
                    wins += 1
                total += 1
            except: continue
        win_rate = int((wins / total) * 100) if total > 0 else 0
        return win_rate
    except: return 0

@st.cache_data(ttl=1800)
def get_market_cycle_status(code):
    try:
        kospi = fdr.DataReader('KS11', datetime.datetime.now()-datetime.timedelta(days=400))
        ma120 = kospi['Close'].rolling(120).mean().iloc[-1]
        curr = kospi['Close'].iloc[-1]
        if curr > ma120: return "📈 시장 상승세 (공격적 매수 유효)"
        else: return "📉 시장 하락세 (보수적 접근 필요)"
    except: return "시장 분석 중"

# -----------------------------------------------------------
# [메인 분석 함수 - 로직 대폭 강화!]
# -----------------------------------------------------------
def calculate_sniper_score(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=400))
        if df.empty or len(df) < 60: return 0, [], 0, 0, 0, pd.DataFrame(), ""
        
        # [기본 지표]
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

        # [신규 지표 3종 적용!]
        df['Stoch_K'], df['Stoch_D'] = calculate_stochastic(df)
        df['MFI'] = calculate_mfi(df)
        df['SAR'], df['SAR_Trend'] = calculate_sar(df) # SAR_Trend가 1이면 상승장, -1이면 하락장
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
        
        score = 0; tags = []
        vol_ratio = curr['Volume'] / vol_avg if vol_avg > 0 else 0
        price_chg = (curr['Close'] - prev['Close']) / prev['Close'] * 100
        is_bullish = curr['Close'] >= curr['Open']

        main_reason = "관망 필요"

        # 1. 거래량 분석 (MFI로 강화)
        if curr['MFI'] > 80:
             score += 10; tags.append("🔥 자금유입(MFI)")
        elif curr['MFI'] < 20:
             score += 10; tags.append("💧 바닥다지기(MFI)")

        if vol_ratio >= 3.0: 
            if price_chg > 0 or is_bullish:
                score += 30
                tags.append("💥 거래량폭발")
                main_reason = "거래량 실린 장대양봉"
            else:
                score -= 50 
                tags.append("😱 투매폭탄(위험)")
                main_reason = "세력 이탈 경고"
        elif vol_ratio >= 1.5:
            if price_chg > 0 or is_bullish:
                score += 10
                tags.append("📈 거래량증가")

        # 2. 추세 분석 (SAR 적용)
        if curr['SAR_Trend'] == 1:
            score += 20
            tags.append("📈 추세전환(SAR)")
            if main_reason == "관망 필요": main_reason = "파라볼릭 상승 추세"
        else:
            score -= 10

        if curr['Close'] > curr['MA20']: score += 10
        if curr['MACD'] > curr['MACD_Signal']: score += 10; tags.append("🌊 MACD상승")

        # 3. 모멘텀 (스토캐스틱 + RSI)
        # 스토캐스틱 골든크로스
        if prev['Stoch_K'] < prev['Stoch_D'] and curr['Stoch_K'] > curr['Stoch_D']:
             if curr['Stoch_K'] < 40:
                 score += 30; tags.append("⚡ 스토캐스틱GC")
                 main_reason = "저점 매수 골든크로스"
             else:
                 score += 10

        if curr['RSI'] < 30: 
            score += 10; tags.append("💎 RSI과매도")
            if main_reason == "관망 필요": main_reason = "바닥 잡을 찬스"

        # 백테스팅 승률
        win_rate = backtest_strategy(df)
        if win_rate >= 70: 
            score += 10; tags.append(f"👑 승률{win_rate}%")

        change = (curr['Close'] - df.iloc[-2]['Close']) / df.iloc[-2]['Close'] * 100

        if score < 60 and main_reason == "관망 필요": main_reason = "힘 모으는 중"

        return min(max(score, 0), 100), tags, vol_ratio, change, win_rate, df, main_reason
    except: return 0, [], 0, 0, 0, pd.DataFrame(), ""

@st.cache_data(ttl=3600)
def get_macro_data():
    results = {}
    tickers = {
        "KOSPI": "KS11", "KOSDAQ": "KQ11", "S&P500": "US500", "USD/KRW": "USD/KRW", 
        "US_10Y": "US10YT", "WTI": "CL=F", "구리": "HG=F" 
    }
    for name, code in tickers.items():
        try:
            df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=14))
            if not df.empty:
                curr = df.iloc[-1]
                results[name] = {"val": curr['Close'], "change": (curr['Close'] - curr['Open']) / curr['Open'] * 100}
            else: results[name] = {"val": 0.0, "change": 0.0}
        except: results[name] = {"val": 0.0, "change": 0.0}
    if all(v['val'] == 0.0 for v in results.values()): return None
    return results

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    per, pbr, div = 0.0, 0.0, 0.0
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            def get_val_by_id(id_name):
                tag = soup.select_one(f"#{id_name}")
                if tag:
                    txt = tag.text.replace(',', '').replace('%', '').replace('배', '').strip()
                    try: return float(txt)
                    except: return 0.0
                return 0.0
            per = get_val_by_id("_per")
            pbr = get_val_by_id("_pbr")
            div = get_val_by_id("_dvr")
    except: pass
    if per == 0 and pbr == 0:
        if not krx_df.empty and code in krx_df['Code'].values:
            try:
                row = krx_df[krx_df['Code'] == code].iloc[0]
                per = float(row.get('PER', 0)) if pd.notnull(row.get('PER')) else 0
                pbr = float(row.get('PBR', 0)) if pd.notnull(row.get('PBR')) else 0
                div = float(row.get('DividendYield', 0)) if pd.notnull(row.get('DividendYield')) else 0
            except: pass
    if per == 0 and pbr == 0:
        try:
            end_str = datetime.datetime.now().strftime("%Y%m%d")
            start_str = (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y%m%d")
            df = stock.get_market_fundamental_by_date(start_str, end_str, code)
            if not df.empty:
                recent = df.iloc[-1]
                per = float(recent.get('PER', 0))
                pbr = float(recent.get('PBR', 0))
                div = float(recent.get('DIV', 0))
        except: pass
    pbr_stat = "good" if 0 < pbr < 1.0 else ("neu" if 1.0 <= pbr < 2.5 else "bad")
    pbr_txt = "저평가(좋음)" if 0 < pbr < 1.0 else ("적정" if 1.0 <= pbr < 2.5 else "고평가/정보없음")
    per_stat = "good" if 0 < per < 10 else ("neu" if 10 <= per < 20 else "bad")
    per_txt = "실적우수" if 0 < per < 10 else ("보통" if 10 <= per < 20 else "고평가/적자/정보없음")
    div_stat = "good" if div > 3.0 else "neu"
    div_txt = "고배당" if div > 3.0 else "일반"
    score = 20
    if pbr_stat=="good": score+=15
    if per_stat=="good": score+=10
    if div_stat=="good": score+=5
    fund_data = {"per": {"val": per, "stat": per_stat, "txt": per_txt}, "pbr": {"val": pbr, "stat": pbr_stat, "txt": pbr_txt}, "div": {"val": div, "stat": div_stat, "txt": div_txt}}
    return min(score, 50), "분석완료", fund_data

def analyze_news_by_keywords(news_titles):
    pos_words = ["상승", "급등", "최고", "호재", "개선", "성장", "흑자", "수주", "돌파", "기대", "매수"]
    neg_words = ["하락", "급락", "최저", "악재", "우려", "감소", "적자", "이탈", "매도", "공매도"]
    sc_pos = ["공급 안정", "수율 개선", "장기 계약", "원가 절감", "공장 가동"]
    sc_neg = ["공급난", "품귀", "물류 대란", "원자재 상승", "지연", "숏티지", "부족"]

    score = 0; found_keywords = []
    sc_detected = False
    
    for title in news_titles:
        for w in pos_words:
            if w in title: score += 1; found_keywords.append(w)
        for w in neg_words:
            if w in title: score -= 1; found_keywords.append(w)
        for w in sc_pos:
            if w in title: score += 2; found_keywords.append(w); sc_detected=True
        for w in sc_neg:
            if w in title: score -= 2; found_keywords.append(w); sc_detected=True
            
    final_score = min(max(score, -10), 10)
    summary = f"긍정 키워드 {len([w for w in found_keywords if w in pos_words or w in sc_pos])}개, 부정 키워드 {len([w for w in found_keywords if w in neg_words or w in sc_neg])}개 감지."
    if sc_detected: summary += " [공급망 이슈 감지]"
    return final_score, summary, "키워드 분석", ""

def get_valid_model_name(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            models = response.json().get('models', [])
            chat_models = [m['name'] for m in models if 'generateContent' in m.get('supportedGenerationMethods', [])]
            preferences = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
            for pref in preferences:
                if pref in chat_models: return pref
            if chat_models: return chat_models[0]
    except: pass
    return "models/gemini-pro"

def call_gemini_dynamic(prompt):
    api_key = USER_GOOGLE_API_KEY
    if not api_key: return None, "NO_KEY"
    
    model_name = get_valid_model_name(api_key)
    clean_model_name = model_name.replace("models/", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0}
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code == 200: return res.json(), None
        elif res.status_code == 429: time.sleep(1); return None, "Rate Limit"
        else: return None, f"HTTP {res.status_code}: {res.text}"
    except Exception as e: return None, f"Connection Error: {str(e)}"

def get_ai_recommended_stocks(keyword):
    prompt = f"""
    당신은 한국 주식 전문가입니다.
    사용자가 입력한 검색어 '{keyword}'와 가장 관련성이 높은 한국(KOSPI/KOSDAQ) 상장 주식 5개를 추천해주세요.
    
    [핵심 규칙]
    1. 각 종목이 검색어와 어떤 관계인지 5글자 이내의 '핵심 태그(relation)'를 반드시 포함하세요. (예: 대장주, 지분보유, 경쟁사, 납품사)
    2. JSON 형식으로만 출력하세요.
    
    [출력 예시]
    [
        {{"name": "삼성전자", "code": "005930", "relation": "HBM 대장주"}}, 
        {{"name": "한미반도체", "code": "042700", "relation": "장비 납품"}}
    ]
    """
    
    res_data, error = call_gemini_dynamic(prompt)
    if res_data and 'candidates' in res_data:
        try:
            raw = res_data['candidates'][0]['content']['parts'][0]['text']
            raw = raw.replace("```json", "").replace("```", "").strip()
            stock_list = json.loads(raw)
            valid_list = []
            for item in stock_list:
                if 'name' in item and 'code' in item:
                    tag = item.get('relation', '관련주')
                    valid_list.append({"name": item['name'], "code": item['code'], "price": 0, "relation_tag": tag})
            return valid_list, f"🤖 AI가 '{keyword}' 관련주와 핵심 관계를 파악했습니다!"
        except:
            return [], "AI 응답 해석 실패"
    return [], "AI 연결 실패"

def get_naver_finance_news(code):
    titles = []
    try:
        url = f"https://finance.naver.com/item/news_news.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('.title') 
        for item in items:
            t = item.get_text().strip()
            if t: titles.append(t)
    except: pass
    return titles[:5]

def get_naver_search_news(keyword):
    titles = []
    try:
        url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(keyword)}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('.news_tit')
        for item in items:
            t = item.get_text().strip()
            if t: titles.append(t)
    except: pass
    return titles[:5]

@st.cache_data(ttl=600)
def get_news_sentiment_llm(company_name, stock_data_context=None):
    if stock_data_context is None: stock_data_context = {}
    news_titles = []; news_data = []
    
    try:
        query = f"{company_name} 주가"
        encoded_query = urllib.parse.quote(query)
        base_url = "https://news.google.com/rss/search"
        rss_url = base_url + f"?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]:
            date_str = time.strftime("%Y-%m-%d", entry.published_parsed) if entry.published_parsed else ""
            news_data.append({"title": entry.title, "link": entry.link, "date": date_str})
            news_titles.append(entry.title)
    except: pass

    code = stock_data_context.get('code', '')
    if code:
        naver_fin_titles = get_naver_finance_news(code)
        news_titles.extend(naver_fin_titles)
    
    naver_search_titles = get_naver_search_news(company_name)
    news_titles.extend(naver_search_titles)

    news_titles = list(set(news_titles))

    if not news_titles: 
        return {"score": 0, "headline": "관련 뉴스 없음", "raw_news": [], "method": "none", "catalyst": "", "opinion": "중립", "risk": "", "supply_score": 0}

    try:
        if not USER_GOOGLE_API_KEY: raise Exception("API Key가 설정되지 않았습니다.")
        
        trend = stock_data_context.get('trend', '분석중')
        cycle = stock_data_context.get('cycle', '정보없음')
        is_holding = stock_data_context.get('is_holding', False)
        profit_rate = stock_data_context.get('profit_rate', 0.0)
        quant_signal = stock_data_context.get('quant_signal', '중립')
        current_price = stock_data_context.get('current_price', 0)
        
        supply_analysis_hint = []
        
        usd_krw_change = stock_data_context.get('usd_krw_change', 0.0)
        if usd_krw_change > 0.5: supply_analysis_hint.append(f"원/달러 환율 급등(+{usd_krw_change:.2f}%)으로 인한 외국인 환차손 회피 매물 가능성")
        elif usd_krw_change < -0.5: supply_analysis_hint.append("환율 하락으로 인한 외국인 수급 개선 기대")
        
        price_surge = stock_data_context.get('price_surge', 0.0)
        if price_surge > 15: supply_analysis_hint.append(f"단기 급등(+{price_surge:.1f}%)에 따른 기관/외인의 차익 실현 욕구 증가")
        
        round_fig_msg = stock_data_context.get('round_figure_msg', "")
        if round_fig_msg: supply_analysis_hint.append(round_fig_msg)
        
        hint_str = "\n".join(supply_analysis_hint) if supply_analysis_hint else "특이사항 없음"

        if is_holding:
            role_prompt = f"""
            당신은 20년 경력의 베테랑 '헤지펀드 매니저'입니다.
            사용자는 현재 이 주식을 보유 중이며, 수익률은 {profit_rate:.2f}% 입니다.
            
            [중요 정보]
            - **현재 주가:** {current_price:,}원
            - 퀀트 알고리즘 신호: {quant_signal}
            - 수급 원인 분석 힌트: {hint_str}
            
            [지시사항]
            1. 현재 주가({current_price:,}원)를 기준으로 판단하세요. 
            2. 외국인/기관 수급의 원인을 위 '수급 원인 분석 힌트'를 참고하여 추론해 주세요. (예: 환율 상승, 차익 실현 등)
            3. 실전 대응 전략(익절/홀딩)을 제시하세요.
            """
            
            output_guideline = """
            "opinion": "🚨 홀딩 (추가 상승 기대) / 💰 부분 익절 (리스크 관리) / 🛡️ 전량 익절 (추세 꺾임) / 💧 버티기 (물타기 금지) / ✂️ 손절매",
            "summary": "수급 원인 분석과 현재 주가 위치를 종합한 구체적인 행동 가이드 (한 문장)",
            """
        else:
            role_prompt = f"""
            당신은 30년 경력의 글로벌 헤지펀드 수석 전략가입니다.
            신규 진입을 고려하는 투자자에게 매수/매도 전략을 수립하세요.
            현재 주가는 {current_price:,}원입니다.
            수급 특이사항: {hint_str}
            """
            output_guideline = """
            "opinion": "강력매수 / 매수 / 관망 / 비중축소 / 매도",
            "summary": "전문가 분석 코멘트 (핵심 요약 1문장)",
            """

        prompt = f"""
        {role_prompt}

        [분석 데이터]
        1. 기술적 추세: {trend}
        2. 시장 사이클: {cycle}
        3. 뉴스 헤드라인 (출처: Google, Naver Finance, Naver Search):
        {str(news_titles)}

        [분석 지침]
        1. 다양한 출처의 뉴스를 종합하여 '공급망 이슈', '반도체/AI 사이클', '사회적 관심도'를 파악하세요.
        2. 단순 등락보다는 기업의 **본질적인 가치 변화**에 주목하세요.
        3. 감정을 배제하고 매우 논리적이고 전문적인 어조를 사용하세요.
        4. **절대 서론이나 부가 설명 없이 오직 JSON 데이터만 출력하세요.**

        [출력 형식 (반드시 JSON 포맷 준수)]
        {{
            "score": (정수 -10 ~ 10, 뉴스 종합 점수),
            "supply_score": (정수 -5 ~ 5, 산업 사이클/공급망 영향 점수),
            {output_guideline}
            "catalyst": "주가 핵심 재료 (5단어 이내)",
            "risk": "잠재적 리스크 (1문장)"
        }}
        """
        
        res_data, error_msg = call_gemini_dynamic(prompt)
        
        if res_data and 'candidates' in res_data and res_data['candidates']:
            raw = res_data['candidates'][0]['content']['parts'][0]['text']
            
            try:
                js = json.loads(raw)
            except:
                cleaned = raw.replace("```json", "").replace("```", "").strip()
                match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                if match:
                    js = json.loads(match.group())
                else:
                    raise Exception("AI 응답에서 JSON 데이터를 추출할 수 없습니다.")

            return {
                "score": js.get('score', 0),
                "supply_score": js.get('supply_score', 0),
                "headline": js.get('summary', "분석 결과 없음"),
                "raw_news": news_data,
                "method": "ai",
                "catalyst": js.get('catalyst', ""),
                "opinion": js.get('opinion', "중립"),
                "risk": js.get('risk', "특이사항 없음")
            }
        else: raise Exception(error_msg)
        
    except Exception as e:
        score, summary, _, _ = analyze_news_by_keywords(news_titles)
        return {"score": score, "supply_score": 0, "headline": f"{summary} (AI 분석 실패: {str(e)})", "raw_news": news_data, "method": "keyword", "catalyst": "키워드", "opinion": "관망", "risk": "API 오류"}

def get_supply_demand(code):
    try:
        e = datetime.datetime.now().strftime("%Y%m%d")
        s = (datetime.datetime.now()-datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(s, e, code).tail(3)
        if df.empty: return {"f":0, "i":0}
        return {"f": int(df['외국인'].sum()), "i": int(df['기관합계'].sum())}
    except: return {"f":0, "i":0}

def round_to_tick(price):
    if price < 2000: return int(round(price, -1))
    elif price < 5000: return int(round(price / 5) * 5)
    elif price < 20000: return int(round(price, -1))
    elif price < 50000: return int(round(price / 50) * 50)
    elif price < 200000: return int(round(price, -2))
    elif price < 500000: return int(round(price / 500) * 500)
    else: return int(round(price, -3))

def analyze_pro(code, name_override=None, relation_tag=None, my_buy_price=None):
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
        "score": 50,
        "strategy": {}, 
        "fund_data": None, 
        "ma_status": [], 
        "trend_txt": "분석 중",
        "news": {"score":0, "supply_score":0, "headline":"로딩 실패", "raw_news":[], "method":"none", "opinion":"", "catalyst":"", "risk":""}, 
        "history": df, 
        "supply": {"f":0, "i":0},
        "stoch": {"k": curr.get('Stoch_K', 50), "d": curr.get('Stoch_D', 50)}, # 스토캐스틱 사용
        "vol_ratio": vol_ratio,
        "investor_trend": pd.DataFrame(),
        "fin_history": pd.DataFrame(),
        "win_rate": win_rate, 
        "cycle_txt": "확인 중", 
        "relation_tag": relation_tag,
        "my_buy_price": my_buy_price 
    }

    try:
        pass_cnt = 0
        mas = [('5일', 'MA5'), ('20일', 'MA20'), ('60일', 'MA60')]
        ma_status = []
        for label, col in mas:
            val = curr.get(col, 0)
            if curr['Close'] >= val: pass_cnt += 1; ma_status.append({"label": label, "ok": True})
            else: ma_status.append({"label": label, "ok": False})
            
        if pass_cnt >= 3: trend_txt = "강력한 상승 추세 (정배열)"
        elif pass_cnt >= 2: trend_txt = "상승세 유지 (양호)"
        else: trend_txt = "조정 또는 하락세"
        
        result_dict['ma_status'] = ma_status
        result_dict['trend_txt'] = trend_txt
        tech_score = score 
    except: tech_score = 0

    try: fund_score, _, fund_data = get_company_guide_score(code); result_dict['fund_data'] = fund_data
    except: fund_score = 0; fund_data = {}
    
    cycle_txt = get_market_cycle_status(code)
    result_dict['cycle_txt'] = cycle_txt
    if "상승세" in cycle_txt: tech_score += 10 

    try: result_dict['investor_trend'] = get_investor_trend(code)
    except: pass
    try: result_dict['fin_history'] = get_financial_history(code)
    except: pass
    try: result_dict['supply'] = get_supply_demand(code)
    except: pass

    try:
        bonus = 0
        if not result_dict['investor_trend'].empty: bonus += 5
        if not result_dict['fin_history'].empty: bonus += 5
        
        temp_score = int((tech_score * 0.5) + fund_score + bonus)
        
        atr = curr.get('ATR', curr['Close'] * 0.03)
        current_price = curr['Close']
        
        quant_signal = "중립"
        if my_buy_price:
            if profit_rate > 0:
                if temp_score >= 50: quant_signal = "보유 권장 (상승 추세)"
                else: quant_signal = "차익 실현 권장 (과열/탄력 둔화)"
            else:
                if temp_score >= 50: quant_signal = "보유 권장 (반등 기대)"
                else: quant_signal = "손절매 고려 (하락 추세)"
    except: quant_signal = "판단 불가"

    try:
        supply_txt = "특이사항 없음"
        f_net = result_dict['supply'].get('f', 0)
        i_net = result_dict['supply'].get('i', 0)
        if f_net > 0 and i_net > 0: supply_txt = "외국인/기관 양매수 유입"
        elif f_net > 0: supply_txt = "외국인 매수 우위"
        elif i_net > 0: supply_txt = "기관 매수 우위"
        elif f_net < 0 and i_net < 0: supply_txt = "외국인/기관 동반 매도"

        macro_data = get_macro_data()
        usd_change = 0.0
        if macro_data and 'USD/KRW' in macro_data:
            usd_change = macro_data['USD/KRW']['change']
            
        price_surge = 0.0
        if len(df) >= 20:
            past_price = df['Close'].iloc[-20]
            if past_price > 0:
                price_surge = (current_price - past_price) / past_price * 100
                
        round_fig_msg = ""
        str_price = str(int(current_price))
        if len(str_price) >= 4: 
            unit = 10**(len(str_price)-1) 
            next_big = (int(current_price / unit) + 1) * unit
            if (next_big - current_price) / current_price < 0.03:
                round_fig_msg = f"심리적 저항선({next_big:,}원) 접근 중"

        context = {
            "code": code,
            "trend": result_dict['trend_txt'],
            "pbr": fund_data.get('pbr', {}).get('val', 0) if fund_data else 0,
            "per": fund_data.get('per', {}).get('val', 0) if fund_data else 0,
            "supply": supply_txt,
            "cycle": cycle_txt,
            "is_holding": True if my_buy_price else False,
            "profit_rate": profit_rate,
            "quant_signal": quant_signal,
            "current_price": result_dict['price'],
            "usd_krw_change": usd_change, 
            "price_surge": price_surge, 
            "round_figure_msg": round_fig_msg 
        }
        result_dict['news'] = get_news_sentiment_llm(result_dict['name'], stock_data_context=context)
    except: pass 

    try:
        ai_news_score = result_dict['news'].get('score', 0)
        ai_cycle_score = result_dict['news'].get('supply_score', 0) * 2
        
        final_score = temp_score + ai_news_score + ai_cycle_score
        final_score = min(max(final_score, 0), 100)
        result_dict['score'] = final_score

        if my_buy_price:
            action_txt = result_dict['news'].get('opinion', quant_signal)
            stop_raw = my_buy_price * 0.95 
            target_raw = my_buy_price * 1.10
            buy_basis_txt = "보유 중"
            buy_price_raw = my_buy_price
        else:
            if final_score >= 80:
                buy_price_raw = current_price
                buy_basis_txt = "🚀 상승 기류 포착"
                stop_raw = current_price - (atr * 2) 
                target_raw = current_price + (atr * 4) 
                action_txt = f"🔥 지금이 기회! ({main_reason})"
            elif final_score >= 60:
                buy_price_raw = current_price
                buy_basis_txt = "✨ 좋은 흐름"
                ma20 = curr.get('MA20', current_price * 0.95)
                stop_raw = min(ma20, current_price - (atr * 1.5))
                target_raw = current_price + (atr * 3)
                action_txt = f"📈 매수 ({main_reason})"
            else:
                bb_lower = curr.get('BB_Lower', current_price * 0.9)
                if current_price < curr.get('MA20', current_price):
                    buy_price_raw = bb_lower
                    buy_basis_txt = "밴드 하단 대기"
                else:
                    buy_price_raw = curr.get('MA20', current_price * 0.95)
                    buy_basis_txt = "눌림목 대기"
                stop_raw = buy_price_raw * 0.95 
                target_raw = buy_price_raw * 1.10 
                action_txt = f"👀 관망 ({main_reason})"

        buy_price = round_to_tick(buy_price_raw)
        target_price = round_to_tick(target_raw)
        stop_price = round_to_tick(stop_raw)
        
        result_dict['strategy'] = {
            "buy": buy_price,
            "buy_basis": buy_basis_txt,
            "target": target_price,
            "stop": stop_price,
            "action": action_txt
        }
    except: pass

    return result_dict

def send_telegram_msg(token, chat_id, msg):
    try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": msg})
    except: pass

# --- [3. 메인 화면] ---

col_title, col_guide = st.columns([0.7, 0.3])

with col_title:
    st.title("💎 Quant Sniper V49.9 (Rescue Mode)")

with col_guide:
    st.write("") 
    st.write("") 
    with st.expander("📘 V49.9 업데이트 노트", expanded=False):
        st.markdown("""
        * **[New] 강력한 보조지표 3종 추가:** 스토캐스틱, MFI, 파라볼릭 SAR 적용
        * **[New] 구조대(Rescue) 모드:** 손실률이 10% 이상일 경우, 기준을 '평단가'에서 '현재가'로 자동 전환하여 현실적인 탈출 목표(+15%)와 추가 방어선(-5%)을 제시합니다.
        * **[UI] 3단계 상태 시각화:** 일반(Red) / 오버드라이브(Gold/Purple) / 구조대(Blue) 모드로 직관적인 상태 구분.
        """)

with st.expander("🌍 글로벌 거시 경제 & 공급망 대시보드 (Click to Open)", expanded=False):
    macro = get_macro_data()
    if macro:
        cols = st.columns(7)
        keys = ["KOSPI", "KOSDAQ", "S&P500", "USD/KRW", "US_10Y", "WTI", "구리"]
        for i, key in enumerate(keys):
            d = macro.get(key, {"val": 0.0, "change": 0.0})
            val_color = "#F04452" if d['change'] > 0 else "#3182F6"
            badge_text = "상승" if d['change'] > 0 else "하락"
            badge_style = "color:#F04452; background:#FFF1F1;" if d['change'] > 0 else "color:#3182F6; background:#E8F3FF;"
            with cols[i]:
                st.markdown(f"""<div class='metric-box'><div class='metric-title'>{key}</div><div class='metric-value' style='color:{val_color}'>{d['val']:,.2f}</div><div style='font-size:12px; color:{val_color}'>{d['change']:+.2f}%</div><div class='metric-badge' style='{badge_style}'>{badge_text}</div></div>""", unsafe_allow_html=True)
    else: st.warning("거시 경제 데이터를 불러오지 못했습니다.")

# [V49.0] 탭 분리 (Tab Separation)
tab1, tab2, tab3 = st.tabs(["🔍 테마/종목 발굴", "💰 내 잔고 (Portfolio)", "👀 관심 종목 (Watchlist)"])

# --- Tab 1: 테마 검색 (Existing) ---
with tab1:
    if st.button("🔄 화면 정리 (상세창 닫기)"):
        st.rerun()

    if st.session_state.get('preview_list'):
        st.markdown(f"### 🔍 '{st.session_state['current_theme_name']}' 주도주 심층 분석")
        
        with st.spinner("🚀 고속 AI 분석 엔진 & 백테스팅 가동 중..."):
            preview_results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(analyze_pro, item['code'], item['name'], item.get('relation_tag')) for item in st.session_state['preview_list']]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): preview_results.append(f.result())
            preview_results.sort(key=lambda x: x['score'], reverse=True)

        for res in preview_results:
            # ui.py에서 가져온 함수 사용
            st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
            
            ai_summary_txt = res['news'].get('headline', '분석 대기 중...')
            if len(ai_summary_txt) > 40: ai_summary_txt = ai_summary_txt[:40] + "..."
            opinion = res['news'].get('opinion', '')
            icon = "🔥" if "매수" in opinion or "확대" in opinion else "🤖"
            expander_label = f"{icon} AI 요약: {ai_summary_txt} (▼ 상세 분석 펼치기)"
            
            with st.expander(expander_label):
                col_add, col_info = st.columns([1, 5])
                with col_add:
                    if st.button(f"📌 관심등록", key=f"add_prev_{res['code']}"):
                        st.session_state['data_store']['watchlist'][res['name']] = {'code': res['code']}
                        if update_github_file(st.session_state['data_store']):
                            st.success("저장 완료")
                        time.sleep(0.5); st.rerun()
                col1, col2 = st.columns(2)
                with col1:
                    st.write("###### 📈 기술적 분석")
                    st.markdown(f"<div class='tech-summary'>{res['trend_txt']}</div>", unsafe_allow_html=True)
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_signal_lights(res['history'].iloc[-1]['RSI'], res['history'].iloc[-1]['MACD'], res['history'].iloc[-1]['MACD_Signal'])
                    render_ma_status(res['ma_status'])
                    st.markdown(render_chart_legend(), unsafe_allow_html=True)
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                with col2:
                    st.write("###### 🏢 재무 펀더멘탈")
                    render_fund_scorecard(res['fund_data'])
                    render_financial_table(res['fin_history'])
                st.write("###### 🧠 큰손 투자 동향")
                render_investor_chart(res['investor_trend'])
                st.write("###### 📰 AI 헤지펀드 매니저 분석")
                if res['news']['method'] == "ai": 
                    op = res['news']['opinion']; badge_cls = "ai-opinion-hold"
                    if "매수" in op or "비중확대" in op: badge_cls = "ai-opinion-buy"
                    elif "매도" in op or "비중축소" in op: badge_cls = "ai-opinion-sell"
                    st.markdown(f"""<div class='news-ai'><div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'><span class='ai-badge {badge_cls}'>{res['news']['opinion']}</span><span style='font-size:12px; color:#555;'>💡 핵심 재료: <b>{res['news']['catalyst']}</b></span></div><div style='font-size:13px; line-height:1.6; font-weight:600; color:#333; margin-bottom:8px;'>🤖 <b>Deep Analysis:</b> {res['news']['headline']}</div><div style='font-size:12px; color:#D9480F; background-color:#FFF5F5; padding:8px; border-radius:6px; border:1px solid #FFD8A8;'>⚠️ <b>Risk Factor:</b> {res['news'].get('risk', '특이사항 없음')}</div></div>""", unsafe_allow_html=True)
                else: st.markdown(f"<div class='news-fallback'><b>{res['news']['headline']}</b></div>", unsafe_allow_html=True)
                st.markdown("<div class='news-scroll-box'>", unsafe_allow_html=True)
                for news in res['news']['raw_news']:
                    st.markdown(f"<div class='news-box'><a href='{news['link']}' target='_blank' class='news-link'>📄 {news['title']}</a><span class='news-date'>{news['date']}</span></div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

# --- Tab 2: 내 잔고 (Portfolio) ---
with tab2:
    st.markdown("### 💰 내 보유 종목 (Portfolio)")
    portfolio_items = list(st.session_state['data_store']['portfolio'].items())
    
    if not portfolio_items:
        st.info("보유 중인 종목이 없습니다. 사이드바에서 추가하거나 관심 종목에서 이동해주세요.")
    else:
        with st.spinner("🚀 보유 종목 수익률 분석 중..."):
            port_results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for name, info in portfolio_items:
                    try:
                        safe_buy_price = float(info.get('buy_price', 0))
                    except:
                        safe_buy_price = 0.0
                    futures.append(executor.submit(analyze_pro, info['code'], name, None, safe_buy_price))

                for f in concurrent.futures.as_completed(futures):
                    if f.result(): port_results.append(f.result())
            
        for res in port_results:
            st.markdown(create_portfolio_card_html(res), unsafe_allow_html=True)
            
            with st.expander(f"📊 {res['name']} 상세 분석 펼치기"):
                col_btn, col_rest = st.columns([0.2, 0.8])
                with col_btn:
                    if st.button(f"🗑️ 삭제", key=f"del_port_{res['code']}"):
                        del st.session_state['data_store']['portfolio'][res['name']]
                        update_github_file(st.session_state['data_store'])
                        st.rerun()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("###### 📈 기술적 분석")
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    st.markdown(render_chart_legend(), unsafe_allow_html=True)
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                with col2:
                    st.write("###### 🧠 수급 동향")
                    render_investor_chart(res['investor_trend'])
                
                st.markdown("---")
                st.write("###### 🤖 AI 포트폴리오 매니저의 조언")
                
                if res['news']['method'] == "ai":
                    op = res['news']['opinion']; badge_cls = "ai-opinion-hold"
                    
                    if "익절" in op or "손절" in op: badge_cls = "ai-opinion-sell" 
                    elif "홀딩" in op or "버티기" in op or "매수" in op: badge_cls = "ai-opinion-buy"
                    
                    st.markdown(f"""
                    <div class='news-ai'>
                        <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'>
                            <span class='ai-badge {badge_cls}'>{res['news']['opinion']}</span>
                            <span style='font-size:12px; color:#555;'>💡 핵심 재료: <b>{res['news']['catalyst']}</b></span>
                        </div>
                        <div style='font-size:14px; line-height:1.6; font-weight:600; color:#191F28; margin-bottom:8px;'>
                            🗣️ <b>Manager's Comment:</b><br>{res['news']['headline']}
                        </div>
                        <div style='font-size:12px; color:#D9480F; background-color:#FFF5F5; padding:8px; border-radius:6px; border:1px solid #FFD8A8;'>
                            ⚠️ <b>Risk Factor:</b> {res['news'].get('risk', '특이사항 없음')}
                        </div>
                    </div>""", unsafe_allow_html=True)
                else:
                    fallback_headline = res['news'].get('headline', '분석 결과 없음')
                    fallback_risk = res['news'].get('risk', 'API 키 확인 또는 뉴스 데이터 부족')
                    
                    st.markdown(f"""
                    <div class='news-fallback'>
                        <div style='font-size:12px; color:#D9480F; margin-bottom:4px;'>⚡ 키워드 분석 모드 (AI 미연동)</div>
                        <div style='font-size:14px; font-weight:700; color:#333; margin-bottom:6px;'>{fallback_headline}</div>
                        <div style='font-size:11px; color:#666;'>※ {fallback_risk}</div>
                    </div>
                    """, unsafe_allow_html=True)

                if res['news'].get('raw_news'):
                    st.markdown("<div class='news-scroll-box'>", unsafe_allow_html=True)
                    for news in res['news']['raw_news']:
                        st.markdown(f"<div class='news-box'><a href='{news['link']}' target='_blank' class='news-link'>📄 {news['title']}</a><span class='news-date'>{news['date']}</span></div>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

# --- Tab 3: 관심 종목 (Watchlist) ---
with tab3:
    st.markdown("### 👀 관심 종목 (Watchlist)")
    watchlist_items = list(st.session_state['data_store']['watchlist'].items())
    
    if not watchlist_items:
        st.info("관심 종목이 없습니다.")
    else:
        with st.spinner("🚀 관심 종목 분석 중..."):
            wl_results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(analyze_pro, info['code'], name) for name, info in watchlist_items]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): wl_results.append(f.result())
            wl_results.sort(key=lambda x: x['score'], reverse=True)
        
        for res in wl_results:
            st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
            
            ai_summary_txt = res['news'].get('headline', '분석 대기 중...')
            if len(ai_summary_txt) > 40: ai_summary_txt = ai_summary_txt[:40] + "..."
            opinion = res['news'].get('opinion', '')
            icon = "🔥" if "매수" in opinion or "확대" in opinion else "🤖"
            expander_label = f"{icon} AI 요약: {ai_summary_txt} (▼ 상세 분석 펼치기)"
            
            with st.expander(expander_label):
                
                # [V49.1] 매수 체결 및 이동 섹션
                st.markdown("---")
                st.write("### 🛒 매수 체결 하셨나요?")
                c1, c2 = st.columns([0.4, 0.6])
                with c1:
                    input_price = st.number_input("매수 단가 (평단)", value=res['price'], step=100, key=f"bp_{res['code']}")
                with c2:
                    st.write("") 
                    st.write("")
                    if st.button("📥 내 잔고로 이동", key=f"move_{res['code']}"):
                        # 1. Add to Portfolio
                        st.session_state['data_store']['portfolio'][res['name']] = {
                            "code": res['code'],
                            "buy_price": input_price
                        }
                        # 2. Remove from Watchlist
                        if res['name'] in st.session_state['data_store']['watchlist']:
                            del st.session_state['data_store']['watchlist'][res['name']]

                        # 3. Save & Rerun
                        if update_github_file(st.session_state['data_store']):
                            st.success(f"✅ {res['name']} 매수 등록 완료! (잔고 탭으로 이동됨)")
                            time.sleep(1.0)
                            st.rerun()

                col_btn, col_rest = st.columns([0.2, 0.8])
                with col_btn:
                    if st.button(f"🗑️ 삭제", key=f"del_wl_{res['code']}"):
                        del st.session_state['data_store']['watchlist'][res['name']]
                        update_github_file(st.session_state['data_store'])
                        st.rerun()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("###### 📈 기술적 분석")
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_signal_lights(res['history'].iloc[-1]['RSI'], res['history'].iloc[-1]['MACD'], res['history'].iloc[-1]['MACD_Signal'])
                    render_ma_status(res['ma_status'])
                    st.markdown(render_chart_legend(), unsafe_allow_html=True)
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                with col2:
                    st.write("###### 🏢 재무 펀더멘탈")
                    render_fund_scorecard(res['fund_data'])
                    render_financial_table(res['fin_history'])
                st.write("###### 🧠 수급 동향")
                render_investor_chart(res['investor_trend'])
                st.write("###### 📰 AI 분석")
                if res['news']['method'] == "ai": 
                    op = res['news']['opinion']; badge_cls = "ai-opinion-hold"
                    if "매수" in op or "비중확대" in op: badge_cls = "ai-opinion-buy"
                    elif "매도" in op or "비중축소" in op: badge_cls = "ai-opinion-sell"
                    st.markdown(f"""<div class='news-ai'><div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;'><span class='ai-badge {badge_cls}'>{res['news']['opinion']}</span><span style='font-size:12px; color:#555;'>💡 핵심 재료: <b>{res['news']['catalyst']}</b></span></div><div style='font-size:13px; line-height:1.6; font-weight:600; color:#333; margin-bottom:8px;'>🤖 <b>Deep Analysis:</b> {res['news']['headline']}</div></div>""", unsafe_allow_html=True)
                else: st.markdown(f"<div class='news-fallback'><b>{res['news']['headline']}</b></div>", unsafe_allow_html=True)

with st.sidebar:
    st.write("### ⚙️ 기능 메뉴")
    with st.expander("🔍 지능형 테마/주도주 찾기", expanded=True):
        THEME_KEYWORDS = { "직접 입력": None, "반도체": "반도체", "2차전지": "2차전지", "HBM": "HBM", "AI/인공지능": "지능형로봇", "로봇": "로봇", "제약바이오": "제약업체", "자동차/부품": "자동차", "방위산업": "방위산업", "원자력발전": "원자력발전", "초전도체": "초전도체", "저PBR": "은행" }
        selected_preset = st.selectbox("⚡ 인기 테마 선택", list(THEME_KEYWORDS.keys()))
        
        with st.form(key="search_form"):
            user_input = ""
            if selected_preset == "직접 입력": 
                user_input = st.text_input("검색할 테마/종목명/키워드", placeholder="예: 비만치료제, 저출산, 초전도체")
            else: st.info(f"✅ 선택된 테마: **{THEME_KEYWORDS[selected_preset]}**")
            submit_btn = st.form_submit_button("지능형 분석 시작")
        
        if submit_btn:
            if selected_preset == "직접 입력": target_keyword = user_input.strip()
            else: target_keyword = THEME_KEYWORDS[selected_preset]
            
            if not target_keyword: st.warning("검색어를 입력하세요!")
            else:
                if krx_df.empty:
                    with st.spinner("종목 리스트 업데이트..."): krx_df = get_krx_list_safe() 

                is_stock_found = False; target_code = None
                
                if target_keyword.isdigit() and not krx_df.empty:
                    if target_keyword in krx_df['Code'].values:
                        target_code = target_keyword
                        try: target_keyword = krx_df[krx_df['Code'] == target_code].iloc[0]['Name']
                        except: pass
                elif not krx_df.empty and target_keyword in krx_df['Name'].values:
                    try: target_code = krx_df[krx_df['Name'] == target_keyword].iloc[0]['Code']
                    except: pass

                if target_code:
                    try:
                        st.info(f"🔎 '{target_keyword}' 분석 중...")
                        res = analyze_pro(target_code, target_keyword)
                        if res:
                            st.session_state['preview_list'] = [res]
                            st.session_state['current_theme_name'] = f"개별 종목: {target_keyword}"
                            is_stock_found = True; st.rerun()
                    except Exception as e: st.error(f"오류: {str(e)}")

                if not is_stock_found:
                    try:
                        with st.spinner(f"🤖 AI가 '{target_keyword}' 관련주를 생각 중입니다..."):
                            ai_stocks, msg = get_ai_recommended_stocks(target_keyword)
                            if ai_stocks:
                                st.success(msg)
                                st.session_state['preview_list'] = ai_stocks
                                st.session_state['current_theme_name'] = f"AI 추천: {target_keyword}"
                                st.rerun()
                            else:
                                with st.spinner("네이버 금융 테마 스캔 (Fallback)..."):
                                    raw_stocks, msg = get_naver_theme_stocks(target_keyword)
                                if raw_stocks:
                                    st.success(msg)
                                    st.session_state['preview_list'] = raw_stocks
                                    st.session_state['current_theme_name'] = target_keyword
                                    st.rerun()
                                else: st.error(f"❌ '{target_keyword}'에 대한 결과를 찾을 수 없습니다.")
                    except Exception as e: st.error(f"오류: {str(e)}")

    if st.button("🚀 텔레그램 리포트 전송"):
        token = USER_TELEGRAM_TOKEN
        chat_id = USER_CHAT_ID
        if token and chat_id and 'wl_results' in locals() and wl_results:
            msg = f"💎 Quant Sniper V49.9 (Rescue Mode)\n\n"
            if macro: msg += f"[시장] KOSPI {macro.get('KOSPI',{'val':0})['val']:.0f}\n\n"
            for i, r in enumerate(wl_results[:3]): 
                rel_txt = f"[{r.get('relation_tag', '')}] " if r.get('relation_tag') else ""
                msg += f"{i+1}. {r['name']} {rel_txt}({r['score']}점)\n   가격: {r['price']:,}원\n   목표: {r['strategy']['target']:,}\n   손절: {r['strategy']['stop']:,}\n   요약: {r['news']['headline'][:50]}...\n\n"
            send_telegram_msg(token, chat_id, msg)
            st.success("전송 완료!")
        else: st.warning("설정 확인 필요")

    with st.expander("개별 종목 추가"):
        name = st.text_input("이름"); code = st.text_input("코드")
        is_hold = st.checkbox("💰 보유 중인 종목인가요?")
        buy_price = 0
        if is_hold:
            buy_price = st.number_input("평단가 (매수 가격)", min_value=0, step=100)
            
        if st.button("추가") and name and code:
            if is_hold:
                st.session_state['data_store']['portfolio'][name] = {"code": code, "buy_price": buy_price}
            else:
                st.session_state['data_store']['watchlist'][name] = {"code": code}
                
            if update_github_file(st.session_state['data_store']):
                st.success("✅ 저장 완료!")
            else:
                st.error("❌ 저장 실패")
            time.sleep(0.5); st.rerun()
            
    if st.button("초기화"): 
        st.session_state['data_store'] = {"portfolio": {}, "watchlist": {}}
        st.session_state['preview_list'] = []
        st.rerun()
