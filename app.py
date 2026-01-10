import streamlit as st
import pandas as pd
import datetime
import google.generativeai as genai
import FinanceDataReader as fdr
import time
import data_loader as db

# 1. 설정
st.set_page_config(page_title="Quant Sniper", page_icon="📈", layout="wide")

if 'data_store' not in st.session_state:
    try:
        st.session_state['data_store'] = db.load_data()
    except:
        st.session_state['data_store'] = {"portfolio": {}, "watchlist": {}}

# 2. AI 및 분석 함수
def get_ai_summary(name, price, trend):
    if "GEMINI_API_KEY" not in st.secrets:
        return "⚠️ Secrets에 GEMINI_API_KEY가 없습니다."
    
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # 최신 라이브러리(0.7.0 이상)에서는 이 모델이 가장 잘 돌아갑니다.
        model = genai.GenerativeModel('gemini-1.5-flash') 
        
        prompt = f"""
        주식 전문가로서 '{name}'(현재가 {price}원, 추세: {trend})을 분석해줘.
        [조건] 3줄 요약. 1.현재상황 2.기술적분석 3.매수/관망 의견.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"분석 대기 중... (잠시 후 다시 시도해주세요)"

def analyze_stock(keyword):
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

        if not code: return None

        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty: return None

        df['MA20'] = df['Close'].rolling(20).mean()
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        price = int(curr['Close'])
        
        trend = "상승 추세" if price > curr['MA20'] else "하락/조정세"
        change_rate = (price - prev['Close']) / prev['Close'] * 100
        
        score = 50
        if change_rate > 0: score += 10
        if trend.startswith("상승"): score += 20

        return {"name": name, "code": code, "price": price, "change_rate": change_rate, "trend": trend, "score": score}
    except:
        return None

# 3. 화면 구성
st.title("📈 Quant Sniper (Final)")

with st.sidebar:
    st.header("🔍 종목 검색")
    keyword = st.text_input("종목명 입력", placeholder="예: 삼성전자")
    if st.button("분석 시작") and keyword:
        with st.spinner("데이터 분석 중..."):
            st.session_state['search_result'] = analyze_stock(keyword)

tab1, tab2, tab3 = st.tabs(["🔍 분석 결과", "💰 내 잔고", "👀 관심 종목"])

with tab1:
    if 'search_result' in st.session_state and st.session_state['search_result']:
        res = st.session_state['search_result']
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"{res['name']} ({res['code']})")
                st.metric("현재가", f"{res['price']:,}원", f"{res['change_rate']:.2f}%")
            with c2:
                st.metric("점수", f"{res['score']}점")
            
            st.info("🤖 AI 분석 결과")
            st.write(get_ai_summary(res['name'], res['price'], res['trend']))

            if st.button("📌 관심종목 추가"):
                if db.add_stock_to_db("watchlist", res['name'], res['code']):
                    st.success("저장 완료!")
                    st.session_state['data_store']['watchlist'][res['name']] = {'code': res['code']}
                    time.sleep(1)
                    st.rerun()
    else:
        st.info("왼쪽에서 종목을 검색하세요.")

with tab2:
    port = st.session_state['data_store'].get('portfolio', {})
    if not port: st.warning("보유 종목 없음")
    else:
        for name, info in port.items():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1: st.write(f"**{name}** ({info['code']})")
                with c2:
                    if st.button("삭제", key=f"d_{info['code']}"):
                        db.delete_stock_from_db("portfolio", name)
                        del st.session_state['data_store']['portfolio'][name]
                        st.rerun()

with tab3:
    watch = st.session_state['data_store'].get('watchlist', {})
    if not watch: st.info("관심 종목 없음")
    else:
        for name, info in watch.items():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1: st.write(f"**{name}**")
                with c2: bp = st.number_input("매수 체결가", key=f"bp_{info['code']}", step=100)
                with c3:
                    if st.button("매수", key=f"b_{info['code']}"):
                        db.add_stock_to_db("portfolio", name, info['code'], bp)
                        db.delete_stock_from_db("watchlist", name)
                        st.session_state['data_store'] = db.load_data()
                        st.rerun()
