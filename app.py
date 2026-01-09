import streamlit as st
import pandas as pd
import time

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
if 'current_theme_name' not in st.session_state:
    st.session_state['current_theme_name'] = ""

# 2. 메인 타이틀 & 매크로 대시보드
col_title, col_guide = st.columns([0.7, 0.3])
with col_title:
    st.title("💎 Quant Sniper V50.14 (Universal Radar)")
with col_guide:
    st.write("")
    with st.expander("📘 V50.14 업데이트 노트", expanded=False):
        st.markdown("* **[Radar] 만능 레이더 탑재**\n* **[New] 개별 종목 시뮬레이션**")

with st.expander("🌍 글로벌 거시 경제 & 공급망 대시보드 (Click)", expanded=False):
    macro = dl.get_macro_data()
    if macro:
        cols = st.columns(len(macro))
        for i, (key, val) in enumerate(macro.items()):
            color = "#F04452" if val['change'] > 0 else "#3182F6"
            badge = "상승" if val['change'] > 0 else "하락"
            bg = "#FFF1F1" if val['change'] > 0 else "#E8F3FF"
            with cols[i]:
                st.markdown(f"""<div class='metric-box'><div class='metric-title'>{key}</div><div class='metric-value' style='color:{color}'>{val['val']:,.2f}</div><div style='font-size:12px; color:{color}'>{val['change']:+.2f}%</div><div class='metric-badge' style='color:{color}; background:{bg};'>{badge}</div></div>""", unsafe_allow_html=True)
    else: st.info("매크로 데이터 로딩 중...")

# 3. 탭 구성
tab1, tab2, tab3 = st.tabs(["🔍 테마/종목 발굴", "💰 내 잔고 (Portfolio)", "👀 관심 종목 (Watchlist)"])

# [탭 1] 발굴 & 테마 분석
with tab1:
    if st.button("🔄 화면 정리"):
        st.session_state['preview_list'] = []
        st.rerun()
        
    if st.session_state.get('preview_list'):
        st.markdown(f"### 🔍 '{st.session_state.get('current_theme_name','')}' 심층 분석")
        
        # [수정] 병렬 처리 제거 -> 순차 처리 (에러 방지)
        preview_results = []
        with st.spinner("🚀 고속 AI 분석 엔진 & 백테스팅 가동 중..."):
            for item in st.session_state['preview_list']:
                res = dl.analyze_pro(item['code'], item['name'], item.get('relation_tag'))
                if res: preview_results.append(res)
            preview_results.sort(key=lambda x: x['score'], reverse=True)
            
        for res in preview_results:
            st.markdown(ui.create_watchlist_card_html(res), unsafe_allow_html=True)
            
            ai_txt = res['news'].get('headline', '분석 대기 중...')
            icon = "🔥" if "매수" in res['news'].get('opinion','') else "🤖"
            
            with st.expander(f"{icon} AI 요약: {ai_txt[:40]}... (▼ 상세)"):
                c1, c2 = st.columns([1, 5])
                with c1:
                    if st.button(f"📌 관심등록", key=f"add_{res['code']}"):
                        st.session_state['data_store']['watchlist'][res['name']] = {'code': res['code']}
                        utils.update_github_file(st.session_state['data_store'])
                        st.success("완료")
                        time.sleep(0.5); st.rerun()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("###### 📈 기술적 분석")
                    st.markdown(f"<div class='tech-summary'>{res['trend_txt']}</div>", unsafe_allow_html=True)
                    ui.render_tech_metrics(res['stoch'], res['vol_ratio'])
                    ui.render_signal_lights(res['history'].iloc[-1]['RSI'], res['history'].iloc[-1]['MACD'], res['history'].iloc[-1]['MACD_Signal'])
                    ui.render_ma_status(res['ma_status'])
                    st.markdown(ui.render_chart_legend(), unsafe_allow_html=True)
                    st.altair_chart(ui.create_chart_clean(res['history']), use_container_width=True)
                with col2:
                    st.write("###### 🏢 재무 펀더멘탈")
                    ui.render_fund_scorecard(res['fund_data'])
                    ui.render_financial_table(res['fin_history'])
                
                st.write("###### 🧠 수급 동향")
                ui.render_investor_chart(res['investor_trend'])
                
                # AI 분석 섹션
                st.write("###### 📰 AI 분석 리포트")
                badge_cls = "ai-opinion-buy" if "매수" in res['news']['opinion'] else "ai-opinion-hold"
                st.markdown(f"""<div class='news-ai'><span class='ai-badge {badge_cls}'>{res['news']['opinion']}</span> <b>{res['news']['headline']}</b><br><br>⚠️ Risk: {res['news']['risk']}</div>""", unsafe_allow_html=True)
                
                # 시뮬레이션 버튼
                if st.button(f"🧪 3개월 백테스팅 실행", key=f"sim_{res['code']}"):
                    sim = dl.run_single_stock_simulation(res['history'])
                    if sim: st.success(f"수익률: {sim['return']:.1f}% / 승률: {sim['win_rate']:.1f}% (총 {sim['trades']}회 매매)")
                    else: st.warning("데이터 부족")

# [탭 2] 내 잔고
with tab2:
    portfolio = st.session_state['data_store'].get('portfolio', {})
    if not portfolio: st.info("보유 종목이 없습니다.")
    else:
        with st.spinner("보유 종목 분석 중..."):
            port_results = []
            for name, info in portfolio.items():
                res = dl.analyze_pro(info['code'], name, None, float(info.get('buy_price',0)))
                if res: port_results.append(res)
            
        for res in port_results:
            st.markdown(ui.create_portfolio_card_html(res), unsafe_allow_html=True)
            with st.expander(f"상세 분석 ({res['name']})"):
                if st.button("삭제", key=f"del_p_{res['code']}"):
                    del st.session_state['data_store']['portfolio'][res['name']]
                    utils.update_github_file(st.session_state['data_store'])
                    st.rerun()
                
                col1, col2 = st.columns(2)
                with col1:
                    ui.render_tech_metrics(res['stoch'], res['vol_ratio'])
                    st.markdown(ui.render_chart_legend(), unsafe_allow_html=True)
                    st.altair_chart(ui.create_chart_clean(res['history']), use_container_width=True)
                with col2:
                    ui.render_investor_chart(res['investor_trend'])
                
                # AI 분석 섹션
                st.markdown("---")
                st.write("###### 📰 AI 분석 리포트")
                badge_cls = "ai-opinion-buy" if "매수" in res['news']['opinion'] else "ai-opinion-hold"
                st.markdown(f"""<div class='news-ai'><span class='ai-badge {badge_cls}'>{res['news']['opinion']}</span> <b>{res['news']['headline']}</b><br><br>⚠️ Risk: {res['news']['risk']}</div>""", unsafe_allow_html=True)


# [탭 3] 관심 종목
with tab3:
    watchlist = st.session_state['data_store'].get('watchlist', {})
    if not watchlist: st.info("관심 종목이 없습니다.")
    else:
        with st.spinner("관심 종목 분석 중..."):
            wl_results = []
            for name, info in watchlist.items():
                res = dl.analyze_pro(info['code'], name)
                if res: wl_results.append(res)
            wl_results.sort(key=lambda x: x['score'], reverse=True)
            
        for res in wl_results:
            st.markdown(ui.create_watchlist_card_html(res), unsafe_allow_html=True)
            with st.expander("상세 보기"):
                c1, c2 = st.columns(2)
                with c1:
                    price = st.number_input("매수단가", key=f"p_{res['code']}")
                    if st.button("잔고이동", key=f"mv_{res['code']}"):
                        st.session_state['data_store']['portfolio'][res['name']] = {'code':res['code'], 'buy_price':price}
                        del st.session_state['data_store']['watchlist'][res['name']]
                        utils.update_github_file(st.session_state['data_store'])
                        st.rerun()
                with c2:
                    if st.button("삭제", key=f"del_w_{res['code']}"):
                        del st.session_state['data_store']['watchlist'][res['name']]
                        utils.update_github_file(st.session_state['data_store'])
                        st.rerun()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("###### 📈 기술적 분석")
                    ui.render_tech_metrics(res['stoch'], res['vol_ratio'])
                    ui.render_signal_lights(res['history'].iloc[-1]['RSI'], res['history'].iloc[-1]['MACD'], res['history'].iloc[-1]['MACD_Signal'])
                    ui.render_ma_status(res['ma_status'])
                    st.markdown(ui.render_chart_legend(), unsafe_allow_html=True)
                    st.altair_chart(ui.create_chart_clean(res['history']), use_container_width=True)
                with col2:
                    st.write("###### 🏢 재무 펀더멘탈")
                    ui.render_fund_scorecard(res['fund_data'])
                    ui.render_financial_table(res['fin_history'])
                
                st.write("###### 🧠 수급 동향")
                ui.render_investor_chart(res['investor_trend'])
                
                # AI 분석 섹션
                st.write("###### 📰 AI 분석 리포트")
                badge_cls = "ai-opinion-buy" if "매수" in res['news']['opinion'] else "ai-opinion-hold"
                st.markdown(f"""<div class='news-ai'><span class='ai-badge {badge_cls}'>{res['news']['opinion']}</span> <b>{res['news']['headline']}</b><br><br>⚠️ Risk: {res['news']['risk']}</div>""", unsafe_allow_html=True)
                
                # 시뮬레이션 버튼
                if st.button(f"🧪 3개월 백테스팅 실행", key=f"sim_wl_{res['code']}"):
                    sim = dl.run_single_stock_simulation(res['history'])
                    if sim: st.success(f"수익률: {sim['return']:.1f}% / 승률: {sim['win_rate']:.1f}% (총 {sim['trades']}회 매매)")
                    else: st.warning("데이터 부족")

# 4. 사이드바
with st.sidebar:
    st.write("### ⚙️ 기능 메뉴")
    with st.expander("🔍 AI 종목 발굴", expanded=True):
        themes = { "직접 입력": None, "반도체": "반도체", "2차전지": "2차전지", "AI": "인공지능", "로봇": "로봇", "제약": "제약업체" }
        sel = st.selectbox("테마 선택", list(themes.keys()))
        kwd = st.text_input("검색어") if sel == "직접 입력" else themes[sel]
        
        if st.button("🚀 분석 시작"):
            if not kwd: st.warning("키워드 입력 필요")
            else:
                with st.spinner("분석 중..."):
                    df_krx = dl.get_krx_list_safe()
                    # 1. 종목명 일치 확인
                    code = df_krx[df_krx['Name']==kwd]['Code'].iloc[0] if kwd in df_krx['Name'].values else None
                    if code:
                        res = dl.analyze_pro(code, kwd)
                        if res: 
                            st.session_state['preview_list'] = [res]
                            st.session_state['current_theme_name'] = kwd
                            st.rerun()
                    else:
                        # 2. AI 추천 / 테마 검색
                        stocks, msg = dl.get_ai_recommended_stocks(kwd)
                        if not stocks: stocks, msg = dl.get_naver_theme_stocks(kwd)
                        
                        if stocks:
                            st.session_state['preview_list'] = stocks
                            st.session_state['current_theme_name'] = kwd
                            st.rerun()
                        else: st.error("결과 없음")

    with st.expander("📡 시장 레이더"):
        mode = st.radio("모드", ["KOSPI 시총상위", "KOSDAQ 시총상위"])
        if st.button("🛰️ 스캔"):
            mkt = "KOSPI" if "KOSPI" in mode else "KOSDAQ"
            df = dl.get_krx_list_safe()
            # 간단히 상위 50개만
            cands = dl.scan_market_candidates(df.head(50), st.progress(0), st.empty())
            if cands:
                st.session_state['preview_list'] = cands
                st.rerun()
            else: st.warning("조건 만족 종목 없음")
    
    st.markdown("---")
    with st.expander("➕ 수동 추가"):
        n = st.text_input("이름"); c = st.text_input("코드")
        if st.button("추가"):
            st.session_state['data_store']['watchlist'][n] = {'code': c}
            utils.update_github_file(st.session_state['data_store'])
            st.rerun()
