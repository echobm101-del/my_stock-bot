import FinanceDataReader as fdr
import pandas as pd
import datetime
import streamlit as st

# ---------------------------------------------------------
# 1. 한국 시장 종목 리스트 가져오기 (검색 엔진)
# ---------------------------------------------------------
@st.cache_data(ttl=3600*24) # 하루에 한 번만 받아오기
def get_krx_list():
    try:
        # KRX 전체 종목 리스트 다운로드 (시간이 좀 걸림)
        df_krx = fdr.StockListing('KRX')
        # 필요한 컬럼만 남기기
        df = df_krx[['Code', 'Name']].copy()
        return df
    except Exception as e:
        print(f"Stock List Error: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 2. 종목 검색 함수 (이름 -> 코드 변환)
# ---------------------------------------------------------
def find_stock_code(keyword):
    df = get_krx_list()
    if df.empty: return None, None
    
    keyword = keyword.strip()
    
    # 1. 정확히 일치하는 경우
    exact = df[df['Name'] == keyword]
    if not exact.empty:
        return exact.iloc[0]['Name'], exact.iloc[0]['Code']
    
    # 2. 코드를 입력한 경우
    if keyword.isdigit():
        code_match = df[df['Code'] == keyword]
        if not code_match.empty:
            return code_match.iloc[0]['Name'], code_match.iloc[0]['Code']
            
    # 3. 포함되는 단어 검색 (예: '삼성' -> '삼성전자' 찾기)
    contains = df[df['Name'].str.contains(keyword, case=False)]
    if not contains.empty:
        # 가장 먼저 검색된 것 반환
        return contains.iloc[0]['Name'], contains.iloc[0]['Code']
        
    return None, None

# ---------------------------------------------------------
# 3. 통합 분석 함수 (검색 + 기술적 분석)
# ---------------------------------------------------------
def analyze_basic(input_val, name_override=None, my_buy_price=0):
    # 1. 종목 코드 찾기
    found_name, code = find_stock_code(input_val)
    
    # 코드가 아니라 이름이 넘어온 경우 처리
    if not code:
        # 혹시 input_val이 이미 코드(숫자 6자리)라면 그대로 사용
        if str(input_val).isdigit() and len(str(input_val)) >= 6:
            code = str(input_val)
            found_name = name_override if name_override else code
        else:
            return None # 검색 실패

    final_name = name_override if name_override else found_name

    try:
        # 2. 차트 데이터 가져오기 (1년치)
        # 005930 -> 005930 (코스피/코스닥 자동)
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        
        if df.empty: return None
        
        curr = df.iloc[-1]
        
        # 3. 보조지표 계산 (RSI, 이평선)
        df['MA20'] = df['Close'].rolling(20).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        rsi = df['RSI'].iloc[-1]
        ma20 = df['MA20'].iloc[-1]
        price = int(curr['Close'])
        
        # 4. 분석 코멘트 작성
        score = 50
        trend_txt = "관망세"
        
        # 간단한 로직
        if price > ma20:
            score += 20
            trend_txt = "📈 상승 추세 (20일선 위)"
        else:
            score -= 10
            trend_txt = "📉 조정/하락세"
            
        if rsi < 30:
            score += 20
            trend_txt += " + 과매도(반등기회)"
        elif rsi > 70:
            score -= 10
            trend_txt += " + 과열권"
            
        # 전일 대비 등락률
        if len(df) > 1:
            prev = df.iloc[-2]
            chg_rate = (price - prev['Close']) / prev['Close'] * 100
        else:
            chg_rate = 0.0

        # 전략 제안
        action = "관망"
        if score >= 80: action = "🔥 강력매수"
        elif score >= 60: action = "✨ 매수"
        elif score <= 40: action = "💨 매도/손절"

        # 5. 결과 반환 (UI가 그릴 수 있는 형태)
        return {
            "code": code,
            "name": final_name,
            "price": price,
            "change_rate": chg_rate,
            "score": score,
            "history": df,          # 차트 데이터
            "trend_txt": trend_txt,
            "stoch": {"k": rsi, "d": 0}, # UI 호환용
            "vol_ratio": 1.0,            # UI 호환용
            "strategy": {
                "action": action,
                "buy": price,
                "target": int(price * 1.1),
                "stop": int(price * 0.95)
            },
            "news": {
                "headline": "AI 심층 분석을 실행해보세요", 
                "opinion": "-",
                "risk": "",
                "method": "none"
            },
            "fund_data": None,
            "investor_trend": pd.DataFrame(),
            "fin_history": pd.DataFrame(),
            "ma_status": [],
            "my_buy_price": float(my_buy_price)
        }
        
    except Exception as e:
        print(f"Analysis Error ({final_name}): {e}")
        return None
