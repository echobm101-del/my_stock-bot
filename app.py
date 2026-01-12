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
st.set_page_config(page_title="Quant Sniper V49.9.7 (Complete UI)", page_icon="💎", layout="wide")
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
            "message": "Update data via Streamlit App (V49.9.7)",
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
# [보조지표 3대장 탑재: 스토캐스틱 / MFI / 파라볼릭 SAR]
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
        fast_k = ((close - low.rolling(n).min()) / (high.rolling(n).max() - low.rolling(n).min())) * 100
        slow_k = fast_k.rolling(m).mean()
        slow_d = slow_k.rolling(t).mean()
        return slow_k, slow_d
    except:
        return pd.Series(0), pd.Series(0)

def calculate_mfi(data, period=14):
    """MFI (Money Flow Index) - 자금 흐름 지수"""
    try:
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        money_flow = typical_price * data['Volume']
        positive_flow = [0]; negative_flow = [0]
        delta = typical_price.diff()
        pos_mf = pd.Series(0.0, index=data.index)
        neg_mf = pd.Series(0.0, index=data.index)
        pos_mf[delta > 0] = money_flow[delta > 0]
        neg_mf[delta < 0] = money_flow[delta < 0]
        pos_mf_sum = pos_mf.rolling(window=period).sum()
        neg_mf_sum = neg_mf.rolling(window=period).sum()
        mfi = 100 - (100 / (1 + (pos_mf_sum / neg_mf_sum)))
        return mfi.fillna(50)
    except: return pd.Series(50, index=data.index)

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
        sar[0] = low[0]; trend[0] = 1
        ep = high[0]; af = af_start
        for i in range(1, length):
            prev_sar = sar[i-1]; prev_trend = trend[i-1]
            new_sar = prev_sar + af * (ep - prev_sar)
            if prev_trend == 1: 
                if low[i] < new_sar: 
                    trend[i] = -1; sar[i] = ep; ep = low[i]; af = af_start
                else:
                    trend[i] = 1; sar[i] = new_sar
                    if high[i] > ep: ep = high[i]; af = min(af + af_step, af_max)
            else: 
                if high[i] > new_sar: 
                    trend[i] = 1; sar[i] = ep; ep = high[i]; af = af_start
                else:
                    trend[i] = -1; sar[i] = new_sar
                    if low[i] < ep: ep = low[i]; af = min(af + af_step, af_max)
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
                buy_price = sim_df.loc[date, 'Close']
                max_price = future['High'].max()
                if max_price >= buy_price * 1.03: wins += 1
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
# [분석 엔진 - 기술적 지표 계산]
# -----------------------------------------------------------
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

        # [신규 지표 3종]
        df['Stoch_K'], df['Stoch_D'] = calculate_stochastic(df)
        df['MFI'] = calculate_mfi(df)
        df['SAR'], df['SAR_Trend'] = calculate_sar(df) 
        
        curr = df.iloc[-1]; prev = df.iloc[-2]
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
        score = 0; tags = []
        vol_ratio = curr['Volume'] / vol_avg if vol_avg > 0 else 0
        price_chg = (curr['Close'] - prev['Close']) / prev['Close'] * 100
        is_bullish = curr['Close'] >= curr['Open']
        main_reason = "관망 필요"

        # 1. 거래량 (MFI 강화)
        if curr['MFI'] > 80: score += 10; tags.append("🔥 자금유입(MFI)")
        elif curr['MFI'] < 20: score += 10; tags.append("💧 바닥다지기(MFI)")

        if vol_ratio >= 3.0: 
            if price_chg > 0 or is_bullish:
                score += 30; tags.append("💥 거래량폭발"); main_reason = "거래량 실린 장대양봉"
            else:
                score -= 50; tags.append("😱 투매폭탄(위험)"); main_reason = "세력 이탈 경고"
        elif vol_ratio >= 1.5:
            if price_chg > 0 or is_bullish: score += 10; tags.append("📈 거래량증가")

        # 2. 추세 (SAR 적용)
        if curr['SAR_Trend'] == 1:
            score += 20; tags.append("📈 추세전환(SAR)")
            if main_reason == "관망 필요": main_reason = "파라볼릭 상승 추세"
        else: score -= 10

        if curr['Close'] > curr['MA20']: score += 10
        if curr['MACD'] > curr['MACD_Signal']: score += 10; tags.append("🌊 MACD상승")

        # 3. 모멘텀 (스토캐스틱 + RSI)
        if prev['Stoch_K'] < prev['Stoch_D'] and curr['Stoch_K'] > curr['Stoch_D']:
             if curr['Stoch_K'] < 40:
                 score += 30; tags.append("⚡ 스토캐스틱GC"); main_reason = "저점 매수 골든크로스"
             else: score += 10

        if curr['RSI'] < 30: 
            score += 10; tags.append("💎 RSI과매도")
            if main_reason == "관망 필요": main_reason = "바닥 잡을 찬스"

        win_rate = backtest_strategy(df)
        if win_rate >= 70: score += 10; tags.append(f"👑 승률{win_rate}%")

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
            per = get_val_by_id("_per"); pbr = get_val_by_id("_pbr"); div = get_val_by_id("_dvr")
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
    score = 0; found_keywords = []
    for title in news_titles:
        for w in pos_words:
            if w in title: score += 1; found_keywords.append(w)
        for w in neg_words:
            if w in title: score -= 1; found_keywords.append(w)
            
    final_score = min(max(score, -10), 10)
    summary = f"긍정 키워드 {len([w for w in found_keywords if w in pos_words])}개, 부정 키워드 {len([w for w in found_keywords if w in neg_words])}개 감지."
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
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.0}}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code == 200: return res.json(), None
        elif res.status_code == 429: time.sleep(1); return None, "Rate Limit"
        else: return None, f"HTTP {res.status_code}: {res.text}"
    except Exception as e: return None, f"Connection Error: {str(e)}"

def get_ai_recommended_stocks(keyword):
    prompt = f"""
    당신은 한국 주식 전문가입니다. '{keyword}'와 가장 관련성 높은 한국 상장 주식 5개를 JSON으로 추천해주세요.
    [출력 예시] [{{"name": "삼성전자", "code": "005930", "relation": "HBM 대장주"}}]
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
            return valid_list, f"🤖 AI가 '{keyword}' 관련주를 찾았습니다!"
        except: return [], "AI 응답 해석 실패"
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

# [핵심 변경] 엄격한 필터링(Strict Filter) 적용
def get_news_sentiment_llm(company_name, stock_data_context=None):
    if stock_data_context is None: stock_data_context = {}
    news_titles = []
    news_data = [] 
    
    # 1. 뉴스 수집 (구글: 2개월 이내 시도)
    try:
        query = f"{company_name} 주가"
        encoded_query = urllib.parse.quote(query)
        base_url = "https://news.google.com/rss/search"
        # when:2m = 최근 2개월 검색 연산자
        rss_url = base_url + f"?q={encoded_query}+when:2m&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]:
            date_str = time.strftime("%Y-%m-%d", entry.published_parsed) if entry.published_parsed else "날짜없음"
            news_data.append({"title": entry.title, "link": entry.link, "date": date_str})
            news_titles.append(f"[{date_str}] {entry.title}")
    except: pass

    # 2. 네이버 금융 뉴스
    code = stock_data_context.get('code', '')
    if code:
        naver_fin_titles = get_naver_finance_news(code)
        for t in naver_fin_titles: 
             if len(news_data) < 10: 
                 news_data.append({"title": t, "link": "#", "date": "NAVER_FIN"})
                 news_titles.append(f"[날짜확인필요] {t}")

    news_titles = list(set(news_titles))

    if not news_titles: 
        return {"score": 0, "headline": "최근 2개월 내 관련 뉴스 없음", "raw_news": [], "method": "none", "catalyst": "", "opinion": "중립", "risk": "", "supply_score": 0}

    try:
        if not USER_GOOGLE_API_KEY: raise Exception("API Key Missing")
        
        # [AI 필터링 로직]
        trend = stock_data_context.get('trend', '분석중')
        cycle = stock_data_context.get('cycle', '정보없음')
        is_holding = stock_data_context.get('is_holding', False)
        profit_rate = stock_data_context.get('profit_rate', 0.0)
        current_price = stock_data_context.get('current_price', 0)
        
        today = datetime.datetime.now().strftime("%Y년 %m월 %d일")

        role_prompt = "당신은 데이터 정합성을 최우선으로 하는 펀드매니저입니다."
        if is_holding:
            role_prompt += f" 현재 {profit_rate:.2f}% 수익 중인 보유자에게 조언하세요."
        else:
            role_prompt += " 신규 진입 대기자에게 조언하세요."

        prompt = f"""
        {role_prompt}
        [기준 데이터]
        - 분석 시점: {today}
        - 종목: {company_name}
        - **현재가: {current_price:,}원** (절대적 기준값)
        - 기술적 추세: {trend}

        [수집된 뉴스 후보군]
        {str(news_titles)}

        [🚨 필수 필터링 지침 (Filtering Rules)]
        1. **유효기간(Time Limit):** 위 '분석 시점({today})'을 기준으로 **2개월 이상 지난 뉴스**는 분석에서 즉시 **폐기(Discard)**하세요.
        2. **정합성 체크(Reality Check):** 뉴스 내용이 '현재가({current_price:,}원)' 및 '현재 추세'와 정반대이거나 괴리가 심하다면(예: 현재가는 신고가인데 뉴스는 폭락 언급) **오래된 뉴스**로 간주하고 **폐기**하세요.
        3. **결과 도출:** 위 1, 2번 과정에서 살아남은 뉴스만으로 분석하세요.
           - 만약 모든 뉴스가 폐기되었다면, 솔직하게 **"최근 유효한 뉴스가 없습니다."**라고 말하고 **오직 차트(기술적 추세)에 근거해서만** 조언을 작성하세요.

        위 지침을 준수하여 JSON으로 답하세요.
        {{
            "headline": "분석 요약 (유효 뉴스 없으면 '기술적 지표 분석' 위주 작성)",
            "catalyst": "재료 (없으면 '식별 불가')",
            "risk": "리스크 (없으면 '기술적 조정 가능성' 등)",
            "opinion": "매수/홀딩/관망/매도 중 택1",
            "score": (-10 ~ 10 사이 점수, 뉴스 없으면 0점)
        }}
        """
        
        res_data, error_msg = call_gemini_dynamic(prompt)
        if res_data and 'candidates' in res_data:
            raw = res_data['candidates'][0]['content']['parts'][0]['text']
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                js = json.loads(match.group())
                js['raw_news'] = news_data
                js['method'] = "ai"
                return js
            else: raise Exception("JSON Parsing Fail")
        else: raise Exception(error_msg)
        
    except Exception as e:
        score, summary, _, _ = analyze_news_by_keywords(news_titles)
        return {"score": score, "headline": summary, "raw_news": news_data, "method": "keyword", "catalyst": "키워드", "opinion": "관망", "risk": "API 오류"}

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

# [분석 데이터 통합 - 저장된 AI 데이터 활용]
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
        "score": 50,
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

    # [저장된 AI 데이터 불러오기]
    if stored_data and 'ai_analysis' in stored_data:
        result_dict['news'] = stored_data['ai_analysis']

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
        ai_news_score = result_dict['news'].get('score', 0)
        final_score = temp_score + ai_news_score
        final_score = min(max(final_score, 0), 100)
        result_dict['score'] = final_score

        # 전략 수립
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
    st.title("💎 Quant Sniper V49.9.7 (Complete UI)")
with col_guide:
    st.write("") 
    st.write("") 
    with st.expander("📘 업데이트 노트", expanded=False):
        st.markdown("""
        * **[Safety] 뉴스 필터링:** 2개월 이상 된 뉴스나 현재 주가와 괴리가 큰 정보는 AI가 자동으로 무시합니다.
        * **[UI]** 투자자별 매매동향 및 범례 위치 최적화 완료.
        """)

with st.expander("🌍 글로벌 거시 경제 대시보드", expanded=False):
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

tab1, tab2, tab3 = st.tabs(["🔍 테마/종목 발굴", "💰 내 잔고 (Portfolio)", "👀 관심 종목 (Watchlist)"])

# --- Tab 1: 테마 검색 ---
with tab1:
    if st.button("🔄 화면 정리"): st.rerun()

    if st.session_state.get('preview_list'):
        st.markdown(f"### 🔍 '{st.session_state['current_theme_name']}' 분석 결과")
        with st.spinner("🚀 기술적 분석 엔진 가동 중..."):
            preview_results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                # 미리보기는 저장이 안된 상태이므로 stored_data=None
                futures = [executor.submit(analyze_pro, item['code'], item['name'], item.get('relation_tag')) for item in st.session_state['preview_list']]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): preview_results.append(f.result())
            preview_results.sort(key=lambda x: x['score'], reverse=True)

        for res in preview_results:
            st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
            
            with st.expander(f"🤖 AI 심층 분석 & 상세 차트 확인"):
                col_chart, col_ai = st.columns([1, 1])
                
                with col_chart:
                    st.write("###### 📈 기술적 지표")
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                    st.markdown(render_chart_legend(), unsafe_allow_html=True) # [위치 수정] 범례를 차트 바로 아래로
                    
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_signal_lights(res['history'].iloc[-1]['RSI'], res['history'].iloc[-1]['MACD'], res['history'].iloc[-1]['MACD_Signal'])
                    render_ma_status(res['ma_status'])
                    
                    st.write("###### 🧠 수급 동향 (투자자별)") # [복구] 수급 차트 추가
                    render_investor_chart(res['investor_trend'])
                
                with col_ai:
                    st.write("###### 🏢 재무 & AI")
                    render_fund_scorecard(res['fund_data'])
                    if st.button(f"✨ AI 분석 실행 (1 Credit)", key=f"ai_prev_{res['code']}"):
                        with st.spinner("AI 매니저가 분석 중입니다..."):
                            context = {"code": res['code'], "trend": res['trend_txt'], "current_price": res['price']}
                            ai_result = get_news_sentiment_llm(res['name'], context)
                            
                            st.markdown(f"**{ai_result.get('headline')}**")
                            st.caption(f"의견: {ai_result.get('opinion')}")
                    else:
                        st.info("버튼을 누르면 AI 분석이 실행됩니다.")

                if st.button(f"📌 관심등록", key=f"add_prev_{res['code']}"):
                    st.session_state['data_store']['watchlist'][res['name']] = {'code': res['code']}
                    update_github_file(st.session_state['data_store'])
                    st.success("저장 완료")
                    time.sleep(0.5); st.rerun()

# --- Tab 2: 내 잔고 (Portfolio) ---
with tab2:
    st.markdown("### 💰 내 보유 종목 (Portfolio)")
    portfolio_items = list(st.session_state['data_store']['portfolio'].items())
    
    if not portfolio_items:
        st.info("보유 중인 종목이 없습니다.")
    else:
        port_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for name, info in portfolio_items:
                safe_buy_price = float(info.get('buy_price', 0))
                futures.append(executor.submit(analyze_pro, info['code'], name, None, safe_buy_price, info))
            for f in concurrent.futures.as_completed(futures):
                if f.result(): port_results.append(f.result())
        
        for res in port_results:
            st.markdown(create_portfolio_card_html(res), unsafe_allow_html=True)
            
            with st.expander(f"📊 {res['name']} 상세 분석 및 AI 조언"):
                c1, c2 = st.columns([0.6, 0.4])
                
                with c1:
                    st.write("###### 📈 차트 & 보조지표")
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                    st.markdown(render_chart_legend(), unsafe_allow_html=True) # [위치 수정]
                    
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_signal_lights(res['history'].iloc[-1]['RSI'], res['history'].iloc[-1]['MACD'], res['history'].iloc[-1]['MACD_Signal'])
                    render_ma_status(res['ma_status'])
                    
                    st.write("###### 🧠 수급 동향 (투자자별)") # [복구]
                    render_investor_chart(res['investor_trend'])

                with c2:
                    st.write("###### 🤖 AI 매니저 조언")
                    
                    ai_data = res['news']
                    has_ai_result = ai_data.get('method') == 'ai'
                    
                    if has_ai_result:
                        last_time = ai_data.get('timestamp', '알수없음')
                        st.caption(f"🕒 분석 시각: {last_time}")
                        
                        op = ai_data.get('opinion', '')
                        badge_cls = "ai-opinion-hold"
                        if "매수" in op: badge_cls = "ai-opinion-buy"
                        elif "매도" in op: badge_cls = "ai-opinion-sell"
                        
                        st.markdown(f"""
                        <div class='news-ai'>
                            <span class='ai-badge {badge_cls}'>{op}</span>
                            <div style='margin-top:5px; font-weight:bold;'>{ai_data.get('headline')}</div>
                            <div style='font-size:12px; margin-top:5px;'>⚠️ 리스크: {ai_data.get('risk')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button("🔄 업데이트 (재분석)", key=f"re_ai_port_{res['code']}"):
                            with st.spinner("재분석 중..."):
                                context = {"code": res['code'], "trend": res['trend_txt'], "current_price": res['price'], "is_holding": True, "profit_rate": res.get('profit_rate', 0)}
                                new_ai = get_news_sentiment_llm(res['name'], context)
                                new_ai['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                
                                st.session_state['data_store']['portfolio'][res['name']]['ai_analysis'] = new_ai
                                update_github_file(st.session_state['data_store'])
                                st.rerun()
                    else:
                        st.info("아직 AI 분석 기록이 없습니다.")
                        if st.button("✨ AI 심층 분석 실행", key=f"new_ai_port_{res['code']}"):
                            with st.spinner("분석 중..."):
                                context = {"code": res['code'], "trend": res['trend_txt'], "current_price": res['price'], "is_holding": True, "profit_rate": res.get('profit_rate', 0)}
                                new_ai = get_news_sentiment_llm(res['name'], context)
                                new_ai['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                
                                st.session_state['data_store']['portfolio'][res['name']]['ai_analysis'] = new_ai
                                update_github_file(st.session_state['data_store'])
                                st.rerun()

                if st.button(f"🗑️ 포트폴리오 삭제", key=f"del_port_{res['code']}"):
                    del st.session_state['data_store']['portfolio'][res['name']]
                    update_github_file(st.session_state['data_store'])
                    st.rerun()

# --- Tab 3: 관심 종목 (Watchlist) ---
with tab3:
    st.markdown("### 👀 관심 종목 (Watchlist)")
    watchlist_items = list(st.session_state['data_store']['watchlist'].items())
    
    if not watchlist_items:
        st.info("관심 종목이 없습니다.")
    else:
        wl_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for name, info in watchlist_items:
                futures.append(executor.submit(analyze_pro, info['code'], name, None, None, info))
            for f in concurrent.futures.as_completed(futures):
                if f.result(): wl_results.append(f.result())
        wl_results.sort(key=lambda x: x['score'], reverse=True)
        
        for res in wl_results:
            st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
            
            with st.expander(f"🤖 AI 분석 및 매수/삭제"):
                c1, c2 = st.columns([0.6, 0.4])
                
                with c1:
                    st.write("###### 📈 기술적 지표")
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                    st.markdown(render_chart_legend(), unsafe_allow_html=True) # [위치 수정]
                    
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_signal_lights(res['history'].iloc[-1]['RSI'], res['history'].iloc[-1]['MACD'], res['history'].iloc[-1]['MACD_Signal'])
                    render_ma_status(res['ma_status'])
                    
                    st.write("###### 🧠 수급 동향 (투자자별)") # [복구]
                    render_investor_chart(res['investor_trend'])
                
                with c2:
                    ai_data = res['news']
                    has_ai_result = ai_data.get('method') == 'ai'
                    
                    if has_ai_result:
                        last_time = ai_data.get('timestamp', '알수없음')
                        st.caption(f"🕒 {last_time}")
                        st.markdown(f"**{ai_data.get('headline')}**")
                        st.caption(f"의견: {ai_data.get('opinion')}")
                        
                        if st.button("🔄 재분석", key=f"re_ai_wl_{res['code']}"):
                            with st.spinner("..."):
                                context = {"code": res['code'], "trend": res['trend_txt'], "current_price": res['price']}
                                new_ai = get_news_sentiment_llm(res['name'], context)
                                new_ai['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                st.session_state['data_store']['watchlist'][res['name']]['ai_analysis'] = new_ai
                                update_github_file(st.session_state['data_store'])
                                st.rerun()
                    else:
                        st.info("AI 분석 데이터 없음")
                        if st.button("✨ 분석 실행", key=f"new_ai_wl_{res['code']}"):
                            with st.spinner("..."):
                                context = {"code": res['code'], "trend": res['trend_txt'], "current_price": res['price']}
                                new_ai = get_news_sentiment_llm(res['name'], context)
                                new_ai['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                st.session_state['data_store']['watchlist'][res['name']]['ai_analysis'] = new_ai
                                update_github_file(st.session_state['data_store'])
                                st.rerun()

                st.markdown("---")
                input_price = st.number_input("매수 단가", value=res['price'], step=100, key=f"bp_{res['code']}")
                if st.button("📥 내 잔고로 이동", key=f"move_{res['code']}"):
                    st.session_state['data_store']['portfolio'][res['name']] = {
                        "code": res['code'],
                        "buy_price": input_price,
                        "ai_analysis": res['news'] 
                    }
                    if res['name'] in st.session_state['data_store']['watchlist']:
                        del st.session_state['data_store']['watchlist'][res['name']]
                    update_github_file(st.session_state['data_store'])
                    st.success("이동 완료!")
                    st.rerun()
                
                if st.button(f"🗑️ 삭제", key=f"del_wl_{res['code']}"):
                    del st.session_state['data_store']['watchlist'][res['name']]
                    update_github_file(st.session_state['data_store'])
                    st.rerun()

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
            msg = f"💎 Quant Sniper V49.9.7\n\n"
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
        if is_hold: buy_price = st.number_input("평단가 (매수 가격)", min_value=0, step=100)
            
        if st.button("추가") and name and code:
            new_item = {"code": code}
            if is_hold:
                new_item["buy_price"] = buy_price
                st.session_state['data_store']['portfolio'][name] = new_item
            else:
                st.session_state['data_store']['watchlist'][name] = new_item
            update_github_file(st.session_state['data_store'])
            st.success("✅ 저장 완료!"); time.sleep(0.5); st.rerun()
            
    if st.button("초기화"): 
        st.session_state['data_store'] = {"portfolio": {}, "watchlist": {}}
        st.session_state['preview_list'] = []
        st.rerun()
