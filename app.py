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
import urllib.parse
from io import StringIO
import re

# ==============================================================================
# [설정 및 상수 정의]
# ==============================================================================
st.set_page_config(page_title="Quant Sniper V50.0 (The Architect)", page_icon="💎", layout="wide")

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

# 보안 키 로드 (실패 시 빈 값 처리)
SECRETS = {
    "GITHUB": st.secrets.get("GITHUB_TOKEN", ""),
    "TELEGRAM": st.secrets.get("TELEGRAM_TOKEN", ""),
    "CHAT_ID": st.secrets.get("CHAT_ID", ""),
    "GOOGLE": st.secrets.get("GOOGLE_API_KEY", "")
}

# ==============================================================================
# [1. UI/UX 스타일 매니저]
# ==============================================================================
class UIManager:
    @staticmethod
    def apply_styles():
        st.markdown("""
        <style>
            .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
            .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
            .fund-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; background-color: #F9FAFB; padding: 15px; border-radius: 12px; margin-top: 10px; }
            .fund-item { text-align: center; }
            .fund-label { font-size: 11px; color: #8B95A1; }
            .fund-val { font-size: 16px; font-weight: 800; color: #333; }
            .badge { padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; display: inline-block; margin: 2px; }
            .badge.buy { background-color: #E8F3FF; color: #3182F6; }
            .badge.sell { background-color: #FFF1F1; color: #F04452; }
            .badge.neu { background-color: #F2F4F6; color: #4E5968; }
            .badge.vol { background-color: #FFF8E1; color: #D9480F; }
            .news-ai { background: #F3F9FE; padding: 15px; border-radius: 12px; border: 1px solid #D0EBFF; margin-top: 10px; }
            .metric-box { background: #F9FAFB; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #E5E8EB; height: 100%; }
        </style>
        """, unsafe_allow_html=True)

    @staticmethod
    def render_card_html(res, is_portfolio=False):
        # 색상 및 텍스트 로직 분리
        score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
        chg_color = "#F04452" if res['change_rate'] > 0 else ("#3182F6" if res['change_rate'] < 0 else "#333")
        chg_txt = f"{res['change_rate']:+.2f}%"
        
        # 포트폴리오 전용 데이터
        profit_html = ""
        if is_portfolio and res.get('my_buy_price'):
            profit_rate = res['profit_rate']
            p_color = "#F04452" if profit_rate > 0 else "#3182F6"
            profit_html = f"""
            <div style='text-align:right; margin-bottom:5px;'>
                <div style='font-size:20px; font-weight:800; color:{p_color};'>{profit_rate:+.2f}%</div>
                <div style='font-size:11px; color:#888;'>내 평단: {res['my_buy_price']:,}원</div>
            </div>
            """

        html = f"""
        <div class='toss-card' style='border-left: 5px solid {score_col};'>
            <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
                <div>
                    <span style='font-size:18px; font-weight:800;'>{res['name']}</span>
                    <span style='font-size:12px; color:#888; margin-left:4px;'>{res['code']}</span>
                    {'<span class="badge buy">AI 보유중</span>' if is_portfolio else ''}
                    <div style='font-size:24px; font-weight:bold; margin-top:4px;'>
                        {res['price']:,}원 <span style='font-size:16px; color:{chg_color};'>{chg_txt}</span>
                    </div>
                </div>
                <div>
                    {profit_html}
                    <div style='text-align:right;'>
                        <span style='font-size:24px; font-weight:800; color:{score_col};'>{res['score']}점</span>
                    </div>
                </div>
            </div>
            <div style='margin-top:15px; padding-top:10px; border-top:1px solid #eee; display:flex; justify-content:space-between; font-size:12px; font-weight:600;'>
                <span style='color:#555;'>🎯 목표: {res['strategy']['target']:,}원</span>
                <span style='color:#555;'>🛡️ 손절: {res['strategy']['stop']:,}원</span>
                <span style='color:{score_col};'>{res['strategy']['action']}</span>
            </div>
        </div>
        """
        return html

# ==============================================================================
# [2. 데이터 매니저 (GitHub, Crawling, API)]
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
    def get_market_tickers():
        try:
            return fdr.StockListing('KRX')
        except:
            return pd.DataFrame()

    @staticmethod
    def get_stock_data(code, days=365):
        try:
            df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=days))
            return df
        except:
            return pd.DataFrame()

    @staticmethod
    def get_financial_info(code):
        # 네이버 금융 크롤링 (안정성 강화)
        try:
            url = f"https://finance.naver.com/item/main.naver?code={code}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers, timeout=3)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            def get_text(selector):
                elements = soup.select(selector)
                return elements[0].text.strip().replace(',', '') if elements else "0"

            per = float(get_text("#_per") or 0)
            pbr = float(get_text("#_pbr") or 0)
            div = float(get_text("#_dvr") or 0)
            return {"per": per, "pbr": pbr, "div": div}
        except:
            return {"per": 0, "pbr": 0, "div": 0}

# ==============================================================================
# [3. AI 엔진 (Gemini, Parsing)]
# ==============================================================================
class AIEngine:
    @staticmethod
    def clean_json_string(text):
        # Markdown 코드 블록 제거 및 순수 JSON 추출
        text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end+1]
        return text

    @staticmethod
    def get_analysis(company_name, context):
        if not SECRETS["GOOGLE"]:
            return {"score": 0, "headline": "API 키 없음", "opinion": "중립", "method": "none"}

        role = "보유자 포트폴리오 매니저" if context.get('is_holding') else "헤지펀드 수석 전략가"
        prompt = f"""
        당신은 {role}입니다. '{company_name}' 주식에 대해 다음 데이터를 바탕으로 분석하세요.
        
        [데이터]
        - 기술적 추세: {context.get('trend')}
        - PBR: {context.get('pbr')}, PER: {context.get('per')}
        - 수급: {context.get('supply')}
        - 현재 수익률: {context.get('profit_rate', 0):.2f}% (보유중일 경우)

        반드시 아래 JSON 포맷으로만 응답하세요. 잡담 금지.
        {{
            "score": (뉴스/재료 점수 -10~10),
            "opinion": "매수/매도/관망/홀딩 중 택1",
            "catalyst": "핵심재료 (5단어 이내)",
            "headline": "한 줄 요약 코멘트 (존댓말)",
            "risk": "리스크 요인 (1문장)"
        }}
        """
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={SECRETS['GOOGLE']}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
            
            if res.status_code == 200:
                raw_text = res.json()['candidates'][0]['content']['parts'][0]['text']
                clean_text = AIEngine.clean_json_string(raw_text)
                return json.loads(clean_text)
        except Exception as e:
            print(f"AI Error: {e}")
        
        return {"score": 0, "headline": "AI 분석 실패 (일시적 오류)", "opinion": "중립", "method": "error"}

    @staticmethod
    def recommend_stocks(keyword):
        if not SECRETS["GOOGLE"]: return [], "API Key 필요"
        
        prompt = f"""
        '{keyword}' 관련 한국 주식 대장주 및 수혜주 5개를 추천해줘.
        JSON 형식: [{{"name": "종목명", "code": "6자리코드", "reason": "이유"}}]
        """
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={SECRETS['GOOGLE']}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
            raw = res.json()['candidates'][0]['content']['parts'][0]['text']
            return json.loads(AIEngine.clean_json_string(raw)), "AI 추천 완료"
        except:
            return [], "AI 추천 실패"

# ==============================================================================
# [4. 분석 엔진 (Technical & Strategy)]
# ==============================================================================
class Analyzer:
    @staticmethod
    def calculate_indicators(df):
        if df.empty: return df
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        short = df['Close'].ewm(span=12, adjust=False).mean()
        long = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = short - long
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        return df

    @staticmethod
    def get_strategy(df, score, my_buy_price=None):
        curr = df.iloc[-1]
        price = int(curr['Close'])
        atr = price * 0.03 # 간편 ATR
        
        # 보유 여부에 따른 전략 분기
        if my_buy_price and my_buy_price > 0:
            profit_rate = (price - my_buy_price) / my_buy_price * 100
            if profit_rate > 5:
                action = "🔥 수익 홀딩" if score >= 60 else "🟠 익절 고민"
            elif profit_rate < -5:
                action = "💧 버티기" if score >= 60 else "✂️ 손절 권장"
            else:
                action = "👀 관망 (보유)"
            
            return {
                "action": action,
                "target": int(my_buy_price * 1.1),
                "stop": int(my_buy_price * 0.95),
                "profit_rate": profit_rate
            }
        else:
            # 신규 진입 전략
            if score >= 70: action = "🚀 강력 매수"
            elif score >= 50: action = "📈 분할 매수"
            else: action = "👀 관망"
            
            return {
                "action": action,
                "target": int(price + (atr * 3)),
                "stop": int(price - (atr * 1.5)),
                "profit_rate": 0
            }

    @staticmethod
    def analyze_stock(code, name, my_buy_price=0):
        df = DataManager.get_stock_data(code)
        if df.empty or len(df) < 60: return None
        
        df = Analyzer.calculate_indicators(df)
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 1. 기술적 점수 (50점 만점)
        tech_score = 0
        if curr['Close'] > curr['MA20']: tech_score += 20
        if curr['MACD'] > curr['MACD_Signal']: tech_score += 15
        if curr['RSI'] < 70 and curr['RSI'] > 30: tech_score += 15
        
        # 2. 거래량 분석
        vol_ratio = curr['Volume'] / df['Volume'].rolling(20).mean().iloc[-1] if df['Volume'].rolling(20).mean().iloc[-1] > 0 else 1
        
        # 3. 펀더멘털 (20점 만점)
        fund = DataManager.get_financial_info(code)
        fund_score = 0
        if 0 < fund['pbr'] < 3: fund_score += 10
        if 0 < fund['per'] < 20: fund_score += 10
        
        # 4. AI 분석 (30점 만점)
        context = {
            "trend": "상승세" if curr['Close'] > curr['MA20'] else "하락세",
            "pbr": fund['pbr'], "per": fund['per'],
            "supply": "외인매수" if vol_ratio > 1.5 else "일반",
            "is_holding": True if my_buy_price > 0 else False,
            "profit_rate": (curr['Close'] - my_buy_price)/my_buy_price*100 if my_buy_price else 0
        }
        ai_res = AIEngine.get_analysis(name, context)
        ai_score = (ai_res.get('score', 0) + 10) * 1.5  # -10~10 -> 0~30 변환
        
        total_score = int(tech_score + fund_score + ai_score)
        total_score = min(max(total_score, 0), 100)
        
        strategy = Analyzer.get_strategy(df, total_score, my_buy_price)
        
        return {
            "name": name, "code": code, "price": int(curr['Close']),
            "change_rate": (curr['Close'] - prev['Close']) / prev['Close'] * 100,
            "score": total_score,
            "strategy": strategy,
            "history": df,
            "fund": fund,
            "ai": ai_res,
            "my_buy_price": my_buy_price,
            "profit_rate": strategy['profit_rate'],
            "vol_ratio": vol_ratio
        }

# ==============================================================================
# [5. 메인 앱 실행 (Execution)]
# ==============================================================================
def main():
    UIManager.apply_styles()
    
    # 세션 상태 초기화
    if 'data_store' not in st.session_state:
        st.session_state['data_store'] = DataManager.load_github_data()
    if 'analysis_result' not in st.session_state:
        st.session_state['analysis_result'] = []

    st.title("💎 Quant Sniper V50.0 (The Architect)")
    st.caption("AI-Powered All-in-One Investment Dashboard")

    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["🔍 종목 발굴", "💰 포트폴리오", "⚙️ 설정/관리"])

    # --- TAB 1: 종목 발굴 ---
    with tab1:
        col_search, col_res = st.columns([1, 3])
        with col_search:
            st.markdown("### 🕵️ 테마 스캐너")
            theme_key = st.selectbox("테마 선택", ["직접 입력"] + list(CONSTANTS['THEMES'].keys()))
            keyword = st.text_input("검색어") if theme_key == "직접 입력" else CONSTANTS['THEMES'][theme_key]
            
            if st.button("🚀 분석 시작", use_container_width=True):
                with st.spinner(f"'{keyword}' 관련주 AI 발굴 및 심층 분석 중..."):
                    # 1. AI 추천 or 네이버 테마
                    tickers, msg = AIEngine.recommend_stocks(keyword)
                    if not tickers: # AI 실패시 fallback 없음 (단순화 위해 생략, 필요시 추가 가능)
                        st.error("종목을 찾을 수 없습니다.")
                    else:
                        st.success(f"{len(tickers)}개 종목 발견! 분석 시작...")
                        results = []
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            futures = [executor.submit(Analyzer.analyze_stock, t['code'], t['name']) for t in tickers]
                            for f in concurrent.futures.as_completed(futures):
                                res = f.result()
                                if res: results.append(res)
                        results.sort(key=lambda x: x['score'], reverse=True)
                        st.session_state['analysis_result'] = results

        with col_res:
            if st.session_state['analysis_result']:
                for res in st.session_state['analysis_result']:
                    st.markdown(UIManager.render_card_html(res), unsafe_allow_html=True)
                    
                    with st.expander(f"📊 {res['name']} 상세 분석"):
                        c1, c2 = st.columns(2)
                        with c1:
                            chart = alt.Chart(res['history'].reset_index().tail(100)).mark_line().encode(
                                x=alt.X('Date:T', axis=None), y=alt.Y('Close:Q', scale=alt.Scale(zero=False))
                            ).properties(height=200)
                            st.altair_chart(chart, use_container_width=True)
                        with c2:
                            st.info(f"🤖 AI 의견: {res['ai']['headline']}")
                            st.write(f"PER: {res['fund']['per']} / PBR: {res['fund']['pbr']}")
                        
                        # 매수 버튼
                        if st.button(f"🛒 관심/매수 등록 ({res['name']})", key=f"buy_{res['code']}"):
                            st.session_state['data_store']['watchlist'][res['name']] = {"code": res['code']}
                            if DataManager.save_github_data(st.session_state['data_store']):
                                st.toast("저장 완료!")
            else:
                st.info("왼쪽에서 테마를 선택하고 분석을 시작하세요.")

    # --- TAB 2: 포트폴리오 ---
    with tab2:
        port_data = st.session_state['data_store'].get('portfolio', {})
        if not port_data:
            st.warning("보유 종목이 없습니다.")
        else:
            # 포트폴리오 분석 실행
            if st.button("🔄 내 잔고 실시간 진단"):
                with st.spinner("보유 종목 정밀 진단 중..."):
                    res_list = []
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        futures = []
                        for name, info in port_data.items():
                            futures.append(executor.submit(Analyzer.analyze_stock, info['code'], name, info.get('buy_price', 0)))
                        for f in concurrent.futures.as_completed(futures):
                            if f.result(): res_list.append(f.result())
                    st.session_state['port_analysis'] = res_list
            
            # 차트 시각화 (비중)
            if port_data:
                df_port = pd.DataFrame([
                    {"name": k, "value": v.get('buy_price', 10000)} for k, v in port_data.items()
                ])
                pie = alt.Chart(df_port).mark_arc(innerRadius=50).encode(
                    theta="value", color="name", tooltip=["name", "value"]
                ).properties(title="보유 비중")
                st.altair_chart(pie, use_container_width=True)

            # 리스트 출력
            if 'port_analysis' in st.session_state:
                for res in st.session_state['port_analysis']:
                    st.markdown(UIManager.render_card_html(res, is_portfolio=True), unsafe_allow_html=True)
                    with st.expander(f"📝 {res['name']} 대응 전략"):
                        st.markdown(f"### AI 조언: {res['ai']['opinion']}")
                        st.write(res['ai']['headline'])
                        st.caption(f"리스크: {res['ai']['risk']}")

    # --- TAB 3: 관리 ---
    with tab3:
        st.write("### 💾 데이터 관리")
        st.json(st.session_state['data_store'])
        if st.button("🗑️ 전체 데이터 초기화"):
            st.session_state['data_store'] = {"portfolio": {}, "watchlist": {}}
            DataManager.save_github_data(st.session_state['data_store'])
            st.rerun()

        # 수동 추가 기능
        with st.form("manual_add"):
            st.write("종목 수동 추가")
            name = st.text_input("종목명")
            code = st.text_input("종목코드")
            price = st.number_input("평단가 (0이면 관심종목)", value=0)
            if st.form_submit_button("추가"):
                target = 'portfolio' if price > 0 else 'watchlist'
                st.session_state['data_store'][target][name] = {"code": code, "buy_price": price}
                DataManager.save_github_data(st.session_state['data_store'])
                st.success("추가 완료")
                st.rerun()

if __name__ == "__main__":
    main()
