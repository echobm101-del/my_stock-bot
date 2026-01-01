import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
import json
import os
import time
from pykrx import stock  # 수급 분석용 라이브러리

# --- [1. 설정 및 기본 데이터 로딩] ---
st.set_page_config(page_title="Pro Quant Dashboard V3.5", page_icon="💎", layout="wide")
DATA_FILE = "my_watchlist_v3.json"
SETTINGS_FILE = "my_settings.json"

# KRX 종목 리스트 캐싱 (섹터 정보 확인용)
@st.cache_data
def get_krx_list():
    try:
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name', 'Sector']]
    except: return pd.DataFrame()

krx_df = get_krx_list()

def get_sector_info(code):
    try:
        row = krx_df[krx_df['Code'] == code]
        if not row.empty: return row.iloc[0]['Sector']
        return "기타"
    except: return "알수없음"

# --- [2. 데이터 분석 함수들] ---

# 2.1 국제 정세(Macro) 분석
@st.cache_data(ttl=3600) # 1시간마다 갱신
def get_global_macro():
    """환율, 유가, 금, S&P500 데이터를 통해 국제 정세 파악"""
    try:
        indices = {
            "USD/KRW": "USD/KRW", 
            "WTI Crude": "CL=F", 
            "Gold": "GC=F", 
            "S&P 500": "US500"
        }
        result = {}
        market_score = 0
        
        for name, code in indices.items():
            df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=10))
            if not df.empty:
                now_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                change_rate = ((now_price - prev_price) / prev_price) * 100
                
                status = "보합"
                if change_rate > 0.5: status = "상승"
                elif change_rate < -0.5: status = "하락"
                
                result[name] = {"price": now_price, "change": change_rate, "status": status}
                
                # 점수 계산 (한국장에 유리한 조건)
                if name == "USD/KRW":
                    if status == "하락": market_score += 1 # 환율 안정 = 호재
                    elif status == "상승": market_score -= 1 # 환율 급등 = 악재
                elif name == "WTI Crude":
                    if status == "상승": market_score -= 0.5 # 유가 상승 = 비용 증가(약악재)
                elif name == "S&P 500":
                    if status == "상승": market_score += 1 # 미장 상승 = 호재
                    elif status == "하락": market_score -= 1
                    
        return {"data": result, "score": market_score}
    except:
        return None

# 2.2 수급(Supply/Demand) 분석 - NEW!
@st.cache_data(ttl=1800) # 30분마다 갱신
def get_supply_demand(code):
    """최근 3일간 외국인/기관의 순매수 동향 분석"""
    try:
        end_date = datetime.datetime.now().strftime("%Y%m%d")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y%m%d")
        
        # pykrx로 투자자별 순매수 상위 조회
        df = stock.get_market_investor_net_purchase_by_date(start_date, end_date, code)
        
        recent = df.tail(3)
        if recent.empty: return {"score": 0, "reasons": [], "foreigner": 0, "institution": 0}
        
        foreigner_sum = recent['외국인'].sum()
        institution_sum = recent['기관합계'].sum()
        
        score = 0
        reasons = []
        
        # 외국인
        if foreigner_sum > 0: 
            score += 1
            if all(recent['외국인'] > 0): reasons.append("외국인 3일 연속 매수")
            else: reasons.append("외국인 매수 우위")
        elif foreigner_sum < 0:
            score -= 1
            reasons.append("외국인 매도세")
            
        # 기관
        if institution_sum > 0:
            score += 0.5
            if all(recent['기관합계'] > 0): reasons.append("기관 3일 연속 매수")
            else: reasons.append("기관 매수 우위")
        elif institution_sum < 0:
            score -= 0.5
            reasons.append("기관 매도세")
            
        return {"score": score, "reasons": reasons, "foreigner": foreigner_sum, "institution": institution_sum}
    except:
        return {"score": 0, "reasons": [], "foreigner": 0, "institution": 0}

# 2.3 뉴스 분석
def analyze_news_sentiment(code):
    try:
        url = f"https://finance.naver.com/item/news_news.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        titles = soup.select('.title')
        if not titles: return {"score": 0, "news_list": []}
        
        news_list = []
        sentiment_score = 0
        pos_keywords = ['수주', '체결', '돌파', '급등', '최대', '호재', '성장', '기대', '매수', '유망', '세계', '공급']
        neg_keywords = ['하락', '급락', '적자', '소송', '우려', '부진', '매도', '불확실', '제재', '경고', '지연']
        
        for t in titles[:3]: 
            title = t.text.strip()
            link = "https://finance.naver.com" + t.select_one('a')['href']
            score = 0
            for k in pos_keywords: 
                if k in title: score += 1
            for k in neg_keywords: 
                if k in title: score -= 1
            sentiment_score += score
            news_list.append({"title": title, "link": link, "score": score})
        return {"score": sentiment_score, "news_list": news_list}
    except: return {"score": 0, "news_list": []}

# 2.4 실시간 기본 데이터
def get_realtime_data(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        no_today = soup.select_one('.no_today')
        if not no_today: return None
        price = int(no_today.select_one('.blind').text.replace(',', ''))
        change_text = soup.select_one('.no_exday').text.strip()
        change_type = "상승" if "상승" in change_text or "플러스" in change_text else ("하락" if "하락" in change_text or "마이너스" in change_text else "보합")
        vol_tag = soup.select_one('.no_info .blind')
        volume = int(vol_tag.text.replace(',', '')) if vol_tag else 0
        per = soup.select_one('#_per'); per = per.text if per else "N/A"
        cap = soup.select_one('#_market_sum'); cap = cap.text.replace('\t','').replace('\n','') + "억" if cap else "N/A"
        return {"price": price, "change": change_type, "volume": volume, "per": per, "cap": cap}
    except: return None

# 2.5 기술적 분석
def analyze_technical(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=200))
        if df.empty: return None
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['StdDev'] = df['Close'].rolling(window=20).std()
        df['Upper'] = df['MA20'] + (df['StdDev'] * 2)
        df['Lower'] = df['MA20'] - (df['StdDev'] * 2)
        delta = df['Close'].diff(1)
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
        return {"df": df, "rsi": rsi.iloc[-1], "bb_lower": df['Lower'].iloc[-1], "bb_upper": df['Upper'].iloc[-1], "price": df['Close'].iloc[-1], "atr": df['ATR'].iloc[-1]}
    except: return None

def draw_chart(df, lower, upper):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color='#FAFAFA', width=2)))
    fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], mode='lines', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(255, 255, 255, 0.1)', showlegend=False))
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=150, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False)
    return fig

# --- [3. 파일 입출력 및 세션] ---
def load_watchlist():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def save_watchlist(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'watchlist' not in st.session_state: st.session_state['watchlist'] = load_watchlist()

# --- [4. UI 구성] ---
with st.sidebar:
    st.title("⚙️ Control Panel")
    with st.expander("➕ 종목 추가"):
        n_name = st.text_input("종목명", placeholder="삼성전자")
        n_code = st.text_input("코드", placeholder="005930")
        n_price = st.number_input("평단가", value=0)
        if st.button("추가"):
            st.session_state['watchlist'][n_name] = {"code": n_code, "my_price": int(n_price)}
            save_watchlist(st.session_state['watchlist'])
            st.rerun()
    st.divider()
    for name in list(st.session_state['watchlist'].keys()):
        c1, c2 = st.columns([4, 1])
        c1.write(name)
        if c2.button("x", key=f"d_{name}"):
            del st.session_state['watchlist'][name]
            save_watchlist(st.session_state['watchlist'])
            st.rerun()

st.title("🚀 Pro Quant Dashboard V3.5")
st.caption(f"Tech + News + Macro + Supply (All-in-One) | {datetime.datetime.now().strftime('%Y-%m-%d')}")

# [4.1 글로벌 매크로 현황판]
macro = get_global_macro()
if macro:
    m_score = macro['score']
    if m_score >= 1: m_msg = "🌤️ 투자 맑음 (Risk On)"; m_color="green"
    elif m_score <= -1: m_msg = "⛈️ 투자 주의 (Risk Off)"; m_color="red"
    else: m_msg = "☁️ 흐림/혼조세 (Neutral)"; m_color="gray"

    st.markdown(f"""
    <div style='background-color:#1E1E1E; padding:15px; border-radius:10px; border:1px solid #444; margin-bottom:20px;'>
        <h3 style='margin:0 0 10px 0; color:{m_color};'>{m_msg}</h3>
        <div style='display:flex; justify-content:space-around; text-align:center;'>
            <div>🇺🇸 S&P 500<br><span style='font-size:18px; font-weight:bold; color:{'#FF4B4B' if macro['data']['S&P 500']['change']>0 else '#4B88FF'}'>{format(macro['data']['S&P 500']['price'], ',.2f')}</span><br><span style='font-size:12px;'>({macro['data']['S&P 500']['change']:.2f}%)</span></div>
            <div>🇰🇷 USD/KRW<br><span style='font-size:18px; font-weight:bold; color:{'#FF4B4B' if macro['data']['USD/KRW']['change']>0 else '#4B88FF'}'>{format(macro['data']['USD/KRW']['price'], ',.2f')}원</span><br><span style='font-size:12px;'>({macro['data']['USD/KRW']['change']:.2f}%)</span></div>
            <div>🛢️ WTI 유가<br><span style='font-size:18px; font-weight:bold; color:{'#FF4B4B' if macro['data']['WTI Crude']['change']>0 else '#4B88FF'}'>{format(macro['data']['WTI Crude']['price'], ',.2f')}</span><br><span style='font-size:12px;'>({macro['data']['WTI Crude']['change']:.2f}%)</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

if st.button("🔄 전체 데이터 새로고침"): st.rerun()

# [4.2 종목별 분석]
if not st.session_state['watchlist']: st.info("사이드바에서 종목을 추가하세요.")
else:
    for name, info in st.session_state['watchlist'].items():
        code = info['code']; my_price = info['my_price']
        
        # 데이터 수집 (예외처리 포함)
        try:
            basic = get_realtime_data(code)
            tech = analyze_technical(code)
            news = analyze_news_sentiment(code)
            sector = get_sector_info(code)
            supply = get_supply_demand(code) # 수급 분석 호출
        except:
            st.error(f"{name} 데이터 로딩 중 오류 발생"); continue
        
        if not basic or not tech: continue
        price = basic['price']
        
        # --- 종합 점수 계산 ---
        total_score = 0
        final_reasons = []
        
        # 1. 기술적 (RSI)
        if tech['rsi'] <= 30: total_score += 1; final_reasons.append("RSI 과매도")
        elif tech['rsi'] >= 70: total_score -= 1; final_reasons.append("RSI 과매수")
        
        # 2. 뉴스
        if news['score'] > 0: total_score += 1
        elif news['score'] < 0: total_score -= 1
        
        # 3. 매크로 (국제정세)
        if macro:
            if macro['score'] > 0: total_score += 0.5
            elif macro['score'] < 0: total_score -= 0.5
            
        # 4. 수급 (Foreigner & Institution)
        if supply:
            total_score += supply['score']
            if supply['reasons']: final_reasons.extend(supply['reasons'])
            
        # 최종 판단
