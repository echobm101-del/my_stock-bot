import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. 페이지 설정 (아이콘과 레이아웃) ---
st.set_page_config(page_title="AI 황금알 주식 비서", page_icon="💰", layout="wide")

# --- 2. 추천 리스트 (한국/미국 핵심 종목) ---
WATCH_LIST = {
    "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", 
    "현대차": "005380.KS", "엔비디아": "NVDA", "테슬라": "TSLA"
}

# --- 3. 사이드바: 강력한 추천 엔진 ---
with st.sidebar:
    st.header("🤖 AI 지능형 추천")
    st.info("시장의 과매도 종목을 실시간으로 탐색합니다.")
    if st.button("🚀 황금알 종목 찾기"):
        with st.spinner("빅데이터 분석 중..."):
            found = False
            for name, ticker in WATCH_LIST.items():
                df_tmp = yf.download(ticker, period="1mo", interval="1d", progress=False)
                if not df_tmp.empty:
                    # RSI 14 계산
                    delta = df_tmp['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                    
                    if rsi < 45: # 추천 기준
                        st.success(f"✅ {name} ({ticker})")
                        st.write(f"현재 심리 지수: {rsi:.1f} (저평가)")
                        found = True
            if not found:
                st.warning("현재 매수 적기인 종목이 없습니다.")

st.title("🦅 AI 황금알 주식 비서 Pro")
st.markdown("---")

# --- 4. 메인 분석 섹션 ---
target_code = st.text_input("🔍 분석할 종목 코드를 입력하세요 (예: 005930.KS)", "005930.KS")

try:
    # 데이터 가져오기 (기간을 넉넉히 1년으로)
    df = yf.download(target_code, period="1y", interval="1d")
    
    if df.empty:
        st.error("데이터를 찾을 수 없습니다. 코드를 다시 확인해 주세요.")
    else:
        # 최근 정보 요약 카드
        curr = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        dist = curr - prev
        pct = (dist / prev) * 100
        
        c1, c2, c3 = st.columns(3)
        c1.metric("현재가", f"{curr:,.0f}", f"{dist:,.0f} ({pct:.2f}%)")
        
        # 지표 계산 (20일 이평선, 볼린저 밴드)
        df['MA20'] = df['Close'].rolling(20).mean()
        df['Upper'] = df['MA20'] + (df['Close'].rolling(20).std() * 2)
        df['Lower'] = df['MA20'] - (df['Close'].rolling(20).std() * 2)

        # 프로급 차트 (캔들스틱 + 볼린저밴드)
        st.subheader("📊 전문 기술적 분석 차트")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="캔들"))
        fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], name="상단밴드", line=dict(color='rgba(255,0,0,0.2)')))
        fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], name="하단밴드", line=dict(color='rgba(0,0,255,0.2)')))
        fig.update_layout(xaxis_rangeslider_visible=False, height=500)
        st.plotly_chart(fig, use_container_width=True)

        # AI 매매 전략 제안
        st.subheader("💡 AI 매매 전략 제안")
        if curr <= df['Lower'].iloc[-1]:
            st.error("🚨 [강력 매수 의견] 주가가 바닥권 하단 밴드를 이탈했습니다. 반등을 준비하세요!")
        elif curr >= df['Upper'].iloc[-1]:
            st.warning("⚠️ [매도 주의] 주가가 과열권 상단 밴드에 도달했습니다. 분할 매도를 고려하세요.")
        else:
            st.success("✅ [보유/관망] 주가가 안정적인 흐름 내에 있습니다. 추세를 지켜보세요.")

except Exception as e:
    st.info("데이터를 불러오는 중입니다. 잠시만 기다려 주세요.")
