import streamlit as st
import pandas as pd
import datetime
import FinanceDataReader as fdr
import time
import google.generativeai as genai  # 👈 공식 라이브러리 사용
import data_loader as db

st.set_page_config(page_title="Quant Sniper (Final)", page_icon="🎯", layout="wide")

# 1. 데이터 저장소 로드
if 'data_store' not in st.session_state:
    try:
        st.session_state['data_store'] = db.load_data()
    except Exception as e:
        st.session_state['data_store'] = {"portfolio": {}, "watchlist": {}}

# 2. AI 분석 함수 (공식 SDK 사용 방식으로 변경)
def get_ai_summary_genai(name, price, trend):
    # API 키 확인
    if "GEMINI_API_KEY" not in st.secrets:
        return "⚠️ API 키가 설정되지 않았습니다."

    try:
        # 라이브러리 설정
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        # 모델 설정 (가장 최신 안정화 모델)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # 질문 작성
        prompt = f"주식 '{name}'(현재가 {price}원, 추세 {trend})에 대해 투자 관점에서 3줄로 친절하게 요약해줘."
        
        # AI에게 질문 (HTTP 주소 신경 쓸 필요 없음)
        response = model.generate_content(prompt)
        
        return response.text
        
    except Exception as e:
        # 에러 발생 시 메시지 반환
        return f"❌ AI 분석 실패: {str(e)}"

# 3. 주식 데이터 분석
@st.cache_data(ttl=3600)
def get_stock_info(keyword):
    try:
        df_list = fdr.StockListing('KRX')
        code = None
        name = keyword
        
        exact = df_list[df_list['Name'] == keyword]
        if not exact.empty:
            code = exact.iloc[0]['Code']
            name = exact.iloc[0]['Name']
        elif keyword.isdigit():
             code = keyword
             match = df_list[df_list['Code'] == keyword]
             if not match.empty: name = match.iloc[0]['Name']
        
        if not code: return "검색 실패: 종목을 찾을 수 없습니다."

        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty: return "데이터 부족"

        df['MA20'] = df['Close'].rolling(20).mean()
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        price = int(curr['Close'])
        
        trend = "상승" if price > curr['MA20'] else "하락"
        change_rate = (price - prev['Close']) / prev['Close'] * 100
        score = 50 + (10 if change_rate > 0 else 0) + (20 if trend == "상승" else 0)

        return {"name": name, "code": code, "price": price, "change_rate": change_rate, "trend": trend, "score": score}

    except Exception as e:
        return f"시스템 오류: {str(e)}"

# 4. 화면 구성
st.title("🎯 Quant Sniper (최종)")

with st.sidebar:
    keyword = st.text_input("종목명", placeholder="삼성전자")
    if st.button("분석 시작"):
        if keyword:
            with st.spinner("조회 중..."):
                st.session_state['result'] = get_stock_info(keyword)

if 'result' in st.session_state:
    res = st.session_state['result']
    
    if isinstance(res, str):
        st.error(res)
    else:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"{res['name']} ({res['code']})")
                st.metric("현재가", f"{res['price']:,}원", f"{res['change_rate']:.2f}%")
            with c2:
                st.metric("AI 점수", f"{res['score']}점")
            
            st.info("🤖 AI 분석 결과")
            
            # 여기서 바뀐 함수 호출
            ai_msg = get_ai_summary_genai(res['name'], res['price'], res['trend'])
            
            if "❌" in ai_msg:
                st.error(ai_msg)
            else:
                st.write(ai_msg)

            if st.button("📌 관심종목 추가"):
                if db.add_stock_to_db("watchlist", res['name'], res['code']):
                    st.success("저장 완료!")
                    time.sleep(1)
                    st.rerun()
