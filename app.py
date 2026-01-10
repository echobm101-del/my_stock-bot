import streamlit as st
import pandas as pd
import time
import concurrent.futures

# 우리가 만든 파일들 불러오기
import data_loader as db  # 구글 시트 DB (방금 만든 것)
import utils              # 분석 로직 (계산, AI 등)
import ui                 # 화면 꾸미기 (HTML/CSS)

# -----------------------------------------------------------
# 1. 앱 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="Quant Sniper V50 (Google Sheets)", page_icon="💎", layout="wide")

# CSS 스타일 적용 (ui.py에 있는 스타일 가져오기)
try:
    st.markdown(ui.get_css(), unsafe_allow_html=True)
except:
    pass # 혹시 ui.py가 예전 버전이라도 에러 안 나게 처리

# -----------------------------------------------------------
# 2. 데이터 로딩 (구글 시트 연결)
# -----------------------------------------------------------
# 앱이 켜질 때 딱 한 번만 구글 시트에서 데이터를 가져옵니다.
if 'data_store' not in st.session_state:
    with st.spinner("☁️ 구글 시트와 연결 중입니다..."):
        # 여기서 data_loader.py의 load_data()가 실행됨
        st.session_state['data_store'] = db.load_data()

# 검색 결과 저장소 초기화
if 'preview_list' not in st.session_state:
    st.session_state['preview_list'] = []

# -----------------------------------------------------------
# 3. 사이드바 (종목 검색 기능)
# -----------------------------------------------------------
with st.sidebar:
    st.header("🔍 종목 찾기")
    st.caption("구글 시트 연동 버전 (V50.0)")
    
    with st.form(key="search_form"):
        keyword = st.text_input("종목명 또는 테마 입력", placeholder="예: 삼성전자, 로봇")
        submit = st.form_submit_button("분석 시작")
    
    if submit and keyword:
        st.info(f"'{keyword}' 검색 중...")
        try:
            # utils.py에 있는 기본 분석 함수 호출
            # (만약 utils.py를 아직 수정 안 했다면 analyze_pro 등 기존 함수 사용 가능)
            if hasattr(utils, 'analyze_basic'):
                result = utils.analyze_basic(keyword, keyword)
            else:
                # 구버전 utils 호환용
                result = utils.analyze_pro(keyword, keyword)

            if result:
                st.session_state['preview_list'] = [result]
            else:
                st.error("종목을 찾을 수 없거나 데이터가 부족합니다.")
        except Exception as e:
            st.error(f"검색 오류: {e}")

    st.markdown("---")
    # 구글 시트 데이터 다시 불러오기 버튼
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        del st.session_state['data_store']
        st.rerun()

# -----------------------------------------------------------
# 4. 메인 화면 (탭 구성)
# -----------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["🔍 발굴 결과", "💰 내 잔고 (Portfolio)", "👀 관심 종목 (Watchlist)"])

# === [탭 1] 검색 결과 ===
with tab1:
    if st.session_state['preview_list']:
        st.markdown("### 🔎 분석 결과")
        for item in st.session_state['preview_list']:
            # 카드 보여주기
            st.markdown(ui.create_watchlist_card_html(item), unsafe_allow_html=True)
            
            # [저장 버튼]
            col_add, _ = st.columns([0.3, 0.7])
            with col_add:
                # 버튼을 누르면 구글 시트에 저장
                if st.button(f"📌 관심종목 등록 ({item['name']})", key=f"add_{item['code']}"):
                    # 1. 구글 시트에 저장 시도
                    if db.add_stock_to_db("watchlist", item['name'], item['code']):
                        st.success(f"✅ {item['name']} 저장 완료!")
                        # 2. 화면에도 즉시 반영
                        st.session_state['data_store']['watchlist'][item['name']] = {'code': item['code']}
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ 저장 실패 (구글 시트 연결 확인 필요)")

# === [탭 2] 내 포트폴리오 (보유 종목) ===
with tab2:
    st.markdown("### 💰 내 보유 종목")
    portfolio = st.session_state['data_store'].get('portfolio', {})
    
    if not portfolio:
        st.info("보유 중인 종목이 없습니다. '관심 종목' 탭에서 매수 등록을 해보세요!")
    else:
        # 분석 실행
        results = []
        with st.spinner("보유 종목 수익률 계산 중..."):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for name, info in portfolio.items():
                    # 분석 함수 호출
                    if hasattr(utils, 'analyze_basic'):
                        futures.append(executor.submit(utils.analyze_basic, info['code'], name, info.get('buy_price', 0)))
                    else:
                        futures.append(executor.submit(utils.analyze_pro, info['code'], name, None, info.get('buy_price', 0)))
                
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): results.append(f.result())
        
        # 결과 카드 출력
        for res in results:
            st.markdown(ui.create_portfolio_card_html(res), unsafe_allow_html=True)
            
            # [삭제 버튼]
            if st.button(f"🗑️ 삭제 ({res['name']})", key=f"del_port_{res['code']}"):
                if db.delete_stock_from_db("portfolio", res['name']):
                    del st.session_state['data_store']['portfolio'][res['name']]
                    st.rerun()
                else:
                    st.error("삭제 실패")

# === [탭 3] 관심 종목 ===
with tab3:
    st.markdown("### 👀 관심 지켜보기")
    watchlist = st.session_state['data_store'].get('watchlist', {})
    
    if not watchlist:
        st.info("관심 종목이 없습니다. 검색 후 등록해보세요!")
    else:
        results = []
        with st.spinner("관심 종목 스캔 중..."):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for name, info in watchlist.items():
                    if hasattr(utils, 'analyze_basic'):
                        futures.append(executor.submit(utils.analyze_basic, info['code'], name))
                    else:
                        futures.append(executor.submit(utils.analyze_pro, info['code'], name))
                
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): results.append(f.result())
        
        for res in results:
            st.markdown(ui.create_watchlist_card_html(res), unsafe_allow_html=True)
            
            c1, c2 = st.columns([0.5, 0.5])
            with c1:
                # [매수 기능] -> 포트폴리오로 이동
                buy_price = st.number_input(f"체결가 ({res['name']})", value=res['price'], step=100, key=f"bp_{res['code']}")
                if st.button(f"📥 매수 체결", key=f"buy_{res['code']}"):
                    # 1. 포트폴리오 시트에 추가
                    db.add_stock_to_db("portfolio", res['name'], res['code'], buy_price)
                    # 2. 관심종목 시트에서 삭제
                    db.delete_stock_from_db("watchlist", res['name'])
                    
                    st.success(f"🎉 {res['name']} 매수 완료! 잔고 탭으로 이동합니다.")
                    time.sleep(1)
                    # 데이터 재로딩 (확실한 동기화)
                    st.session_state['data_store'] = db.load_data()
                    st.rerun()
            
            with c2:
                # [삭제 버튼]
                if st.button(f"🗑️ 삭제", key=f"del_watch_{res['code']}"):
                    if db.delete_stock_from_db("watchlist", res['name']):
                        del st.session_state['data_store']['watchlist'][res['name']]
                        st.rerun()
