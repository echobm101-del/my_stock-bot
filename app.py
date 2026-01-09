import streamlit as st
import time
import concurrent.futures

# 우리가 분리한 파일들 불러오기
import config
import utils
import ui
import data_loader as dl

# 1. 페이지 설정
st.set_page_config(page_title="Quant Sniper V50.14", page_icon="💎", layout="wide")
st.markdown(ui.get_css_style(), unsafe_allow_html=True)

# 2. 데이터 저장소 로드
if 'data_store' not in st.session_state:
    st.session_state['data_store'] = utils.load_from_github()

# 3. 메인 화면
st.title("💎 Quant Sniper V50.14 (Modular Ver.)")

tab1, tab2 = st.tabs(["👀 관심 종목", "💰 내 잔고"])

# 탭 1: 관심 종목
with tab1:
    watchlist = st.session_state['data_store'].get('watchlist', {})
    if not watchlist:
        st.info("관심 종목이 없습니다. 사이드바에서 추가해주세요.")
    else:
        for name, info in watchlist.items():
            # data_loader에 있는 분석 함수 사용
            res = dl.analyze_pro(info['code'], name)
            if res:
                # ui에 있는 카드 그리기 함수 사용
                st.markdown(ui.create_watchlist_card_html(res), unsafe_allow_html=True)

# 탭 2: 내 잔고
with tab2:
    portfolio = st.session_state['data_store'].get('portfolio', {})
    if not portfolio:
        st.info("보유 종목이 없습니다.")
    else:
        for name, info in portfolio.items():
            buy_price = float(info.get('buy_price', 0))
            res = dl.analyze_pro(info['code'], name, my_buy_price=buy_price)
            if res:
                st.markdown(ui.create_portfolio_card_html(res), unsafe_allow_html=True)

# 4. 사이드바 (종목 추가 기능)
with st.sidebar:
    st.header("⚙️ 종목 추가")
    name = st.text_input("종목명")
    code = st.text_input("종목코드 (예: 005930)")
    
    if st.button("관심종목 추가"):
        if name and code:
            st.session_state['data_store']['watchlist'][name] = {"code": code}
            if utils.update_github_file(st.session_state['data_store']):
                st.success("저장 완료!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("저장 실패 (config.py 토큰 확인 필요)")ㅍ
if st.button("관심종목 추가"):
        if name and code:
            st.session_state['data_store']['watchlist'][name] = {"code": code}
            if utils.update_github_file(st.session_state['data_store']):
                st.success("저장 완료!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("저장 실패 (config.py 토큰 확인 필요)")
