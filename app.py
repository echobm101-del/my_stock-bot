import streamlit as st
import pandas as pd
import datetime
import requests
import FinanceDataReader as fdr
import time
import data_loader as db

st.set_page_config(page_title="Quant Sniper (Debug)", page_icon="🛠️", layout="wide")

# 1. 데이터 저장소 로드
if 'data_store' not in st.session_state:
    try:
        st.session_state['data_store'] = db.load_data()
    except Exception as e:
        st.error(f"데이터베이스 연결 실패: {e}")
        st.session_state['data_store'] = {"portfolio": {}, "watchlist": {}}

# 2. AI 분석 함수 (HTTP 직접 요청 - 라이브러리 미사용)
def get_ai_summary_http(name, price, trend):
    if "GEMINI_API_KEY" not in st.secrets:
        return "⚠️ Secrets에 GEMINI_API_KEY가 없습니다."
    
    api_key = st.secrets["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"주식 '{name}'(현재가 {price}원, 추세 {trend}) 3줄 투자 요약 분석 (말투 친절하게)"}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"❌ AI 서버 오류 ({response.status_code}): {response.text}"
    except Exception as e:
        return f"❌ 통신 실패: {str(e)}"

# 3. 주식 데이터 분석 함수 (에러가 나면 이유를 반환)
@st.cache_data(ttl=3600) # 1시간 동안 검색 결과 기억 (속도 향상)
def get_stock_info(keyword):
    try:
        # 종목 리스트 다운로드 (여기서 실패하면 에러 뜸)
        df_list = fdr.StockListing('KRX')
        
        code = None
        name = keyword
        
        # 이름 검색
        exact = df_list[df_list['Name'] == keyword]
        if not exact.empty:
            code = exact.iloc[0]['Code']
            name = exact.iloc[0]['Name']
        # 코드 검색
        elif keyword.isdigit():
             code = keyword
             match = df_list[df_list['Code'] == keyword]
             if not match.empty: name = match.iloc[0]['Name']
        
        if not code:
            return "검색 실패: 종목을 찾을 수 없습니다."

        # 차트 데이터
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty: return "데이터 부족: 차트 데이터가 없습니다."

        # 지표 계산
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
st.title("🛠️ Quant Sniper (복구 모드)")

with st.sidebar:
    keyword = st.text_input("종목명 (예: 삼성전자)", placeholder="삼성전자")
    if st.button("분석 시작"):
        if not keyword:
            st.warning("종목명을 입력하세요.")
        else:
            with st.spinner(f"'{keyword}' 데이터 조회 중..."):
                st.session_state['result'] = get_stock_info(keyword)

# 결과 표시
if 'result' in st.session_state:
    res = st.session_state['result']
    
    # 1. 에러가 났을 경우 (문자열이면 에러 메시지임)
    if isinstance(res, str):
        st.error(res)
        st.info("팁: 잠시 후 다시 시도하거나, 정확한 종목명을 입력하세요.")
        
    # 2. 성공했을 경우 (딕셔너리 데이터)
    else:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"{res['name']} ({res['code']})")
                st.metric("현재가", f"{res['price']:,}원", f"{res['change_rate']:.2f}%")
            with c2:
                st.metric("AI 점수", f"{res['score']}점")
            
            # AI 분석 (여기서 에러나면 바로 보여줌)
            st.info("🤖 AI 분석 결과")
            ai_msg = get_ai_summary_http(res['name'], res['price'], res['trend'])
            
            if "❌" in ai_msg:
                st.error(ai_msg) # 에러면 빨간 박스
            else:
                st.write(ai_msg) # 성공이면 글자 출력

            if st.button("📌 관심종목 추가"):
                if db.add_stock_to_db("watchlist", res['name'], res['code']):
                    st.success("저장됨!")
                    time.sleep(1)
                    st.rerun()
