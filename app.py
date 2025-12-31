import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
import json
import os
import time

# --- [1. 설정 및 파일 저장 기능] ---
st.set_page_config(page_title="Pro Quant Dashboard", page_icon="💎", layout="wide")
DATA_FILE = "my_watchlist_v2.json"
SETTINGS_FILE = "my_settings.json"

def load_watchlist():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_watchlist(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {"token": "", "chat_id": ""}
    return {"token": "", "chat_id": ""}

def save_settings(token, chat_id):
    data = {"token": token, "chat_id": chat_id}
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'watchlist' not in st.session_state: st.session_state['watchlist'] = load_watchlist()
saved_settings = load_settings()
if 'sent_alerts' not in st.session_state: st.session_state['sent_alerts'] = {}

def send_telegram_msg(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        params = {"chat_id": chat_id, "text": message}
        requests.get(url, params=params)
        return True
    except: return False

# --- [스타일 설정] ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .stock-card {
        background-color: #262730;
        border-radius: 15px; padding: 25px; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid #363945;
    }
    .stock-name { font-size: 26px; font-weight: bold; color: #FFFFFF; }
    .price-text { font-size: 36px; font-weight: 800; margin-top: 5px; }
    .profit-plus { color: #FF4B4B; font-weight: bold; }
    .profit-minus { color: #4B88FF; font-weight: bold; }
    .up { color: #FF4B4B; }
    .down { color: #4B88FF; }
    .flat { color: #FAFAFA; }
    .badge-buy { background-color: #FF4B4B; color: white; padding: 4px 8px; border-radius: 4px; font-size: 14px; font-weight: bold; }
    .badge-sell { background-color: #4B88FF; color: white; padding: 4px 8px; border-radius: 4px; font-size: 14px; font-weight: bold; }
    .badge-info { background-color: #555; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; margin-right: 5px; }
    
    /* 목표가 박스 스타일 */
    .target-box { background-color: #333; padding: 10px; border-radius: 8px; text-align: center; margin-top: 10px; min-width: 130px; cursor: pointer; transition: 0.3s; }
    .target-box:hover { background-color: #444; border: 1px solid #777; }
    .target-label { font-size: 12px; color: #aaa; margin-bottom: 4px;}
    .target-val { font-size: 18px; font-weight: bold; }
    .target-reason { font-size: 11px; color: #888; margin-top: 4px; }
    
    /* 상세 설명 숨김/펼치기 스타일 */
    details > summary { list-style: none; outline: none; }
    details > summary::-webkit-details-marker { display: none; }
    .detail-content {
        background-color: #1E1E1E;
        padding: 10px;
        border-radius: 8px;
        margin-top: 8px;
        font-size: 13px;
        line-height: 1.6;
        color: #ddd;
        border: 1px solid #555;
        text-align: left;
    }

    .legend-table { width: 100%; border-collapse: collapse; color: #ddd; font-size: 14px; margin-top: 5px; }
    .legend-table td, .legend-table th { padding: 8px; border-bottom: 1px solid #444; text-align: left; }
    .legend-header { font-weight: bold; color: #fff; background-color: #333; }
    .legend-cat { font-weight: bold; color: #FFD700; width: 100px; }
    
    div.stButton > button {
        background-color: #262730; 
        color: white; 
        border: 1px solid #555;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #333;
        border-color: #FF4B4B;
        color: #FF4B4B;
    }
</style>
""", unsafe_allow_html=True)

# --- [2. 핵심 분석 함수들] ---
def get_realtime_data(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        no_today = soup.select_one('.no_today')
        if not no_today: return None
        price = int(no_today.select_one('.blind').text.replace(',', ''))
        ex_info = soup.select('.no_exday')
        change_type = "보합"
        if ex_info:
            if ex_info[0].select_one('.no_up'): change_type = "상승"
            elif ex_info[0].select_one('.no_down'): change_type = "하락"
        vol_tag = soup.select_one('.no_info .blind')
        volume = int(vol_tag.text.replace(',', '')) if vol_tag else 0
        per = soup.select_one('#_per'); per = per.text if per else "N/A"
        pbr = soup.select_one('#_pbr'); pbr = pbr.text if pbr else "N/A"
        market_cap = soup.select_one('#_market_sum')
        market_cap = market_cap.text.strip().replace('\t', '').replace('\n', '') + "억" if market_cap else "N/A"
        return {"price": price, "change": change_type, "volume": volume, "per": per, "pbr": pbr, "cap": market_cap}
    except: return None

def analyze_technical(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=180))
        if df.empty: return None
        delta = df['Close'].diff(1)
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['StdDev'] = df['Close'].rolling(window=20).std()
        df['Upper'] = df['MA20'] + (df['StdDev'] * 2)
        df['Lower'] = df['MA20'] - (df['StdDev'] * 2)
        df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
        df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA12'] - df['EMA26']
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['VolMA20'] = df['Volume'].rolling(window=20).mean()
        df['High-Low'] = df['High'] - df['Low']
        df['High-PrevClose'] = abs(df['High'] - df['Close'].shift(1))
        df['Low-PrevClose'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['High-Low', 'High-PrevClose', 'Low-PrevClose']].max(axis=1)
        df['ATR'] = df['TR'].rolling(window=14).mean()
        return {
            "df": df, "rsi": rsi.iloc[-1],
            "bb_lower": df['Lower'].iloc[-1], "bb_upper": df['Upper'].iloc[-1],
            "macd": df['MACD'].iloc[-1], "macd_signal": df['Signal'].iloc[-1],
            "price": df['Close'].iloc[-1], "avg_vol": df['VolMA20'].iloc[-1],
            "atr": df['ATR'].iloc[-1]
        }
    except: return None

def draw_chart(df, lower, upper):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color='#FAFAFA', width=2)))
    fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], mode='lines', line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(255, 255, 255, 0.1)', showlegend=False))
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=150, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False)
    return fig

# --- [3. 사이드바 UI] ---
with st.sidebar:
    st.title("⚙️ Control Panel")
    with st.expander("🔔 알림 설정 (필수)", expanded=True):
        tg_token = st.text_input("봇 토큰", value=saved_settings.get("token", ""), type="password")
        tg_id = st.text_input("내 ID", value=saved_settings.get("chat_id", ""))
        c_save, c_test = st.columns(2)
        if c_save.button("💾 설정 저장"):
            save_settings(tg_token, tg_id)
            st.success("저장됨!")
            time.sleep(1)
            st.rerun()
        if c_test.button("테스트 발송"):
            if tg_token and tg_id:
                if send_telegram_msg(tg_token, tg_id, "🚀 알림 시스템 정상 작동 중!"): st.success("성공!")
                else: st.error("실패")
        st.write("---")
        col_check, col_time = st.columns([1.5, 1])
        with col_check: auto_mode = st.checkbox("🔴 자동 감시", value=False)
        with col_time:
            interval_options = {"1분": 60, "3분": 180, "5분": 300, "10분": 600, "30분": 1800}
            selected_label = st.selectbox("주기", list(interval_options.keys()), index=0, label_visibility="collapsed")
            refresh_sec = interval_options[selected_label]
        if auto_mode: st.caption(f"⚡ {selected_label}마다 확인 중...")

    with st.expander("➕ 종목 추가", expanded=False):
        new_name = st.text_input("종목명", placeholder="NAVER")
        new_code = st.text_input("코드", placeholder="035420")
        new_price = st.number_input("평단가", value=0, step=100)
        if st.button("Add Stock"):
            if new_name and new_code:
                st.session_state['watchlist'][new_name] = {"code": new_code, "my_price": int(new_price)}
                save_watchlist(st.session_state['watchlist'])
                st.rerun()
    st.divider()
    if st.session_state['watchlist']:
        for name in list(st.session_state['watchlist'].keys()):
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{name}**")
            if c2.button("✖", key=f"del_{name}"):
                del st.session_state['watchlist'][name]
                save_watchlist(st.session_state['watchlist'])
                st.rerun()

# --- [4. 메인 대시보드 UI] ---
st.title("🧠 AI Quant Master Pro")
st.caption(f"Quantitative Analysis System | {datetime.datetime.now().strftime('%H:%M:%S')}")

if auto_mode: st.info(f"🚨 실시간 자동 감시 중입니다 ({selected_label} 간격) - 창을 켜두세요.")

with st.expander("📘 범례 및 용어 설명서 (여기를 눌러 확인하세요)", expanded=False):
    st.markdown("""
    <table class="legend-table">
        <tr class="legend-header"><th>구분</th><th>항목</th><th>설명</th></tr>
        <tr><td rowspan="2" class="legend-cat">🤖 AI 전략</td><td><b>🚀 목표가</b></td><td>볼린저 밴드 상단 + ATR 돌파 시 상향 조정</td></tr>
        <tr><td><b>🛡️ 손익절</b></td><td>ATR(변동성) 기반 스마트 트레일링 스톱</td></tr>
        <tr><td rowspan="4" class="legend-cat">📊 펀더멘털</td><td><b>PER</b></td><td>주가수익비율 (낮을수록 저평가)</td></tr>
        <tr><td><b>PBR</b></td><td>주가순자산비율 (1배 미만은 자산가치 대비 저평가)</td></tr>
        <tr><td><b>시총</b></td><td>기업의 규모 (안정성 지표)</td></tr>
        <tr><td><b>거래량</b></td><td>평소 대비 150% 이상 폭발 시 '세력 개입/추세 전환'</td></tr>
        <tr><td rowspan="2" class="legend-cat">🚦 신호</td><td><b><span class="badge-buy">매수</span></b></td><td>RSI 침체 + 볼린저 하단 + MACD 상승</td></tr>
        <tr><td><b><span class="badge-sell">매도</span></b></td><td>RSI 과열 + 볼린저 상단 + 추세 꺾임</td></tr>
    </table>
    """, unsafe_allow_html=True)

if st.button("🔄 전체 데이터 새로고침 (Manual Refresh)", use_container_width=True):
    st.rerun()

st.write("")

if not st.session_state['watchlist']: st.info("👈 사이드바에서 종목을 추가해주세요.")
else:
    for name, info in st.session_state['watchlist'].items():
        if isinstance(info, str): code = info; my_price = 0
        else: code = info['code']; my_price = info['my_price']

        basic = get_realtime_data(code)
        tech = analyze_technical(code)
        
        if not basic: continue
        price = basic['price']
        
        profit_html = ""
        if my_price > 0:
            profit_rate = ((price - my_price) / my_price) * 100
            color_class = "profit-plus" if profit_rate > 0 else "profit-minus"
            profit_html = f"<span class='{color_class}' style='font-size:16px; margin-left:10px;'>({profit_rate:.2f}%)</span>"
        
        target_box_html = ""; final_decision = "관망 (Hold)"; badge_class = "badge-info"; score = 0; reasons = []
        ai_target = 0; stop_price = 0
        target_detail_txt = "데이터 부족"; stop_detail_txt = "데이터 부족"

        if tech:
            bb_upper = int(tech['bb_upper'])
            atr_val = int(tech['atr'])
            
            if price >= tech['bb_upper'] * 0.99:
                ai_target = int(price + (tech['atr'] * 2))
                target_reason = f"추세 돌파 (ATR 반영)"
                target_detail_txt = f"<b>🔥 추세 추종 전략 (Trend Following)</b><br>현재 주가가 볼린저 밴드 상단({format(bb_upper, ',')}원)을 돌파하거나 근접했습니다. 강한 상승세로 판단하여, 변동성 지표인 ATR({format(atr_val, ',')}원)의 2배만큼 목표가를 상향 조정했습니다."
            else:
                ai_target = int(tech['bb_upper'])
                target_reason = "볼린저 밴드 상단"
                target_detail_txt = f"<b>📉 평균 회귀 전략 (Mean Reversion)</b><br>현재 주가가 밴드 내부에 있습니다. 통계적으로 주가는 볼린저 밴드 상단({format(bb_upper, ',')}원)에서 저항을 받을 확률이 높습니다. 안전한 이익 실현을 위해 상단 가격을 목표로 잡았습니다."

            stop_price = int(price - (tech['atr'] * 2))
            if stop_price > my_price: 
                stop_reason = f"이익 보전 라인"
                stop_detail_txt = f"<b>🛡️ 이익 보전 (Trailing Stop)</b><br>이미 수익 구간입니다! 주가가 흔들려도 이익을 지킬 수 있도록, 현재가에서 ATR({format(atr_val, ',')}원)의 2배만큼 여유를 둔 가격을 '익절 마지노선'으로 설정했습니다."
            else: 
                stop_reason = f"스마트 손절"
                stop_detail_txt = f"<b>⚠️ 위험 관리 (Smart Stop-loss)</b><br>단순한 % 손절이 아닙니다. 이 종목의 하루 평균 변동폭(ATR {format(atr_val, ',')}원)을 고려하여, '정상적인 흔들림'은 버티고 '추세 이탈' 시에만 매도하도록 계산된 가격입니다."

            # [핵심 수정] 줄바꿈과 공백을 없애서 한 줄로 만듦 (Markdown 해석 방지)
            target_box_html = f"""
            <div style='display:flex; gap:10px; justify-content:flex-end; margin-top:10px;'>
                <details><summary><div class='target-box'><div class='target-label' style='color:#FF4B4B;'>🚀 AI 목표가 (클릭)</div><div class='target-val' style='color:#FF4B4B;'>{format(ai_target, ',')}</div><div class='target-reason'>{target_reason}</div></div></summary><div class='detail-content'>{target_detail_txt}</div></details>
                <details><summary><div class='target-box'><div class='target-label' style='color:#4B88FF;'>🛡️ 손익절가 (클릭)</div><div class='target-val' style='color:#4B88FF;'>{format(stop_price, ',')}</div><div class='target-reason'>{stop_reason}</div></div></summary><div class='detail-content'>{stop_detail_txt}</div></details>
            </div>
            """.replace('\n', '')

            if tech['rsi'] <= 30: score += 1; reasons.append("RSI 과매도")
            elif tech['rsi'] >= 70: score -= 1; reasons.append("RSI 과매수")
            if price <= tech['bb_lower'] * 1.02: score += 1; reasons.append("볼린저 하단")
            elif price >= tech['bb_upper'] * 0.98: score -= 1; reasons.append("볼린저 상단")
            if tech['macd'] > tech['macd_signal']: score += 0.5
            if (basic['volume'] / tech['avg_vol']) >= 1.5: score += 0.5; reasons.append(f"거래량 폭발")

            if score >= 2: final_decision = "🔥 강력 매수"; badge_class = "badge-buy"
            elif score >= 1: final_decision = "✅ 매수 우위"; badge_class = "badge-buy"
            elif score <= -1: final_decision = "⛔ 매도 권장"; badge_class = "badge-sell"

        if auto_mode and tech and tg_token and tg_id:
            alert_type = None
            if price >= ai_target: alert_type = "TARGET_REACHED"
            elif price <= stop_price: alert_type = "STOP_LOSS"
            last_alert = st.session_state['sent_alerts'].get(code)
            if alert_type and last_alert != alert_type:
                alert_title = "🚀 익절 신호" if alert_type == "TARGET_REACHED" else "🛡️ 손절 신호"
                msg = f"📢 [AI 자동 알림]\n{alert_title}\n종목: {name}\n현재: {format(price, ',')}원"
                if send_telegram_msg(tg_token, tg_id, msg):
                    st.toast(f"🔔 {name} 알림 발송!", icon="✅")
                    st.session_state['sent_alerts'][code] = alert_type
        
        css_class = "flat"
        if basic['change'] == "상승": css_class = "up"
        elif basic['change'] == "하락": css_class = "down"
        reason_text = ' / '.join(reasons) if reasons else '신호 대기'

        with st.container():
            final_html = f"<div class='stock-card'><div style='display:flex; justify-content:space-between; align-items:flex-start;'><div><div class='stock-name'>{name} <span style='font-size:16px; color:#aaa;'>{code}</span></div><div class='price-text {css_class}'>{format(price, ',')}원</div><div style='font-size:14px; color:#aaa; margin-top:5px;'>내 평단가: {format(my_price, ',')}원 {profit_html}</div></div><div style='text-align:right;'><span class='{badge_class}' style='font-size: 20px; font-weight:bold;'>{final_decision}</span><div style='margin-top:8px; color:#ccc; font-size:14px;'>{reason_text}</div>{target_box_html}</div></div><hr style='border-color:#444; margin: 15px 0;'><div style='display:flex; gap:15px; font-size:14px; color:#ddd;'><span style='background:#444; padding:3px 8px; border-radius:4px;'>📊 시총: {basic['cap']}</span><span style='background:#444; padding:3px 8px; border-radius:4px;'>💰 PER: {basic['per']}배</span><span style='background:#444; padding:3px 8px; border-radius:4px;'>📈 거래량: {format(basic['volume'], ',')}주</span></div></div>"
            st.markdown(final_html, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns([2, 1, 1])
            if tech:
                with c1:
                    fig = draw_chart(tech['df'], tech['bb_lower'], tech['bb_upper'])
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                with c2:
                    st.write("**지표 분석**")
                    st.progress(min(tech['rsi'], 100)/100)
                    st.caption(f"RSI: {tech['rsi']:.1f}")
                with c3:
                    st.write("**알림**")
                    if st.button(f"📱 {name} 상태 전송", key=f"btn_{code}"):
                        msg = f"📢 [수동 알림]\n{name} ({code})\n현재가: {format(price, ',')}원\n목표가: {format(ai_target, ',')}원\n손절가: {format(stop_price, ',')}원\n\nAI의견: {target_detail_txt.replace('<br>', ' ').replace('<b>','').replace('</b>','')}"
                        if send_telegram_msg(tg_token, tg_id, msg): st.success("전송됨")
                        else: st.error("실패")
        st.divider()

if auto_mode:
    time.sleep(refresh_sec)
    st.rerun()