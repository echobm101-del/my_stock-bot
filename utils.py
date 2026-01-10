import FinanceDataReader as fdr
import pandas as pd
import datetime
import streamlit as st
import google.generativeai as genai

# ---------------------------------------------------------
# 1. Gemini AI 설정 (무료 키 연결)
# ---------------------------------------------------------
def configure_genai():
    try:
        # Secrets에서 키를 가져옴
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        return True
    except:
        return False

# ---------------------------------------------------------
# 2. 한국 시장 종목 리스트 (검색용)
# ---------------------------------------------------------
@st.cache_data(ttl=3600*24)
def get_krx_list():
    try:
        df_krx = fdr.StockListing('KRX')
        return df_krx[['Code', 'Name']]
    except:
        return pd.DataFrame()

def find_stock_code(keyword):
    df = get_krx_list()
    if df.empty: return None, None
    keyword = keyword.strip()
    
    # 이름 정확 일치
    exact = df[df['Name'] == keyword]
    if not exact.empty: return exact.iloc[0]['Name'], exact.iloc[0]['Code']
    
    # 코드 입력
    if keyword.isdigit():
        match = df[df['Code'] == keyword]
        if not match.empty: return match.iloc[0]['Name'], match.iloc[0]['Code']
        
    # 포함 검색
    contains = df[df['Name'].str.contains(keyword, case=False)]
    if not contains.empty: return contains.iloc[0]['Name'], contains.iloc[0]['Code']
    
    return None, None

# ---------------------------------------------------------
# 3. AI 한줄평 생성 함수 (Gemini 호출)
# ---------------------------------------------------------
def get_ai_summary(name, price, change_rate, rsi, trend):
    # 키가 없으면 분석 생략
    if not configure_genai():
        return "⚠️ AI 키가 설정되지 않았습니다."

    try:
        # 봇에게 줄 질문지(프롬프트)
        prompt = f"""
        주식 전문가로서 '{name}' 종목을 3줄로 요약 분석해줘.
        
        [현재 데이터]
        - 가격: {price}원
        - 등락률: {change_rate:.2f}%
        - RSI: {rsi:.2f} (30이하 과매도, 70이상 과매수)
        - 추세: {trend}

        [작성 조건]
        1. 첫 줄: 현재 주가 흐름과 시장 상황을 한 문장으로 요약.
        2. 둘째 줄: RSI와 추세를 기반으로 기술적 분석 평가.
        3. 셋째 줄: '매수', '매도', '관망' 중 하나의 키워드를 포함하여 투자 조언 제시.
        4. 말투: 친절하고 신뢰감 있게. 이모지 1~2개 사용.
        """
        
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 분석 중 오류 발생: {str(e)}"

# ---------------------------------------------------------
# 4. 통합 분석 실행 (기술적 분석 + AI)
# ---------------------------------------------------------
def analyze_basic(input_val, name_override=None, my_buy_price=0):
    # 1. 종목 찾기
    found_name, code = find_stock_code(input_val)
    if not code:
        if str(input_val).isdigit() and len(str(input_val)) >= 6:
            code = str(input_val)
            found_name = name_override if name_override else code
        else:
            return None

    final_name = name_override if name_override else found_name

    try:
        # 2. 데이터 수집
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty: return None
        
        # 3. 지표 계산
        df['MA20'] = df['Close'].rolling(20).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        curr = df.iloc[-1]
        price = int(curr['Close'])
        rsi = df['RSI'].iloc[-1]
        ma20 = df['MA20'].iloc[-1]
        
        # 추세 판단
        trend_txt = "상승 추세" if price > ma20 else "하락/조정세"
        if rsi < 30: trend_txt += " (과매도 구간)"
        elif rsi > 70: trend_txt += " (과열 구간)"
        
        # 등락률
        if len(df) > 1:
            prev = df.iloc[-2]
            chg_rate = (price - prev['Close']) / prev['Close'] * 100
        else:
            chg_rate = 0.0

        # 점수 계산
        score = 50
        if price > ma20: score += 20
        if rsi < 30: score += 20
        if rsi > 70: score -= 10
        if chg_rate > 0: score += 10

        # 4. 🔥 AI 분석 호출 (여기가 핵심!)
        with st.spinner(f'{final_name} AI 분석 중...'):
            ai_comment = get_ai_summary(final_name, price, chg_rate, rsi, trend_txt)

        # 5. 결과 반환
        return {
            "code": code,
            "name": final_name,
            "price": price,
            "change_rate": chg_rate,
            "score": score,
            "history": df,
            "trend_txt": trend_txt,
            # UI에 표시될 뉴스/AI 섹션
            "news": {
                "headline": f"🤖 Gemini AI 투자 코멘트", 
                "opinion": ai_comment,              
                "risk": "투자 판단은 본인의 책임입니다."
            },
            "strategy": {"action": "매수" if score>=70 else "관망"},
            "my_buy_price": float(my_buy_price)
        }

    except Exception as e:
        print(f"Error: {e}")
        return None
