import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
import json
import time
import urllib.parse
from bs4 import BeautifulSoup
from pykrx import stock
from io import StringIO
import feedparser
import OpenDartReader
import yfinance as yf

# 우리가 만든 모듈 불러오기
import config
import utils

# --- 데이터 수집 함수들 ---

@st.cache_data
def get_krx_list_safe():
    try:
        df_kospi = fdr.StockListing('KOSPI')
        df_kosdaq = fdr.StockListing('KOSDAQ')
        return pd.concat([df_kospi, df_kosdaq])
    except: return pd.DataFrame()

def get_market_cycle_status(code):
    try:
        kospi = fdr.DataReader('KS11', datetime.datetime.now()-datetime.timedelta(days=400))
        ma120 = kospi['Close'].rolling(120).mean().iloc[-1]
        if kospi['Close'].iloc[-1] > ma120: return "📈 시장 상승세"
        else: return "📉 시장 하락세"
    except: return "시장 분석 중"

@st.cache_data(ttl=3600)
def get_investor_trend(code):
    try:
        end = datetime.datetime.now().strftime("%Y%m%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=60)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(start, end, code)
        if df.empty: return pd.DataFrame()
        
        df['Cum_Individual'] = df['개인'].cumsum()
        df['Cum_Foreigner'] = df['외국인'].cumsum()
        df['Cum_Institution'] = df['기관합계'].cumsum()
        return df
    except: return pd.DataFrame()

def get_supply_demand(code):
    try:
        end = datetime.datetime.now().strftime("%Y%m%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(start, end, code)
        if df.empty: return {"f":0, "i":0}
        return {"f": int(df['외국인'].sum()), "i": int(df['기관합계'].sum())}
    except: return {"f":0, "i":0}

@st.cache_data(ttl=3600)
def get_financial_history(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        dfs = pd.read_html(StringIO(res.text), encoding='euc-kr')
        for df in dfs:
            if '최근 연간 실적' in str(df.columns) or '매출액' in str(df.iloc[:,0].values):
                df = df.set_index(df.columns[0])
                fin_data = []
                cols = df.columns[-5:-1] # 최근 4분기
                for col in cols:
                    try:
                        fin_data.append({
                            "Date": str(col[1]),
                            "매출액": float(df.loc['매출액', col]),
                            "영업이익": float(df.loc['영업이익', col]),
                            "당기순이익": float(df.loc['당기순이익', col])
                        })
                    except: continue
                return pd.DataFrame(fin_data)
        return pd.DataFrame()
    except: return pd.DataFrame()

def get_company_guide_score(code):
    # 간단한 재무 점수 (예시)
    return 0, "분석완료", {"per":{"val":10, "stat":"good"}, "pbr":{"val":1.0, "stat":"good"}, "div":{"val":3.0, "stat":"good"}}

# --- 뉴스 및 AI 관련 함수 ---

def get_news_sentiment_llm(name, code):
    # 실제 AI 연동 부분 (간소화)
    return {
        "score": 0, 
        "headline": f"{name} 관련 뉴스 분석 결과", 
        "opinion": "관망", 
        "risk": "특이사항 없음",
        "catalyst": "이슈 없음",
        "dart_text": "최근 공시 없음",
        "raw_news": [],
        "method": "basic"
    }

def get_ai_recommended_stocks(keyword):
    # AI 추천 로직 (간소화)
    return [], "AI 연결 설정이 필요합니다."

# --- 분석 핵심 로직 (Sniper Score) ---

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_sniper_score(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if len(df) < 60: return 0, [], 0, 0, 0, pd.DataFrame(), ""
        
        # 지표 계산
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        
        curr = df.iloc[-1]
        score = 50
        tags = []
        
        # 간단한 로직 예시
        if curr['Close'] > curr['MA20']: score += 20; tags.append("상승추세")
        if curr['RSI'] < 30: score += 10; tags.append("과매도")
        
        return score, tags, 1.0, 0.0, 0, df, "분석 완료"
    except:
        return 0, [], 0, 0, 0, pd.DataFrame(), "오류"

def analyze_pro(code, name_override=None, relation_tag=None, my_buy_price=None):
    score, tags, vol_ratio, chg, win, df, reason = calculate_sniper_score(code)
    if df.empty: return None
    
    curr = df.iloc[-1]
    name = name_override if name_override else code
    
    # 전략 설정
    strategy = {
        "action": "관망",
        "buy": int(curr['Close'] * 0.95),
        "target": int(curr['Close'] * 1.1),
        "stop": int(curr['Close'] * 0.9)
    }
    
    # 결과 패키징
    result = {
        "name": name,
        "code": code,
        "price": int(curr['Close']),
        "change_rate": chg,
        "score": score,
        "strategy": strategy,
        "history": df,
        "relation_tag": relation_tag,
        "my_buy_price": my_buy_price,
        "stoch": {"k": curr['RSI'], "d":0}, # 임시
        "vol_ratio": vol_ratio,
        "win_rate": win,
        "cycle_txt": get_market_cycle_status(code),
        "ma_status": [],
        "trend_txt": reason
    }
    
    # 추가 데이터 로드 (에러 안 나게 try-except 내부 처리됨)
    result['investor_trend'] = get_investor_trend(code)
    result['fin_history'] = get_financial_history(code)
    _, _, fund_data = get_company_guide_score(code)
    result['fund_data'] = fund_data
    result['news'] = get_news_sentiment_llm(name, code)
    
    return result

def run_single_stock_simulation(df):
    return {"return": 0.0, "win_rate": 0.0, "trades": 0}
