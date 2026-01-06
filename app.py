import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
import json
import time
import base64
import altair as alt
from pykrx import stock
import concurrent.futures
from bs4 import BeautifulSoup
import re
import random

# ==============================================================================
# [설정 및 상수 정의]
# ==============================================================================
st.set_page_config(page_title="Quant Sniper V50.0 (Perfect Merge)", page_icon="💎", layout="wide")

CONSTANTS = {
    "REPO_OWNER": "echobm101-del",
    "REPO_NAME": "my_stock-bot",
    "FILE_PATH": "my_watchlist_v7.json",
    "THEMES": {
        "반도체": "반도체", "2차전지": "2차전지", "HBM": "HBM", 
        "AI/로봇": "지능형로봇", "제약바이오": "제약업체", 
        "자동차": "자동차", "방산": "방위산업", "원전": "원자력발전", 
        "초전도체": "초전도체", "저PBR(은행)": "은행"
    }
}

SECRETS = {
    "GITHUB": st.secrets.get("GITHUB_TOKEN", ""),
    "TELEGRAM": st.secrets.get("TELEGRAM_TOKEN", ""),
    "CHAT_ID": st.secrets.get("CHAT_ID", ""),
    "GOOGLE": st.secrets.get("GOOGLE_API_KEY", "")
}

# ==============================================================================
# [1. UI/UX 스타일 매니저 - V49.2 스타일 100% 복원]
# ==============================================================================
class UIManager:
    @staticmethod
    def apply_styles():
        st.markdown("""
        <style>
            .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
            .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
            
            /* 기술적 지표 배지 스타일 */
            .tech-status-box { display: flex; gap: 10px; margin-bottom: 10px; }
            .status-badge { flex: 1; padding: 12px 10px; border-radius: 12px; text-align: center; font-size: 13px; font-weight: 700; color: #4E5968; background: #F2F4F6; border: 1px solid #E5E8EB; }
            .status-badge.buy { background-color: #E8F3FF; color: #3182F6; border-color: #3182F6; }
            .status-badge.sell { background-color: #FFF1F1; color: #F04452; border-color: #F04452; }
            .status-badge.vol { background-color: #FFF8E1; color: #D9480F; border-color: #FFD8A8; }
            .status-badge.neu { background-color: #FFF9DB; color: #F08C00; border-color: #FFEC99; }

            /* 재무 그리드 스타일 */
            .fund-grid-v2 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 10px; background-color: #F9FAFB; padding: 15px; border-radius: 12px; }
            .fund-item-v2 { text-align: center; }
            .fund-title-v2 { font-size: 12px; color: #8B95A1; margin-bottom: 5px; }
            .fund-value-v2 { font-size: 18px; font-weight: 800; color: #333D4B; }
            .fund-desc-v2 { font-size: 11px; font-weight: 600; margin-top: 4px; display: inline-block; padding: 2px 6px; border-radius: 4px;}

            /* AI 뉴스 스타일 */
            .news-ai { background: #F3F9FE; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #D0EBFF; color: #333; }
            .ai-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; margin-bottom: 6px; }
            .ai-opinion-buy { background-color: #E8F3FF; color: #3182F6; border: 1px solid #3182F6; }
            .ai-opinion-sell { background-color: #FFF1F1; color: #F04452; border: 1px solid #F04452; }
            .ai-opinion-hold { background-color: #F2F4F6; color: #4E5968; border: 1px solid #4E5968; }

            .badge-clean { font-size: 12px; padding: 4px 8px; border-radius: 6px; }
            .profit-positive { color: #F04452; font-weight: 800; font-size: 20px; }
            .profit-negative { color: #3182F6; font-weight: 800; font-size: 20px; }
        </style>
        """, unsafe_allow_html=True)

    @staticmethod
    def render_card_html(res, is_portfolio=False):
        score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
        buy_price = res['strategy'].get('target', 0) * 0.9 # 역산 추정
        target_price = res['strategy']['target']
        stop_price = res['strategy']['stop']
        
        chg = res.get('change_rate', 0.0)
        chg_color = "#F04452" if chg > 0 else ("#3182F6" if chg < 0 else "#333")
        chg_txt = f"({chg:+.2f}%)" if chg != 0 else "(-)"
        
        backtest_txt = f"⚡ 승률 High" if res['score'] > 70 else "⚡ 분석 완료"

        # 포트폴리오 전용 섹션
        profit_html = ""
        port_border_style = f"border-left: 5px solid {score_col};"
        
        if is_portfolio and res.get('my_buy_price'):
            profit_rate = res['profit_rate']
            profit_val = (res['price'] - res['my_buy_price']) 
            p_color = "#F04452" if profit_rate > 0 else "#3182F6"
            port_border_style = f"border: 2px solid {p_color}40; background-color: {p_color}05;"
            
            profit_html = f"""
            <div style='text-align:right;'>
                <div class='profit-positive' style='color:{p_color};'>{profit_rate:+.2f}%</div>
                <div style='font-size:12px; font-weight:600; color:{p_color};'>{profit_val:+,}원</div>
            </div>
            """

        html = f"""
        <div class='toss-card' style='{port_border_style}'>
          <div style='display:flex; justify-content:space-between; align-items:center;'>
              <div>
                  <span style='font-size:18px; font-weight:800;'>{res['name']}</span>
                  <span style='font-size:12px; color:#888; margin-left:4px;'>{res['code']}</span>
                  <div style='font-size:24px; font-weight:800; margin-top:4px;'>{res['price']:,}원 <span style='font-size:16px; color:{chg_color}; font-weight:600; margin-left:5px;'>{chg_txt}</span></div>
              </div>
              <div style='text-align:right;'>
                  {profit_html if is_portfolio else f"<div style='font-size:28px; font-weight:800; color:{score_col};'>{res['score']}점</div><div class='badge-clean' style='background-color:{score_col}20; color:{score_col}; font-weight:700;'>{res['strategy']['action']}</div>"}
              </div>
          </div>
          <div style='margin-top:15px; padding-top:10px; border-top:1px solid #F2F4F6; display:grid; grid-template-columns: 1fr 1fr 1fr; gap:5px; font-size:12px; font-weight:700; text-align:center;'>
              <div style='color:#3182F6; background-color:#E8F3FF; padding:6px; border-radius:6px;'>🛒 {("평단 " + str(res['my_buy_price'])) if is_portfolio else "현재가"}</div>
              <div style='color:#F04452; background-color:#FFF1F1; padding:6px; border-radius:6px;'>💰 목표 {target_price:,}</div>
              <div style='color:#4E5968; background-color:#F2F4F6; padding:6px; border-radius:6px;'>🛡️ 손절 {stop_price:,}</div>
          </div>
          <div style='margin-top:8px; display:flex; justify-content:space-between; align-items:center;'>
                <span style='font-size:11px; font-weight:700; color:#555;'>{backtest_txt}</span>
                <span style='font-size:12px; color:#888;'>{res.get('trend_txt', '분석중')}</span>
          </div>
        </div>
        """
        return html

    @staticmethod
    def render_tech_metrics(res):
        # RSI, MACD 신호등 복원
        rsi = res['history'].iloc[-1]['RSI']
        macd = res['history'].iloc[-1]['MACD']
        sig = res['history'].iloc[-1]['MACD_Signal']
        
        rsi_cls = "buy" if rsi <= 35 else ("sell" if rsi >= 70 else "neu")
        rsi_msg = "저평가 (Good)" if rsi <= 35 else ("과열 (Bad)" if rsi >= 70 else "중립")
        
        macd_cls = "buy" if macd > sig else "sell"
        macd_msg = "상승 추세" if macd > sig else "하락 반전"

        html = f"""
        <div class='tech-status-box'>
            <div class='status-badge {rsi_cls}'>
                <div>📊 RSI ({rsi:.1f})</div>
                <div style='font-size:15px; margin-top:4px; font-weight:800;'>{rsi_msg}</div>
            </div>
            <div class='status-badge {macd_cls}'>
                <div>🌊 MACD</div>
                <div style='font-size:15px; margin-top:4px; font-weight:800;'>{macd_msg}</div>
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

    @staticmethod
    def render_fund_scorecard(fund):
        # 재무제표 카드 복원
        per_col = "#F04452" if 0 < fund['per'] < 10 else "#333"
        pbr_col = "#F04452" if 0 < fund['pbr'] < 1 else "#333"
        
        html = f"""
        <div class='fund-grid-v2'>
          <div class='fund-item-v2'><div class='fund-title-v2'>PER</div><div class='fund-value-v2' style='color:{per_col}'>{fund['per']:.1f}배</div></div>
          <div class='fund-item-v2'><div class='fund-title-v2'>PBR</div><div class='fund-value-v2' style='color:{pbr_col}'>{fund['pbr']:.1f}배</div></div>
          <div class='fund-item-v2'><div class='fund-title-v2'>배당률</div><div class='fund-value-v2'>{fund['div']:.1f}%</div></div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

# ==============================================================================
# [2. 데이터 매니저 (GitHub, Crawling, API) - 안정성 강화]
# ==============================================================================
class DataManager:
    @staticmethod
    def load_github_data():
        if not SECRETS["GITHUB"]: return {"portfolio": {}, "watchlist": {}}
        try:
            url = f"https://api.github.com/repos/{CONSTANTS['REPO_OWNER']}/{CONSTANTS['REPO_NAME']}/contents/{CONSTANTS['FILE_PATH']}"
            headers = {"Authorization": f"token {SECRETS['GITHUB']}", "Accept": "application/vnd.github.v3+json"}
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                content = base64.b64decode(r.json()['content']).decode('utf-8')
                return json.loads(content)
        except Exception as e:
            print(f"GitHub Load Error: {e}")
        return {"portfolio": {}, "watchlist": {}}

    @staticmethod
    def save_github_data(new_data):
        if not SECRETS["GITHUB"]: return False
        try:
            url = f"https://api.github.com/repos/{CONSTANTS['REPO_OWNER']}/{CONSTANTS['REPO_NAME']}/contents/{CONSTANTS['FILE_PATH']}"
            headers = {"Authorization": f"token {SECRETS['GITHUB']}", "Accept": "application/vnd.github.v3+json"}
            r_get = requests.get(url, headers=headers)
            sha = r_get.json().get('sha') if r_get.status_code == 200 else None
            
            payload = {
                "message": "Update from Quant Sniper V50",
                "content": base64.b64encode(json.dumps(new_data, indent=4, ensure_ascii=False).encode('utf-8')).decode('utf-8')
            }
            if sha: payload["sha"] = sha
            
            r_put = requests.put(url, headers=headers, json=payload)
            return r_put.status_code in [200, 201]
        except Exception as e:
            st.error(f"저장 실패: {e}")
            return False

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_stock_data(code, days=365):
        try:
            df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=days))
            return df
        except:
            return pd.DataFrame()

    @staticmethod
    def get_financial_info(code):
        try:
            url = f"https://finance.naver.com/item/main.naver?code={code}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers, timeout=3)
            soup = BeautifulSoup(res.text, 'html.parser')
            def get_text(selector):
                elements = soup.select(selector)
                return elements[0].text.strip().replace(',', '') if elements else "0"
            return {
                "per": float(get_text("#_per") or 0),
                "pbr": float(get_text("#_pbr") or 0),
                "div": float(get_text("#_dvr") or 0)
            }
        except:
            return {"per": 0, "pbr": 0, "div": 0}

# ==============================================================================
# [3. AI 엔진 (Gemini, Parsing) - V50 안정성]
# ==============================================================================
class AIEngine:
    @staticmethod
    def clean_json_string(text):
        text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1: return text[start:end+1]
        return text

    @staticmethod
    def get_analysis(company_name, context):
        if not SECRETS["GOOGLE"]:
            return {"score": 0, "headline": "API Key 없음", "opinion": "중립", "method": "none", "catalyst": "-", "risk": "-"}

        role = "보유자 포트폴리오 매니저" if context.get('is_holding') else "헤지펀드 수석 전략가"
        prompt = f"""
        당신은 {role}입니다. '{company_name}' 주식에 대해 분석하세요.
        [데이터] 추세: {context.get('trend')}, PBR: {context.get('pbr')}, 수급: {context.get('supply')}
        반드시 JSON 포맷으로만 응답하세요.
        {{
            "score": (-10~10), "opinion": "매수/매도/관망/홀딩",
            "catalyst": "핵심재료 (5단어)", "headline": "한 줄 코멘트", "risk": "리스크"
        }}
        """
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={SECRETS['GOOGLE']}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
            if res.status_code == 200:
                return json.loads(AIEngine.clean_json_string(res.json()['candidates'][0]['content']['parts'][0]['text']))
        except Exception as e: print(f"AI Error: {e}")
        return {"score": 0, "headline": "AI 분석 지연", "opinion": "중립", "method": "error", "catalyst": "분석불가", "risk": "-"}

    @staticmethod
    def recommend_stocks(keyword):
        if not SECRETS["GOOGLE"]: return [], "API Key 필요"
        prompt = f"'{keyword}' 관련 한국 대장주 5개 추천. JSON: [{{\"name\": \"이름\", \"code\": \"코드\", \"reason\": \"이유\"}}]"
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={SECRETS['GOOGLE']}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
            return json.loads(AIEngine.clean_json_string(res.json()['candidates'][0]['content']['parts'][0]['text'])), "완료"
        except: return [], "실패"

# ==============================================================================
# [4. 분석 엔진 (Technical)]
# ==============================================================================
class Analyzer:
    @staticmethod
    def analyze_stock(code, name, my_buy_price=0):
        df = DataManager.get_stock_data(code)
        if df.empty or len(df) < 60: return None
        
        # 지표 계산
        df['MA20'] = df['Close'].rolling(20).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        
        curr = df.iloc[-1]
        
        # 점수 계산
        tech_score = 0
        if curr['Close'] > curr['MA20']: tech_score += 20
        if curr['MACD'] > curr['MACD_Signal']: tech_score += 15
        if 30 < curr['RSI'] < 70: tech_score += 15
        
        fund = DataManager.get_financial_info(code)
        fund_score = 20 if 0 < fund['pbr'] < 3 else 0
        
        context = {
            "trend": "상승" if curr['Close'] > curr['MA20'] else "하락",
            "pbr": fund['pbr'], "supply": "보통", "is_holding": my_buy_price > 0
        }
        ai_res = AIEngine.get_analysis(name, context)
        ai_score = (ai_res.get('score', 0) + 10) * 1.5
        
        total_score = min(max(int(tech_score + fund_score + ai_score), 0), 100)
        
        # 전략
        atr = int(curr['Close'] * 0.03)
        if my_buy_price > 0:
            profit_rate = (curr['Close'] - my_buy_price)/my_buy_price*100
            action = "🔥 홀딩" if total_score >= 60 else "✂️ 정리 고민"
            target, stop = int(my_buy_price * 1.1), int(my_buy_price * 0.95)
        else:
            profit_rate = 0
            action = "🚀 매수" if total_score >= 70 else ("👀 관망" if total_score < 50 else "📈 분할")
            target, stop = int(curr['Close'] + atr*3), int(curr['Close'] - atr*1.5)

        return {
            "name": name, "code": code, "price": int(curr['Close']),
            "change_rate": (curr['Close'] - df.iloc[-2]['Close']) / df.iloc[-2]['Close'] * 100,
            "score": total_score,
            "strategy": {"action": action, "target": target, "stop": stop},
            "history": df, "fund": fund, "ai": ai_res,
            "my_buy_price": my_buy_price, "profit_rate": profit_rate,
            "trend_txt": "상승세 (정배열)" if curr['Close'] > curr['MA20'] else "조정/하락세"
        }

# ==============================================================================
# [5. 메인 앱 실행]
# ==============================================================================
def main():
    UIManager.apply_styles()
    
    if 'data_store' not in st.session_state:
        st.session_state['data_store'] = DataManager.load_github_data()
    if 'analysis_result' not in st.session_state:
        st.session_state['analysis_result'] = []

    st.title("💎 Quant Sniper V50.0 (Ultimate UI)")
    
    tab1, tab2, tab3 = st.tabs(["🔍 종목 발굴", "💰 내 잔고 (Portfolio)", "⚙️ 설정"])

    # --- TAB 1: 종목 발굴 ---
    with tab1:
        col_search, col_res = st.columns([1, 2.5])
        with col_search:
            st.write("### 🕵️ 테마 스캐너")
            theme_key = st.selectbox("테마 선택", ["직접 입력"] + list(CONSTANTS['THEMES'].keys()))
            keyword = st.text_input("검색어") if theme_key == "직접 입력" else CONSTANTS['THEMES'][theme_key]
            
            if st.button("🚀 AI 분석 시작", use_container_width=True):
                with st.spinner(f"'{keyword}' 관련주 정밀 스캔 중..."):
                    tickers, msg = AIEngine.recommend_stocks(keyword)
                    if tickers:
                        st.success(f"{len(tickers)}개 종목 발견!")
                        results = []
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            futures = [executor.submit(Analyzer.analyze_stock, t['code'], t['name']) for t in tickers]
                            for f in concurrent.futures.as_completed(futures):
                                res = f.result()
                                if res: results.append(res)
                        results.sort(key=lambda x: x['score'], reverse=True)
                        st.session_state['analysis_result'] = results
                    else: st.error("종목 없음")

        with col_res:
            if st.session_state['analysis_result']:
                for res in st.session_state['analysis_result']:
                    st.markdown(UIManager.render_card_html(res), unsafe_allow_html=True)
                    
                    with st.expander(f"📊 {res['name']} 상세 분석 펼치기"):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write("###### 📈 기술적 분석")
                            UIManager.render_tech_metrics(res)
                            chart = alt.Chart(res['history'].reset_index().tail(100)).mark_line().encode(
                                x=alt.X('Date:T', axis=None), y=alt.Y('Close:Q', scale=alt.Scale(zero=False))
                            ).properties(height=200)
                            st.altair_chart(chart, use_container_width=True)
                        with c2:
                            st.write("###### 🏢 펀더멘탈")
                            UIManager.render_fund_scorecard(res['fund'])
                            st.markdown(f"""
                            <div class='news-ai'>
                                <div style='display:flex; justify-content:space-between; margin-bottom:5px;'>
                                    <span class='ai-badge ai-opinion-buy'>{res['ai']['opinion']}</span>
                                    <span style='font-size:11px;'>핵심: {res['ai']['catalyst']}</span>
                                </div>
                                <div style='font-size:13px; font-weight:600;'>{res['ai']['headline']}</div>
                                <div style='margin-top:5px; font-size:11px; color:#D9480F;'>⚠️ 리스크: {res['ai']['risk']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        if st.button(f"🛒 관심 등록 ({res['name']})", key=f"wl_{res['code']}"):
                            st.session_state['data_store']['watchlist'][res['name']] = {"code": res['code']}
                            DataManager.save_github_data(st.session_state['data_store'])
                            st.toast("저장 완료!")

    # --- TAB 2: 포트폴리오 ---
    with tab2:
        port_data = st.session_state['data_store'].get('portfolio', {})
        if not port_data:
            st.info("보유 종목이 없습니다.")
        else:
            if st.button("🔄 내 잔고 실시간 진단"):
                with st.spinner("진단 중..."):
                    res_list = []
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        futures = [executor.submit(Analyzer.analyze_stock, v['code'], k, v.get('buy_price', 0)) for k, v in port_data.items()]
                        for f in concurrent.futures.as_completed(futures):
                            if f.result(): res_list.append(f.result())
                    st.session_state['port_analysis'] = res_list

            # 도넛 차트 (V50 신기능)
            if port_data:
                df_port = pd.DataFrame([{"name": k, "value": v.get('buy_price', 1)} for k, v in port_data.items()])
                pie = alt.Chart(df_port).mark_arc(innerRadius=60).encode(
                    theta="value", color="name", tooltip=["name", "value"]
                ).properties(title="보유 비중", height=250)
                st.altair_chart(pie, use_container_width=True)

            if 'port_analysis' in st.session_state:
                for res in st.session_state['port_analysis']:
                    st.markdown(UIManager.render_card_html(res, is_portfolio=True), unsafe_allow_html=True)
                    with st.expander(f"📝 {res['name']} 심층 리포트"):
                        c1, c2 = st.columns(2)
                        with c1:
                            UIManager.render_tech_metrics(res)
                            chart = alt.Chart(res['history'].reset_index().tail(60)).mark_line().encode(
                                x=alt.X('Date:T', axis=None), y=alt.Y('Close:Q', scale=alt.Scale(zero=False))
                            ).properties(height=150)
                            st.altair_chart(chart, use_container_width=True)
                        with c2:
                            st.markdown(f"###### 🤖 {res['ai']['opinion']} 의견")
                            st.write(res['ai']['headline'])
                            st.info(f"목표가: {res['strategy']['target']:,}원 / 손절가: {res['strategy']['stop']:,}원")

    # --- TAB 3: 관리 ---
    with tab3:
        st.json(st.session_state['data_store'])
        with st.form("manual_add"):
            name = st.text_input("종목명")
            code = st.text_input("종목코드")
            price = st.number_input("평단가 (0=관심)", value=0)
            if st.form_submit_button("추가"):
                target = 'portfolio' if price > 0 else 'watchlist'
                st.session_state['data_store'][target][name] = {"code": code, "buy_price": price}
                DataManager.save_github_data(st.session_state['data_store'])
                st.rerun()

if __name__ == "__main__":
    main()
