import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai
import FinanceDataReader as fdr
import time

# -----------------------------------------------------------
# 1. 설정 및 디자인 (CSS)
# -----------------------------------------------------------
st.set_page_config(page_title="Quant Sniper AI", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: white; border-radius: 16px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border: 1px solid #eee; margin-bottom: 15px; }
    .price-up { color: #E8382F; font-weight: bold; }
    .price-down { color: #2D65F0; font-weight: bold; }
    .ai-box { background-color: #F3F5F9; padding: 15px; border-radius: 10px; margin-top: 15px; border: 1px solid #E1E4E8; }
    .ai-title { font-size: 13px; font-weight: bold; color: #555; margin-bottom: 5px; }
    .ai-content { font-size: 14px; line-height: 1.5; color: #333; white-space: pre-line; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# 2. 기능 함수들 (여기에 다 넣었습니다!)
# -----------------------------------------------------------
def get_ai_summary(name, price, change_rate, rsi, trend):
    # 키 확인
    if "GEMINI_API_KEY" not in st.secrets:
        return "⚠️ Secrets에 GEMINI_API_KEY가 없습니다."
    
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # 최신 무료 모델 (호환성 좋음)
        model = genai.GenerativeModel('gemini-1.5-flash') 
        
        prompt = f"""
        주식 전문가로서 '{name}'(현재가 {price}원)을 분석해줘.
        [데이터] 등락률: {change_rate:.2f}%, RSI: {rsi:.2f}, 추세: {trend}
        [조건] 3줄 요약. 1.상황 2.기술적분석 3.매수/매도/관망 의견. 명확하게.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 분석 오류: {str(e)}"

@st.cache_data(ttl=3600)
def get_stock_data(keyword):
    try:
        df_list = fdr.StockListing('KRX')
        # 종목 찾기
        code = None
        name = keyword
        
        # 이름 일치
        exact = df_list[df_list['Name'] == keyword]
        if not exact.empty:
            code = exact.iloc[0]['Code']
        # 포함 검색
        elif not df_list[df_list['Name'].str.contains(keyword)].empty:
            found = df_list[df_list['Name'].str.contains(keyword)].iloc[0]
            code = found['Code']
            name = found['Name']
        # 코드 검색
        elif keyword.isdigit():
             code = keyword

        if not code: return None

        # 차트 데이터
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty: return None

        # 지표 계산
        df['MA20'] = df['Close'].rolling(20).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        curr = df.iloc[-1]
        price = int(curr['Close'])
        rsi = df['RSI'].iloc[-1]
        
        trend = "상승" if price > curr['MA20'] else "하락"
        if rsi < 30: trend += " (과매도)"
        elif rsi > 70: trend += " (과열)"
        
        chg_rate = (price - df.iloc[-2]['Close']) / df.iloc[-2]['Close'] * 100

        return {
            "name": name, "code": code, "price": price, 
            "change_rate": chg_rate, "rsi": rsi, "trend": trend
        }
    except:
        return None

# -----------------------------------------------------------
# 3. 메인 화면 구성
# -----------------------------------------------------------
st.header("🔍 Quant Sniper AI (통합버전)")

with st.sidebar:
    keyword = st.text_input("종목명", placeholder="삼성전자")
    if st.button("분석 시작") and keyword:
        st.session_state['result'] = get_stock_data(keyword)

if 'result' in st.session_state and st.session_state['result']:
    res = st.session_state['result']
    
    # AI 분석 실행
    with st.spinner("🤖 AI가 분석 중입니다..."):
        ai_msg = get_ai_summary(res['name'], res['price'], res['change_rate'], res['rsi'], res['trend'])
    
    # 색상 결정
    color = "price-up" if res['change_rate'] > 0 else "price-down"
    sign = "+" if res['change_rate'] > 0 else ""
    
    # HTML 카드 생성 (여기서 unsafe_allow_html=True로 그립니다!)
    html_code = f"""
    <div class='toss-card'>
        <h3>{res['name']} <span style='font-size:14px; color:#888'>{res['code']}</span></h3>
        <div class='{color}' style='font-size:24px;'>
            {res['price']:,}원 ({sign}{res['change_rate']:.2f}%)
        </div>
        <div style='margin-top:10px; color:#555;'>📊 {res['trend']} / RSI {res['rsi']:.1f}</div>
        
        <div class='ai-box'>
            <div class='ai-title'>🤖 Gemini AI 투자 의견</div>
            <div class='ai-content'>{ai_msg}</div>
        </div>
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)

    # 버튼들
    c1, c2 = st.columns(2)
    with c1: st.button("관심종목 저장 (기능 준비중)") 
    with c2: 
        if st.button("데이터 초기화"):
            del st.session_state['result']
            st.rerun()

else:
    st.info("왼쪽에서 종목을 검색해주세요.")
