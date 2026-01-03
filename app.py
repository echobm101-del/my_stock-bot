import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
import json
import os
import time
import base64
import altair as alt
from pykrx import stock
import concurrent.futures
from bs4 import BeautifulSoup
import textwrap
import re
import feedparser
import urllib.parse
import numpy as np
from io import StringIO

# --- [1. UI 스타일링] ---
st.set_page_config(page_title="Quant Sniper V33.0", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    
    .fund-grid-v2 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 10px; background-color: #F9FAFB; padding: 15px; border-radius: 12px; }
    .fund-item-v2 { text-align: center; }
    .fund-title-v2 { font-size: 12px; color: #8B95A1; margin-bottom: 5px; }
    .fund-value-v2 { font-size: 18px; font-weight: 800; color: #333D4B; }
    .fund-desc-v2 { font-size: 11px; font-weight: 600; margin-top: 4px; display: inline-block; padding: 2px 6px; border-radius: 4px;}
    
    .tech-status-box { display: flex; gap: 10px; margin-bottom: 5px; }
    .status-badge { flex: 1; padding: 10px; border-radius: 8px; text-align: center; font-size: 13px; font-weight: 700; color: #4E5968; background: #F2F4F6; border: 1px solid #E5E8EB; }
    .status-badge.buy { background-color: #E8F3FF; color: #3182F6; border-color: #3182F6; }
    .status-badge.sell { background-color: #FFF1F1; color: #F04452; border-color: #F04452; }
    .status-badge.vol { background-color: #FFF8E1; color: #D9480F; border-color: #FFD8A8; }

    .tech-summary { background: #F2F4F6; padding: 10px; border-radius: 8px; font-size: 13px; color: #4E5968; margin-bottom: 10px; font-weight: 600; }
    .ma-badge { padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; margin-right: 5px; background: #EEE; color: #888; }
    .ma-ok { background: #F04452; color: white; }
    
    .news-ai { background: #F3F9FE; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #D0EBFF; color: #333; }
    .ai-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; margin-bottom: 6px; }
    .ai-opinion-buy { background-color: #E8F3FF; color: #3182F6; border: 1px solid #3182F6; }
    .ai-opinion-sell { background-color: #FFF1F1; color: #F04452; border: 1px solid #F04452; }
    .ai-opinion-hold { background-color: #F2F4F6; color: #4E5968; border: 1px solid #4E5968; }
    
    .news-fallback { background: #FFF4E6; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #FFD8A8; color: #D9480F; font-weight: 600; }
    
    .news-scroll-box { max-height: 300px; overflow-y: auto; border: 1px solid #F2F4F6; border-radius: 8px; padding: 10px; }
    .news-box { padding: 8px 0; border-bottom: 1px solid #F2F4F6; font-size: 13px; }
    .news-link { color: #333; text-decoration: none; font-weight: 500; display: block; margin-bottom: 2px;}
    .news-link:hover { color: #3182F6; text-decoration: underline; }
    .news-date { font-size: 11px; color: #999; }
    
    .metric-box { background: #F9FAFB; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #E5E8EB; }
    .metric-title { font-size: 12px; color: #666; }
    .metric-value { font-size: 18px; font-weight: bold; color: #333; }

    .sniper-tag { font-size: 10px; padding: 2px 5px; border-radius: 4px; font-weight: 700; margin-right: 4px; }
    .tag-vol { background: #FFF0EB; color: #D9480F; border: 1px solid #FFD8A8; }
    .tag-smart { background: #E8F3FF; color: #3182F6; border: 1px solid #D0EBFF; }
    .tag-pull { background: #E6FCF5; color: #087F5B; border: 1px solid #B2F2BB; }
    
    .fin-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; margin-bottom: 10px; border: 1px solid #E5E8EB; }
    .fin-table th { background-color: #F9FAFB; padding: 8px; border-bottom: 1px solid #E5E8EB; color: #4E5968; font-weight: 600; }
    .fin-table td { padding: 8px; border-bottom: 1px solid #F2F4F6; color: #333; font-weight: 500; }
    .text-red { color: #F04452; font-weight: 700; }
    .text-blue { color: #3182F6; font-weight: 700; }
    .change-rate { font-size: 10px; color: #888; font-weight: 400; margin-left: 4px; }
</style>
""", unsafe_allow_html=True)

# --- [2. 시각화 및 렌더링 함수] ---

def create_card_html(res):
    score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
    
    buy_price = res['strategy'].get('buy', 0)
    target_price = res['strategy'].get('target', 0)
    stop_price = res['strategy'].get('stop', 0)
    buy_basis = res['strategy'].get('buy_basis', '20일선')
    
    chg = res.get('change_rate', 0.0)
    if chg > 0:
        chg_color = "#F04452"
        chg_txt = f"(+{chg:.2f}% ▲)"
    elif chg < 0:
        chg_color = "#3182F6"
        chg_txt = f"({chg:.2f}% ▼)"
    else:
        chg_color = "#333333"
        chg_txt = f"({chg:.2f}% -)"

    html = f"""
    <div class='toss-card'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <span class='stock-name'>{res['name']}</span>
                <span class='stock-code'>{res['code']}</span>
                <div class='big-price'>
                    {res['price']:,}원 <span style='font-size:16px; color:{chg_color}; font-weight:600; margin-left:5px;'>{chg_txt}</span>
                </div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:28px; font-weight:800; color:{score_col};'>{res['score']}점</div>
                <div class='badge-clean' style='background-color:{score_col}20; color:{score_col};'>{res['strategy']['action']}</div>
            </div>
        </div>
        <div style='margin-top:15px; padding-top:10px; border-top:1px solid #F2F4F6; display:grid; grid-template-columns: 1fr 1fr 1fr; gap:5px; font-size:12px; font-weight:700; text-align:center;'>
            <div style='color:#3182F6; background-color:#E8F3FF; padding:6px; border-radius:6px;'>🔵 매수 {buy_price:,}<br><span style='font-size:10px; opacity:0.7;'>({buy_basis} 기준)</span></div>
            <div style='color:#F04452; background-color:#FFF1F1; padding:6px; border-radius:6px;'>🎯 목표 {target_price:,}<br><span style='font-size:10px; opacity:0.7;'>(익절가)</span></div>
            <div style='color:#4E5968; background-color:#F2F4F6; padding:6px; border-radius:6px;'>🛡️ 손절 {stop_price:,}<br><span style='font-size:10px; opacity:0.7;'>(방어선)</span></div>
        </div>
        <div style='margin-top:8px; color:#888; font-size:12px; text-align:right;'>{res['trend_txt']}</div>
    </div>
    """
    return html

def create_chart_clean(df):
    try:
        chart_data = df.tail(120).copy().reset_index()
        chart_data['Prev_Close'] = chart_data['Close'].shift(1)
        chart_data['Prev_MA20'] = chart_data['MA20'].shift(1)
        chart_data['Buy_Signal'] = (chart_data['Prev_Close'] <= chart_data['Prev_MA20']) & (chart_data['Close'] > chart_data['MA20'])
        chart_data['Sell_Signal'] = (chart_data['Prev_Close'] >= chart_data['Prev_MA20']) & (chart_data['Close'] < chart_data['MA20'])
        
        base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=alt.Axis(format='%m-%d', title=None)))
        band = base.mark_area(opacity=0.15, color='#868E96').encode(y='BB_Lower:Q', y2='BB_Upper:Q')
        line = base.mark_line(color='#000000').encode(y='Close:Q')
        ma20 = base.mark_line(color='#F2A529').encode(y='MA20:Q')
        ma60 = base.mark_line(color='#3182F6').encode(y='MA60:Q')
        
        buy_points = base.mark_point(shape='triangle-up', color='#F04452', size=100, opacity=1).encode(
            y='Close:Q', tooltip=[alt.Tooltip('Date', format='%Y-%m-%d'), alt.Tooltip('Close', format=','), alt.Tooltip('MA20', format=',')]
        ).transform_filter(alt.datum.Buy_Signal == True)
        
        sell_points = base.mark_point(shape='triangle-down', color='#3182F6', size=100, opacity=1).encode(
            y='Close:Q', tooltip=[alt.Tooltip('Date', format='%Y-%m-%d'), alt.Tooltip('Close', format=','), alt.Tooltip('MA20', format=',')]
        ).transform_filter(alt.datum.Sell_Signal == True)

        return (band + line + ma20 + ma60 + buy_points + sell_points).properties(height=250)
    except: return alt.Chart(pd.DataFrame()).mark_text()

def render_tech_metrics(stoch, vol_ratio):
    k = stoch['k']
    if k < 20: stoch_txt = f"🟢 침체 구간 ({k:.1f}%)"; stoch_sub = "매수 기회 탐색"; stoch_cls = "buy"
    elif k > 80: stoch_txt = f"🔴 과열 구간 ({k:.1f}%)"; stoch_sub = "매도/조정 주의"; stoch_cls = "sell"
    else: stoch_txt = f"⚪ 중립 구간 ({k:.1f}%)"; stoch_sub = "추세 지속"; stoch_cls = ""

    if vol_ratio >= 2.0: vol_txt = f"🔥 거래량 폭발 ({vol_ratio*100:.0f}%)"; vol_cls = "vol"
    elif vol_ratio >= 1.2: vol_txt = f"📈 거래량 증가 ({vol_ratio*100:.0f}%)"; vol_cls = "buy"
    else: vol_txt = "☁️ 거래량 평이"; vol_cls = ""

    st.markdown(f"""
    <div class='tech-status-box'>
        <div class='status-badge {stoch_cls}'>
            <div>📊 스토캐스틱</div><div style='font-size:16px; margin-top:4px;'>{stoch_txt}</div><div style='font-size:11px; opacity:0.8;'>{stoch_sub}</div>
        </div>
        <div class='status-badge {vol_cls}'>
            <div>📢 거래강도(전일비)</div><div style='font-size:16px; margin-top:4px;'>{vol_txt}</div><div style='font-size:11px; opacity:0.8;'>평소보다 {vol_ratio:.1f}배 활발</div>
        </div>
    </div>""", unsafe_allow_html=True)

def render_chart_legend():
    return """<div style='display:flex; gap:12px; font-size:12px; color:#555; margin-bottom:8px; align-items:center;'>
        <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#000000; margin-right:4px;'></div>현재가</div>
        <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#F2A529; margin-right:4px;'></div>20일선(생명선)</div>
        <div style='display:flex; align-items:center;'><div style='width:0; height:0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-bottom: 8px solid #F04452; margin-right:4px;'></div>매수시그널(돌파)</div>
        <div style='display:flex; align-items:center;'><div style='width:0; height:0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 8px solid #3182F6; margin-right:4px;'></div>매도시그널(이탈)</div>
    </div>"""

def render_fund_scorecard(fund_data):
    if not fund_data: st.info("재무 정보 로딩 실패 (일시적 오류)"); return
    per = fund_data['per']['val']
    pbr = fund_data['pbr']['val']
    div = fund_data['div']['val']
    per_col = "#F04452" if fund_data['per']['stat']=='good' else ("#3182F6" if fund_data['per']['stat']=='bad' else "#333")
    pbr_col = "#F04452" if fund_data['pbr']['stat']=='good' else ("#3182F6" if fund_data['pbr']['stat']=='bad' else "#333")
    div_col = "#F04452" if fund_data['div']['stat']=='good' else "#333"
    st.markdown(f"""
    <div class='fund-grid-v2'>
        <div class='fund-item-v2'><div class='fund-title-v2'>PER</div><div class='fund-value-v2' style='color:{per_col}'>{per:.1f}배</div><div class='fund-desc-v2' style='background-color:{per_col}20; color:{per_col}'>{fund_data['per']['txt']}</div></div>
        <div class='fund-item-v2'><div class='fund-title-v2'>PBR</div><div class='fund-value-v2' style='color:{pbr_col}'>{pbr:.1f}배</div><div class='fund-desc-v2' style='background-color:{pbr_col}20; color:{pbr_col}'>{fund_data['pbr']['txt']}</div></div>
        <div class='fund-item-v2'><div class='fund-title-v2'>배당률</div><div class='fund-value-v2' style='color:{div_col}'>{div:.1f}%</div><div class='fund-desc-v2' style='background-color:{div_col}20; color:{div_col}'>{fund_data['div']['txt']}</div></div>
    </div>""", unsafe_allow_html=True)

def render_financial_table(df):
    if df.empty:
        st.caption("재무 데이터가 없습니다.")
        return
    html = "<table class='fin-table'><thead><tr><th>구분</th>"
    dates = df['Date'].tolist()
    for d in dates: html += f"<th>{d}</th>"
    html += "</tr></thead><tbody>"
    metrics = ['매출액', '영업이익', '당기순이익']
    for m in metrics:
        html += f"<tr><td>{m}</td>"
        vals = df[m].tolist()
        for i, val in enumerate(vals):
            display_val = f"{int(val):,}"
            change_txt = ""; color_class = ""; arrow = ""
            if i > 0:
                prev = vals[i-1]
                if prev != 0:
                    pct = (val - prev) / abs(prev) * 100
                    if pct > 0: 
                        color_class = "text-red"; arrow = "▲"; change_txt = f"<span class='change-rate'>(+{pct:.1f}%)</span>"
                    elif pct < 0: 
                        color_class = "text-blue"; arrow = "▼"; change_txt = f"<span class='change-rate'>({pct:.1f}%)</span>"
            html += f"<td class='{color_class}'>{display_val} {arrow} {change_txt}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
    st.caption("※ 단위: 억 원 / (괄호): 전분기/전년 대비 증감률")

def render_investor_chart(df):
    if df.empty:
        st.caption("수급 데이터가 없습니다. (장중/집계 지연 가능성)")
        return
    df = df.reset_index()
    if '날짜' not in df.columns: 
        if 'index' in df.columns: df.rename(columns={'index': '날짜'}, inplace=True)
    cum_cols = [c for c in ['Cum_Individual', 'Cum_Foreigner', 'Cum_Institution', 'Cum_Pension'] if c in df.columns]
    df_line = df.melt('날짜', value_vars=cum_cols, var_name='Key', value_name='Cumulative')
    daily_map = {'Cum_Individual': '개인', 'Cum_Foreigner': '외국인', 'Cum_Institution': '기관', 'Cum_Pension': '연기금'}
    if '기관합계' in df.columns: daily_map['Cum_Institution'] = '기관합계'
    def get_daily(row):
        col = daily_map.get(row['Key'])
        if col and col in df.columns: return df.loc[df['날짜'] == row['날짜'], col].values[0]
        return 0
    df_line['Daily'] = df_line.apply(get_daily, axis=1)
    type_map = {'Cum_Individual': '개인', 'Cum_Foreigner': '외국인', 'Cum_Institution': '기관합계', 'Cum_Pension': '연기금'}
    df_line['Type'] = df_line['Key'].map(type_map)
    base = alt.Chart(df_line).encode(x=alt.X('날짜:T', axis=alt.Axis(format='%m-%d', title=None)))
    bar = base.mark_bar(opacity=0.3).encode(y=alt.Y('Daily:Q', axis=alt.Axis(title='일별 순매수 (막대)', titleColor='#888')), color=alt.Color('Type:N'))
    line = base.mark_line().encode(y=alt.Y('Cumulative:Q', axis=alt.Axis(title='누적 순매수 (선)')), color=alt.Color('Type:N', legend=alt.Legend(title="투자자")), tooltip=[alt.Tooltip('날짜:T', format='%Y-%m-%d'), alt.Tooltip('Type:N', title='투자자'), alt.Tooltip('Cumulative:Q', format=',', title='📈 누적'), alt.Tooltip('Daily:Q', format=',', title='💰 당일(강도)')])
    chart = alt.layer(bar, line).resolve_scale(y='independent').properties(height=250)
    st.altair_chart(chart, use_container_width=True)

# --- [3. 데이터 로딩 및 분석 로직] ---
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

@st.cache_data
def get_krx_list():
    try: df = fdr.StockListing('KRX'); return df
    except: return pd.DataFrame()
krx_df = get_krx_list()

def load_from_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return {}
        token = st.secrets["GITHUB_TOKEN"]
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            return json.loads(content)
        return {}
    except: return {}

if 'watchlist' not in st.session_state: st.session_state['watchlist'] = load_from_github()
if 'preview_list' not in st.session_state: st.session_state['preview_list'] = []
if 'current_theme_name' not in st.session_state: st.session_state['current_theme_name'] = ""

@st.cache_data(ttl=1800)
def get_naver_theme_stocks(keyword):
    headers = {'User-Agent': 'Mozilla/5.0'}
    target_link = None
    for page in range(1, 8):
        base_url = f"https://finance.naver.com/sise/theme.naver?&page={page}"
        try:
            res = requests.get(base_url, headers=headers)
            res.encoding = 'EUC-KR' 
            soup = BeautifulSoup(res.text, 'html.parser')
            themes = soup.select('table.type_1 tr td.col_type1 a')
            for t in themes:
                if keyword.strip() in t.text.strip():
                    target_link = "https://finance.naver.com" + t['href']
                    break
            if target_link: break
        except: continue
    if not target_link: return [], f"네이버 금융 테마에서 '{keyword}'를 찾을 수 없습니다."
    try:
        res_detail = requests.get(target_link, headers=headers)
        res_detail.encoding = 'EUC-KR'
        soup_detail = BeautifulSoup(res_detail.text, 'html.parser')
        stocks = []
        rows = soup_detail.select('div.box_type_l table.type_5 tr')
        for row in rows:
            name_tag = row.select_one('td.name a')
            if name_tag:
                code = name_tag['href'].split('=')[-1]
                name = name_tag.text.strip()
                price_txt = row.select('td.number')[0].text.strip().replace(',', '')
                try: price = int(price_txt)
                except: price = 0
                stocks.append({"code": code, "name": name, "price": price})
        return stocks, f"'{keyword}' 관련 테마 발견: {len(stocks)}개 종목"
    except Exception as e: return [], f"크롤링 오류: {str(e)}"

def get_investor_trend_from_naver(code):
    try:
        url = f"https://finance.naver.com/item/frgn.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        try: dfs = pd.read_html(StringIO(res.text), match='날짜', header=0, encoding='euc-kr')
        except: dfs = pd.read_html(StringIO(res.text), header=0, encoding='euc-kr')
        target_df = None
        for df in dfs:
            cols_str = " ".join([str(c) for c in df.columns])
            if '기관' in cols_str and '외국인' in cols_str: target_df = df; break
        if target_df is None and len(dfs) > 1: target_df = dfs[1]
        if target_df is not None:
            df = target_df.dropna().copy()
            first_col = df.columns[0]
            try:
                df[first_col] = pd.to_datetime(df[first_col], format='%Y.%m.%d', errors='coerce')
                df = df.dropna(subset=[first_col])
            except: return pd.DataFrame()
            df = df.rename(columns={first_col: '날짜'})
            inst_col = [c for c in df.columns if '기관' in str(c)][0]
            frgn_col = [c for c in df.columns if '외국인' in str(c)][0]
            df = df.iloc[:20].copy().sort_values('날짜')
            df['기관'] = df[inst_col].astype(str).str.replace(',', '').astype(float)
            df['외국인'] = df[frgn_col].astype(str).str.replace(',', '').astype(float)
            df['개인'] = -(df['기관'] + df['외국인'])
            df['Cum_Individual'] = df['개인'].cumsum()
            df['Cum_Foreigner'] = df['외국인'].cumsum()
            df['Cum_Institution'] = df['기관'].cumsum()
            df['Cum_Pension'] = 0 
            return df
    except: pass
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_investor_trend(code):
    try:
        end_d = datetime.datetime.now().strftime("%Y%m%d")
        start_d = (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(start_d, end_d, code)
        if not df.empty:
            df = df.tail(20).copy()
            df['Cum_Individual'] = df['개인'].cumsum()
            df['Cum_Foreigner'] = df['외국인'].cumsum()
            df['Cum_Institution'] = df['기관합계'].cumsum()
            df['Cum_Pension'] = df['연기금'].cumsum()
            return df
    except: pass
    return get_investor_trend_from_naver(code)

@st.cache_data(ttl=3600)
def get_financial_history(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        df_list = pd.read_html(StringIO(res.text), encoding='euc-kr')
        for df in df_list:
            if '최근 연간 실적' in str(df.columns) or '매출액' in str(df.iloc[:,0].values):
                df = df.set_index(df.columns[0])
                fin_data = []
                cols = df.columns[-5:-1]
                for col in cols:
                    try:
                        col_name = col[1] if isinstance(col, tuple) else col
                        val_sales = df.loc['매출액', col] if '매출액' in df.index else 0
                        val_op = df.loc['영업이익', col] if '영업이익' in df.index else 0
                        val_net = df.loc['당기순이익', col] if '당기순이익' in df.index else 0
                        fin_data.append({
                            "Date": str(col_name).strip(),
                            "매출액": float(val_sales) if val_sales != '-' and pd.notnull(val_sales) else 0,
                            "영업이익": float(val_op) if val_op != '-' and pd.notnull(val_op) else 0,
                            "당기순이익": float(val_net) if val_net != '-' and pd.notnull(val_net) else 0
                        })
                    except: continue
                return pd.DataFrame(fin_data)
        return pd.DataFrame()
    except: return pd.DataFrame()

def calculate_sniper_score(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=90))
        if df.empty or len(df) < 20: return 0, [], 0, 0
        curr = df.iloc[-1]
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
        score = 0; tags = []
        vol_ratio = curr['Volume'] / vol_avg if vol_avg > 0 else 0
        if vol_ratio >= 3.0: score += 40; tags.append("🔥 거래량폭발")
        elif vol_ratio >= 1.5: score += 20; tags.append("📈 거래량증가")
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        if curr['Close'] > ma20 and curr['Close'] <= ma20 * 1.05: score += 30; tags.append("🏹 눌림목")
        try:
            end_d = datetime.datetime.now().strftime("%Y%m%d")
            start_d = (datetime.datetime.now() - datetime.timedelta(days=5)).strftime("%Y%m%d")
            inv_df = stock.get_market_investor_net_purchase_by_date(start_d, end_d, code).tail(3)
            if not inv_df.empty and (inv_df['기관합계'].sum() + inv_df['외국인'].sum() > 0): score += 30; tags.append("🏦 메이저매집")
        except: pass
        change = (curr['Close'] - df.iloc[-2]['Close']) / df.iloc[-2]['Close'] * 100
        if change > 15: tags.append("🚀 급등주")
        return score, tags, vol_ratio, change
    except: return 0, [], 0, 0

@st.cache_data(ttl=3600)
def get_macro_data():
    results = {}
    tickers = {"KOSPI": "KS11", "KOSDAQ": "KQ11", "S&P500": "US500", "USD/KRW": "USD/KRW", "US_10Y": "US10YT"}
    for name, code in tickers.items():
        try:
            df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=14))
            if not df.empty:
                curr = df.iloc[-1]
                results[name] = {"val": curr['Close'], "change": (curr['Close'] - curr['Open']) / curr['Open'] * 100}
            else: results[name] = {"val": 0.0, "change": 0.0}
        except: results[name] = {"val": 0.0, "change": 0.0}
    if all(v['val'] == 0.0 for v in results.values()): return None
    return results

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    per, pbr, div = 0.0, 0.0, 0.0
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            def get_val_by_id(id_name):
                tag = soup.select_one(f"#{id_name}")
                if tag:
                    txt = tag.text.replace(',', '').replace('%', '').replace('배', '').strip()
                    try: return float(txt)
                    except: return 0.0
                return 0.0
            per = get_val_by_id("_per")
            pbr = get_val_by_id("_pbr")
            div = get_val_by_id("_dvr")
    except: pass
    if per == 0 and pbr == 0:
        if not krx_df.empty and code in krx_df['Code'].values:
            try:
                row = krx_df[krx_df['Code'] == code].iloc[0]
                per = float(row.get('PER', 0)) if pd.notnull(row.get('PER')) else 0
                pbr = float(row.get('PBR', 0)) if pd.notnull(row.get('PBR')) else 0
                div = float(row.get('DividendYield', 0)) if pd.notnull(row.get('DividendYield')) else 0
            except: pass
    if per == 0 and pbr == 0:
        try:
            end_str = datetime.datetime.now().strftime("%Y%m%d")
            start_str = (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y%m%d")
            df = stock.get_market_fundamental_by_date(start_str, end_str, code)
            if not df.empty:
                recent = df.iloc[-1]
                per = float(recent.get('PER', 0))
                pbr = float(recent.get('PBR', 0))
                div = float(recent.get('DIV', 0))
        except: pass
    pbr_stat = "good" if 0 < pbr < 1.0 else ("neu" if 1.0 <= pbr < 2.5 else "bad")
    pbr_txt = "저평가(좋음)" if 0 < pbr < 1.0 else ("적정" if 1.0 <= pbr < 2.5 else "고평가/정보없음")
    per_stat = "good" if 0 < per < 10 else ("neu" if 10 <= per < 20 else "bad")
    per_txt = "실적우수" if 0 < per < 10 else ("보통" if 10 <= per < 20 else "고평가/적자/정보없음")
    div_stat = "good" if div > 3.0 else "neu"
    div_txt = "고배당" if div > 3.0 else "일반"
    score = 20
    if pbr_stat=="good": score+=15
    if per_stat=="good": score+=10
    if div_stat=="good": score+=5
    fund_data = {"per": {"val": per, "stat": per_stat, "txt": per_txt}, "pbr": {"val": pbr, "stat": pbr_stat, "txt": pbr_txt}, "div": {"val": div, "stat": div_stat, "txt": div_txt}}
    return min(score, 50), "분석완료", fund_data

def analyze_news_by_keywords(news_titles):
    pos_words = ["상승", "급등", "최고", "호재", "개선", "성장", "흑자", "수주", "돌파", "기대", "매수"]
    neg_words = ["하락", "급락", "최저", "악재", "우려", "감소", "적자", "이탈", "매도", "공매도"]
    score = 0; found_keywords = []
    for title in news_titles:
        for w in pos_words:
            if w in title: score += 1; found_keywords.append(w)
        for w in neg_words:
            if w in title: score -= 1; found_keywords.append(w)
    final_score = min(max(score, -10), 10)
    summary = f"긍정 키워드 {len([w for w in found_keywords if w in pos_words])}개, 부정 키워드 {len([w for w in found_keywords if w in neg_words])}개 감지."
    return final_score, summary, "키워드 분석", ""

def call_gemini_auto(prompt):
    api_key = st.secrets.get("GOOGLE_API_KEY", "")
    if not api_key: return None, "NO_KEY"
    models = ["gemini-1.5-flash", "gemini-pro"]
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"response_mime_type": "application/json"}}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=6)
            if res.status_code == 200: return res.json(), None
        except: continue
    return None, "ALL_FAILED"

@st.cache_data(ttl=600)
def get_news_sentiment_llm(company_name, trend_context=""):
    news_titles = []; news_data = []
    try:
        query = f"{company_name} 주가"
        encoded_query = urllib.parse.quote(query)
        base_url = "https://news.google.com/rss/search"
        rss_url = base_url + f"?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:15]:
            date_str = time.strftime("%Y-%m-%d", entry.published_parsed) if entry.published_parsed else ""
            news_data.append({"title": entry.title, "link": entry.link, "date": date_str})
            news_titles.append(entry.title)
    except: return {"score": 0, "headline": "뉴스 데이터 로딩 실패", "raw_news": [], "method": "error", "catalyst": "", "opinion": ""}
    if not news_titles: return {"score": 0, "headline": "관련 뉴스 없음", "raw_news": [], "method": "none", "catalyst": "", "opinion": "중립"}
    try:
        prompt = f"""당신은 20년 경력의 베테랑 헤지펀드 매니저입니다. 아래 정보를 바탕으로 투자 의견을 JSON으로 제시하세요. [대상 종목]: {company_name} [현재 기술적 위치]: {trend_context} [최근 뉴스 헤드라인]: {str(news_titles)} [출력 형식 (JSON)]: {{ "score": -10~10, "opinion": "매수/관망/매도", "catalyst": "핵심키워드", "summary": "한줄평" }}"""
        res_data, error_code = call_gemini_auto(prompt)
        if res_data:
            raw = res_data['candidates'][0]['content']['parts'][0]['text']
            js = json.loads(raw)
            return {"score": js.get('score', 0), "headline": js.get('summary', ""), "raw_news": news_data, "method": "ai", "catalyst": js.get('catalyst', ""), "opinion": js.get('opinion', "중립")}
    except: pass
    score, summary, _, _ = analyze_news_by_keywords(news_titles)
    return {"score": score, "headline": summary, "raw_news": news_data, "method": "keyword", "catalyst": "", "opinion": ""}

def get_supply_demand(code):
    try:
        e = datetime.datetime.now().strftime("%Y%m%d")
        s = (datetime.datetime.now()-datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(s, e, code).tail(3)
        if df.empty: return {"f":0, "i":0}
        return {"f": int(df['외국인'].sum()), "i": int(df['기관합계'].sum())}
    except: return {"f":0, "i":0}

def analyze_pro(code, name_override=None):
    try:
        df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=450))
        if df.empty or len(df) < 60: return None
    except: return None

    curr = df.iloc[-1]
    
    # 등락률 계산
    try:
        prev_close = df.iloc[-2]['Close']
        chg_rate = (curr['Close'] - prev_close) / prev_close * 100
    except: chg_rate = 0.0

    result_dict = {
        "name": name_override if name_override else code, 
        "code": code, 
        "price": int(curr['Close']),
        "change_rate": chg_rate, 
        "score": 50,
        "strategy": {}, 
        "fund_data": None, 
        "ma_status": [], 
        "trend_txt": "분석 중",
        "news": {"score":0, "headline":"로딩 실패", "raw_news":[], "method":"none", "opinion":"", "catalyst":""}, 
        "history": df, 
        "supply": {"f":0, "i":0},
        "stoch": {"k": 50, "d": 50},
        "vol_ratio": 1.0,
        "investor_trend": pd.DataFrame(),
        "fin_history": pd.DataFrame()
    }

    try:
        df['MA5'] = df['Close'].rolling(5).mean(); df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean(); df['MA120'] = df['Close'].rolling(120).mean()
        df['MA240'] = df['Close'].rolling(240).mean()
        df['std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['MA20'] + (df['std'] * 2); df['BB_Lower'] = df['MA20'] - (df['std'] * 2)
        df['Vol_MA20'] = df['Volume'].rolling(20).mean()
        
        n=14; m=3; t=3
        df['L14'] = df['Low'].rolling(window=n).min(); df['H14'] = df['High'].rolling(window=n).max()
        df['%K'] = (df['Close'] - df['L14']) / (df['H14'] - df['L14']) * 100
        df['%D'] = df['%K'].rolling(window=m).mean(); df['%J'] = df['%D'].rolling(window=t).mean()
        
        curr = df.iloc[-1]
        pass_cnt = 0
        mas = [('5일', 'MA5'), ('20일', 'MA20'), ('60일', 'MA60'), ('120일', 'MA120'), ('240일', 'MA240')]
        ma_status = []
        for label, col in mas:
            val = curr.get(col, 0)
            if curr['Close'] >= val: pass_cnt += 1; ma_status.append({"label": label, "ok": True})
            else: ma_status.append({"label": label, "ok": False})
            
        if pass_cnt >= 4: trend_txt = "강력한 상승 추세 (정배열)"
        elif pass_cnt >= 3: trend_txt = "상승세 유지 (양호)"
        elif pass_cnt >= 1: trend_txt = "하락 중 반등 시도"
        else: trend_txt = "완전 역배열 (하락세)"
        
        result_dict['ma_status'] = ma_status
        result_dict['trend_txt'] = trend_txt
        result_dict['stoch'] = {"k": curr['%K'], "d": curr['%J']}
        result_dict['vol_ratio'] = curr['Volume'] / curr['Vol_MA20'] if curr['Vol_MA20'] > 0 else 1.0
        tech_score = (pass_cnt * 6)
        if curr['%K'] < 20: tech_score += 5 
    except: tech_score = 0

    try: result_dict['news'] = get_news_sentiment_llm(result_dict['name'], trend_context=result_dict['trend_txt'])
    except: pass 

    try: fund_score, _, fund_data = get_company_guide_score(code); result_dict['fund_data'] = fund_data
    except: fund_score = 0

    try: result_dict['investor_trend'] = get_investor_trend(code)
    except: pass
    
    try: result_dict['fin_history'] = get_financial_history(code)
    except: pass
    
    try: result_dict['supply'] = get_supply_demand(code)
    except: pass

    try:
        bonus = 0
        if not result_dict['investor_trend'].empty: bonus += 5
        if not result_dict['fin_history'].empty: bonus += 5
        final_score = int((tech_score * 0.4) + fund_score + bonus + result_dict['news']['score'])
        final_score = min(max(final_score, 0), 100)
        result_dict['score'] = final_score

        if final_score >= 80:
            buy_basis_col = 'MA5'; target_ratio = 1.20; stop_ratio = 0.97; action_txt = "🔥 강력매수"
        elif final_score >= 60:
            buy_basis_col = 'MA20'; target_ratio = 1.15; stop_ratio = 0.95; action_txt = "매수"
        else:
            buy_basis_col = 'MA60'
            if curr.get('MA60', 0) == 0: buy_basis_col = 'MA20'
            target_ratio = 1.10; stop_ratio = 0.90; action_txt = "관망/단기"

        buy_price = int(curr.get(buy_basis_col, 0))
        if buy_price == 0: buy_price = int(curr['Close'])

        result_dict['strategy'] = {
            "buy": buy_price,
            "buy_basis": buy_basis_col.replace('MA', '') + "일선",
            "target": int(curr['Close'] * target_ratio),
            "stop": int(buy_price * stop_ratio),
            "action": action_txt
        }
    except: pass

    return result_dict

def send_telegram_msg(token, chat_id, msg):
    try: requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": msg})
    except: pass

# --- [4. 메인 화면] ---

# [수정됨] 제목 옆에 가이드 버튼 추가 (사장님의 의도를 담은 내용으로 업데이트 완료)
col_title, col_guide = st.columns([0.7, 0.3])

with col_title:
    st.title("💎 Quant Sniper V33.0")

with col_guide:
    st.write("") # 줄 간격 맞춤
    st.write("") 
    with st.expander("📘 개발 리포트 & 가이드 (Click)", expanded=False):
        st.markdown("""
        ### 1. 개발 기조 (Code Manifesto)
        > **"차후 업그레이드를 위한 초심(初心) 유지"**
        
        이 코드는 단발성으로 끝나지 않고 지속적으로 발전하기 위해, **초기 개발 단계의 코딩 기조**를 엄격히 준수합니다. 확장성과 유지보수를 최우선으로 고려하여 설계되었습니다.
        
        ---
        ### 2. 개발 배경 (Vision)
        > **"주린이에게 20년 경력 애널리스트의 안목을"**
        
        투자의 경험이 부족한 '주린이'라도, 이 프로그램을 통해 **20년 경력의 베테랑 애널리스트와 동일한 안목**을 갖출 수 있어야 합니다. 우리의 궁극적인 목표는 사용자가 **연 20% 이상의 안정적인 투자 성적**을 거두도록 기술적으로 돕는 것입니다.
        
        ---
        ### 3. 기능 및 구현 원리 (Mechanism)
        **데이터와 조언은 어떻게 도출되는가?**
        * **객관적 데이터:** 시장의 감정을 배제하고, 수치화된 알고리즘을 통해 냉철한 데이터를 도출합니다.
        * **직관적 조언:** 복잡한 분석 과정을 거쳐, 사용자에겐 "지금 사야 하는가?"에 대한 명확한 해답을 제시합니다.
        * **기능 요약:** 기술적/재무적 분석, 수급 파악, AI 리포트를 통합하여 최적의 의사결정을 지원합니다.
        
        <div style="text-align: right; color: grey; font-size: 0.8em; margin-top: 10px;">
            Defined by Project Owner
        </div>
        """, unsafe_allow_html=True)

with st.expander("🌍 글로벌 거시 경제 대시보드 (Click to Open)", expanded=False):
    macro = get_macro_data()
    if macro:
        cols = st.columns(5)
        keys = ["KOSPI", "KOSDAQ", "S&P500", "USD/KRW", "US_10Y"]
        for i, key in enumerate(keys):
            d = macro.get(key, {"val": 0.0, "change": 0.0})
            color = "#F04452" if d['change'] > 0 else "#3182F6"
            with cols[i]:
                st.markdown(f"<div class='metric-box'><div class='metric-title'>{key}</div><div class='metric-value' style='color:{color}'>{d['val']:,.2f}</div><div style='font-size:12px; color:{color}'>{d['change']:+.2f}%</div></div>", unsafe_allow_html=True)
    else: st.warning("거시 경제 데이터를 불러오지 못했습니다.")

tab1, tab2 = st.tabs(["🔍 테마/종목 발굴", "📂 관심 종목"])

with tab1:
    if st.session_state.get('preview_list'):
        st.markdown(f"### 🔍 '{st.session_state['current_theme_name']}' 주도주 심층 분석 (미리보기)")
        st.info("💡 마음에 드는 종목의 **'📌 관심종목 등록'** 버튼을 누르면 '관심 종목' 탭에 저장됩니다.")
        
        with st.spinner("주도주 심층 분석 데이터 생성 중..."):
            preview_results = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(analyze_pro, item['code'], item['name']) for item in st.session_state['preview_list']]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): preview_results.append(f.result())
            preview_results.sort(key=lambda x: x['score'], reverse=True)

        for res in preview_results:
            st.markdown(create_card_html(res), unsafe_allow_html=True)
            with st.expander(f"📊 {res['name']} 상세 분석 및 추가"):
                col_add, col_info = st.columns([1, 5])
                with col_add:
                    if st.button(f"📌 {res['name']} 관심종목 등록", key=f"add_{res['code']}"):
                        st.session_state['watchlist'][res['name']] = {'code': res['code']}
                        st.success(f"✅ {res['name']} 추가 완료!")
                        time.sleep(0.5)
                        st.rerun()
                col1, col2 = st.columns(2)
                with col1:
                    st.write("###### 📈 기술적 분석 & 차트")
                    st.markdown(f"<div class='tech-summary'>{res['trend_txt']}</div>", unsafe_allow_html=True)
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    st.markdown(render_chart_legend(), unsafe_allow_html=True)
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                with col2:
                    st.write("###### 🏢 재무 펀더멘탈 & 실적")
                    render_fund_scorecard(res['fund_data'])
                    render_financial_table(res['fin_history'])
                st.write("###### 🧠 큰손 투자 동향 (최근 20일 누적)")
                render_investor_chart(res['investor_trend'])
                st.write("###### 📰 AI 헤지펀드 매니저 분석")
                if res['news']['method'] == "ai": 
                    op = res['news']['opinion']; badge_cls = "ai-opinion-hold"
                    if "매수" in op: badge_cls = "ai-opinion-buy"
                    elif "매도" in op: badge_cls = "ai-opinion-sell"
                    st.markdown(f"""<div class='news-ai'><div style='margin-bottom:8px;'><span class='ai-badge {badge_cls}'>{res['news']['opinion']}</span><span style='font-size:13px; font-weight:700; margin-left:5px;'>💡 핵심 재료: {res['news']['catalyst']}</span></div><div style='font-size:13px; line-height:1.6;'><b>🤖 전문가 코멘트:</b> {res['news']['headline']}</div></div>""", unsafe_allow_html=True)
                else: 
                    st.markdown(f"<div class='news-fallback'><b>⚠️ 단순 키워드 분석:</b> {res['news']['headline']}</div>", unsafe_allow_html=True)
                st.markdown("<div class='news-scroll-box'>", unsafe_allow_html=True)
                for news in res['news']['raw_news']:
                    st.markdown(f"<div class='news-box'><a href='{news['link']}' target='_blank' class='news-link'>📄 {news['title']}</a><span class='news-date'>{news['date']}</span></div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
    else: st.info("👈 왼쪽 사이드바에서 **테마를 검색**하거나 **종목을 입력**해주세요.")

with tab2:
    st.markdown("### 📂 관심 종목 (Watchlist)")
    combined_watchlist = list(st.session_state['watchlist'].items())
    if not combined_watchlist: 
        st.info("아직 관심 종목이 없습니다. '테마/종목 발굴' 탭에서 종목을 추가해보세요.")
    else:
        with st.spinner("관심 종목 데이터 갱신 중..."):
            wl_results = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(analyze_pro, info['code'], name) for name, info in combined_watchlist]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): wl_results.append(f.result())
            wl_results.sort(key=lambda x: x['score'], reverse=True)
        for res in wl_results:
            st.markdown(create_card_html(res), unsafe_allow_html=True)
            with st.expander(f"📊 {res['name']} 상세 분석"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("###### 📈 기술적 분석")
                    st.markdown(f"<div class='tech-summary'>{res['trend_txt']}</div>", unsafe_allow_html=True)
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    st.markdown(render_chart_legend(), unsafe_allow_html=True)
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                with col2:
                    st.write("###### 🏢 재무 펀더멘탈")
                    render_fund_scorecard(res['fund_data'])
                    render_financial_table(res['fin_history'])
                st.write("###### 🧠 큰손 투자 동향")
                render_investor_chart(res['investor_trend'])
                st.write("###### 📰 AI 헤지펀드 매니저 분석")
                if res['news']['method'] == "ai": 
                    op = res['news']['opinion']; badge_cls = "ai-opinion-hold"
                    if "매수" in op: badge_cls = "ai-opinion-buy"
                    elif "매도" in op: badge_cls = "ai-opinion-sell"
                    st.markdown(f"""<div class='news-ai'><div style='margin-bottom:8px;'><span class='ai-badge {badge_cls}'>{res['news']['opinion']}</span><span style='font-size:13px; font-weight:700; margin-left:5px;'>💡 핵심 재료: {res['news']['catalyst']}</span></div><div style='font-size:13px; line-height:1.6;'><b>🤖 전문가 코멘트:</b> {res['news']['headline']}</div></div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='news-fallback'><b>⚠️ 단순 키워드 분석:</b> {res['news']['headline']}</div>", unsafe_allow_html=True)
                st.markdown("<div class='news-scroll-box'>", unsafe_allow_html=True)
                for news in res['news']['raw_news']:
                    st.markdown(f"<div class='news-box'><a href='{news['link']}' target='_blank' class='news-link'>📄 {news['title']}</a><span class='news-date'>{news['date']}</span></div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

with st.sidebar:
    st.write("### ⚙️ 기능 메뉴")
    with st.expander("🔍 지능형 테마/주도주 찾기", expanded=True):
        THEME_KEYWORDS = { "직접 입력": None, "반도체": "반도체", "2차전지": "2차전지", "HBM": "HBM", "AI/인공지능": "지능형로봇", "로봇": "로봇", "제약바이오": "제약업체", "자동차/부품": "자동차", "방위산업": "방위산업", "원자력발전": "원자력발전", "초전도체": "초전도체", "저PBR": "은행" }
        selected_preset = st.selectbox("⚡ 인기 테마 선택", list(THEME_KEYWORDS.keys()))
        with st.form(key="search_form"):
            user_input = ""
            if selected_preset == "직접 입력": user_input = st.text_input("검색할 테마 입력", placeholder="예: 리튬, 화장품, 엔터")
            else: st.info(f"✅ 선택된 테마: **{THEME_KEYWORDS[selected_preset]}**")
            submit_btn = st.form_submit_button("테마 분석 및 미리보기")
        
        if submit_btn:
            if selected_preset == "직접 입력": target_keyword = user_input
            else: target_keyword = THEME_KEYWORDS[selected_preset]
            if not target_keyword: st.warning("⚠️ 검색어를 입력하거나 테마를 선택해주세요!")
            else:
                try:
                    with st.spinner(f"네이버 금융에서 '{target_keyword}' 관련주 찾는 중... (1~7p 스캔)"):
                        raw_stocks, msg = get_naver_theme_stocks(target_keyword)
                    if raw_stocks:
                        st.success(msg)
                        processed_stocks = []
                        progress_text = "주도주 스코어링 분석 중..."
                        my_bar = st.progress(0, text=progress_text)
                        total_items = min(len(raw_stocks), 5) 
                        for i, stock_info in enumerate(raw_stocks[:total_items]):
                            score, tags, vol, chg = calculate_sniper_score(stock_info['code'])
                            stock_info['sniper_score'] = score; stock_info['tags'] = tags; stock_info['vol_ratio'] = vol; stock_info['real_change'] = chg
                            processed_stocks.append(stock_info)
                            my_bar.progress((i + 1) / total_items, text=f"{stock_info['name']} 분석 완료...")
                        my_bar.empty()
                        processed_stocks.sort(key=lambda x: x['sniper_score'], reverse=True)
                        st.session_state['preview_list'] = processed_stocks
                        st.session_state['current_theme_name'] = target_keyword
                        st.rerun()
                    else: st.error(f"❌ 결과 없음: {msg}")
                except Exception as e: st.error(f"🚫 시스템 오류 발생: {str(e)}")

    if st.button("🚀 텔레그램으로 리포트 전송"):
        token = st.secrets.get("TELEGRAM_TOKEN", "")
        chat_id = st.secrets.get("CHAT_ID", "")
        if token and chat_id and 'wl_results' in locals() and wl_results:
            msg = f"💎 Quant Sniper V33.0 리포트 ({datetime.date.today()})\n\n"
            if macro: msg += f"[시장] KOSPI {macro.get('KOSPI',{'val':0})['val']:.0f}\n\n"
            for i, r in enumerate(wl_results[:3]): msg += f"{i+1}. {r['name']} ({r['score']}점)\n   가격: {r['price']:,}원\n   요약: {r['news']['headline'][:50]}...\n\n"
            send_telegram_msg(token, chat_id, msg)
            st.success("전송 완료!")
        else: st.warning("설정 확인 필요")

    with st.expander("개별 종목 추가", expanded=False):
        name = st.text_input("이름"); code = st.text_input("코드")
        if st.button("추가") and name and code:
            st.session_state['watchlist'][name] = {"code": code}
            st.rerun()
    if st.button("초기화"): st.session_state['watchlist'] = {}; st.session_state['preview_list'] = []; st.rerun()
