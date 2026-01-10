import streamlit as st
import pandas as pd
import time
import concurrent.futures

# 파일 불러오기
import data_loader as db
import utils
import ui

# 1. 페이지 설정
st.set_page_config(page_title="Quant Sniper AI", page_icon="💎", layout="wide")

# 스타일 적용 (여기서 HTML 렌더링 준비)
try:
    st.markdown(ui.get_css(), unsafe_allow_html=True)
except:
    pass

# 2. 데이터 로딩
if 'data_store' not in st.session_state:
    with st.spinner("☁️ 구글 시트 데이터 불러오는 중..."):
        st.session_state['data_store'] = db.load_data()

if 'preview_list' not in st.session_state:
    st.session_state['preview_list'] = []

# 3. 사이드바 (검색)
with st.sidebar:
    st.header("🔍 종목 찾기")
    with st.form(key="search_form"):
        keyword = st.text_input("종목명 입력", placeholder="예: 삼성전자")
        submit = st.form_submit_button("분석 시작")
    
    if submit and keyword:
        st.info(f"'{keyword}' 분석 중...")
        try:
            # utils 함수 호출
            result = utils.analyze_basic(keyword, keyword)
            if result:
                st.session_state['preview_list'] = [result]
            else:
                st.error("종목을 찾을 수 없거나 데이터가 부족합니다.")
        except Exception as e:
            st.error(f"오류: {e}")

    st.markdown("---")
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        del st.session_state['data_store']
        st.rerun()

# 4. 메인 탭
tab1, tab2, tab3 = st.tabs(["🔍 발굴 결과", "💰 내 잔고", "👀 관심 종목"])

# [탭 1] 검색 결과
with tab1:
    if st.session_state['preview_list']:
        st.markdown("### 🔎 분석 결과")
        for item in st.session_state['preview_list']:
            # 🔥 [핵심 수정] HTML을 'unsafe_allow_html=True'로 그려줍니다!
            st.markdown(ui.create_watchlist_card_html(item), unsafe_allow_html=True)
            
            if st.button(f"📌 관심종목 등록 ({item['name']})", key=f"add_{item['code']}"):
                if db.add_stock_to_db("watchlist", item['name'], item['code']):
                    st.success(f"✅ {item['name']} 저장 완료!")
                    st.session_state['data_store']['watchlist'][item['name']] = {'code': item['code']}
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("저장 실패 (구글 시트 연결 확인)")

# [탭 2] 내 잔고
with tab2:
    st.markdown("### 💰 내 보유 종목")
    portfolio = st.session_state['data_store'].get('portfolio', {})
    if not portfolio:
        st.info("보유 종목이 없습니다.")
    else:
        results = []
        with st.spinner("수익률 계산 중..."):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(utils.analyze_basic, info['code'], name, info.get('buy_price', 0)) for name, info in portfolio.items()]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): results.append(f.result())
        
        for res in results:
            st.markdown(ui.create_portfolio_card_html(res), unsafe_allow_html=True)
            if st.button(f"🗑️ 삭제 ({res['name']})", key=f"del_p_{res['code']}"):
                db.delete_stock_from_db("portfolio", res['name'])
                del st.session_state['data_store']['portfolio'][res['name']]
                st.rerun()

# [탭 3] 관심 종목
with tab3:
    st.markdown("### 👀 관심 지켜보기")
    watchlist = st.session_state['data_store'].get('watchlist', {})
    if not watchlist:
        st.info("관심 종목이 없습니다.")
    else:
        results = []
        with st.spinner("관심 종목 스캔 중..."):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(utils.analyze_basic, info['code'], name) for name, info in watchlist.items()]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): results.append(f.result())
        
        for res in results:
            st.markdown(ui.create_watchlist_card_html(res), unsafe_allow_html=True)
            c1, c2 = st.columns([0.5, 0.5])
            with c1:
                bp = st.number_input(f"체결가 ({res['name']})", value=res['price'], step=100, key=f"bp_{res['code']}")
                if st.button(f"📥 매수 체결", key=f"buy_{res['code']}"):
                    db.add_stock_to_db("portfolio", res['name'], res['code'], bp)
                    db.delete_stock_from_db("watchlist", res['name'])
                    st.success("매수 완료!")
                    st.session_state['data_store'] = db.load_data()
                    st.rerun()
            with c2:
                if st.button(f"🗑️ 삭제", key=f"del_w_{res['code']}"):
                    db.delete_stock_from_db("watchlist", res['name'])
                    del st.session_state['data_store']['watchlist'][res['name']]
                    st.rerun()
