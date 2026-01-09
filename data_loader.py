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
import re
import config
import utils

# ==========================================
# 1. 기본 데이터 수집 (크롤링/API)
# ==========================================

@st.cache_data
def get_krx_list_safe():
    try:
        df_kospi = fdr.StockListing('KOSPI')
        df_kosdaq = fdr.StockListing('KOSDAQ')
        list_df = pd.concat([df_kospi, df_kosdaq])
        if 'Code' not in list_df.columns and 'Symbol' in list_df.columns:
            list_df.rename(columns={'Symbol':'Code'}, inplace=True)
        if 'Name' not in list_df.columns:
            list_df.rename(columns={'Name':'Name'}, inplace=True)
        return list_df[['Code', 'Name']]
    except: return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_market_cycle_status(code):
    try:
        kospi = fdr.DataReader('KS11', datetime.datetime.now()-datetime.timedelta(days=400))
        ma120 = kospi['Close'].rolling(120).mean().iloc[-1]
        curr = kospi['Close'].iloc[-1]
        if curr > ma120: return "📈 시장 상승세 (공격적 매수 유효)"
        else: return "📉 시장 하락세 (보수적 접근 필요)"
    except: return "시장 분석 중"

@st.cache_data(ttl=3600)
def get_macro_data():
    results = {}
    tickers = {"KOSPI": "KS11", "KOSDAQ": "KQ11", "S&P500": "US500", "USD/KRW": "USD/KRW", "US_10Y": "US10YT", "WTI": "CL=F", "구리": "HG=F"}
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

def get_investor_trend_from_naver(code):
    try:
        url = f"https://finance.naver.com/item/frgn.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        try: dfs = pd.read_html(StringIO(res.text), match='날짜', header=0, encoding='euc-kr')
        except: dfs = pd.read_html(StringIO(res.text), header=0, encoding='euc-kr')
        
        target_df = None
        for df in dfs:
            if '기관' in str(df.columns) and '외국인' in str(df.columns): target_df = df; break
        if target_df is None and len(dfs) > 1: target_df = dfs[1]
        
        if target_df is not None:
            df = target_df.dropna().copy()
            df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]
            df.rename(columns={'날짜': 'Date'}, inplace=True)
            inst_col = [c for c in df.columns if '기관' in str(c)][0]
            frgn_col = [c for c in df.columns if '외국인' in str(c)][0]
            df['기관'] = df[inst_col].astype(str).str.replace(',', '').astype(float)
            df['외국인'] = df[frgn_col].astype(str).str.replace(',', '').astype(float)
            df['개인'] = -(df['기관'] + df['외국인'])
            df['Cum_Individual'] = df['개인'].cumsum()
            df['Cum_Foreigner'] = df['외국인'].cumsum()
            df['Cum_Institution'] = df['기관'].cumsum()
            return df.iloc[:20]
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_investor_trend(code):
    try:
        end_d = datetime.datetime.now().strftime("%Y%m%d")
        start_d = (datetime.datetime.now() - datetime.timedelta(days=60)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(start_d, end_d, code)
        if not df.empty:
            df['Cum_Individual'] = df['개인'].cumsum()
            df['Cum_Foreigner'] = df['외국인'].cumsum()
            df['Cum_Institution'] = df['기관합계'].cumsum()
            return df
    except: pass
    return get_investor_trend_from_naver(code)

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
                cols = df.columns[-5:-1]
                for col in cols:
                    try:
                        col_name = col[1] if isinstance(col, tuple) else col
                        fin_data.append({
                            "Date": str(col_name).strip(),
                            "매출액": float(df.loc['매출액', col]),
                            "영업이익": float(df.loc['영업이익', col]),
                            "당기순이익": float(df.loc['당기순이익', col])
                        })
                    except: continue
                return pd.DataFrame(fin_data)
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    per, pbr, div = 0.0, 0.0, 0.0
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        def get_val(id_name):
            tag = soup.select_one(f"#{id_name}")
            if tag: return float(tag.text.replace(',', '').replace('%', '').replace('배', '').strip())
            return 0.0
        per = get_val("_per"); pbr = get_val("_pbr"); div = get_val("_dvr")
    except: pass
    
    pbr_stat = "good" if 0 < pbr < 1.0 else ("neu" if 1.0 <= pbr < 2.5 else "bad")
    pbr_txt = "저평가(좋음)" if 0 < pbr < 1.0 else ("적정" if 1.0 <= pbr < 2.5 else "고평가")
    per_stat = "good" if 0 < per < 10 else ("neu" if 10 <= per < 20 else "bad")
    per_txt = "실적우수" if 0 < per < 10 else ("보통" if 10 <= per < 20 else "고평가")
    div_stat = "good" if div > 3.0 else "neu"
    div_txt = "고배당" if div > 3.0 else "일반"
    
    score = 20
    if pbr_stat=="good": score+=15
    if per_stat=="good": score+=10
    if div_stat=="good": score+=5
    
    return min(score, 50), "분석완료", {"per": {"val": per, "stat": per_stat, "txt": per_txt}, "pbr": {"val": pbr, "stat": pbr_stat, "txt": pbr_txt}, "div": {"val": div, "stat": div_stat, "txt": div_txt}}

@st.cache_data(ttl=3600)
def get_dart_disclosure_summary(code):
    if not config.USER_DART_KEY: return "DART API 키 미설정"
    try:
        dart = OpenDartReader(config.USER_DART_KEY)
        end = datetime.datetime.now().strftime("%Y%m%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=90)).strftime("%Y%m%d")
        df = dart.list(code, start=start, end=end)
        if df is None or df.empty: return "최근 3개월 내 특이 공시 없음"
        summary = []
        for _, row in df.head(5).iterrows():
            summary.append(f"[{row['rcept_dt']}] {row['report_nm']}")
        return "\n".join(summary)
    except Exception as e: return f"DART 조회 실패: {str(e)}"

def get_supply_demand(code):
    try:
        end = datetime.datetime.now().strftime("%Y%m%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(start, end, code)
        if df.empty: return {"f":0, "i":0}
        return {"f": int(df['외국인'].sum()), "i": int(df['기관합계'].sum())}
    except: return {"f":0, "i":0}

# ==========================================
# 2. 뉴스 및 AI 분석 (복구 완료)
# ==========================================

def get_naver_finance_news(code):
    news_data = []
    try:
        url = f"https://finance.naver.com/item/news_news.naver?code={code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        for t, d in zip(soup.select('.title'), soup.select('.date')):
            news_data.append({
                "title": t.get_text().strip(),
                "link": "https://finance.naver.com" + t.select_one('a')['href'],
                "date": utils.parse_relative_date(d.get_text().strip()).strftime("%Y-%m-%d")
            })
            if len(news_data) >= 5: break
    except: pass
    return news_data

def get_naver_search_news(keyword):
    news_data = []
    try:
        url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(keyword)}&sort=1"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        for item in soup.select('div.news_area')[:5]:
            title_tag = item.select_one('.news_tit')
            date_tag = item.select_one('.info_group span.info')
            if title_tag:
                date_str = date_tag.text.strip() if date_tag else ""
                news_data.append({
                    "title": title_tag.get_text().strip(),
                    "link": title_tag['href'],
                    "date": utils.parse_relative_date(date_str).strftime("%Y-%m-%d")
                })
    except: pass
    return news_data

@st.cache_data(ttl=1800)
def get_hankyung_news_rss():
    news = []
    try:
        feed = feedparser.parse("https://rss.hankyung.com/feed/market")
        for entry in feed.entries[:5]: news.append(f"[한경] {entry.title}")
    except: pass
    return news

@st.cache_data(ttl=1800)
def get_yahoo_global_news():
    news = []
    try:
        t = yf.Ticker("SPY")
        for n in t.news[:3]: news.append(f"[Global] {n['title']}")
    except: pass
    return news

def call_gemini_dynamic(prompt):
    # [중요] config.py에서 API 키를 확실하게 가져옵니다.
    api_key = config.USER_GOOGLE_API_KEY
    if not api_key: return None, "NO_KEY"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    try:
        res = requests.post(
            url, 
            headers={"Content-Type": "application/json"}, 
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.0}},
            timeout=30
        )
        if res.status_code == 200: return res.json(), None
        elif res.status_code == 429: time.sleep(1); return None, "Rate Limit"
        return None, f"HTTP {res.status_code}"
    except Exception as e: return None, str(e)

@st.cache_data(ttl=600)
def get_news_sentiment_llm(name, stock_context={}):
    news_list = []
    if stock_context.get('code'): news_list.extend(get_naver_finance_news(stock_context['code']))
    news_list.extend(get_naver_search_news(name))
    
    unique_news = []
    seen = set()
    for n in news_list:
        if n['title'] not in seen:
            seen.add(n['title']); unique_news.append(n)
    
    news_titles = [f"- {n['date']} {n['title']}" for n in unique_news[:5]]
    dart = get_dart_disclosure_summary(stock_context.get('code',''))
    macro = "\n".join(get_hankyung_news_rss()[:3] + get_yahoo_global_news()[:2])
    
    if not news_titles and "공시 없음" in dart:
         return {"score": 0, "headline": "최근 특이 뉴스 없음", "opinion": "중립", "risk": "", "catalyst": "", "raw_news": unique_news, "method": "none", "dart_text": dart}

    prompt = f"""
    당신은 주식 투자 전문가입니다. 아래 정보를 바탕으로 투자 의견을 JSON 형식으로 주세요.
    
    [종목 정보]
    종목명: {name} ({stock_context.get('code','')})
    현재가: {stock_context.get('current_price',0)}원
    추세: {stock_context.get('trend','분석중')}
    수급: {stock_context.get('supply','특이사항 없음')}
    
    [최근 뉴스]
    {chr(10).join(news_titles)}
    [DART 공시]
    {dart}
    [시장 분위기]
    {macro}
    
    위 데이터를 바탕으로 투자 의견을 JSON으로 주세요.
    형식: {{ "score": -10~10, "opinion": "매수/매도/관망", "summary": "한줄요약", "catalyst": "핵심재료", "risk": "리스크" }}
    JSON 코드만 출력하세요.
    """
    
    res_data, err = call_gemini_dynamic(prompt)
    if res_data:
        try:
            txt = res_data['candidates'][0]['content']['parts'][0]['text']
            txt = txt.replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{.*\}', txt, re.DOTALL)
            js = json.loads(match.group() if match else txt)
            return {"score": js.get('score', 0), "supply_score": js.get('supply_score', 0), "headline": js.get('summary', "분석 결과 없음"), "opinion": js.get('opinion', "중립"), "risk": js.get('risk', "특이사항 없음"), "catalyst": js.get('catalyst', ""), "raw_news": unique_news, "method": "ai", "dart_text": dart}
        except: pass
    return {"score": 0, "headline": "AI 분석 실패 (키워드 대체)", "opinion": "관망", "risk": "API 오류", "catalyst": "키워드", "raw_news": unique_news, "method": "keyword", "dart_text": dart}

def get_ai_recommended_stocks(keyword):
    prompt = f"사용자가 입력한 검색어 '{keyword}'와 관련된 한국 주식 5개를 추천해주세요. JSON 형식: [{{'name':'삼성전자', 'code':'005930', 'relation':'대장주'}}]"
    res, err = call_gemini_dynamic(prompt)
    if res:
        try:
            txt = res['candidates'][0]['content']['parts'][0]['text'].replace("```json", "").replace("```", "").strip()
            return json.loads(txt), "AI 추천 완료"
        except: pass
    return [], "AI 추천 실패"

@st.cache_data(ttl=1800)
def get_naver_theme_stocks(keyword):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(f"https://finance.naver.com/sise/theme.naver", headers=headers)
        res.encoding = 'EUC-KR'
        soup = BeautifulSoup(res.text, 'html.parser')
        target_link = None
        for t in soup.select('table.type_1 tr td.col_type1 a'):
            if keyword in t.text:
                target_link = "https://finance.naver.com" + t['href']
                break
        
        if target_link:
            res2 = requests.get(target_link, headers=headers)
            res2.encoding = 'EUC-KR'
            soup2 = BeautifulSoup(res2.text, 'html.parser')
            stocks = []
            for row in soup2.select('div.box_type_l table.type_5 tr'):
                a = row.select_one('td.name a')
                if a: stocks.append({"code": a['href'].split('=')[-1], "name": a.text.strip()})
            return stocks, f"'{keyword}' 테마 {len(stocks)}개 발견"
    except: pass
    return [], "테마 검색 실패"

# ==========================================
# 3. 핵심 알고리즘 (스나이퍼 스코어 & 전략)
# ==========================================

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_atr(data, window=14):
    high = data['High']; low = data['Low']; close = data['Close']
    tr = pd.concat([high-low, (high-close.shift(1)).abs(), (low-close.shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(window=window).mean()

def backtest_strategy(df):
    try:
        sim = df.copy()
        sim['Signal'] = (sim['Close'] > sim['MA20']) & (sim['RSI'] < 40)
        wins = 0; total = 0
        signals = sim[sim['Signal']].index
        for date in signals:
            try:
                future = sim.loc[date:].iloc[1:11]
                if not future.empty and future['High'].max() >= sim.loc[date, 'Close'] * 1.03: wins += 1
                total += 1
            except: continue
        return int((wins/total)*100) if total > 0 else 0
    except: return 0

def calculate_sniper_score(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if len(df) < 60: return 0, [], 0, 0, 0, pd.DataFrame(), ""
        
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['MA120'] = df['Close'].rolling(120).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        df['ATR'] = calculate_atr(df)
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        df['BB_Upper'] = df['MA20'] + (df['Close'].rolling(20).std() * 2)
        df['BB_Lower'] = df['MA20'] - (df['Close'].rolling(20).std() * 2)

        curr = df.iloc[-1]; prev = df.iloc[-2]
        score = 0; tags = []
        main_reason = "관망 필요"
        
        vol_ratio = curr['Volume'] / df['Volume'].rolling(20).mean().iloc[-1] if df['Volume'].rolling(20).mean().iloc[-1] > 0 else 0
        price_chg = (curr['Close'] - prev['Close']) / prev['Close'] * 100
        
        if vol_ratio >= 3.0:
            if price_chg > 0: score += 40; tags.append("🔥 거래량폭발(매수)"); main_reason = "큰손 쓸어담는 중"
            else: score -= 50; tags.append("😱 투매폭탄(위험)"); main_reason = "세력 이탈 경고"
        elif vol_ratio >= 1.5: score += 20; tags.append("📈 거래량증가")
        
        if curr['Close'] > curr['MA20']: score += 20
        if curr['RSI'] < 30: score += 10; tags.append("💎 과매도(기회)"); main_reason = "바닥 잡을 찬스"
        if curr['MACD'] > curr['MACD_Signal']: score += 10; tags.append("🌊 추세전환")
        
        win_rate = backtest_strategy(df)
        if win_rate >= 70: score += 10; tags.append(f"👑 승률{win_rate}%")
        
        if score < 60 and main_reason == "관망 필요": main_reason = "힘 모으는 중"
        return score, tags, vol_ratio, price_chg, win_rate, df, main_reason
    except: return 0, [], 0, 0, 0, pd.DataFrame(), "오류"

def run_single_stock_simulation(df):
    try:
        if len(df) < 100: return None
        balance = 1000000; shares = 0; wins = 0; trades = 0
        sim_df = df.copy()
        
        for i in range(len(sim_df)-90, len(sim_df)):
            row = sim_df.iloc[i]
            if shares == 0 and row['RSI'] < 40 and row['Close'] > row['MA20']:
                shares = int(balance / row['Close']); buy_price = row['Close']; balance -= shares * buy_price; trades += 1
            elif shares > 0:
                profit = (row['Close'] - buy_price) / buy_price
                if profit >= 0.05 or profit <= -0.03:
                    balance += shares * row['Close']; shares = 0
                    if profit > 0: wins += 1
        
        final_asset = balance + (shares * sim_df.iloc[-1]['Close'])
        return {"return": (final_asset - 1000000) / 1000000 * 100, "win_rate": (wins / trades * 100) if trades > 0 else 0, "trades": trades}
    except: return None

def scan_market_candidates(target_df, progress_bar, status_text):
    candidates = []
    limit = min(len(target_df), 50)
    for i in range(limit):
        try:
            row = target_df.iloc[i]
            progress_bar.progress((i+1)/limit)
            status_text.text(f"스캔 중: {row['Name']}")
            df = fdr.DataReader(row['Code'], datetime.datetime.now() - datetime.timedelta(days=100))
            if len(df) < 60: continue
            rsi = calculate_rsi(df['Close']).iloc[-1]
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            if rsi < 45 and df['Close'].iloc[-1] > ma20:
                candidates.append({"name": row['Name'], "code": row['Code'], "price": df['Close'].iloc[-1], "rsi": round(rsi, 1), "score": "조건 만족"})
        except: continue
    return candidates

# ==========================================
# 4. 최종 통합 분석 (Analyze Pro)
# ==========================================

def analyze_pro(code, name_override=None, relation_tag=None, my_buy_price=None):
    score, tags, vol_ratio, chg_rate, win_rate, df, main_reason = calculate_sniper_score(code)
    if df.empty: return None
    curr = df.iloc[-1]
    name = name_override if name_override else code
    
    ma_status = []
    pass_cnt = 0
    for label, col in [('5일', 'MA5'), ('20일', 'MA20'), ('60일', 'MA60')]:
        if curr['Close'] >= curr.get(col, 0): pass_cnt += 1; ma_status.append({"label": label, "ok": True})
        else: ma_status.append({"label": label, "ok": False})
    
    trend_bonus = 20 if pass_cnt >= 3 else (10 if pass_cnt >= 2 else 0)
    trend_txt = "강력한 상승 추세" if pass_cnt >= 3 else ("상승세 유지" if pass_cnt >= 2 else "조정/하락세")
    
    fund_score, _, fund_data = get_company_guide_score(code)
    cycle_txt = get_market_cycle_status(code)
    cycle_bonus = 10 if "상승세" in cycle_txt else 0
    investor_bonus = 5 if not get_investor_trend(code).empty else 0
    
    final_score = int((score * 0.5) + fund_score + investor_bonus + trend_bonus + cycle_bonus)
    atr = curr.get('ATR', curr['Close']*0.03)
    current_price = int(curr['Close'])
    
    quant_signal = "중립"
    if my_buy_price:
        profit_rate = (current_price - my_buy_price) / my_buy_price * 100
        action_txt = "보유"
        buy_price = my_buy_price
        target_price = int(buy_price * 1.10)
        stop_price = int(buy_price * 0.95)
        if profit_rate > 10: final_score += 20
        elif profit_rate > 0: final_score += 10
        quant_signal = "보유 권장" if final_score >= 50 else "차익/손절 고려"
    else:
        if final_score >= 80:
            buy_price = current_price
            target_price = int(current_price + (atr * 4))
            stop_price = int(current_price - (atr * 2))
            action_txt = f"🔥 강력 매수 ({main_reason})"
        elif final_score >= 60:
            buy_price = current_price
            target_price = int(current_price + (atr * 3))
            stop_price = int(current_price - (atr * 1.5))
            action_txt = f"📈 매수 ({main_reason})"
        else:
            buy_price = int(curr.get('MA20', current_price*0.95))
            target_price = int(buy_price * 1.10)
            stop_price = int(buy_price * 0.95)
            action_txt = f"👀 관망 ({main_reason})"
            
    buy_price = utils.round_to_tick(buy_price)
    target_price = utils.round_to_tick(target_price)
    stop_price = utils.round_to_tick(stop_price)
    
    supply_info = get_supply_demand(code)
    supply_txt = "외인매수" if supply_info['f'] > 0 else "특이사항 없음"
    
    context = {"code": code, "trend": trend_txt, "current_price": current_price, "supply": supply_txt, "is_holding": bool(my_buy_price)}
    news_result = get_news_sentiment_llm(name, context)
    
    final_score += news_result.get('score', 0) + news_result.get('supply_score', 0) * 2
    final_score = min(max(final_score, 0), 100)
    
    if my_buy_price: action_txt = news_result.get('opinion', quant_signal)
    
    return {
        "name": name, "code": code, "price": current_price, "change_rate": chg_rate,
        "score": final_score,
        "strategy": {"buy": buy_price, "target": target_price, "stop": stop_price, "action": action_txt, "buy_basis": main_reason},
        "history": df, "relation_tag": relation_tag, "my_buy_price": my_buy_price,
        "stoch": {"k": curr['RSI'], "d": 0}, "vol_ratio": vol_ratio,
        "win_rate": win_rate, "cycle_txt": cycle_txt, "trend_txt": trend_txt,
        "ma_status": ma_status, "fund_data": fund_data,
        "investor_trend": get_investor_trend(code),
        "fin_history": get_financial_history(code),
        "news": news_result
    }
