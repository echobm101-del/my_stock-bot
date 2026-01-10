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
        # Secrets에서 키를 가져옵니다.
        # Streamlit Cloud의 Secrets에 GEMINI_API_KEY가 있어야 합니다.
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            genai.configure(api_key=api_key)
            return True
        else:
            return False
    except Exception as e:
        print(f"Key Error: {e}")
        return False

# ---------------------------------------------------------
# 2. 한국 시장 종목 리스트 (검색용 데이터)
# ---------------------------------------------------------
@st.cache_data(ttl=3600*24) # 하루에 한 번만 다운로드 (속도 향상)
def get_krx_list():
    try:
        # 한국거래소(KRX) 전체 종목 리스트 가져오기
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name']]
    except:
        return pd.DataFrame()

def find_stock_code(keyword):
    df = get_krx_list()
    if df.empty: return None, None
    keyword = keyword.strip()
    
    # 1. 이름이 정확히 일치하는 경우
    exact = df[df['Name'] == keyword]
    if not exact.empty: return exact.iloc[0]['Name'], exact.iloc[0]['Code']
    
    # 2. 종목 코드(숫자 6자리)를 직접 입력한 경우
    if keyword.isdigit():
        match = df[df['Code'] == keyword]
        if not match.empty: return match.iloc[0]['Name'], match.iloc[0]['Code']
        
    # 3. 검색어를 포함하는 경우 (예: '삼성' -> '삼성전자')
    contains = df[df['Name'].str.contains(keyword, case=False)]
    if not contains.empty: return contains.iloc[0]['Name'], contains.iloc[0]['Code']
    
    return None, None

# ---------------------------------------------------------
# 3. AI 한줄평 생성 함수 (Gemini 호출)
# ---------------------------------------------------------
def get_ai_summary(name, price, change_rate, rsi, trend):
    # 키 설정 확인
    if not configure_genai():
        return "⚠️ AI API 키가 설정되지 않았습니다."

    try:
        # 봇에게 줄 질문지(프롬프트)
        prompt = f"""
        주식 전문가로서 '{name}' 종목(현재가 {price}원)을 분석해줘.
        
        [현재 지표]
        - 등락률: {change_rate:.2f}%
        - RSI(상대강도지수): {rsi:.2f} (30이하 과매도, 70이상 과매수)
        - 추세 방향: {trend}

        [답변 조건]
        1. 첫 줄: 현재 주가 흐름을 한 문장으로 요약.
        2. 둘째 줄: RSI와 추세를 근거로 기술적 분석 멘트.
        3. 셋째 줄: '매수', '매도', '관망' 중 하나의 단어를 반드시 포함하여 결론 제시.
        4. 말투: 3줄 이내로 간결하고 명확하게.
        """
        
        # 최신 모델 사용 (gemini-1.5-flash)
        # 만약 에러가 나면 gemini-pro로 자동 변경되도록 로직 구성도 가능하나,
        # 현재는 가장 빠르고 무료인 1.5-flash를 기본으로 씁니다.
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        # 에러 발생 시 사용자에게 이유를 보여줌
        return f"AI 분석 불가: {str(e)}"

# ---------------------------------------------------------
# 4. 통합 분석 실행 (차트 데이터 + 기술적 지표 + AI)
# ---------------------------------------------------------
def analyze_basic(input_val, name_override=None, my_buy_price=0):
    # 1. 종목 코드 찾기
    found_name, code = find_stock_code(input_val)
    if not code:
        # 입력값이 코드 형식이면 그대로 사용 시도
        if str(input_val).isdigit() and len(str(input_val)) >= 6:
            code = str(input_val)
            found_name = name_override if name_override else code
        else:
            return None # 검색 실패

    final_name = name_override if name_override else found_name

    try:
        # 2. 차트 데이터 가져오기 (최근 1년)
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty: return None
        
        # 3. 보조지표 계산 (이동평균선, RSI)
        df['MA20'] = df['Close'].rolling(20).mean() # 20일 이동평균
        
        # RSI 계산 로직
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 현재 상태 추출
        curr = df.iloc[-1]
        price = int(curr['Close'])
        rsi = df['RSI'].iloc[-1]
        ma20 = df['MA20'].iloc[-1]
        
        # 추세 텍스트 생성
        trend_txt = "상승 추세" if price > ma20 else "하락/조정세"
        if rsi < 30: trend_txt += " (과매도 구간)"
        elif rsi > 70: trend_txt += " (과열 구간)"
        
        # 전일 대비 등락률
        if len(df) > 1:
            prev = df.iloc[-2]
            chg_rate = (price - prev['Close']) / prev['Close'] * 100
        else:
            chg_rate = 0.0

        # 자체 점수 계산 (간단 버전)
        score = 50
        if price > ma20: score += 20
        if rsi < 30: score += 20
        if rsi > 70: score -= 10
        if chg_rate > 0: score += 10

        # 4. 🔥 AI 분석 호출 (여기가 핵심!)
        # 화면에 '분석 중...' 뱅글이를 돌리며 AI에게 물어봅니다.
        with st.spinner(f'🤖 AI가 {final_name} 차트를 분석하고 있습니다...'):
            ai_comment = get_ai_summary(final_name, price, chg_rate, rsi, trend_txt)

        # 5. 최종 결과 포장 (UI로 보낼 데이터)
        return {
            "code": code,
            "name": final_name,
            "price": price,
            "change_rate": chg_rate,
            "score": score,
            "history": df,
            "trend_txt": trend_txt,
            # UI에 표시될 AI 뉴스 섹션
            "news": {
                "headline": "Gemini AI 투자 코멘트", 
                "opinion": ai_comment,              
                "risk": "투자 판단은 본인의 책임입니다."
            },
            "strategy": {"action": "매수" if score>=70 else "관망"},
            "my_buy_price": float(my_buy_price)
        }

    except Exception as e:
        print(f"Analysis Error ({final_name}): {e}")
        return None
