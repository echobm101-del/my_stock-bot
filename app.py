import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai
import FinanceDataReader as fdr
import time
import data_loader as db # 기존에 만든 DB 연결 파일 사용

# -----------------------------------------------------------
# 1. 앱 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="Quant Sniper (순정)", page_icon="📈", layout="wide")

# 데이터 저장소 초기화
if 'data_store' not in st.session_state:
    try:
        st.session_state['data_store'] = db.load_data()
    except:
        st.session_state['data_store'] = {"portfolio": {}, "watchlist": {}}

# -----------------------------------------------------------
# 2. 핵심 기능 함수 (AI + 주식데이터)
# -----------------------------------------------------------
def get_ai_summary(name, price, trend):
    # 키가 없으면 바로 종료
    if "GEMINI_API_KEY" not in st.secrets:
        return "⚠️ Secrets에 GEMINI_API_KEY를 설정해주세요."
    
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # 에러 없는 가장 안정적인 모델 'gemini-pro' 사용
        model = genai.GenerativeModel('gemini-pro') 
        
        prompt = f"""
        주식 전문가로서 '{name}'(현재가 {price}원, 추세: {trend})을 분석해줘.
        [조건] 3줄 요약. 1.현재상황 2.기술적분석 3.매수/관망 의견. 말투는 친절하게.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 연결 지연 (잠시 후 다시 시도해주세요): {e}"

def analyze_stock(keyword):
    try:
        # 종목 코드 찾기
        df_list = fdr.StockListing('KRX')
        code = None
        name = keyword
        
        # 이름으로 찾기
        exact = df_list[df_list['Name'] == keyword]
        if not exact.empty:
            code = exact.iloc[0]['Code']
            name = exact.iloc[0]['Name']
        # 코드로 찾기
        elif keyword.isdigit():
             code = keyword
             match = df_list[df_list['Code'] == keyword]
             if not match.empty: name = match.iloc[0]['Name']

        if not code: return None

        # 차트 데이터 (1년치)
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty: return None

        # 보조지표 계산
        df['MA20'] = df['Close'].rolling(20).mean()
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        price = int(curr['Close'])
        
        # 추세 및 등락률
        trend = "상승 추세" if price > curr['MA20'] else "하락/조정세"
        change_rate = (price - prev['Close']) / prev['Close'] * 100
        
        # 점수 계산
        score = 50
        if change_rate > 0: score += 10
        if trend.startswith("상승"): score += 20

        return {
            "name": name, "code": code, "price": price, 
            "change_rate": change_rate, "trend": trend, "score": score
        }
    except:
        return None

# -----------------------------------------------------------
# 3. 화면 구성 (HTML 코드 없이 순수 Streamlit 사용)
# -----------------------------------------------------------
st.title("📈 Quant Sniper (AI 탑재)")

# 사이드바: 검색
with st.sidebar:
    st.header("🔍 종목 검색")
    keyword = st.text_input("종목명 입력", placeholder="예: 삼성전자")
    if st.button("분석 시작") and keyword:
        with st.spinner("데이터 분석 중..."):
            st.session_state['search_result'] = analyze_stock(keyword)

# 메인 화면: 탭 구성
tab1, tab2, tab3 = st.tabs(["🔍 분석 결과", "💰 내 잔고", "👀 관심 종목"])

# [탭 1] 검색 결과 표시
with tab1:
    if 'search_result' in st.session_state and st.session_state['search_result']:
        res = st.session_state['search_result']
        
        # 깔끔한 네이티브 카드 디자인 (HTML 아님)
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"{res['name']} ({res['code']})")
                st.metric("현재가", f"{res['price']:,}원", f"{res['change_rate']:.2f}%")
            with c2:
                st.metric("AI 점수", f"{res['score']}점")
                st.caption(res['trend'])
            
            # AI 분석 내용 (파란 박스)
            st.info("🤖 AI가 차트를 분석하고 있습니다...")
            ai_msg = get_ai_summary(res['name'], res['price'], res['trend'])
            st.write(ai_msg)

            # 저장 버튼
            if st.button("📌 관심종목 추가"):
                if db.add_stock_to_db("watchlist", res['name'], res['code']):
                    st.success("저장 완료!")
                    # 데이터 갱신
                    st.session_state['data_store']['watchlist'][res['name']] = {'code': res['code']}
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("저장 실패 (DB 연결 확인)")
    else:
        st.info("왼쪽 사이드바에서 종목을 검색해주세요.")

# [탭 2] 내 잔고 (포트폴리오)
with tab2:
    port = st.session_state['data_store'].get('portfolio', {})
    if not port:
        st.warning("보유 중인 종목이 없습니다.")
    else:
        for name, info in port.items():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.write(f"**{name}** ({info['code']})")
                    st.caption(f"매수가: {info.get('buy_price', 0):,}원")
                with c2:
                    if st.button("삭제", key=f"del_p_{info['code']}"):
                        db.delete_stock_from_db("portfolio", name)
                        del st.session_state['data_store']['portfolio'][name]
                        st.rerun()

# [탭 3] 관심 종목 (워치리스트)
with tab3:
    watch = st.session_state['data_store'].get('watchlist', {})
    if not watch:
        st.info("관심 종목이 없습니다.")
    else:
        for name, info in watch.items():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    st.write(f"**{name}**")
                    st.caption(info['code'])
                with c2:
                    bp = st.number_input("매수 체결가", key=f"bp_{info['code']}", step=100)
                with c3:
                    if st.button("매수", key=f"buy_{info['code']}"):
                        db.add_stock_to_db("portfolio", name, info['code'], bp)
                        db.delete_stock_from_db("watchlist", name)
                        st.success("매수됨!")
                        st.session_state['data_store'] = db.load_data()
                        st.rerun()
