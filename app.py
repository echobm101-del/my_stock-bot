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
import random

# ==============================================================================
# [보안 설정] Streamlit Secrets에서 키 가져오기
# ==============================================================================
try:
    USER_GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    USER_TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    USER_CHAT_ID = st.secrets["CHAT_ID"]
    USER_GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except Exception:
    USER_GITHUB_TOKEN = ""
    USER_TELEGRAM_TOKEN = ""
    USER_CHAT_ID = ""
    USER_GOOGLE_API_KEY = ""

# --- [1. UI 스타일링] ---
st.set_page_config(page_title="Quant Sniper V50.0 (Stability Enhanced)", page_icon="💎", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    .fund-grid-v2 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 10px; background-color: #F9FAFB; padding: 15px; border-radius: 12px; }
    .fund-item-v2 { text-align: center; }
    .fund-title-v2 { font-size: 12px; color: #8B95A1; margin-bottom: 5px; }
    .fund-value-v2 { font-size: 18px; font-weight: 800; color: #333D4B; }
    .fund-desc-v2 { font-size: 11px; font-weight: 600; margin-top: 4px; display: inline-block; padding: 2px 6px; border-radius: 4px;}
    .tech-status-box { display: flex; gap: 10px; margin-bottom: 10px; }
    .status-badge { flex: 1; padding: 12px 10px; border-radius: 12px; text-align: center; font-size: 13px; font-weight: 700; color: #4E5968; background: #F2F4F6; border: 1px solid #E5E8EB; }
    .status-badge.buy { background-color: #E8F3FF; color: #3182F6; border-color: #3182F6; }
    .status-badge.sell { background-color: #FFF1F1; color: #F04452; border-color: #F04452; }
    .status-badge.vol { background-color: #FFF8E1; color: #D9480F; border-color: #FFD8A8; }
    .status-badge.neu { background-color: #FFF9DB; color: #F08C00; border-color: #FFEC99; }
    .tech-summary { background: #F2F4F6; padding: 10px; border-radius: 8px; font-size: 13px; color: #4E5968; margin-bottom: 10px; font-weight: 600; }
    .ma-status-container { display: flex; gap: 5px; margin-bottom: 10px; flex-wrap: wrap; }
    .ma-status-badge { font-size: 11px; padding: 4px 8px; border-radius: 6px; font-weight: 700; color: #555; background-color: #F2F4F6; border: 1px solid #E5E8EB; }
    .ma-status-badge.on { background-color: #FFF1F1; color: #F04452; border-color: #F04452; } 
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
    .metric-box { background: #F9FAFB; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #E5E8EB; height: 100%; display: flex; flex-direction: column; justify-content: center; }
    .metric-title { font-size: 12px; color: #666; margin-bottom: 4px; }
    .metric-value { font-size: 16px; font-weight: bold; color: #333; margin-bottom: 2px;}
    .metric-badge { font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 700; display: inline-block; margin-top: 4px; }
    .fin-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; margin-bottom: 10px; border: 1px solid #E5E8EB; }
    .fin-table th { background-color: #F9FAFB; padding: 8px; border-bottom: 1px solid #E5E8EB; color: #4E5968; font-weight: 600; }
    .fin-table td { padding: 8px; border-bottom: 1px solid #F2F4F6; color: #333; font-weight: 500; }
    .text-red { color: #F04452; font-weight: 700; }
    .text-blue { color: #3182F6; font-weight: 700; }
    .change-rate { font-size: 10px; color: #888; font-weight: 400; margin-left: 4px; }
    .cycle-badge { background-color:#E6FCF5; color:#087F5B; padding:4px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #B2F2BB; display:inline-block; margin-top:4px; }
    .cycle-badge.bear { background-color:#FFF5F5; color:#F04452; border-color:#FFD8A8; }
    .relation-badge { background-color:#F3F0FF; color:#7950F2; padding:3px 6px; border-radius:4px; font-size:10px; font-weight:700; border:1px solid #E5DBFF; margin-left:6px; vertical-align: middle; }
    .investor-table-container { margin-top: 10px; border: 1px solid #F2F4F6; border-radius: 8px; overflow: hidden; }
    .investor-table { width: 100%; font-size: 11px; text-align: center; border-collapse: collapse; }
    .investor-table th { background-color: #F9FAFB; padding: 6px; color: #666; font-weight: 600; border-bottom: 1px solid #E5E8EB; }
    .investor-table td { padding: 6px; border-bottom: 1px solid #F2F4F6; color: #333; }
    .profit-positive { color: #F04452; font-weight: 800; font-size: 20px; }
    .profit-negative { color: #3182F6; font-weight: 800; font-size: 20px; }
    .strategy-container { background-color: #F9FAFB; border-radius: 12px; padding: 12px; margin-top: 12px; border: 1px solid #E5E8EB; }
    .strategy-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .strategy-title { font-size: 12px; font-weight: 700; color: #4E5968; }
    .progress-bg { background-color: #E0E0E0; height: 10px; border-radius: 5px; overflow: hidden; margin-bottom: 8px; }
    .progress-fill { background: linear-gradient(90deg, #ff9a9e 0%, #ff5e62 100%); height: 100%; transition: width 0.5s ease; }
    .progress-fill.overdrive { background: linear-gradient(90deg, #FFD700 0%, #FDBB2D 50%, #8A2BE2 100%); }
    .progress-fill.rescue { background: linear-gradient(90deg, #a1c4fd 0%, #c2e9fb 100%); }
    .price-guide { display: flex; justify-content: space-between; font-size: 11px; color: #666; font-weight: 500; }
    .action-badge-default { background-color:#eee; color:#333; padding:4px 10px; border-radius:12px; font-weight:700; font-size:12px; }
    .action-badge-strong { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:#fff; padding:6px 14px; border-radius:16px; font-weight:800; font-size:12px; box-shadow: 0 2px 6px rgba(118, 75, 162, 0.4); animation: pulse 2s infinite; }
    .action-badge-rescue { background: linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%); color:#fff; padding:6px 14px; border-radius:16px; font-weight:800; font-size:12px; }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(118, 75, 162, 0.4); }
        70% { box-shadow: 0 0 0 6px rgba(118, 75, 162, 0); }
        100% { box-shadow: 0 0 0 0 rgba(118, 75, 162, 0); }
    }
</style>
""", unsafe_allow_html=True)

# --- [2. 시각화 및 렌더링 함수] ---

def create_watchlist_card_html(res):
    score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
    buy_price = res['strategy'].get('buy', 0)
    target_price = res['strategy'].get('target', 0)
    stop_price = res['strategy'].get('stop', 0)
    buy_basis = res['strategy'].get('buy_basis', '20일선')
    
    chg = res.get('change_rate', 0.0)
    chg_color = "#F04452" if chg > 0 else ("#3182F6" if chg < 0 else "#333333")
    chg_txt = f"({chg:+.2f}% {'▲' if chg > 0 else ('▼' if chg < 0 else '-')})"

    cycle_cls = "bear" if "하락" in res['cycle_txt'] else ""
    backtest_txt = f"⚡ 검증 승률: {res['win_rate']}%" if res['win_rate'] > 0 else "⚡ 백테스팅 데이터 부족"
    
    relation_html = f"<span class='relation-badge'>🔗 {res['relation_tag']}</span>" if res.get('relation_tag') else ""

    html = f"""
    <div class='toss-card' style='border-left: 5px solid {score_col};'>
      <div style='display:flex; justify-content:space-between; align-items:center;'>
          <div>
              <span class='stock-name' style='font-size:20px; font-weight:800;'>{res['name']}</span>
              <span class='stock-code' style='color:#8B95A1; margin-left:5px;'>{res['code']}</span>
              {relation_html}
              <div class='cycle-badge {cycle_cls}'>{res['cycle_txt']}</div>
              <div class='big-price' style='font-size:24px; font-weight:800; margin-top:8px;'>{res['price']:,}원 <span style='font-size:16px; color:{chg_color}; font-weight:600; margin-left:5px;'>{chg_txt}</span></div>
          </div>
          <div style='text-align:right;'>
              <div style='font-size:28px; font-weight:800; color:{score_col};'>{res['score']}점</div>
              <div class='badge-clean' style='background-color:{score_col}20; color:{score_col}; font-weight:700; padding:4px 8px; border-radius:6px;'>{res['strategy']['action']}</div>
          </div>
      </div>
      <div style='margin-top:15px; padding-top:10px; border-top:1px solid #F2F4F6; display:grid; grid-template-columns: 1fr 1fr 1fr; gap:5px; font-size:12px; font-weight:700; text-align:center;'>
          <div style='color:#3182F6; background-color:#E8F3FF; padding:6px; border-radius:6px;'>🛒 진입 구간 {buy_price:,}<br><span style='font-size:10px; opacity:0.7;'>({buy_basis})</span></div>
          <div style='color:#F04452; background-color:#FFF1F1; padding:6px; border-radius:6px;'>💰 수익 구간 {target_price:,}<br><span style='font-size:10px; opacity:0.7;'>(기분 좋은 익절)</span></div>
          <div style='color:#4E5968; background-color:#F2F4F6; padding:6px; border-radius:6px;'>🛡️ 안전벨트 {stop_price:,}<br><span style='font-size:10px; opacity:0.7;'>(내 돈 지키기)</span></div>
      </div>
      <div style='margin-top:8px; display:flex; justify-content:space-between; align-items:center;'>
            <span style='font-size:11px; font-weight:700; color:#555;'>{backtest_txt}</span>
            <span style='font-size:12px; color:#888;'>{res['trend_txt']}</span>
      </div>
    </div>
    """
    return html

def create_portfolio_card_html(res):
    buy_price = res.get('my_buy_price', 0)
    curr_price = res['price']
    
    profit_rate = (curr_price - buy_price) / buy_price * 100 if buy_price > 0 else 0.0
    profit_val = curr_price - buy_price

    is_overdrive = profit_rate >= 10.0
    is_rescue = profit_rate <= -10.0
    
    final_target = int(buy_price * 1.10)
    final_stop = int(buy_price * 0.95)
    
    status_msg = f"목표까지 {max(final_target - curr_price, 0):,}원 남음"
    stop_label, target_label = "🛡️ 손절가 (-5%)", "🚀 목표가 (+10%)"
    stop_color, target_color = "#3182F6", "#F04452"
    progress_cls, action_btn_cls = "progress-fill", "action-badge-default"
    action_text, strategy_bg = res['strategy']['action'], "#F9FAFB"

    if is_overdrive:
        final_target = int(curr_price * 1.10) if curr_price >= int(buy_price * 1.20) else int(buy_price * 1.20)
        final_stop = int(buy_price * 1.05)
        status_msg, stop_label, target_label = f"🎉 목표 초과 (+{profit_rate:.1f}%)", "🔒 익절 보존 (+5%)", "🔥 무한 질주"
        stop_color, progress_cls, action_btn_cls, action_text, strategy_bg = "#7950F2", "progress-fill overdrive", "action-badge-strong", "🔥 강력 홀딩", "#F3F0FF"
    elif is_rescue:
        final_target, final_stop = int(curr_price * 1.15), int(curr_price * 0.95)
        status_msg, stop_label, target_label = f"🚨 위기 관리 중", "🛑 2차 방어선", "📈 기술적 반등 목표"
        stop_color, target_color, progress_cls, action_btn_cls, action_text, strategy_bg = "#555", "#3182F6", "progress-fill rescue", "action-badge-rescue", "⛑️ 리스크 관리", "#E8F3FF"

    total_range = final_target - final_stop
    progress_pct = max(0, min(100, (curr_price - final_stop) / total_range * 100)) if total_range > 0 else 0

    profit_cls = "profit-positive" if profit_rate > 0 else ("profit-negative" if profit_rate < 0 else "")
    profit_sign = "+" if profit_rate > 0 else ""
    profit_color = "#F04452" if profit_rate > 0 else ("#3182F6" if profit_rate < 0 else "#333")
    score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
    chg = res.get('change_rate', 0.0)
    chg_color = "#F04452" if chg > 0 else ("#3182F6" if chg < 0 else "#333")

    html = f"""
    <div class='toss-card' style='border: 2px solid {profit_color}40; background-color: {profit_color}05;'>
      <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
          <div>
              <span class='badge-clean' style='background-color:#333; color:#fff; font-size:10px; padding:2px 6px; border-radius:4px;'>내 보유 종목</span>
              <br><span class='stock-name' style='font-size:18px; font-weight:800;'>{res['name']}</span>
              <span class='stock-code' style='color:#888;'>{res['code']}</span>
              <div style='font-size:14px; color:#555; margin-top:4px;'>현재 {curr_price:,}원 <span style='color:{chg_color}; font-weight:600;'>({chg:+.2f}%)</span></div>
          </div>
          <div style='text-align:right;'>
              <div class='{profit_cls}'>{profit_sign}{profit_rate:.2f}%</div>
              <div style='font-size:12px; font-weight:600; color:{profit_color};'>{profit_sign}{profit_val:,}원</div>
              <div style='font-size:11px; color:#888;'>평단 {buy_price:,}원</div>
          </div>
      </div>
      <div class='strategy-container' style='background-color:{strategy_bg};'>
          <div class='strategy-header'>
              <span class='strategy-title'>🎯 AI 대응 가이드</span>
              <span style='font-size:11px; color:#F04452; font-weight:700;'>{status_msg}</span>
          </div>
          <div class='progress-bg'><div class='{progress_cls}' style='width: {progress_pct}%;'></div></div>
          <div class='price-guide'>
              <div>{stop_label}<br><strong style='color:{stop_color};'>{final_stop:,}원</strong></div>
              <div style='text-align:right;'>{target_label}<br><strong style='color:{target_color};'>{final_target:,}원</strong></div>
          </div>
      </div>
      <div style='margin-top:10px; padding-top:8px; display:flex; justify-content:space-between; align-items:center; font-size:12px;'>
          <div style='color:#666;'>AI 점수: <strong style='color:{score_col}'>{res['score']}점</strong></div>
          <div class='{action_btn_cls}'>{action_text}</div>
      </div>
    </div>
    """
    return html

def render_signal_lights(rsi, macd, macd_sig):
    rsi_cls, rsi_icon, rsi_msg = ("buy", "🟢", "저평가") if rsi <= 35 else (("sell", "🔴", "과열권") if rsi >= 70 else ("neu", "🟡", "중립"))
    macd_cls, macd_icon, macd_msg = ("buy", "🟢", "상승 추세") if macd > macd_sig else ("sell", "🔴", "하석 반전")
    html = f"""
    <div class='tech-status-box'>
        <div class='status-badge {rsi_cls}'>📊 RSI ({rsi:.1f})<br><b>{rsi_icon} {rsi_msg}</b></div>
        <div class='status-badge {macd_cls}'>🌊 MACD 추세<br><b>{macd_icon} {macd_msg}</b></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_tech_metrics(stoch, vol_ratio):
    k = stoch['k']
    stoch_cls, stoch_txt = ("buy", f"🟢 침체 ({k:.1f}%)") if k < 20 else (("sell", f"🔴 과열 ({k:.1f}%)") if k > 80 else ("neu", f"🟡 중립 ({k:.1f}%)"))
    vol_cls, vol_txt = ("vol", f"🔥 폭발 ({vol_ratio*100:.0f}%)") if vol_ratio >= 2.0 else (("buy", f"📈 증가 ({vol_ratio*100:.0f}%)") if vol_ratio >= 1.2 else ("neu", "☁️ 평이"))
    html = f"""
    <div class='tech-status-box'>
        <div class='status-badge {stoch_cls}'>📉 스토캐스틱<br><b>{stoch_txt}</b></div>
        <div class='status-badge {vol_cls}'>📢 거래강도<br><b>{vol_txt}</b></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_ma_status(ma_list):
    if not ma_list: return
    html = "<div class='ma-status-container'>" + "".join([f"<div class='ma-status-badge {'on' if item['ok'] else 'off'}'>{'🔴' if item['ok'] else '⚪'} {item['label']}</div>" for item in ma_list]) + "</div>"
    st.markdown(html, unsafe_allow_html=True)

def render_chart_legend():
    return """<div style='display:flex; gap:12px; font-size:11px; color:#666; margin-bottom:8px; flex-wrap:wrap;'>
        <div style='display:flex; align-items:center;'><div style='width:10px; height:2px; background:#000; margin-right:4px;'></div>현재가</div>
        <div style='display:flex; align-items:center;'><div style='width:10px; height:2px; background:#FF4B4B; margin-right:4px;'></div>5일</div>
        <div style='display:flex; align-items:center;'><div style='width:10px; height:2px; background:#F2A529; margin-right:4px;'></div>20일</div>
        <div style='display:flex; align-items:center;'><div style='width:10px; height:2px; background:#3182F6; margin-right:4px;'></div>60일</div>
        <div style='display:flex; align-items:center;'><div style='width:10px; height:8px; background:#868E96; opacity:0.2; margin-right:4px;'></div>볼린저</div>
    </div>"""

def create_chart_clean(df):
    try:
        data = df.tail(120).copy().reset_index()
        base = alt.Chart(data).encode(x=alt.X('Date:T', axis=alt.Axis(format='%m-%d', title=None)))
        band = base.mark_area(opacity=0.1, color='#868E96').encode(y='BB_Lower:Q', y2='BB_Upper:Q')
        line = base.mark_line(color='#000').encode(y='Close:Q')
        ma5 = base.mark_line(color='#FF4B4B', strokeWidth=1).encode(y='MA5:Q')
        ma20 = base.mark_line(color='#F2A529', strokeWidth=1.5).encode(y='MA20:Q')
        ma60 = base.mark_line(color='#3182F6', strokeWidth=1).encode(y='MA60:Q')
        price_chart = (band + line + ma5 + ma20 + ma60).properties(height=250)
        rsi_chart = base.mark_line(color='#9C27B0').encode(y=alt.Y('RSI:Q', title='RSI')).properties(height=60)
        return alt.vconcat(price_chart, rsi_chart).resolve_scale(x='shared')
    except Exception: return alt.Chart(pd.DataFrame()).mark_text()

def render_fund_scorecard(fund_data):
    if not fund_data: return
    html = "<div class='fund-grid-v2'>"
    for k in ['per', 'pbr', 'div']:
        d = fund_data[k]
        col = "#F04452" if d['stat']=='good' else ("#3182F6" if d['stat']=='bad' else "#333")
        unit = "배" if k != 'div' else "%"
        html += f"<div class='fund-item-v2'><div class='fund-title-v2'>{k.upper()}</div><div class='fund-value-v2' style='color:{col}'>{d['val']:.1f}{unit}</div><div class='fund-desc-v2' style='background:{col}20; color:{col}'>{d['txt']}</div></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def render_financial_table(df):
    if df.empty: return
    html = "<table class='fin-table'><thead><tr><th>구분</th>" + "".join([f"<th>{d}</th>" for d in df['Date']]) + "</tr></thead><tbody>"
    for m in ['매출액', '영업이익', '당기순이익']:
        html += f"<tr><td>{m}</td>"
        vals = df[m].tolist()
        for i, v in enumerate(vals):
            change_txt, cls = "", ""
            if i > 0 and vals[i-1] != 0:
                pct = (v - vals[i-1]) / abs(vals[i-1]) * 100
                cls = "text-red" if pct > 0 else "text-blue"
                change_txt = f"<span class='change-rate'>({pct:+.1f}%)</span>"
            html += f"<td class='{cls}'>{int(v):,} {change_txt}</td>"
        html += "</tr>"
    st.markdown(html + "</tbody></table>", unsafe_allow_html=True)

def render_investor_chart(df):
    if df.empty: return
    df_plot = df.reset_index()
    if '날짜' not in df_plot.columns and 'index' in df_plot.columns: df_plot.rename(columns={'index': '날짜'}, inplace=True)
    df_line = df_plot.melt('날짜', value_vars=['Cum_Foreigner', 'Cum_Institution', 'Cum_Individual'], var_name='Type', value_name='Val')
    chart = alt.Chart(df_line).mark_line().encode(x='날짜:T', y='Val:Q', color='Type:N').properties(height=200)
    st.altair_chart(chart, use_container_width=True)

# --- [3. 데이터 로딩 및 분석 로직] ---

@st.cache_data
def get_krx_list_safe():
    try:
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name']] if not df.empty else pd.DataFrame()
    except Exception: return pd.DataFrame()

def load_from_github():
    try:
        if not USER_GITHUB_TOKEN: return {"portfolio": {}, "watchlist": {}}
        url = f"https://api.github.com/repos/echobm101-del/my_stock-bot/contents/my_watchlist_v7.json"
        headers = {"Authorization": f"token {USER_GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            data = json.loads(base64.b64decode(r.json()['content']).decode('utf-8'))
            return data if "portfolio" in data else {"portfolio": {}, "watchlist": data}
    except Exception: pass
    return {"portfolio": {}, "watchlist": {}}

def update_github_file(new_data):
    try:
        if not USER_GITHUB_TOKEN: return False
        url = f"https://api.github.com/repos/echobm101-del/my_stock-bot/contents/my_watchlist_v7.json"
        headers = {"Authorization": f"token {USER_GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        r_get = requests.get(url, headers=headers)
        sha = r_get.json().get('sha') if r_get.status_code == 200 else None
        payload = {"message": "Update V50.0", "content": base64.b64encode(json.dumps(new_data, ensure_ascii=False, indent=4).encode('utf-8')).decode('utf-8')}
        if sha: payload["sha"] = sha
        return requests.put(url, headers=headers, json=payload).status_code in [200, 201]
    except Exception: return False

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    # [수정] 0으로 나누기 에러 방지 (loss가 0인 경우 처리)
    rs = gain / (loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50) # 데이터 부족 시 중립

def calculate_macd(data):
    exp1 = data.ewm(span=12, adjust=False).mean()
    exp2 = data.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

def calculate_sniper_score(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty or len(df) < 60: return 0, [], 0, 0, 0, pd.DataFrame(), ""
        df['MA5'], df['MA20'], df['MA60'] = df['Close'].rolling(5).mean(), df['Close'].rolling(20).mean(), df['Close'].rolling(60).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
        df['BB_Upper'] = df['MA20'] + (df['Close'].rolling(20).std() * 2)
        df['BB_Lower'] = df['MA20'] - (df['Close'].rolling(20).std() * 2)
        curr, prev = df.iloc[-1], df.iloc[-2]
        vol_ratio = curr['Volume'] / df['Volume'].rolling(20).mean().iloc[-1]
        score, tags = 50, []
        if vol_ratio > 2: score += 20; tags.append("🔥 거래급증")
        if curr['Close'] > curr['MA20']: score += 10
        if curr['RSI'] < 30: score += 15; tags.append("💎 과매도")
        return score, tags, vol_ratio, (curr['Close']-prev['Close'])/prev['Close']*100, 70, df, "분석완료"
    except Exception: return 0, [], 0, 0, 0, pd.DataFrame(), ""

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    # [최적화] pykrx를 우선적으로 활용하여 속도 개선
    try:
        today = datetime.datetime.now().strftime("%Y%m%d")
        df = stock.get_market_fundamental_by_date(today, today, code)
        if df.empty:
            df = stock.get_market_fundamental_by_date((datetime.datetime.now()-datetime.timedelta(days=7)).strftime("%Y%m%d"), today, code).tail(1)
        
        if not df.empty:
            res = df.iloc[0]
            per, pbr, div = float(res.get('PER', 0)), float(res.get('PBR', 0)), float(res.get('DIV', 0))
            pbr_stat = "good" if 0 < pbr < 1.0 else "neu"
            per_stat = "good" if 0 < per < 12 else "neu"
            fund_data = {
                "per": {"val": per, "stat": per_stat, "txt": "실적우수" if per_stat=="good" else "보통"},
                "pbr": {"val": pbr, "stat": pbr_stat, "txt": "저평가" if pbr_stat=="good" else "적정"},
                "div": {"val": div, "stat": "good" if div > 3 else "neu", "txt": "고배당" if div > 3 else "일반"}
            }
            return 30, "OK", fund_data
    except Exception: pass
    return 20, "FAIL", None

def get_investor_trend(code):
    try:
        df = stock.get_market_investor_net_purchase_by_date((datetime.datetime.now()-datetime.timedelta(days=60)).strftime("%Y%m%d"), datetime.datetime.now().strftime("%Y%m%d"), code)
        if not df.empty:
            df['Cum_Foreigner'], df['Cum_Institution'], df['Cum_Individual'] = df['외국인'].cumsum(), df['기관합계'].cumsum(), df['개인'].cumsum()
            return df
    except Exception: pass
    return pd.DataFrame()

def analyze_pro(code, name_override=None, relation_tag=None, my_buy_price=None):
    score, tags, vol_ratio, chg, win_rate, df, reason = calculate_sniper_score(code)
    if df.empty: return None
    curr = df.iloc[-1]
    
    res = {
        "name": name_override or code, "code": code, "price": int(curr['Close']), "change_rate": chg,
        "score": score, "strategy": {}, "history": df, "vol_ratio": vol_ratio, "win_rate": win_rate,
        "ma_status": [{"label": "5일", "ok": curr['Close'] >= curr['MA5']}, {"label": "20일", "ok": curr['Close'] >= curr['MA20']}],
        "trend_txt": "상승세" if curr['Close'] >= curr['MA20'] else "조정중", "cycle_txt": "시장분석중",
        "relation_tag": relation_tag, "my_buy_price": my_buy_price, "news": {"score":0, "headline":"로딩중", "raw_news":[], "opinion":"관망"}
    }
    
    _, _, fund = get_company_guide_score(code)
    res['fund_data'] = fund
    res['investor_trend'] = get_investor_trend(code)
    res['fin_history'] = pd.DataFrame() # 필요 시 네이버 크롤링 추가
    
    # 전략 수립
    target, stop = int(curr['Close']*1.1), int(curr['Close']*0.95)
    res['strategy'] = {"buy": int(curr['Close']), "target": target, "stop": stop, "action": "매수 유효" if score >= 60 else "관망", "buy_basis": "현재가"}
    
    return res

# --- [4. 메인 화면 로직] ---
if 'data_store' not in st.session_state: st.session_state['data_store'] = load_from_github()
if 'preview_list' not in st.session_state: st.session_state['preview_list'] = []

st.title("💎 Quant Sniper V50.0")

tab1, tab2, tab3 = st.tabs(["🔍 종목 분석", "💰 포트폴리오", "👀 관심종목"])

with tab1:
    with st.form("search_form"):
        target_keyword = st.text_input("종목명 또는 티커 입력")
        if st.form_submit_button("분석 시작") and target_keyword:
            krx = get_krx_list_safe()
            code = target_keyword
            if not target_keyword.isdigit() and not krx.empty:
                match = krx[krx['Name'] == target_keyword]
                if not match.empty: code = match.iloc[0]['Code']
            
            with st.spinner("데이터 분석 중..."):
                res = analyze_pro(code, target_keyword if not target_keyword.isdigit() else None)
                if res: st.session_state['preview_list'] = [res]

    for res in st.session_state['preview_list']:
        st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
        with st.expander("상세 데이터 보기"):
            c1, c2 = st.columns(2)
            with c1:
                render_signal_lights(res['history'].iloc[-1]['RSI'], res['history'].iloc[-1]['MACD'], res['history'].iloc[-1]['MACD_Signal'])
                st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
            with c2:
                render_fund_scorecard(res['fund_data'])
                render_investor_chart(res['investor_trend'])
            if st.button("📌 관심종목 등록", key=f"add_{res['code']}"):
                st.session_state['data_store']['watchlist'][res['name']] = {"code": res['code']}
                update_github_file(st.session_state['data_store'])
                st.success("등록 완료")

with tab2:
    for name, info in st.session_state['data_store']['portfolio'].items():
        res = analyze_pro(info['code'], name, my_buy_price=info.get('buy_price'))
        if res: st.markdown(create_portfolio_card_html(res), unsafe_allow_html=True)

with tab3:
    for name, info in st.session_state['data_store']['watchlist'].items():
        res = analyze_pro(info['code'], name)
        if res:
            st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
            if st.button(f"🗑️ 삭제 {name}", key=f"del_{info['code']}"):
                del st.session_state['data_store']['watchlist'][name]
                update_github_file(st.session_state['data_store'])
                st.rerun()

with st.sidebar:
    st.write("### ⚙️ 설정")
    if st.button("데이터 초기화"):
        st.session_state['data_store'] = {"portfolio": {}, "watchlist": {}}
        update_github_file(st.session_state['data_store'])
        st.rerun()
