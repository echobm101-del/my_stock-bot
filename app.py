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
from bs4 import BeautifulSoup
import re
import feedparser
import urllib.parse
import numpy as np
from io import StringIO
import OpenDartReader
import yfinance as yf

# ==============================================================================
# [0] 설정 및 보안 (Secrets)
# ==============================================================================
try:
    USER_GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
    USER_TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
    USER_CHAT_ID = st.secrets.get("CHAT_ID", "")
    USER_GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
    USER_DART_KEY = st.secrets.get("DART_API_KEY", "")
except:
    USER_GITHUB_TOKEN = ""
    USER_TELEGRAM_TOKEN = ""
    USER_CHAT_ID = ""
    USER_GOOGLE_API_KEY = ""
    USER_DART_KEY = ""

REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

st.set_page_config(page_title="Quant Sniper V50.14 (Universal Radar)", page_icon="💎", layout="wide")

# ==============================================================================
# [1] 스타일 및 UI 함수 (NameError 방지를 위해 맨 위로 배치)
# ==============================================================================
st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
    .stock-name { font-size: 20px; font-weight: 800; color: #333; margin-right: 6px; }
    .stock-code { font-size: 14px; color: #8B95A1; }
    .big-price { font-size: 24px; font-weight: 800; color: #333; margin-top: 4px; }
    .fund-grid-v2 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 10px; background-color: #F9FAFB; padding: 15px; border-radius: 12px; }
    .fund-item-v2 { text-align: center; }
    .fund-title-v2 { font-size: 12px; color: #8B95A1; margin-bottom: 5px; }
    .fund-value-v2 { font-size: 18px; font-weight: 800; color: #333D4B; }
    .fund-desc-v2 { font-size: 11px; font-weight: 600; margin-top: 4px; display: inline-block; padding: 2px 6px; border-radius: 4px;}
    .tech-status-box { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
    .status-badge { flex: 1; min-width: 120px; padding: 12px 10px; border-radius: 12px; text-align: center; font-size: 13px; font-weight: 700; color: #4E5968; background: #F2F4F6; border: 1px solid #E5E8EB; }
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
    .news-scroll-box { max-height: 200px; overflow-y: auto; border: 1px solid #F2F4F6; border-radius: 8px; padding: 10px; margin-top:5px; }
    .news-box { padding: 10px 0; border-bottom: 1px solid #F2F4F6; font-size: 13px; line-height: 1.4; }
    .news-link { color: #333; text-decoration: none; font-weight: 500; display: block; margin-bottom: 2px;}
    .news-link:hover { color: #3182F6; text-decoration: underline; }
    .news-date { font-size: 11px; color: #999; }
    .metric-box { background: #F9FAFB; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #E5E8EB; height: 100%; display: flex; flex-direction: column; justify-content: center; }
    .metric-title { font-size: 12px; color: #666; margin-bottom: 4px; }
    .metric-value { font-size: 16px; font-weight: bold; color: #333; margin-bottom: 2px;}
    .metric-badge { font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 700; display: inline-block; margin-top: 4px; }
    .fin-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; margin-bottom: 10px; border: 1px solid #E5E8EB; }
    .fin-table th { background-color: #F9FAFB; padding: 8px; border-bottom: 1px solid #E5E8EB; color: #4E5968; font-weight: 600; white-space: nowrap; }
    .fin-table td { padding: 8px; border-bottom: 1px solid #F2F4F6; color: #333; font-weight: 500; }
    .text-red { color: #F04452; font-weight: 700; }
    .text-blue { color: #3182F6; font-weight: 700; }
    .change-rate { font-size: 10px; color: #888; font-weight: 400; margin-left: 4px; }
    .cycle-badge { background-color:#E6FCF5; color:#087F5B; padding:4px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #B2F2BB; display:inline-block; margin-top:4px; }
    .cycle-badge.bear { background-color:#FFF5F5; color:#F04452; border-color:#FFD8A8; }
    .relation-badge { background-color:#F3F0FF; color:#7950F2; padding:3px 6px; border-radius:4px; font-size:10px; font-weight:700; border:1px solid #E5DBFF; margin-left:6px; vertical-align: middle; }
    .investor-table-container { margin-top: 10px; border: 1px solid #F2F4F6; border-radius: 8px; overflow: hidden; overflow-x: auto; }
    .investor-table { width: 100%; font-size: 11px; text-align: center; border-collapse: collapse; min-width: 300px; }
    .investor-table th { background-color: #F9FAFB; padding: 6px; color: #666; font-weight: 600; border-bottom: 1px solid #E5E8EB; white-space: nowrap; }
    .investor-table td { padding: 6px; border-bottom: 1px solid #F2F4F6; color: #333; }
    .profit-positive { color: #F04452; font-weight: 800; font-size: 20px; }
    .profit-negative { color: #3182F6; font-weight: 800; font-size: 20px; }
    .port-label { font-size: 11px; color: #888; margin-top: 4px; }
    .strategy-container { background-color: #F9FAFB; border-radius: 12px; padding: 12px; margin-top: 12px; border: 1px solid #E5E8EB; }
    .strategy-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .strategy-title { font-size: 12px; font-weight: 700; color: #4E5968; }
    .progress-bg { background-color: #E0E0E0; height: 10px; border-radius: 5px; overflow: hidden; margin-bottom: 8px; }
    .progress-fill { background: linear-gradient(90deg, #ff9a9e 0%, #ff5e62 100%); height: 100%; transition: width 0.5s ease; }
    .progress-fill.overdrive { background: linear-gradient(90deg, #FFD700 0%, #FDBB2D 50%, #8A2BE2 100%); }
    .progress-fill.rescue { background: linear-gradient(90deg, #a1c4fd 0%, #c2e9fb 100%); }
    .price-guide { display: flex; justify-content: space-between; font-size: 11px; color: #666; font-weight: 500; }
    .price-guide strong { color: #333; }
    .action-badge-default { background-color:#eee; color:#333; padding:4px 10px; border-radius:12px; font-weight:700; font-size:12px; }
    .action-badge-strong { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:#fff; padding:6px 14px; border-radius:16px; font-weight:800; font-size:12px; box-shadow: 0 2px 6px rgba(118, 75, 162, 0.4); animation: pulse 2s infinite; }
    .action-badge-rescue { background: linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%); color:#fff; padding:6px 14px; border-radius:16px; font-weight:800; font-size:12px; }
    @media screen and (max-width: 768px) {
        .toss-card { padding: 16px; border-radius: 20px; }
        .stock-name { font-size: 18px; }
        .big-price { font-size: 20px; }
        .fund-grid-v2 { gap: 8px; padding: 10px; }
        .fund-value-v2 { font-size: 15px; }
        .tech-status-box { gap: 8px; }
        .status-badge { padding: 10px 8px; font-size: 12px; }
        .fin-table { font-size: 11px; }
        .fin-table th, .fin-table td { padding: 6px 4px; }
        .toss-card > div:nth-child(2) { gap: 4px !important; }
        .toss-card > div:nth-child(2) > div { font-size: 11px !important; padding: 6px 2px !important; }
        .metric-box { padding: 10px; margin-bottom: 5px; }
        .metric-value { font-size: 14px; }
        .stTabs [data-baseweb="tab"] { font-size: 14px; padding: 10px; }
    }
</style>
""", unsafe_allow_html=True)

def create_watchlist_card_html(res):
    strategy = res.get('strategy', {})
    score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
    buy_price = strategy.get('buy', 0)
    target_price = strategy.get('target', 0)
    stop_price = strategy.get('stop', 0)
    buy_basis = strategy.get('buy_basis', '20일선')
    action_txt = strategy.get('action', '분석 중')
    
    badge_bg = f"{score_col}20"
    badge_fg = score_col
    if "유보" in action_txt or "데이터 부족" in action_txt:
        badge_bg = "#F2F4F6"; badge_fg = "#4E5968"
    
    chg = res.get('change_rate', 0.0)
    if chg > 0: chg_color = "#F04452"; chg_txt = f"(+{chg:.2f}% ▲)"
    elif chg < 0: chg_color = "#3182F6"; chg_txt = f"({chg:.2f}% ▼)"
    else: chg_color = "#333333"; chg_txt = f"({chg:.2f}% -)"

    cycle_cls = "bear" if "하락" in res['cycle_txt'] else ""
    backtest_txt = f"⚡ 검증 승률: {res['win_rate']}%" if res['win_rate'] > 0 else "⚡ 백테스팅 데이터 부족"
    relation_html = f"<span class='relation-badge'>🔗 {res['relation_tag']}</span>" if res.get('relation_tag') else ""

    return f"""
<div class='toss-card' style='border-left: 5px solid {score_col};'>
  <div style='display:flex; justify-content:space-between; align-items:center;'>
      <div>
          <span class='stock-name'>{res['name']}</span><span class='stock-code'>{res['code']}</span>{relation_html}
          <div class='cycle-badge {cycle_cls}'>{res['cycle_txt']}</div>
          <div class='big-price'>{res['price']:,}원 <span style='font-size:16px; color:{chg_color}; font-weight:600; margin-left:5px;'>{chg_txt}</span></div>
      </div>
      <div style='text-align:right;'>
          <div style='font-size:28px; font-weight:800; color:{score_col};'>{res['score']}점</div>
          <div class='badge-clean' style='background-color:{badge_bg}; color:{badge_fg}; font-weight:700;'>{action_txt}</div>
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

def create_portfolio_card_html(res):
    strategy = res.get('strategy', {})
    if not strategy: strategy = {'action': '분석 대기', 'buy': 0, 'target': 0, 'stop': 0}
    buy_price = res.get('my_buy_price', 0)
    curr_price = res['price']
    profit_rate = (curr_price - buy_price) / buy_price * 100 if buy_price > 0 else 0
    profit_val = curr_price - buy_price

    is_overdrive = profit_rate >= 10.0
    is_rescue = profit_rate <= -10.0
    
    final_target = int(buy_price * 1.10) 
    final_stop = int(buy_price * 0.95)   
    
    status_msg = f"목표까지 {max(final_target - curr_price, 0):,}원 남음"
    stop_label = "🛡️ 손절가 (-5%)"
    target_label = "🚀 목표가 (+10%)"
    stop_color = "#3182F6"
    target_color = "#F04452"
    
    progress_cls = "progress-fill" 
    action_btn_cls = "action-badge-default"
    action_text = strategy.get('action', '분석 대기')
    strategy_bg = "#F9FAFB"

    if is_overdrive:
        base_target_2nd = int(buy_price * 1.20)
        final_target = int(curr_price * 1.10) if curr_price >= base_target_2nd else base_target_2nd
        target_label = "🔥 무한 질주 (추세 추종)" if curr_price >= base_target_2nd else "🌟 2차 목표가 (+20%)"
        final_stop = int(buy_price * 1.05) 
        status_msg = f"🎉 목표 초과 달성 중 (+{profit_rate:.2f}%)"
        stop_label = "🔒 익절 보존선 (+5%)"
        stop_color = "#7950F2"
        progress_cls = "progress-fill overdrive"
        action_btn_cls = "action-badge-strong"
        action_text = "🔥 강력 홀딩 (수익 극대화)"
        strategy_bg = "#F3F0FF"

    elif is_rescue:
        final_target = int(curr_price * 1.15) 
        final_stop = int(curr_price * 0.95)   
        status_msg = f"🚨 위기 관리: 단기 반등 목표 {final_target:,}원"
        stop_label = "🛑 2차 방어선 (현재가 -5%)"
        target_label = "📈 기술적 반등 목표 (+15%)"
        stop_color = "#555" 
        target_color = "#3182F6" 
        progress_cls = "progress-fill rescue" 
        action_btn_cls = "action-badge-rescue"
        action_text = "⛑️ 리스크 관리 (반등 시 비중 축소)"
        strategy_bg = "#E8F3FF"

    progress_pct = max(0, min(100, (curr_price - final_stop) / (final_target - final_stop) * 100)) if (final_target - final_stop) > 0 else 0
    profit_cls = "profit-positive" if profit_rate > 0 else ("profit-negative" if profit_rate < 0 else "")
    profit_color = "#F04452" if profit_rate > 0 else ("#3182F6" if profit_rate < 0 else "#333")
    profit_sign = "+" if profit_rate > 0 else ""
    score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
    chg = res.get('change_rate', 0.0)
    chg_txt = f"{chg:+.2f}%" if chg != 0 else "0.00%"
    chg_color = "#F04452" if chg > 0 else ("#3182F6" if chg < 0 else "#333")

    return f"""
<div class='toss-card' style='border: 2px solid {profit_color}40; background-color: {profit_color}05;'>
  <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
      <div>
          <span class='badge-clean' style='background-color:#333; color:#fff; font-size:10px; margin-bottom:4px;'>내 보유 종목</span>
          <br><span class='stock-name'>{res['name']}</span>
          <span class='stock-code'>{res['code']}</span>
          <div style='font-size:14px; color:#555; margin-top:4px;'>현재 {curr_price:,}원 <span style='color:{chg_color}; font-weight:600;'>({chg_txt})</span></div>
      </div>
      <div style='text-align:right;'>
          <div class='{profit_cls}'>{profit_sign}{profit_rate:.2f}%</div>
          <div style='font-size:12px; font-weight:600; color:{profit_color};'>{profit_sign}{profit_val:,}원</div>
          <div style='font-size:11px; color:#888; margin-top:2px;'>평단 {buy_price:,}원</div>
      </div>
  </div>
  <div class='strategy-container' style='background-color:{strategy_bg};'>
      <div class='strategy-header'>
          <span class='strategy-title'>🎯 AI 대응 가이드</span>
          <span style='font-size:11px; color:#F04452; font-weight:700;'>{status_msg}</span>
      </div>
      <div class='progress-bg'>
          <div class='{progress_cls}' style='width: {progress_pct}%;'></div>
      </div>
      <div class='price-guide'>
          <div>{stop_label}<br><strong style='color:{stop_color};'>{final_stop:,}원</strong></div>
          <div style='text-align:right;'>{target_label}<br><strong style='color:{target_color};'>{final_target:,}원</strong></div>
      </div>
  </div>
  <div style='margin-top:10px; display:flex; justify-content:space-between; align-items:center; font-size:12px; color:#666;'>
      <div>AI 점수: <strong style='color:{score_col}'>{res['score']}점</strong></div>
      <div class='{action_btn_cls}'>{action_text}</div>
  </div>
</div>
"""

def render_signal_lights(rsi, macd, macd_sig):
    if rsi <= 35: rsi_cls = "buy"; rsi_icon = "🟢"; rsi_msg = "저평가"
    elif rsi >= 70: rsi_cls = "sell"; rsi_icon = "🔴"; rsi_msg = "과열권"
    else: rsi_cls = "neu"; rsi_icon = "🟡"; rsi_msg = "중립"

    macd_cls = "buy" if macd > macd_sig else "sell"
    macd_icon = "🟢" if macd > macd_sig else "🔴"
    macd_msg = "상승 추세" if macd > macd_sig else "하락 반전"

    st.markdown(f"""
    <div class='tech-status-box'>
        <div class='status-badge {rsi_cls}'><div>📊 RSI ({rsi:.1f})</div><div style='font-size:15px; margin-top:4px;'>{rsi_icon} {rsi_msg}</div></div>
        <div class='status-badge {macd_cls}'><div>🌊 MACD 추세</div><div style='font-size:15px; margin-top:4px;'>{macd_icon} {macd_msg}</div></div>
    </div>
    """, unsafe_allow_html=True)

def render_tech_metrics(stoch, vol_ratio):
    k = stoch['k']
    stoch_cls = "buy" if k < 20 else ("sell" if k > 80 else "neu")
    stoch_txt = f"🟢 침체" if k < 20 else (f"🔴 과열" if k > 80 else f"⚪ 중립")
    vol_cls = "vol" if vol_ratio >= 2.0 else ("buy" if vol_ratio >= 1.2 else "neu")
    vol_txt = f"🔥 폭발" if vol_ratio >= 2.0 else (f"📈 증가" if vol_ratio >= 1.2 else "☁️ 평이")

    st.markdown(f"""
    <div class='tech-status-box'>
        <div class='status-badge {stoch_cls}'><div>📉 스토캐스틱</div><div style='font-size:15px; margin-top:4px;'>{stoch_txt} ({k:.0f}%)</div></div>
        <div class='status-badge {vol_cls}'><div>📢 거래강도</div><div style='font-size:15px; margin-top:4px;'>{vol_txt} ({vol_ratio*100:.0f}%)</div></div>
    </div>
    """, unsafe_allow_html=True)

def render_ma_status(ma_list):
    if not ma_list: return
    html = "<div class='ma-status-container'>"
    for item in ma_list:
        cls = "on" if item['ok'] else "off"
        icon = "🔴" if item['ok'] else "⚪"
        html += f"<div class='ma-status-badge {cls}'>{icon} {item['label']}</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def render_chart_legend():
    st.markdown("""
    <div style='display:flex; gap:12px; font-size:12px; color:#555; margin-bottom:8px; align-items:center; flex-wrap:wrap;'>
       <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#000000; margin-right:4px;'></div>현재가</div>
       <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#FF4B4B; margin-right:4px;'></div>5일선</div>
       <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#F2A529; margin-right:4px;'></div>20일선</div>
       <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#3182F6; margin-right:4px;'></div>60일선</div>
       <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#9C27B0; margin-right:4px;'></div>120일선</div>
    </div>
    """, unsafe_allow_html=True)

def create_chart_clean(df):
    try:
        chart_data = df.tail(120).copy().reset_index()
        base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=alt.Axis(format='%m-%d', title=None)))
        band = base.mark_area(opacity=0.15, color='#868E96').encode(y='BB_Lower:Q', y2='BB_Upper:Q')
        line = base.mark_line(color='#000000').encode(y='Close:Q')
        ma5 = base.mark_line(color='#FF4B4B', strokeWidth=1.5).encode(y='MA5:Q')
        ma20 = base.mark_line(color='#F2A529', strokeWidth=1.5).encode(y='MA20:Q')
        ma60 = base.mark_line(color='#3182F6', strokeWidth=1.5).encode(y='MA60:Q')
        ma120 = base.mark_line(color='#9C27B0', strokeWidth=1).encode(y='MA120:Q')
        price_chart = (band + line + ma5 + ma20 + ma60 + ma120).properties(height=250)
        
        rsi_base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=None))
        rsi_line = rsi_base.mark_line(color='#9C27B0').encode(y=alt.Y('RSI:Q', title='RSI'))
        rsi_rule = rsi_base.mark_rule(color='gray', strokeDash=[2,2]).encode(y=alt.datum(30)) + rsi_base.mark_rule(color='gray', strokeDash=[2,2]).encode(y=alt.datum(70))
        rsi_chart = (rsi_line + rsi_rule).properties(height=60)
        
        macd_base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=None))
        macd_line = macd_base.mark_line(color='#2196F3').encode(y=alt.Y('MACD:Q', title='MACD'))
        signal_line = macd_base.mark_line(color='#FF5722').encode(y='MACD_Signal:Q')
        macd_chart = (macd_line + signal_line).properties(height=60)
        
        return alt.vconcat(price_chart, rsi_chart, macd_chart).resolve_scale(x='shared')
    except: return alt.Chart(pd.DataFrame()).mark_text()

def render_fund_scorecard(fund_data):
    if not fund_data: st.info("재무 정보 로딩 실패"); return
    per = fund_data['per']['val']
    pbr = fund_data['pbr']['val']
    div = fund_data['div']['val']
    per_col = "#F04452" if fund_data['per']['stat']=='good' else ("#3182F6" if fund_data['per']['stat']=='bad' else "#333")
    pbr_col = "#F04452" if fund_data['pbr']['stat']=='good' else ("#3182F6" if fund_data['pbr']['stat']=='bad' else "#333")
    div_col = "#F04452" if fund_data['div']['stat']=='good' else "#333"
    
    html = f"<div class='fund-grid-v2'>"
    html += f"<div class='fund-item-v2'><div class='fund-title-v2'>PER</div><div class='fund-value-v2' style='color:{per_col}'>{per:.1f}배</div><div class='fund-desc-v2' style='background-color:{per_col}20; color:{per_col}'>{fund_data['per']['txt']}</div></div>"
    html += f"<div class='fund-item-v2'><div class='fund-title-v2'>PBR</div><div class='fund-value-v2' style='color:{pbr_col}'>{pbr:.1f}배</div><div class='fund-desc-v2' style='background-color:{pbr_col}20; color:{pbr_col}'>{fund_data['pbr']['txt']}</div></div>"
    html += f"<div class='fund-item-v2'><div class='fund-title-v2'>배당률</div><div class='fund-value-v2' style='color:{div_col}'>{div:.1f}%</div><div class='fund-desc-v2' style='background-color:{div_col}20; color:{div_col}'>{fund_data['div']['txt']}</div></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def render_financial_table(df):
    if df.empty: return
    html = "<table class='fin-table'><thead><tr><th>구분</th>"
    for d in df['Date']: html += f"<th>{d}</th>"
    html += "</tr></thead><tbody>"
    for m in ['매출액', '영업이익', '당기순이익']:
        html += f"<tr><td>{m}</td>"
        for i, val in enumerate(df[m]):
            arrow = ""; color = ""
            if i>0 and df[m].iloc[i-1]!=0:
                pct = (val - df[m].iloc[i-1])/abs(df[m].iloc[i-1])*100
                if pct>0: arrow="▲"; color="text-red"
                elif pct<0: arrow="▼"; color="text-blue"
            html += f"<td class='{color}'>{int(val):,} {arrow}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)

def render_investor_chart(df):
    if df.empty:
        st.caption("수급 데이터가 없습니다.")
        return
    
    df = df.reset_index()
    if '날짜' not in df.columns: 
        if 'index' in df.columns: df.rename(columns={'index': '날짜'}, inplace=True)
    try: df['날짜'] = pd.to_datetime(df['날짜'])
    except: pass 

    cum_cols = [c for c in ['Cum_Individual', 'Cum_Foreigner', 'Cum_Institution'] if c in df.columns]
    df_line = df.melt('날짜', value_vars=cum_cols, var_name='Key', value_name='Cumulative')
    type_map = {'Cum_Individual': '개인', 'Cum_Foreigner': '외국인', 'Cum_Institution': '기관'}
    df_line['Type'] = df_line['Key'].map(type_map)
    
    chart = alt.Chart(df_line).mark_line().encode(
        x=alt.X('날짜:T', axis=alt.Axis(format='%m-%d', title=None)), 
        y=alt.Y('Cumulative:Q', axis=alt.Axis(title='누적 순매수')), 
        color=alt.Color('Type:N', legend=alt.Legend(orient="top", title=None))
    ).properties(height=250)
    st.altair_chart(chart, use_container_width=True)

    recent = df.tail(5).sort_values('날짜', ascending=False)
    html = "<div class='investor-table-container'><table class='investor-table'><thead><tr><th>날짜</th><th>외국인</th><th>기관</th><th>개인</th></tr></thead><tbody>"
    for _, row in recent.iterrows():
        d_str = row['날짜'].strftime('%m-%d')
        frgn = f"<span style='color:{'#F04452' if row.get('외국인',0)>0 else '#3182F6'}'>{int(row.get('외국인',0)):,}</span>"
        inst = f"<span style='color:{'#F04452' if row.get('기관합계',0)>0 else '#3182F6'}'>{int(row.get('기관합계',0)):,}</span>"
        indv = f"<span style='color:{'#F04452' if row.get('개인',0)>0 else '#3182F6'}'>{int(row.get('개인',0)):,}</span>"
        html += f"<tr><td>{d_str}</td><td>{frgn}</td><td>{inst}</td><td>{indv}</td></tr>"
    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)

# ==============================================================================
# [3] 유틸리티 및 데이터 처리 함수
# ==============================================================================
def load_from_github():
    try:
        if not USER_GITHUB_TOKEN: return {"portfolio": {}, "watchlist": {}}
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {USER_GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            data = json.loads(content)
            if "portfolio" not in data and "watchlist" not in data: return {"portfolio": {}, "watchlist": data}
            return data
        return {"portfolio": {}, "watchlist": {}}
    except: return {"portfolio": {}, "watchlist": {}}

def update_github_file(new_data):
    try:
        if not USER_GITHUB_TOKEN: return False
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {USER_GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        r_get = requests.get(url, headers=headers)
        sha = r_get.json().get('sha') if r_get.status_code == 200 else None
        
        json_str = json.dumps(new_data, ensure_ascii=False, indent=4)
        b64_content = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        data = {"message": "Update", "content": b64_content}
        if sha: data["sha"] = sha
        r_put = requests.put(url, headers=headers, json=data)
        return r_put.status_code in [200, 201]
    except: return False

def parse_relative_date(date_text):
    now = datetime.datetime.now()
    date_text = str(date_text).strip()
    try:
        if "분 전" in date_text: return now - datetime.timedelta(minutes=int(re.search(r'(\d+)', date_text).group(1)))
        elif "시간 전" in date_text: return now - datetime.timedelta(hours=int(re.search(r'(\d+)', date_text).group(1)))
        elif "일 전" in date_text: return now - datetime.timedelta(days=int(re.search(r'(\d+)', date_text).group(1)))
        elif "어제" in date_text: return now - datetime.timedelta(days=1)
        else: return pd.to_datetime(date_text.replace('.', '-').rstrip('-'))
    except: return now - datetime.timedelta(days=365)

def round_to_tick(price):
    if price < 2000: return int(round(price, -1))
    elif price < 5000: return int(round(price / 5) * 5)
    elif price < 20000: return int(round(price, -1))
    elif price < 50000: return int(round(price / 50) * 50)
    elif price < 200000: return int(round(price, -2))
    elif price < 500000: return int(round(price / 500) * 500)
    else: return int(round(price, -3))

@st.cache_data
def get_krx_list_safe():
    try:
        df_kospi = fdr.StockListing('KOSPI')
        df_kosdaq = fdr.StockListing('KOSDAQ')
        list_df = pd.concat([df_kospi, df_kosdaq])
        if 'Code' not in list_df.columns: list_df.rename(columns={'Symbol':'Code'}, inplace=True)
        if 'Name' not in list_df.columns: list_df.rename(columns={'Name':'Name'}, inplace=True)
        return list_df[['Code', 'Name']]
    except: return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_market_cycle_status(code):
    try:
        kospi = fdr.DataReader('KS11', datetime.datetime.now()-datetime.timedelta(days=400))
        ma120 = kospi['Close'].rolling(120).mean().iloc[-1]
        return "📈 시장 상승세 (공격적 매수 유효)" if kospi['Close'].iloc[-1] > ma120 else "📉 시장 하락세 (보수적 접근 필요)"
    except: return "시장 분석 중"

@st.cache_data(ttl=3600)
def get_macro_data():
    results = {}
    tickers = {"KOSPI": "KS11", "KOSDAQ": "KQ11", "S&P500": "US500", "USD/KRW": "USD/KRW"}
    for name, code in tickers.items():
        try:
            df = fdr.DataReader(code, datetime.datetime.now()-datetime.timedelta(days=14))
            curr = df.iloc[-1]
            results[name] = {"val": curr['Close'], "change": (curr['Close'] - curr['Open']) / curr['Open'] * 100}
        except: results[name] = {"val": 0.0, "change": 0.0}
    return results

def get_investor_trend(code):
    try:
        end = datetime.datetime.now().strftime("%Y%m%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=60)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(start, end, code)
        if not df.empty:
            df['Cum_Individual'] = df['개인'].cumsum()
            df['Cum_Foreigner'] = df['외국인'].cumsum()
            df['Cum_Institution'] = df['기관합계'].cumsum()
            return df
    except: pass
    
    try: # Naver Fallback
        url = f"https://finance.naver.com/item/frgn.naver?code={code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        try: dfs = pd.read_html(StringIO(res.text), match='날짜', header=0, encoding='euc-kr')
        except: dfs = pd.read_html(StringIO(res.text), header=0, encoding='euc-kr')
        df = dfs[1].dropna().copy()
        df.columns = [c[1] if isinstance(c, tuple) else c for c in df.columns]
        df.rename(columns={'날짜':'Date'}, inplace=True)
        inst = [c for c in df.columns if '기관' in str(c)][0]
        frgn = [c for c in df.columns if '외국인' in str(c)][0]
        df['기관'] = df[inst].astype(str).str.replace(',', '').astype(float)
        df['외국인'] = df[frgn].astype(str).str.replace(',', '').astype(float)
        df['개인'] = -(df['기관'] + df['외국인'])
        df['Cum_Individual'] = df['개인'].cumsum()
        df['Cum_Foreigner'] = df['외국인'].cumsum()
        df['Cum_Institution'] = df['기관'].cumsum()
        return df.iloc[:20]
    except: return pd.DataFrame()

def get_financial_history(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        dfs = pd.read_html(StringIO(res.text), encoding='euc-kr')
        for df in dfs:
            if '매출액' in str(df.iloc[:,0].values):
                df = df.set_index(df.columns[0])
                data = []
                for col in df.columns[-5:-1]:
                    try: data.append({"Date": str(col[1]).strip(), "매출액": float(df.loc['매출액', col]), "영업이익": float(df.loc['영업이익', col]), "당기순이익": float(df.loc['당기순이익', col])})
                    except: continue
                return pd.DataFrame(data)
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=1200)
def get_company_guide_score(code):
    per, pbr, div = 0.0, 0.0, 0.0
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        def get_val(id): return float(soup.select_one(f"#{id}").text.replace(',', '').replace('%', '').replace('배', '').strip())
        per = get_val("_per"); pbr = get_val("_pbr"); div = get_val("_dvr")
    except: pass
    
    return 0, "", {"per": {"val": per, "stat": "good" if 0<per<10 else "bad", "txt": ""}, "pbr": {"val": pbr, "stat": "good" if 0<pbr<1 else "bad", "txt": ""}, "div": {"val": div, "stat": "good" if div>3 else "bad", "txt": ""}}

@st.cache_data(ttl=3600)
def get_dart_disclosure_summary(code):
    if not USER_DART_KEY: return "DART API 키 미설정"
    try:
        dart = OpenDartReader(USER_DART_KEY)
        df = dart.list(code, start=(datetime.datetime.now()-datetime.timedelta(days=90)).strftime("%Y%m%d"), end=datetime.datetime.now().strftime("%Y%m%d"))
        if df is None or df.empty: return "최근 3개월 내 특이 공시 없음"
        return "\n".join([f"[{row['rcept_dt']}] {row['report_nm']}" for _, row in df.head(5).iterrows()])
    except: return "DART 조회 실패"

def get_naver_search_news(keyword):
    news = []
    try:
        url = f"https://search.naver.com/search.naver?where=news&query={urllib.parse.quote(keyword)}&sort=1"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(res.text, 'html.parser')
        for item in soup.select('div.news_area')[:5]:
            title = item.select_one('.news_tit').get_text().strip()
            link = item.select_one('.news_tit')['href']
            date = item.select_one('.info_group span.info').text.strip() if item.select_one('.info_group span.info') else ""
            news.append({"title": title, "link": link, "date": parse_relative_date(date).strftime("%Y-%m-%d")})
    except: pass
    return news

def call_gemini_dynamic(prompt):
    if not USER_GOOGLE_API_KEY: return None, "NO_KEY"
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={USER_GOOGLE_API_KEY}"
        res = requests.post(url, headers={"Content-Type": "application/json"}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        if res.status_code == 200: return res.json(), None
        return None, f"HTTP {res.status_code}"
    except Exception as e: return None, str(e)

@st.cache_data(ttl=600)
def get_news_sentiment_llm(name, stock_context={}):
    news_list = get_naver_search_news(name)
    news_titles = [f"- {n['date']} {n['title']}" for n in news_list]
    if not news_titles: return {"score": 0, "headline": "뉴스 없음", "opinion": "중립", "risk": "", "catalyst": "", "raw_news": [], "method": "none"}
    
    dart = get_dart_disclosure_summary(stock_context.get('code',''))
    prompt = f"종목: {name}\n뉴스:\n{chr(10).join(news_titles)}\n공시:\n{dart}\n위 데이터를 보고 투자 의견을 JSON으로 줘. 형식: {{score: -10~10, opinion: '매수/매도/관망', summary: '한줄요약', catalyst: '재료', risk: '리스크'}}"
    
    res, err = call_gemini_dynamic(prompt)
    if res:
        try:
            txt = res['candidates'][0]['content']['parts'][0]['text'].replace("```json", "").replace("```", "").strip()
            return {**json.loads(txt), "raw_news": news_list, "method": "ai"}
        except: pass
    return {"score": 0, "headline": "AI 분석 실패", "opinion": "관망", "risk": "API 오류", "catalyst": "", "raw_news": news_list, "method": "keyword"}

def get_ai_recommended_stocks(keyword):
    prompt = f"'{keyword}' 관련 한국 주식 5개를 JSON으로 추천해줘. 형식: [{{'name':'삼성전자', 'code':'005930', 'relation':'대장주'}}]"
    res, err = call_gemini_dynamic(prompt)
    if res:
        try:
            return json.loads(res['candidates'][0]['content']['parts'][0]['text'].replace("```json", "").replace("```", "").strip()), "완료"
        except: pass
    return [], "실패"

def get_naver_theme_stocks(keyword):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get("https://finance.naver.com/sise/theme.naver", headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser', from_encoding='euc-kr')
        for t in soup.select('table.type_1 tr td.col_type1 a'):
            if keyword in t.text:
                res2 = requests.get("https://finance.naver.com" + t['href'], headers=headers)
                soup2 = BeautifulSoup(res2.text, 'html.parser', from_encoding='euc-kr')
                stocks = []
                for row in soup2.select('div.box_type_l table.type_5 tr'):
                    a = row.select_one('td.name a')
                    if a: stocks.append({"code": a['href'].split('=')[-1], "name": a.text.strip()})
                return stocks, f"테마 발견: {len(stocks)}개"
    except: pass
    return [], "실패"

# ==============================================================================
# [4] 분석 로직 (Sniper Score)
# ==============================================================================
def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_sniper_score(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if len(df) < 60: return 0, [], 0, 0, 0, pd.DataFrame(), ""
        
        df['MA5'] = df['Close'].rolling(5).mean()
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        df['BB_Upper'] = df['MA20'] + (df['Close'].rolling(20).std() * 2)
        df['BB_Lower'] = df['MA20'] - (df['Close'].rolling(20).std() * 2)
        
        curr = df.iloc[-1]
        score = 50; tags = []
        reason = "관망"
        
        if curr['Close'] > curr['MA20']: score += 20
        if curr['RSI'] < 30: score += 10; tags.append("💎 과매도")
        if curr['MACD'] > curr['MACD_Signal']: score += 10; tags.append("🌊 골든크로스")
        
        vol_ratio = curr['Volume'] / df['Volume'].rolling(20).mean().iloc[-1] if df['Volume'].rolling(20).mean().iloc[-1] > 0 else 0
        if vol_ratio >= 3.0: score += 20; tags.append("🔥 거래량폭발")

        return score, tags, vol_ratio, 0.0, 0, df, reason
    except: return 0, [], 0, 0, 0, pd.DataFrame(), "오류"

def analyze_pro(code, name_override=None, relation_tag=None, my_buy_price=None):
    score, tags, vol_ratio, chg, win, df, reason = calculate_sniper_score(code)
    if df.empty: return None
    
    curr = df.iloc[-1]
    name = name_override if name_override else code
    atr = curr['Close'] * 0.03
    
    res = {
        "name": name, "code": code, "price": int(curr['Close']), "change_rate": chg,
        "score": score,
        "strategy": {
            "action": "관망" if score < 60 else "매수",
            "buy": int(curr['Close']), "target": int(curr['Close'] + atr*3), "stop": int(curr['Close'] - atr*1.5),
            "buy_basis": reason
        },
        "history": df, "relation_tag": relation_tag, "my_buy_price": my_buy_price,
        "stoch": {"k": curr['RSI'], "d": 0}, "vol_ratio": vol_ratio, "win_rate": win,
        "cycle_txt": get_market_cycle_status(code), "trend_txt": reason, "ma_status": []
    }
    
    res['investor_trend'] = get_investor_trend(code)
    res['fin_history'] = get_financial_history(code)
    _, _, fund_data = get_company_guide_score(code)
    res['fund_data'] = fund_data
    
    context = {"code": code, "current_price": curr['Close']}
    res['news'] = get_news_sentiment_llm(name, context)
    
    return res

def run_single_stock_simulation(df):
    try:
        if len(df) < 100: return None
        balance = 1000000; shares = 0; wins = 0; trades = 0
        for i in range(len(df)-90, len(df)):
            row = df.iloc[i]
            if shares == 0 and row['RSI'] < 40 and row['Close'] > row['MA20']:
                shares = int(balance / row['Close']); balance -= shares * row['Close']; trades += 1
            elif shares > 0 and (row['Close'] >= df.iloc[i-1]['Close']*1.05 or row['Close'] <= df.iloc[i-1]['Close']*0.97):
                balance += shares * row['Close']; shares = 0; wins += 1
        return {"return": (balance - 1000000)/10000, "win_rate": (wins/trades*100) if trades else 0, "trades": trades}
    except: return None

def scan_market_candidates(target_df, progress_bar, status_text):
    results = []
    limit = min(len(target_df), 30)
    for i in range(limit):
        try:
            row = target_df.iloc[i]
            progress_bar.progress((i+1)/limit)
            status_text.text(f"Scanning... {row['Name']}")
            df = fdr.DataReader(row['Code'], datetime.datetime.now()-datetime.timedelta(days=100))
            if len(df) < 60: continue
            rsi = calculate_rsi(df['Close']).iloc[-1]
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            if rsi < 45 and df['Close'].iloc[-1] > ma20:
                results.append({"name": row['Name'], "code": row['Code'], "price": df['Close'].iloc[-1], "rsi": round(rsi,1), "score": "조건만족"})
        except: continue
    return results

# ==============================================================================
# [5] 메인 실행 (Main)
# ==============================================================================
if 'data_store' not in st.session_state: st.session_state['data_store'] = load_from_github()
if 'preview_list' not in st.session_state: st.session_state['preview_list'] = []
if 'current_theme_name' not in st.session_state: st.session_state['current_theme_name'] = ""

col_title, col_guide = st.columns([0.7, 0.3])
with col_title: st.title("💎 Quant Sniper V50.14 (Universal Radar)")

with st.expander("🌍 글로벌 시장 & 매크로 (Click)", expanded=False):
    macro = get_macro_data()
    if macro:
        cols = st.columns(len(macro))
        for i, (key, val) in enumerate(macro.items()):
            color = "#F04452" if val['change'] > 0 else "#3182F6"
            with cols[i]: st.markdown(f"<div class='metric-box'><div class='metric-title'>{key}</div><div class='metric-value' style='color:{color}'>{val['val']:,.2f}</div><div style='font-size:12px; color:{color}'>{val['change']:+.2f}%</div></div>", unsafe_allow_html=True)
    else: st.info("매크로 데이터 로딩 중...")

tab1, tab2, tab3 = st.tabs(["🔍 발굴/테마", "💰 내 잔고", "👀 관심 종목"])

with tab1:
    if st.button("🔄 화면 정리"): st.session_state['preview_list'] = []; st.rerun()
    if st.session_state['preview_list']:
        st.markdown(f"### 🔍 '{st.session_state['current_theme_name']}' 심층 분석")
        with st.spinner("🚀 분석 중..."):
            preview_results = []
            for item in st.session_state['preview_list']:
                res = analyze_pro(item['code'], item['name'], item.get('relation_tag'))
                if res: preview_results.append(res)
            preview_results.sort(key=lambda x: x['score'], reverse=True)
            
        for res in preview_results:
            st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
            with st.expander(f"상세 분석 ({res['name']})"):
                c1, c2 = st.columns([1, 4])
                with c1: 
                    if st.button("관심등록", key=f"add_{res['code']}"):
                        st.session_state['data_store']['watchlist'][res['name']] = {'code': res['code']}
                        update_github_file(st.session_state['data_store'])
                        st.success("완료")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("###### 📈 기술적 분석")
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_signal_lights(res['history'].iloc[-1]['RSI'], res['history'].iloc[-1]['MACD'], res['history'].iloc[-1]['MACD_Signal'])
                with col2:
                    st.write("###### 🏢 재무 & 수급")
                    render_fund_scorecard(res['fund_data'])
                    render_investor_chart(res['investor_trend'])
                    render_financial_table(res['fin_history'])
                
                st.write("###### 📰 AI 리포트")
                st.markdown(f"<div class='news-ai'><b>{res['news']['headline']}</b><br>{res['news']['risk']}</div>", unsafe_allow_html=True)
                
                if st.button(f"🧪 시뮬레이션 ({res['name']})", key=f"sim_{res['code']}"):
                    sim = run_single_stock_simulation(res['history'])
                    if sim: st.success(f"수익률: {sim['return']:.1f}%")

with tab2:
    portfolio = st.session_state['data_store'].get('portfolio', {})
    if not portfolio: st.info("보유 종목이 없습니다.")
    else:
        with st.spinner("분석 중..."):
            for name, info in portfolio.items():
                res = analyze_pro(info['code'], name, None, float(info.get('buy_price',0)))
                if res:
                    st.markdown(create_portfolio_card_html(res), unsafe_allow_html=True)
                    with st.expander(f"상세 분석 ({res['name']})"):
                        if st.button("삭제", key=f"del_p_{res['code']}"):
                            del st.session_state['data_store']['portfolio'][name]
                            update_github_file(st.session_state['data_store'])
                            st.rerun()
                        render_investor_chart(res['investor_trend'])

with tab3:
    watchlist = st.session_state['data_store'].get('watchlist', {})
    if not watchlist: st.info("관심 종목이 없습니다.")
    else:
        with st.spinner("분석 중..."):
            for name, info in watchlist.items():
                res = analyze_pro(info['code'], name)
                if res:
                    st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
                    with st.expander("상세 보기"):
                        if st.button("삭제", key=f"del_w_{res['code']}"):
                            del st.session_state['data_store']['watchlist'][name]
                            update_github_file(st.session_state['data_store'])
                            st.rerun()
                        render_investor_chart(res['investor_trend'])

with st.sidebar:
    st.header("⚙️ 스나이퍼 메뉴")
    with st.expander("🔍 AI 종목 발굴"):
        kwd = st.text_input("검색어")
        if st.button("분석 시작"):
            with st.spinner("검색 중..."):
                df_krx = get_krx_list_safe()
                if kwd in df_krx['Name'].values:
                    code = df_krx[df_krx['Name']==kwd]['Code'].iloc[0]
                    res = analyze_pro(code, kwd)
                    if res: st.session_state['preview_list'] = [res]; st.rerun()
                else:
                    stocks, msg = get_ai_recommended_stocks(kwd)
                    if stocks: st.session_state['preview_list'] = stocks; st.rerun()
                    else: st.error("결과 없음")

    with st.expander("📡 시장 레이더"):
        if st.button("KOSPI 상위 스캔"):
            df = get_krx_list_safe()
            cands = scan_market_candidates(df.head(50), st.progress(0), st.empty())
            if cands: st.session_state['preview_list'] = cands; st.rerun()

    st.markdown("---")
    with st.expander("➕ 수동 추가"):
        n = st.text_input("이름"); c = st.text_input("코드")
        if st.button("추가"):
            st.session_state['data_store']['watchlist'][n] = {'code': c}
            update_github_file(st.session_state['data_store'])
            st.rerun()
