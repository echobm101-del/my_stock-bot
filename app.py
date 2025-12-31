import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="Pro 주식 비서", page_icon="🦅", layout="wide")

# 2. 추천 대상 (원하는 종목을 추가하세요)
WATCH_LIST = ["005930.KS", "000660.KS", "035420.KS", "AAPL", "TSLA", "NVDA"]

st.title("🦅 Pro AI 주식 비서")

# --- 사이드바: 지능형 추천 기능 ---
with st.sidebar:
    st.header("🌟 AI 종목 추천")
    if st.button("지금 살만한 종목 검색"):
        with st.spinner("데이터 분석 중..."):
            for ticker in WATCH_LIST:
                df_temp = yf.download(ticker, period="1mo", interval="1d", progress=False)
                if not df_temp.empty:
                    # RSI 계산 logic
                    delta = df_temp['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                    
                    if rsi < 40: # 과매도 종목 추천
                        st.success(f"🔥 매수 추천: {ticker} (RSI: {rsi:.1f})")
        st.write("분석이 완료되었습니다.")

# --- 메인: 기존 종목 상세 분석 ---
st.sidebar.markdown("---")
target = st.sidebar.text_input("상세 분석할 종목 코드", "005930.KS")

try:
    df = yf.download(target, period="6mo", interval="1d")
    # 현재가 정보
    curr_price = df['Close'].iloc[-1]
    st.subheader(f"📊 {target} 분석 리포트 (현재가: {curr_price:,.0f}원)")
    
    # 볼린저 밴드 계산
    ma20 = df['Close'].rolling(20).mean()
    std = df['Close'].rolling(20).std()
    upper = ma20 + (std * 2)
    lower = ma20 - (std * 2)

    # 차트 시각화
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='주가', line=dict(color='black')))
    fig.add_trace(go.Scatter(x=df.index, y=upper, name='상단', line=dict(dash='dot', color='blue')))
    fig.add_trace(go.Scatter(x=df.index, y=lower, name='하단', line=dict(dash='dot', color='red')))
    st.plotly_chart(fig, use_container_width=True)

except:
    st.error("데이터 로딩 실패! 코드를 확인해 주세요.")

    st.rerun()
