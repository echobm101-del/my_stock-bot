import streamlit as st
import pandas as pd
import time
import concurrent.futures

# 모듈 불러오기
import config
import utils
import ui
import data_loader as dl

# 1. 페이지 설정
st.set_page_config(page_title="Quant Sniper V50.14", page_icon="💎", layout="wide")
st.markdown(ui.get_css_style(), unsafe_allow_html=True)

if 'data_store' not in st.session_state:
    st.session_state['data_store'] = utils.load_from_github()
if 'preview_list' not in st.session_state:
    st.session_state['preview_list'] = []

# 2. 메인 타이틀 & 매크로 대시보드
st.title("💎 Quant Sniper V50.14 (Full Ver.)")

with st.expander("🌍 글로벌 시장 & 매크로 (Click)", expanded=False):
    macro = dl.get_macro_data()
    if macro:
        cols = st.columns(len(macro))
        for i, (key, val) in enumerate(macro.items()):
            color = "#F04452" if val['change'] > 0 else "#3182F6"
            with cols[i]:
                st.markdown(f"<div class='metric-box'><div class='metric-title'>{key}</div><div class='metric-value' style='color:{color}'>{val['val']:,.2f}</div><div style='font-size:12px; color:{color}'>{val['change']:+.2f}%</div></div>", unsafe_allow_html=True)
    else: st.info("매크로 데이터 로딩 중...")

# 3. 탭 구성
tab1, tab2, tab3 = st.tabs(["🔍 발굴/테마", "💰 내 잔고", "👀 관심 종목"])

# [탭 1] 발굴 & 테마 분석
with tab1:
    if st.session_state['preview_list']:
        if st.button("목록 지우기"):
            st.session_state['preview_list'] = []
            st.rerun()
            
        for item in st.session_state['preview_list']:
            res = dl.analyze_pro(item['code'], item['name'], item.get('relation_tag'))
            if res:
                st.markdown(ui.create_watchlist_card_html(res), unsafe_allow_html=True)
                
                # 시뮬레이션 버튼
                if st.button(f"🧪 시뮬레이션 ({res['name']})", key=f"sim_{res['code']}"):
                    sim = dl.run_single_stock_simulation(res['history'])
                    if sim: st.success(f"승률: {sim['win_rate']:.1f}% / 수익률: {sim['return']:.2f}% (매매 {sim['trades']}회)")
                    else: st.warning("데이터 부족")
                    
                # 추가 버튼
                if st.button(f"📌 관심등록 ({res['name']})", key=f"add_prev_{res['code']}"):
                    st.session_state['data_store']['watchlist'][res['name']] = {'code': res['code']}
                    utils.update_github_file(st.session_state['data_store'])
                    st.success("등록 완료")

# [탭 2] 내 잔고
with tab2:
    portfolio = st.session_state['data_store'].get('portfolio', {})
    if not portfolio: st.info("보유 종목이 없습니다.")
    else:
        for name, info in portfolio.items():
            res = dl.analyze_pro(info['code'], name, my_buy_price=float(info.get('buy_price', 0)))
            if res:
                st.markdown(ui.create_portfolio_card_html(res), unsafe_allow_html=True)
                with st.expander("상세 분석 & AI 뉴스"):
                    st.markdown(ui.render_chart_legend(), unsafe_allow_html=True)
                    st.altair_chart(ui.create_chart_clean(res['history']), use_container_width=True)
                    st.write("---")
                    st.write(f"🤖 **AI 의견:** {res['news']['headline']}")
                    st.caption(f"Risk: {res['news']['risk']}")

# [탭 3] 관심 종목
with tab3:
    watchlist = st.session_state['data_store'].get('watchlist', {})
    if not watchlist: st.info("관심 종목이 없습니다.")
    else:
        for name, info in watchlist.items():
            res = dl.analyze_pro(info['code'], name)
            if res:
                st.markdown(ui.create_watchlist_card_html(res), unsafe_allow_html=True)
                c1, c2 = st.columns([1,1])
                with c1:
                    if st.button(f"🗑️ 삭제", key=f"del_{res['code']}"):
                        del st.session_state['data_store']['watchlist'][name]
                        utils.update_github_file(st.session_state['data_store'])
                        st.rerun()
                with c2:
                    price_in = st.number_input(f"매수단가", key=f"p_{res['code']}")
                    if st.button(f"📥 잔고이동", key=f"mov_{res['code']}"):
                        st.session_state['data_store']['portfolio'][name] = {"code": res['code'], "buy_price": price_in}
                        del st.session_state['data_store']['watchlist'][name]
                        utils.update_github_file(st.session_state['data_store'])
                        st.rerun()

# 4. 사이드바 (기능 복구)
with st.sidebar:
    st.header("⚙️ 스나이퍼 메뉴")
    
    with st.expander("🔍 테마/종목 AI 발굴"):
        kwd = st.text_input("검색어 (예: HBM, 비만치료제)")
        if st.button("🚀 AI 분석 시작"):
            with st.spinner("AI가 종목을 찾고 있습니다..."):
                # AI 추천 호출
                stocks, msg = dl.get_ai_recommended_stocks(kwd)
                if stocks:
                    st.session_state['preview_list'] = stocks
                    st.success(msg)
                    st.rerun()
                else:
                    st.error("결과를 찾지 못했습니다.")

    with st.expander("📡 시장 레이더 (스캔)"):
        mode = st.radio("모드", ["KOSPI 시총상위", "KOSDAQ 시총상위"])
        if st.button("🛰️ 스캔 시작"):
            market = "KOSPI" if "KOSPI" in mode else "KOSDAQ"
            target_df = dl.get_krx_list_safe() # 실제로는 마켓별 필터링 필요하나 전체로 예시
            if not target_df.empty:
                bar = st.progress(0); txt = st.empty()
                cands = dl.scan_market_candidates(target_df.head(50), bar, txt) # 50개만 테스트
                txt.empty(); bar.empty()
                if cands:
                    st.success(f"{len(cands)}개 포착!")
                    st.session_state['preview_list'] = cands
                    st.rerun()
                else: st.warning("조건 만족 종목 없음")

    st.markdown("---")
    with st.expander("➕ 수동 추가"):
        name = st.text_input("종목명")
        code = st.text_input("코드")
        if st.button("추가"):
            st.session_state['data_store']['watchlist'][name] = {"code": code}
            utils.update_github_file(st.session_state['data_store'])
            st.success("저장 완료")
