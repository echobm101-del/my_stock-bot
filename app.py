import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
from datetime import timedelta
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
from dateutil import parser as date_parser

# [New] DART 라이브러리 추가
try:
    import OpenDartReader
except ImportError:
    st.error("OpenDartReader가 설치되지 않았습니다. requirements.txt에 'opendartreader'를 추가해주세요.")

# --- [0. 초기화 및 세션 설정 (에러 방지 핵심)] ---
# 이 부분이 가장 먼저 실행되어야 KeyError가 발생하지 않습니다.
if 'data_store' not in st.session_state: st.session_state['data_store'] = {"portfolio": {}, "watchlist": {}}
if 'preview_list' not in st.session_state: st.session_state['preview_list'] = []
if 'current_theme_name' not in st.session_state: st.session_state['current_theme_name'] = ""
if 'ai_cache' not in st.session_state: st.session_state['ai_cache'] = {}

# ==============================================================================
# [보안 설정] Streamlit Secrets에서 키 가져오기
# ==============================================================================
try:
    USER_GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    USER_TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    USER_CHAT_ID = st.secrets["CHAT_ID"]
    USER_GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    USER_NAVER_ID = st.secrets.get("NAVER_CLIENT_ID", "")
    USER_NAVER_SECRET = st.secrets.get("NAVER_CLIENT_SECRET", "")
    USER_DART_KEY = st.secrets.get("DART_API_KEY", "")
except Exception as e:
    USER_GITHUB_TOKEN = ""
    USER_TELEGRAM_TOKEN = ""
    USER_CHAT_ID = ""
    USER_GOOGLE_API_KEY = ""
    USER_NAVER_ID = ""
    USER_NAVER_SECRET = ""
    USER_DART_KEY = ""

# --- [1. UI 스타일링] ---
st.set_page_config(page_title="Quant Sniper V49.9 (Rescue Mode)", page_icon="💎", layout="wide")

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
    
    /* DART Disclosure Style */
    .dart-box { padding: 6px 0; border-bottom: 1px solid #F2F4F6; font-size: 12px; display: flex; justify-content: space-between; }
    .dart-title { color: #333; font-weight: 500; text-decoration: none; }
    .dart-title:hover { color: #D9480F; text-decoration: underline; }
    .dart-badge { font-size: 10px; padding: 2px 4px; border-radius: 4px; background-color: #FFF0EB; color: #D9480F; font-weight: 700; margin-right: 5px; }
    
    .metric-box { background: #F9FAFB; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #E5E8EB; height: 100%; display: flex; flex-direction: column; justify-content: center; }
    .metric-title { font-size: 12px; color: #666; margin-bottom: 4px; }
    .metric-value { font-size: 16px; font-weight: bold; color: #333; margin-bottom: 2px;}
    .metric-badge { font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 700; display: inline-block; margin-top: 4px; }

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
    
    .cycle-badge { background-color:#E6FCF5; color:#087F5B; padding:4px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #B2F2BB; display:inline-block; margin-top:4px; }
    .cycle-badge.bear { background-color:#FFF5F5; color:#F04452; border-color:#FFD8A8; }
    
    .relation-badge { background-color:#F3F0FF; color:#7950F2; padding:3px 6px; border-radius:4px; font-size:10px; font-weight:700; border:1px solid #E5DBFF; margin-left:6px; vertical-align: middle; }
    
    .investor-table-container { margin-top: 10px; border: 1px solid #F2F4F6; border-radius: 8px; overflow: hidden; }
    .investor-table { width: 100%; font-size: 11px; text-align: center; border-collapse: collapse; }
    .investor-table th { background-color: #F9FAFB; padding: 6px; color: #666; font-weight: 600; border-bottom: 1px solid #E5E8EB; }
    .investor-table td { padding: 6px; border-bottom: 1px solid #F2F4F6; color: #333; }
    
    .profit-positive { color: #F04452; font-weight: 800; font-size: 20px; }
    .profit-negative { color: #3182F6; font-weight: 800; font-size: 20px; }
    .port-label { font-size: 11px; color: #888; margin-top: 4px; }
    
    /* V49.9 Dynamic Strategy Styles */
    .strategy-container { background-color: #F9FAFB; border-radius: 12px; padding: 12px; margin-top: 12px; border: 1px solid #E5E8EB; }
    .strategy-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .strategy-title { font-size: 12px; font-weight: 700; color: #4E5968; }
    
    .progress-bg { background-color: #E0E0E0; height: 10px; border-radius: 5px; overflow: hidden; margin-bottom: 8px; }
    
    /* Mode 1: Normal (Red) */
    .progress-fill { background: linear-gradient(90deg, #ff9a9e 0%, #ff5e62 100%); height: 100%; transition: width 0.5s ease; }
    
    /* Mode 2: Overdrive (Gold/Purple) */
    .progress-fill.overdrive { background: linear-gradient(90deg, #FFD700 0%, #FDBB2D 50%, #8A2BE2 100%); }
    
    /* Mode 3: Rescue/Loss (Blue) */
    .progress-fill.rescue { background: linear-gradient(90deg, #a1c4fd 0%, #c2e9fb 100%); }
    
    .price-guide { display: flex; justify-content: space-between; font-size: 11px; color: #666; font-weight: 500; }
    .price-guide strong { color: #333; }
    
    /* Button Styles */
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
    if chg > 0: 
        chg_color = "#F04452"
        chg_txt = f"(+{chg:.2f}% ▲)"
    elif chg < 0: 
        chg_color = "#3182F6"
        chg_txt = f"({chg:.2f}% ▼)"
    else: 
        chg_color = "#333333"
        chg_txt = f"({chg:.2f}% -)"

    cycle_cls = "bear" if "하락" in res['cycle_txt'] else ""
    backtest_txt = f"⚡ 검증 승률: {res['win_rate']}%" if res['win_rate'] > 0 else "⚡ 백테스팅 데이터 부족"
    
    relation_html = ""
    if res.get('relation_tag'):
        relation_html = f"<span class='relation-badge'>🔗 {res['relation_tag']}</span>"

    html = ""
    html += f"<div class='toss-card' style='border-left: 5px solid {score_col};'>"
    html += f"  <div style='display:flex; justify-content:space-between; align-items:center;'>"
    html += f"      <div>"
    html += f"          <span class='stock-name'>{res['name']}</span>"
    html += f"          <span class='stock-code'>{res['code']}</span>"
    html += f"          {relation_html}"
    html += f"          <div class='cycle-badge {cycle_cls}'>{res['cycle_txt']}</div>"
    html += f"          <div class='big-price'>{res['price']:,}원 <span style='font-size:16px; color:{chg_color}; font-weight:600; margin-left:5px;'>{chg_txt}</span></div>"
    html += f"      </div>"
    html += f"      <div style='text-align:right;'>"
    html += f"          <div style='font-size:28px; font-weight:800; color:{score_col};'>{res['score']}점</div>"
    html += f"          <div class='badge-clean' style='background-color:{score_col}20; color:{score_col}; font-weight:700;'>{res['strategy']['action']}</div>"
    html += f"      </div>"
    html += f"  </div>"
    html += f"  <div style='margin-top:15px; padding-top:10px; border-top:1px solid #F2F4F6; display:grid; grid-template-columns: 1fr 1fr 1fr; gap:5px; font-size:12px; font-weight:700; text-align:center;'>"
    html += f"      <div style='color:#3182F6; background-color:#E8F3FF; padding:6px; border-radius:6px;'>🛒 진입 구간 {buy_price:,}<br><span style='font-size:10px; opacity:0.7;'>({buy_basis})</span></div>"
    html += f"      <div style='color:#F04452; background-color:#FFF1F1; padding:6px; border-radius:6px;'>💰 수익 구간 {target_price:,}<br><span style='font-size:10px; opacity:0.7;'>(기분 좋은 익절)</span></div>"
    html += f"      <div style='color:#4E5968; background-color:#F2F4F6; padding:6px; border-radius:6px;'>🛡️ 안전벨트 {stop_price:,}<br><span style='font-size:10px; opacity:0.7;'>(내 돈 지키기)</span></div>"
    html += f"  </div>"
    html += f"  <div style='margin-top:8px; display:flex; justify-content:space-between; align-items:center;'>"
    html += f"        <span style='font-size:11px; font-weight:700; color:#555;'>{backtest_txt}</span>"
    html += f"        <span style='font-size:12px; color:#888;'>{res['trend_txt']}</span>"
    html += f"  </div>"
    html += f"</div>"
    return html

def create_portfolio_card_html(res):
    # [V49.9] 상황별 3단 변신 카드 (일반/오버드라이브/구조대)
    buy_price = res.get('my_buy_price', 0)
    curr_price = res['price']
    
    profit_rate = 0.0
    profit_val = 0
    if buy_price > 0:
        profit_rate = (curr_price - buy_price) / buy_price * 100
        profit_val = curr_price - buy_price

    # --- 전략 분기 (Strategy Branching) ---
    is_overdrive = False
    is_rescue = False
    
    # 변수 초기화 (기본 모드: -10% ~ +10%)
    final_target = int(buy_price * 1.10) # +10%
    final_stop = int(buy_price * 0.95)   # -5%
    
    status_msg = f"목표까지 {max(final_target - curr_price, 0):,}원 남음"
    stop_label = "🛡️ 손절가 (-5%)"
    target_label = "🚀 목표가 (+10%)"
    stop_color = "#3182F6"
    target_color = "#F04452"
    
    progress_cls = "progress-fill" # Default Red
    action_btn_cls = "action-badge-default"
    action_text = res['strategy']['action']
    strategy_bg = "#F9FAFB"

    # [CASE 1] 오버드라이브 모드 (수익률 +10% 이상)
    if profit_rate >= 10.0:
        is_overdrive = True
        
        # 무한 추격 로직 (Infinite Chasing)
        base_target_2nd = int(buy_price * 1.20)
        if curr_price >= base_target_2nd:
            final_target = int(curr_price * 1.10) # 현재가보다 더 위로 도망감
            target_label = "🔥 무한 질주 (추세 추종)"
        else:
            final_target = base_target_2nd
            target_label = "🌟 2차 목표가 (+20%)"

        final_stop = int(buy_price * 1.05) # 익절 보존 (+5%)
        
        status_msg = f"🎉 목표 초과 달성 중 (+{profit_rate:.2f}%)"
        stop_label = "🔒 익절 보존선 (+5%)"
        stop_color = "#7950F2" # Purple for Profit lock
        
        progress_cls = "progress-fill overdrive"
        action_btn_cls = "action-badge-strong"
        action_text = "🔥 강력 홀딩 (수익 극대화)"
        strategy_bg = "#F3F0FF"

    # [CASE 2] 구조대(Rescue) 모드 (수익률 -10% 이하)
    elif profit_rate <= -10.0:
        is_rescue = True
        
        # 현실적인 탈출 목표 설정 (현재가 기준)
        final_target = int(curr_price * 1.15) # 현재가 대비 +15% (기술적 반등 목표)
        final_stop = int(curr_price * 0.95)   # 현재가 대비 -5% (추가 급락 방지)
        
        status_msg = f"🚨 위기 관리: 단기 반등 목표 {final_target:,}원"
        
        stop_label = "🛑 2차 방어선 (현재가 -5%)"
        target_label = "📈 기술적 반등 목표 (+15%)"
        stop_color = "#555" # Dark Gray
        target_color = "#3182F6" # Blue (Cold/Recovery)
        
        progress_cls = "progress-fill rescue" # Blue/Cold Gradient
        action_btn_cls = "action-badge-rescue"
        action_text = "⛑️ 리스크 관리 (반등 시 비중 축소)"
        strategy_bg = "#E8F3FF"

    # --- 프로그레스 바 계산 ---
    progress_pct = 0
    if is_rescue:
        # 구조대 모드는 '현재가'가 기준 (0% 지점)
        total_range = final_target - final_stop
        current_range = curr_price - final_stop
        if total_range > 0:
            progress_pct = (current_range / total_range) * 100
            progress_pct = max(0, min(100, progress_pct))
    elif buy_price > 0:
        # 일반/오버드라이브: [평단 ~ 목표] 또는 [익절선 ~ 목표]
        total_range = final_target - final_stop
        current_range = curr_price - final_stop
        
        if total_range > 0:
            progress_pct = (current_range / total_range) * 100
            progress_pct = max(0, min(100, progress_pct))

    # --- HTML 조립 ---
    profit_cls = "profit-positive" if profit_rate > 0 else ("profit-negative" if profit_rate < 0 else "")
    profit_sign = "+" if profit_rate > 0 else ""
    profit_color = "#F04452" if profit_rate > 0 else ("#3182F6" if profit_rate < 0 else "#333")
    score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
    chg = res.get('change_rate', 0.0)
    chg_txt = f"{chg:+.2f}%" if chg != 0 else "0.00%"
    chg_color = "#F04452" if chg > 0 else ("#3182F6" if chg < 0 else "#333")

    html = ""
    html += f"<div class='toss-card' style='border: 2px solid {profit_color}40; background-color: {profit_color}05;'>"
    html += f"  <div style='display:flex; justify-content:space-between; align-items:flex-start;'>"
    html += f"      <div>"
    html += f"          <span class='badge-clean' style='background-color:#333; color:#fff; font-size:10px; margin-bottom:4px;'>내 보유 종목</span>"
    html += f"          <br><span class='stock-name'>{res['name']}</span>"
    html += f"          <span class='stock-code'>{res['code']}</span>"
    html += f"          <div style='font-size:14px; color:#555; margin-top:4px;'>현재 {curr_price:,}원 <span style='color:{chg_color}; font-weight:600;'>({chg_txt})</span></div>"
    html += f"      </div>"
    html += f"      <div style='text-align:right;'>"
    html += f"          <div class='{profit_cls}'>{profit_sign}{profit_rate:.2f}%</div>"
    html += f"          <div style='font-size:12px; font-weight:600; color:{profit_color};'>{profit_sign}{profit_val:,}원</div>"
    html += f"          <div style='font-size:11px; color:#888; margin-top:2px;'>평단 {buy_price:,}원</div>"
    html += f"      </div>"
    html += f"  </div>"
    
    # 전략 컨테이너
    html += f"  <div class='strategy-container' style='background-color:{strategy_bg};'>"
    html += f"      <div class='strategy-header'>"
    html += f"          <span class='strategy-title'>🎯 AI 대응 가이드</span>"
    html += f"          <span style='font-size:11px; color:#F04452; font-weight:700;'>{status_msg}</span>"
    html += f"      </div>"
    
    # Progress Bar
    html += f"      <div class='progress-bg'>"
    html += f"          <div class='{progress_cls}' style='width: {progress_pct}%;'></div>"
    html += f"      </div>"
    
    # Labels
    html += f"      <div class='price-guide'>"
    html += f"          <div>{stop_label}<br><strong style='color:{stop_color};'>{final_stop:,}원</strong></div>"
    html += f"          <div style='text-align:right;'>{target_label}<br><strong style='color:{target_color};'>{final_target:,}원</strong></div>"
    html += f"      </div>"
    html += f"  </div>"
    
    # Footer
    html += f"  <div style='margin-top:10px; padding-top:8px; display:flex; justify-content:space-between; align-items:center; font-size:12px; color:#666;'>"
    html += f"      <div>AI 점수: <strong style='color:{score_col}'>{res['score']}점</strong></div>"
    html += f"      <div class='{action_btn_cls}'>{action_text}</div>"
    html += f"  </div>"
    html += f"</div>"
    
    return html

def render_signal_lights(rsi, macd, macd_sig):
    if rsi <= 35:
        rsi_cls = "buy"; rsi_icon = "🟢"; rsi_msg = "저평가 (싸다!)"
    elif rsi >= 70:
        rsi_cls = "sell"; rsi_icon = "🔴"; rsi_msg = "과열권 (비싸다!)"
    else:
        rsi_cls = "neu"; rsi_icon = "🟡"; rsi_msg = "중립 (특이사항 없음)"

    if macd > macd_sig:
        macd_cls = "buy"; macd_icon = "🟢"; macd_msg = "상승 추세 (골든크로스)"
    else:
        macd_cls = "sell"; macd_icon = "🔴"; macd_msg = "하락 반전 (데드크로스)"

    html = f"""
    <div class='tech-status-box'>
        <div class='status-badge {rsi_cls}'>
            <div>📊 RSI ({rsi:.1f})</div>
            <div style='font-size:15px; margin-top:4px; font-weight:800;'>{rsi_icon} {rsi_msg}</div>
        </div>
        <div class='status-badge {macd_cls}'>
            <div>🌊 MACD 추세</div>
            <div style='font-size:15px; margin-top:4px; font-weight:800;'>{macd_icon} {macd_msg}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_tech_metrics(stoch, vol_ratio):
    k = stoch['k']
    if k < 20: stoch_txt = f"🟢 침체 구간 ({k:.1f}%)"; stoch_cls = "buy"
    elif k > 80: stoch_txt = f"🔴 과열 구간 ({k:.1f}%)"; stoch_cls = "sell"
    else: stoch_txt = f"⚪ 중립 구간 ({k:.1f}%)"; stoch_cls = "neu"

    if vol_ratio >= 2.0: vol_txt = f"🔥 거래량 폭발 ({vol_ratio*100:.0f}%)"; vol_cls = "vol"
    elif vol_ratio >= 1.2: vol_txt = f"📈 거래량 증가 ({vol_ratio*100:.0f}%)"; vol_cls = "buy"
    else: vol_txt = "☁️ 거래량 평이"; vol_cls = "neu"

    html = f"""
    <div class='tech-status-box'>
        <div class='status-badge {stoch_cls}'>
            <div>📉 스토캐스틱</div>
            <div style='font-size:15px; margin-top:4px; font-weight:800;'>{stoch_txt}</div>
        </div>
        <div class='status-badge {vol_cls}'>
            <div>📢 거래강도(전일비)</div>
            <div style='font-size:15px; margin-top:4px; font-weight:800;'>{vol_txt}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

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
    html = ""
    html += "<div style='display:flex; gap:12px; font-size:12px; color:#555; margin-bottom:8px; align-items:center; flex-wrap:wrap;'>"
    html += "   <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#000000; margin-right:4px;'></div>현재가</div>"
    html += "   <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#FF4B4B; margin-right:4px;'></div>5일선(단기)</div>"
    html += "   <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#F2A529; margin-right:4px;'></div>20일선(생명)</div>"
    html += "   <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#3182F6; margin-right:4px;'></div>60일선(수급)</div>"
    html += "   <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#9C27B0; margin-right:4px;'></div>120일선(경기)</div>"
    html += "   <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#999; border-top:1px dashed #999; margin-right:4px;'></div>240일선(대세)</div>"
    html += "   <div style='display:flex; align-items:center;'><div style='width:12px; height:10px; background:#868E96; opacity:0.5; margin-right:4px;'></div>볼린저밴드</div>"
    html += "</div>"
    return html

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
        ma240 = base.mark_line(color='#999999', strokeDash=[2, 2], strokeWidth=1).encode(y='MA240:Q')
        price_chart = (band + line + ma5 + ma20 + ma60 + ma120 + ma240).properties(height=250)
        rsi_base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=None))
        rsi_line = rsi_base.mark_line(color='#9C27B0').encode(y=alt.Y('RSI:Q', title='RSI'))
        rsi_rule_u = rsi_base.mark_rule(color='gray', strokeDash=[2,2]).encode(y=alt.datum(70))
        rsi_rule_l = rsi_base.mark_rule(color='gray', strokeDash=[2,2]).encode(y=alt.datum(30))
        rsi_chart = (rsi_line + rsi_rule_u + rsi_rule_l).properties(height=60)
        macd_base = alt.Chart(chart_data).encode(x=alt.X('Date:T', axis=None))
        macd_line = macd_base.mark_line(color='#2196F3').encode(y=alt.Y('MACD:Q', title='MACD'))
        signal_line = macd_base.mark_line(color='#FF5722').encode(y='MACD_Signal:Q')
        macd_chart = (macd_line + signal_line).properties(height=60)
        return alt.vconcat(price_chart, rsi_chart, macd_chart).resolve_scale(x='shared')
    except Exception as e: 
        return alt.Chart(pd.DataFrame()).mark_text()

def render_fund_scorecard(fund_data):
    if not fund_data: st.info("재무 정보 로딩 실패 (일시적 오류)"); return
    per = fund_data['per']['val']
    pbr = fund_data['pbr']['val']
    div = fund_data['div']['val']
    per_col = "#F04452" if fund_data['per']['stat']=='good' else ("#3182F6" if fund_data['per']['stat']=='bad' else "#333")
    pbr_col = "#F04452" if fund_data['pbr']['stat']=='good' else ("#3182F6" if fund_data['pbr']['stat']=='bad' else "#333")
    div_col = "#F04452" if fund_data['div']['stat']=='good' else "#333"
    html = ""
    html += f"<div class='fund-grid-v2'>"
    html += f"  <div class='fund-item-v2'><div class='fund-title-v2'>PER</div><div class='fund-value-v2' style='color:{per_col}'>{per:.1f}배</div><div class='fund-desc-v2' style='background-color:{per_col}20; color:{per_col}'>{fund_data['per']['txt']}</div></div>"
    html += f"  <div class='fund-item-v2'><div class='fund-title-v2'>PBR</div><div class='fund-value-v2' style='color:{pbr_col}'>{pbr:.1f}배</div><div class='fund-desc-v2' style='background-color:{pbr_col}20; color:{pbr_col}'>{fund_data['pbr']['txt']}</div></div>"
    html += f"  <div class='fund-item-v2'><div class='fund-title-v2'>배당률</div><div class='fund-value-v2' style='color:{div_col}'>{div:.1f}%</div><div class='fund-desc-v2' style='background-color:{div_col}20; color:{div_col}'>{fund_data['div']['txt']}</div></div>"
    html += f"</div>"
    st.markdown(html, unsafe_allow_html=True)

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
    
    try:
        df['날짜'] = pd.to_datetime(df['날짜'])
    except: pass 

    cum_cols = [c for c in ['Cum_Individual', 'Cum_Foreigner', 'Cum_Institution', 'Cum_Pension'] if c in df.columns]
    df_line = df.melt('날짜', value_vars=cum_cols, var_name='Key', value_name='Cumulative')
    
    type_map = {'Cum_Individual': '개인', 'Cum_Foreigner': '외국인', 'Cum_Institution': '기관합계', 'Cum_Pension': '연기금'}
    df_line['Type'] = df_line['Key'].map(type_map)

    domain = ['개인', '외국인', '기관합계', '연기금']
    range_ = ['#228B22', '#F04452', '#3182F6', '#8B4513']
    color_scale = alt.Scale(domain=domain, range=range_)
    
    color_encoding = alt.Color('Type:N', scale=color_scale, legend=alt.Legend(title="투자자", orient="top"))

    base = alt.Chart(df_line).encode(x=alt.X('날짜:T', axis=alt.Axis(format='%m-%d', title=None)))
    
    line = base.mark_line().encode(
        y=alt.Y('Cumulative:Q', axis=alt.Axis(title='누적 순매수 (선)')), 
        color=color_encoding,
        tooltip=[alt.Tooltip('날짜:T', format='%Y-%m-%d'), alt.Tooltip('Type:N', title='투자자'), alt.Tooltip('Cumulative:Q', format=',', title='📈 누적')]
    )
    
    chart = line.properties(height=250)
    st.altair_chart(chart, use_container_width=True)

    st.markdown("###### 📊 최근 5거래일 수급 (단위: 원)", unsafe_allow_html=True)
    
    try:
        recent_df = df.tail(5).sort_values('날짜', ascending=False)
        html = "<div class='investor-table-container'><table class='investor-table'><thead><tr><th>날짜</th><th>외국인</th><th>기관</th><th>개인</th></tr></thead><tbody>"
        inst_col_name = '기관합계' if '기관합계' in df.columns else ('기관' if '기관' in df.columns else None)

        for idx, row in recent_df.iterrows():
            d_str = row['날짜'].strftime('%m-%d') if hasattr(row['날짜'], 'strftime') else str(row['날짜'])[:10]
            
            def format_val(val):
                try:
                    val = float(val)
                    color = "#F04452" if val > 0 else ("#3182F6" if val < 0 else "#333")
                    return f"<span style='color:{color}; font-weight:700;'>{int(val):,}</span>"
                except: return "-"

            frgn = format_val(row.get('외국인', 0))
            inst = format_val(row.get(inst_col_name, 0)) if inst_col_name else "-"
            indv = format_val(row.get('개인', 0))
            
            html += f"<tr><td>{d_str}</td><td>{frgn}</td><td>{inst}</td><td>{indv}</td></tr>"
        
        html += "</tbody></table></div>"
        st.markdown(html, unsafe_allow_html=True)
    except Exception as e:
        st.caption(f"상세 표 렌더링 오류: {str(e)}")

# --- [3. 데이터 로딩 및 분석 로직] ---
REPO_OWNER = "echobm101-del"
REPO_NAME = "my_stock-bot"
FILE_PATH = "my_watchlist_v7.json"

@st.cache_data
def get_krx_list_safe():
    try:
        df = fdr.StockListing('KRX')
        if not df.empty: return df
    except: pass 

    try:
        target_date = datetime.datetime.now()
        for _ in range(5):
            d_str = target_date.strftime("%Y%m%d")
            try:
                tickers = stock.get_market_ticker_list(d_str, market="KOSPI")
                if tickers: break 
            except: pass
            target_date -= datetime.timedelta(days=1)
        d_str = target_date.strftime("%Y%m%d")
        df_kospi = stock.get_market_cap_by_ticker(d_str, market="KOSPI")
        df_kosdaq = stock.get_market_cap_by_ticker(d_str, market="KOSDAQ")
        df_list = []
        if not df_kospi.empty:
            df_kospi = df_kospi.reset_index()
            df_list.append(df_kospi[['티커', '종목명']].rename(columns={'티커': 'Code', '종목명': 'Name'}))
        if not df_kosdaq.empty:
            df_kosdaq = df_kosdaq.reset_index()
            df_list.append(df_kosdaq[['티커', '종목명']].rename(columns={'티커': 'Code', '종목명': 'Name'}))
        if df_list: return pd.concat(df_list, ignore_index=True)
    except Exception as e: pass
    return pd.DataFrame() 

krx_df = get_krx_list_safe()

def load_from_github():
    try:
        token = USER_GITHUB_TOKEN
        if not token: return {"portfolio": {}, "watchlist": {}}
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            data = json.loads(content)
            if "portfolio" not in data and "watchlist" not in data:
                return {"portfolio": {}, "watchlist": data}
            return data
        return {"portfolio": {}, "watchlist": {}}
    except: return {"portfolio": {}, "watchlist": {}}

def update_github_file(new_data):
    try:
        token = USER_GITHUB_TOKEN
        if not token: return False
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        r_get = requests.get(url, headers=headers)
        if r_get.status_code == 200:
            sha = r_get.json().get('sha')
        else:
            sha = None
        json_str = json.dumps(new_data, ensure_ascii=False, indent=4)
        b64_content = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        data = {
            "message": "Update data via Streamlit App (V49.9)",
            "content": b64_content
        }
        if sha: data["sha"] = sha
        r_put = requests.put(url, headers=headers, json=data)
        return r_put.status_code in [200, 201]
    except Exception as e:
        print(f"GitHub Save Error: {e}")
        return False

# [New] DART 객체 캐싱 (초기화 비용 절약)
@st.cache_resource
def get_dart_instance():
    if USER_DART_KEY:
        try:
            return OpenDartReader(USER_DART_KEY)
        except: return None
    return None

dart = get_dart_instance()

def get_dart_recent_disclosures(code):
    """
    최근 6개월(180일) 간의 주요 공시(보고서) 리스트를 가져옵니다.
    """
    if not dart: return []
    try:
        # [수정] 90일 -> 180일로 변경하여 공시 포착 확률 높이기
        end_d = datetime.datetime.now()
        start_d = end_d - datetime.timedelta(days=180) 
        
        # OpenDartReader는 종목코드로 조회 가능
        df = dart.list(code, start=start_d.strftime('%Y-%m-%d'), end=end_d.strftime('%Y-%m-%d'))
        
        if df is not None and not df.empty:
            # 필요한 컬럼만 추출
            return df[['rcept_dt', 'report_nm', 'pblntf_detail_ty_nm']].head(5).to_dict('records')
    except: pass
    return []

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
        start_d = (datetime.datetime.now() - datetime.timedelta(days=100)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(start_d, end_d, code)
        if not df.empty:
            df = df.tail(60).copy()
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

# [수정] RSI 계산 로직 개선 (Wilder's Smoothing 적용)
def calculate_rsi(data, window=14):
    delta = data.diff()
    # 양수(상승분), 음수(하락분) 분리
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Exponential Weighted Moving Average (Wilder's Smoothing)
    # alpha=1/window는 Wilder's method와 수학적으로 동일
    avg_gain = gain.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(0)

def calculate_macd(data, short=12, long=26, signal=9):
    short_ema = data.ewm(span=short, adjust=False).mean()
    long_ema = data.ewm(span=long, adjust=False).mean()
    macd = short_ema - long_ema
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def calculate_atr(data, window=14):
    try:
        high = data['High']
        low = data['Low']
        close = data['Close']
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=window).mean()
        return atr
    except: return pd.Series(0, index=data.index)

def backtest_strategy(df):
    try:
        sim_df = df.copy()
        sim_df['Signal'] = (sim_df['Close'] > sim_df['MA20']) & (sim_df['RSI'] < 40)
        signals = sim_df[sim_df['Signal']].index
        wins = 0
        total = 0
        for date in signals:
            try:
                idx = sim_df.index.get_loc(date)
                future = sim_df.iloc[idx+1:idx+11]
                if len(future) < 1: continue
                buy_price = sim_df.loc[date, 'Close']
                max_price = future['High'].max()
                if max_price >= buy_price * 1.03: 
                    wins += 1
                total += 1
            except: continue
        win_rate = int((wins / total) * 100) if total > 0 else 0
        return win_rate
    except: return 0

@st.cache_data(ttl=1800)
def get_market_cycle_status(code):
    try:
        kospi = fdr.DataReader('KS11', datetime.datetime.now()-datetime.timedelta(days=400))
        ma120 = kospi['Close'].rolling(120).mean().iloc[-1]
        curr = kospi['Close'].iloc[-1]
        if curr > ma120: return "📈 시장 상승세 (공격적 매수 유효)"
        else: return "📉 시장 하락세 (보수적 접근 필요)"
    except: return "시장 분석 중"

def calculate_sniper_score(code):
    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty or len(df) < 60: return 0, [], 0, 0, 0, pd.DataFrame(), ""
        
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        df['MA120'] = df['Close'].rolling(120).mean()
        df['MA240'] = df['Close'].rolling(240).mean()
        df['MA5'] = df['Close'].rolling(5).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        df['ATR'] = calculate_atr(df)
        df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
        df['BB_Upper'] = df['MA20'] + (df['Close'].rolling(20).std() * 2)
        df['BB_Lower'] = df['MA20'] - (df['Close'].rolling(20).std() * 2)
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        vol_avg = df['Volume'].rolling(20).mean().iloc[-1]
        
        score = 0; tags = []
        vol_ratio = curr['Volume'] / vol_avg if vol_avg > 0 else 0
        
        price_chg = (curr['Close'] - prev['Close']) / prev['Close'] * 100
        is_bullish = curr['Close'] >= curr['Open']

        main_reason = "관망 필요"

        if vol_ratio >= 3.0: 
            if price_chg > 0 or is_bullish:
                score += 40
                tags.append("🔥 거래량폭발(매수)")
                main_reason = "큰손 쓸어담는 중"
            else:
                score -= 50 
                tags.append("😱 투매폭탄(위험)")
                main_reason = "세력 이탈 경고"
        elif vol_ratio >= 1.5:
            if price_chg > 0 or is_bullish:
                score += 20
                tags.append("📈 거래량증가")
            else:
                score -= 10
                tags.append("📉 매도세출현")
        
        if curr['Close'] > curr['MA20']: 
            score += 20
        if curr['RSI'] < 30: 
            score += 10; tags.append("💎 과매도(기회)")
            if main_reason == "관망 필요": main_reason = "바닥 잡을 찬스"
        if curr['MACD'] > curr['MACD_Signal']: 
            score += 10; tags.append("🌊 추세전환")
            if main_reason == "관망 필요": main_reason = "상승 파도타기"
        
        change = (curr['Close'] - df.iloc[-2]['Close']) / df.iloc[-2]['Close'] * 100
        
        win_rate = backtest_strategy(df)
        if win_rate >= 70: 
            score += 10; tags.append(f"👑 승률{win_rate}%")
            if main_reason == "관망 필요": main_reason = "승률 높은 구간"

        if score < 60: main_reason = "힘 모으는 중"

        return score, tags, vol_ratio, change, win_rate, df, main_reason
    except: return 0, [], 0, 0, 0, pd.DataFrame(), ""

@st.cache_data(ttl=3600)
def get_macro_data():
    results = {}
    tickers = {
        "KOSPI": "KS11", "KOSDAQ": "KQ11", "S&P500": "US500", "USD/KRW": "USD/KRW", 
        "US_10Y": "US10YT", "WTI": "CL=F", "구리": "HG=F" 
    }
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
    sc_pos = ["공급 안정", "수율 개선", "장기 계약", "원가 절감", "공장 가동"]
    sc_neg = ["공급난", "품귀", "물류 대란", "원자재 상승", "지연", "숏티지", "부족"]

    score = 0; found_keywords = []
    sc_detected = False
    
    for title in news_titles:
        for w in pos_words:
            if w in title: score += 1; found_keywords.append(w)
        for w in neg_words:
            if w in title: score -= 1; found_keywords.append(w)
        for w in sc_pos:
            if w in title: score += 2; found_keywords.append(w); sc_detected=True
        for w in sc_neg:
            if w in title: score -= 2; found_keywords.append(w); sc_detected=True
            
    final_score = min(max(score, -10), 10)
    summary = f"긍정 키워드 {len([w for w in found_keywords if w in pos_words or w in sc_pos])}개, 부정 키워드 {len([w for w in found_keywords if w in neg_words or w in sc_neg])}개 감지."
    if sc_detected: summary += " [공급망 이슈 감지]"
    return final_score, summary, "키워드 분석", ""

def get_valid_model_name(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            models = response.json().get('models', [])
            chat_models = [m['name'] for m in models if 'generateContent' in m.get('supportedGenerationMethods', [])]
            preferences = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
            for pref in preferences:
                if pref in chat_models: return pref
            if chat_models: return chat_models[0]
    except: pass
    return "models/gemini-pro"

# [수정] Gemini 파싱 및 오류 처리 강화
def call_gemini_dynamic(prompt):
    api_key = USER_GOOGLE_API_KEY
    if not api_key: return None, "NO_KEY"
    
    model_name = get_valid_model_name(api_key)
    clean_model_name = model_name.replace("models/", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1} # JSON 출력을 위해 창의성 낮춤
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        if res.status_code == 200: return res.json(), None
        elif res.status_code == 429: time.sleep(2); return None, "Rate Limit (429)"
        else: return None, f"HTTP {res.status_code}: {res.text[:100]}"
    except Exception as e: return None, f"Connection Error: {str(e)}"

def get_ai_recommended_stocks(keyword):
    prompt = f"""
    당신은 한국 주식 전문가입니다.
    사용자가 입력한 검색어 '{keyword}'와 가장 관련성이 높은 한국(KOSPI/KOSDAQ) 상장 주식 5개를 추천해주세요.
    
    [핵심 규칙]
    1. 각 종목이 검색어와 어떤 관계인지 5글자 이내의 '핵심 태그(relation)'를 반드시 포함하세요. (예: 대장주, 지분보유, 경쟁사, 납품사)
    2. JSON 형식으로만 출력하세요.
    
    [출력 예시]
    [
        {{"name": "삼성전자", "code": "005930", "relation": "HBM 대장주"}}, 
        {{"name": "한미반도체", "code": "042700", "relation": "장비 납품"}}
    ]
    """
    
    res_data, error = call_gemini_dynamic(prompt)
    if res_data and 'candidates' in res_data:
        try:
            raw = res_data['candidates'][0]['content']['parts'][0]['text']
            raw = raw.replace("```json", "").replace("```", "").strip()
            stock_list = json.loads(raw)
            valid_list = []
            for item in stock_list:
                if 'name' in item and 'code' in item:
                    tag = item.get('relation', '관련주')
                    valid_list.append({"name": item['name'], "code": item['code'], "price": 0, "relation_tag": tag})
            return valid_list, f"🤖 AI가 '{keyword}' 관련주와 핵심 관계를 파악했습니다!"
        except:
            return [], "AI 응답 해석 실패"
    return [], "AI 연결 실패"

# [New] 날짜 파싱 헬퍼 함수
def parse_pubdate(date_str):
    try:
        return date_parser.parse(date_str)
    except:
        return datetime.datetime.now() # 파싱 실패시 오늘로 간주

# [New] 네이버 뉴스 API 검색
def get_naver_news_api(keyword, display=10):
    if not USER_NAVER_ID or not USER_NAVER_SECRET: return []
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = { "X-Naver-Client-Id": USER_NAVER_ID, "X-Naver-Client-Secret": USER_NAVER_SECRET }
    params = { "query": keyword, "display": display, "sort": "sim" }
    news_list = []
    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            items = res.json().get('items', [])
            for item in items:
                title = re.sub('<[^<]+?>', '', item['title']).replace("&quot;", '"').replace("&amp;", "&")
                pubDate = item['pubDate'] # e.g. "Thu, 23 Jan 2025 10:00:00 +0900"
                news_list.append({"title": title, "date": pubDate, "link": item['originallink'] or item['link']})
    except: pass
    return news_list

def get_naver_finance_news(code):
    # 크롤링이라 날짜 정확도 떨어질 수 있음, 우선순위 낮음
    titles = []
    try:
        url = f"https://finance.naver.com/item/news_news.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        for item in soup.select('.title')[:5]:
            t = item.get_text().strip()
            if t: titles.append({"title": t, "date": datetime.datetime.now().strftime("%Y-%m-%d"), "link": ""})
    except: pass
    return titles

@st.cache_data(ttl=600)
def get_news_sentiment_llm(company_name, stock_data_context=None):
    if stock_data_context is None: stock_data_context = {}
    
    # 1. 뉴스 수집 (네이버 API 우선 -> 없으면 크롤링)
    raw_news = get_naver_news_api(company_name, display=10)
    if not raw_news and stock_data_context.get('code'):
        raw_news = get_naver_finance_news(stock_data_context['code'])
    
    # 2. 날짜 필터링 (최근 1개월 이내 뉴스 확인)
    one_month_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    recent_news = []
    
    for n in raw_news:
        try:
            # 날짜 파싱 (timezone aware하게 변환 노력)
            dt = parse_pubdate(n['date'])
            if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
            
            if dt >= one_month_ago:
                recent_news.append(n)
        except:
            # 날짜 파싱 실패 시 일단 포함 (안전책)
            recent_news.append(n)

    # 3. 분기 처리 (Branching)
    has_recent_news = len(recent_news) > 0
    
    # 기본 데이터 준비
    trend = stock_data_context.get('trend', '분석중')
    cycle = stock_data_context.get('cycle', '정보없음')
    price = stock_data_context.get('current_price', 0)
    supply = stock_data_context.get('supply', '특이사항 없음')
    pbr = stock_data_context.get('pbr', 0)
    per = stock_data_context.get('per', 0)
    
    if not has_recent_news:
        # [CASE B] 뉴스 없음 -> 퀀트/수급 집중 분석
        prompt = f"""
        당신은 냉철한 '퀀트 펀드 매니저'입니다.
        현재 '{company_name}'에 대한 **최근 1개월 내 유의미한 뉴스가 없습니다.**
        따라서 뉴스는 배제하고, 오직 **기술적 추세, 수급, 펀더멘털** 데이터만으로 매수/매도/관망을 판단하세요.
        
        [분석 데이터]
        - 현재가: {price:,}원
        - 기술적 추세: {trend}
        - 수급 상황: {supply}
        - 펀더멘털: PBR {pbr:.2f}배 / PER {per:.2f}배
        
        [지시사항]
        1. "뉴스가 없다"는 말만 하고 끝내지 마세요. 주어진 데이터로 가치 판단을 내리세요.
        2. headline에는 반드시 "[뉴스 부재] 수급/차트 위주 분석 결과" 내용을 포함하세요.
        3. 수급이 '양매수'이거나 추세가 '정배열'이면 긍정적으로 평가하세요.
        
        [출력 형식 JSON]
        {{
            "score": (정수 -5~5, 데이터 기반 점수),
            "headline": "한줄 요약 (예: [뉴스 부재] 외인 매수세 유입으로 기술적 반등 시도)",
            "opinion": "매수/관망/매도",
            "risk": "거래량 부족 또는 재료 소멸 주의",
            "catalyst": "수급/차트/실적"
        }}
        """
    else:
        # [CASE A] 뉴스 있음 -> 종합 분석
        news_titles_str = "\n".join([f"- {n['title']} ({n['date']})" for n in recent_news[:5]])
        prompt = f"""
        당신은 베테랑 헤지펀드 매니저입니다.
        '{company_name}'의 최신 뉴스(1개월 내)와 데이터를 종합 분석하세요.
        
        [최신 뉴스]
        {news_titles_str}
        
        [데이터]
        - 추세: {trend}
        - 수급: {supply}
        
        [출력 형식 JSON]
        {{
            "score": (정수 -10~10),
            "headline": "핵심 요약 (한 문장)",
            "opinion": "강력매수/매수/관망/매도",
            "risk": "리스크 요인",
            "catalyst": "핵심 재료"
        }}
        """

    # 4. AI 호출 및 안전장치 (Rule-based Fallback)
    try:
        res_data, error = call_gemini_dynamic(prompt)
        
        # AI 응답 성공 시
        if res_data and 'candidates' in res_data:
            text = res_data['candidates'][0]['content']['parts'][0]['text']
            clean_text = text.replace("```json", "").replace("```", "").strip()
            # 가끔 JSON 앞뒤에 잡다한 텍스트가 붙을 경우 제거
            match = re.search(r'\{.*\}', clean_text, re.DOTALL)
            if match:
                js = json.loads(match.group())
                return {
                    "score": js.get('score', 0),
                    "headline": js.get('headline', "분석 결과 없음"),
                    "opinion": js.get('opinion', "관망"),
                    "risk": js.get('risk', ""),
                    "catalyst": js.get('catalyst', ""),
                    "raw_news": recent_news,
                    "method": "ai"
                }
    except Exception as e:
        pass # AI 실패 시 아래 Fallback 로직으로 이동

    # [Fallback] AI 실패 또는 파싱 에러 시 -> 파이썬이 직접 분석 (절대 에러 안 냄)
    fallback_score = 0
    fallback_headline = []
    
    # 추세 점수
    if "상승" in trend: fallback_score += 3; fallback_headline.append("기술적 상승세")
    elif "하락" in trend: fallback_score -= 3; fallback_headline.append("기술적 조정 국면")
    
    # 수급 점수
    if "양매수" in supply: fallback_score += 2; fallback_headline.append("메이저 수급 유입")
    elif "매도" in supply: fallback_score -= 2; fallback_headline.append("수급 이탈 주의")
    
    # 펀더멘털 점수
    if 0 < pbr < 1.0: fallback_score += 2; fallback_headline.append("저PBR 매력")
    
    final_headline = f"[시스템 분석] {' / '.join(fallback_headline)}" if fallback_headline else "[시스템 분석] 특이사항 없음, 관망 권장"
    final_opinion = "매수" if fallback_score >= 3 else ("매도" if fallback_score <= -3 else "관망")
    
    risk_txt = "AI 연결 지연으로 인한 시스템 대체 분석" if not has_recent_news else "AI 파싱 오류, 기본 데이터 참고"

    return {
        "score": fallback_score,
        "headline": final_headline,
        "opinion": final_opinion,
        "risk": risk_txt,
        "catalyst": "기술적/수급 데이터",
        "raw_news": recent_news,
        "method": "fallback" # AI가 아닌 시스템 분석임을 명시
    }

def get_supply_demand(code):
    try:
        e = datetime.datetime.now().strftime("%Y%m%d")
        s = (datetime.datetime.now()-datetime.timedelta(days=7)).strftime("%Y%m%d")
        df = stock.get_market_investor_net_purchase_by_date(s, e, code).tail(3)
        if df.empty: return {"f":0, "i":0}
        return {"f": int(df['외국인'].sum()), "i": int(df['기관합계'].sum())}
    except: return {"f":0, "i":0}

def round_to_tick(price):
    if price < 2000: return int(round(price, -1))
    elif price < 5000: return int(round(price / 5) * 5)
    elif price < 20000: return int(round(price, -1))
    elif price < 50000: return int(round(price / 50) * 50)
    elif price < 200000: return int(round(price, -2))
    elif price < 500000: return int(round(price / 500) * 500)
    else: return int(round(price, -3))

# [수정] AI 로직을 완전히 메인 스레드로 위임
def analyze_pro(code, name_override=None, relation_tag=None, my_buy_price=None):
    # analyze_pro 함수 내부에서는 st.session_state에 접근하지 않습니다. (스레드 안전성 확보)
    try:
        score, tags, vol_ratio, chg_rate, win_rate, df, main_reason = calculate_sniper_score(code)
        if df.empty: return None
        curr = df.iloc[-1]
    except: return None

    profit_rate = 0.0
    if my_buy_price and my_buy_price > 0:
        profit_rate = (int(curr['Close']) - my_buy_price) / my_buy_price * 100

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
        "news": {"score":0, "supply_score":0, "headline":"로딩 실패", "raw_news":[], "method":"none", "opinion":"", "catalyst":"", "risk":""}, 
        "history": df, 
        "supply": {"f":0, "i":0},
        "stoch": {"k": curr['RSI'], "d": 0}, 
        "vol_ratio": vol_ratio,
        "investor_trend": pd.DataFrame(),
        "fin_history": pd.DataFrame(),
        "win_rate": win_rate, 
        "cycle_txt": "확인 중", 
        "relation_tag": relation_tag,
        "my_buy_price": my_buy_price,
        "ai_context": {},
        "dart_disclosures": [] # [New] DART 공시 데이터 저장 공간
    }

    try:
        pass_cnt = 0
        mas = [('5일', 'MA5'), ('20일', 'MA20'), ('60일', 'MA60')]
        ma_status = []
        for label, col in mas:
            val = curr.get(col, 0)
            if curr['Close'] >= val: pass_cnt += 1; ma_status.append({"label": label, "ok": True})
            else: ma_status.append({"label": label, "ok": False})
            
        if pass_cnt >= 3: trend_txt = "강력한 상승 추세 (정배열)"
        elif pass_cnt >= 2: trend_txt = "상승세 유지 (양호)"
        else: trend_txt = "조정 또는 하락세"
        
        result_dict['ma_status'] = ma_status
        result_dict['trend_txt'] = trend_txt
        tech_score = score 
    except: tech_score = 0

    try: fund_score, _, fund_data = get_company_guide_score(code); result_dict['fund_data'] = fund_data
    except: fund_score = 0; fund_data = {}
    
    cycle_txt = get_market_cycle_status(code)
    result_dict['cycle_txt'] = cycle_txt
    if "상승세" in cycle_txt: tech_score += 10 

    try: result_dict['investor_trend'] = get_investor_trend(code)
    except: pass
    try: result_dict['fin_history'] = get_financial_history(code)
    except: pass
    try: result_dict['supply'] = get_supply_demand(code)
    except: pass
    
    # [New] DART 공시 가져오기
    try: result_dict['dart_disclosures'] = get_dart_recent_disclosures(code)
    except: pass

    try:
        bonus = 0
        if not result_dict['investor_trend'].empty: bonus += 5
        if not result_dict['fin_history'].empty: bonus += 5
        
        temp_score = int((tech_score * 0.5) + fund_score + bonus)
        
        atr = curr.get('ATR', curr['Close'] * 0.03)
        current_price = curr['Close']
        
        quant_signal = "중립"
        if my_buy_price:
            if profit_rate > 0:
                if temp_score >= 50: quant_signal = "보유 권장 (상승 추세)"
                else: quant_signal = "차익 실현 권장 (과열/탄력 둔화)"
            else:
                if temp_score >= 50: quant_signal = "보유 권장 (반등 기대)"
                else: quant_signal = "손절매 고려 (하락 추세)"
    except: quant_signal = "판단 불가"

    try:
        supply_txt = "특이사항 없음"
        f_net = result_dict['supply'].get('f', 0)
        i_net = result_dict['supply'].get('i', 0)
        if f_net > 0 and i_net > 0: supply_txt = "외국인/기관 양매수 유입"
        elif f_net > 0: supply_txt = "외국인 매수 우위"
        elif i_net > 0: supply_txt = "기관 매수 우위"
        elif f_net < 0 and i_net < 0: supply_txt = "외국인/기관 동반 매도"

        # 수급/매크로 데이터 준비
        macro_data = get_macro_data()
        usd_change = 0.0
        if macro_data and 'USD/KRW' in macro_data:
            usd_change = macro_data['USD/KRW']['change']
            
        price_surge = 0.0
        if len(df) >= 20:
            past_price = df['Close'].iloc[-20]
            if past_price > 0:
                price_surge = (current_price - past_price) / past_price * 100
                
        round_fig_msg = ""
        str_price = str(int(current_price))
        if len(str_price) >= 4:
            unit = 10**(len(str_price)-1)
            next_big = (int(current_price / unit) + 1) * unit
            if (next_big - current_price) / current_price < 0.03:
                round_fig_msg = f"심리적 저항선({next_big:,}원) 접근 중"

        context = {
            "code": code,
            "trend": result_dict['trend_txt'],
            "pbr": fund_data.get('pbr', {}).get('val', 0) if fund_data else 0,
            "per": fund_data.get('per', {}).get('val', 0) if fund_data else 0,
            "supply": supply_txt,
            "cycle": cycle_txt,
            "is_holding": True if my_buy_price else False,
            "profit_rate": profit_rate,
            "quant_signal": quant_signal,
            "current_price": result_dict['price'],
            "usd_krw_change": usd_change,
            "price_surge": price_surge,
            "round_figure_msg": round_fig_msg
        }
        result_dict['ai_context'] = context # 컨텍스트 저장

        # [핵심 변경] 여기서는 무조건 Standby 상태만 반환합니다.
        # 실제 캐시 데이터 주입은 메인 스레드(UI 루프)에서 수행합니다.
        result_dict['news'] = {
             "score": 0, "supply_score": 0, 
             "headline": "💎 AI 심층 분석 대기 중 (버튼을 눌러주세요)", 
             "raw_news": [], "method": "standby", 
             "opinion": "대기", "catalyst": "", "risk": ""
        }

    except: pass 

    try:
        # 점수 계산 시 AI 점수는 실행 전엔 0점으로 처리하거나 기본값 부여
        ai_news_score = result_dict['news'].get('score', 0)
        ai_cycle_score = result_dict['news'].get('supply_score', 0) * 2
        
        final_score = temp_score + ai_news_score + ai_cycle_score
        final_score = min(max(final_score, 0), 100)
        result_dict['score'] = final_score

        if my_buy_price:
            action_txt = result_dict['news'].get('opinion', quant_signal)
            if action_txt == "대기": action_txt = quant_signal # AI 대기중일 땐 퀀트신호 표시
            
            stop_raw = my_buy_price * 0.95 
            target_raw = my_buy_price * 1.10
            buy_basis_txt = "보유 중"
            buy_price_raw = my_buy_price
        else:
            if final_score >= 80:
                buy_price_raw = current_price
                buy_basis_txt = "🚀 상승 기류 포착"
                stop_raw = current_price - (atr * 2) 
                target_raw = current_price + (atr * 4) 
                action_txt = f"🔥 지금이 기회! ({main_reason})"
            elif final_score >= 60:
                buy_price_raw = current_price
                buy_basis_txt = "✨ 좋은 흐름"
                ma20 = curr.get('MA20', current_price * 0.95)
                stop_raw = min(ma20, current_price - (atr * 1.5))
                target_raw = current_price + (atr * 3)
                action_txt = f"📈 매수 ({main_reason})"
            else:
                bb_lower = curr.get('BB_Lower', current_price * 0.9)
                if current_price < curr.get('MA20', current_price):
                    buy_price_raw = bb_lower
                    buy_basis_txt = "밴드 하단 대기"
                else:
                    buy_price_raw = curr.get('MA20', current_price * 0.95)
                    buy_basis_txt = "눌림목 대기"
                stop_raw = buy_price_raw * 0.95 
                target_raw = buy_price_raw * 1.10 
                action_txt = f"👀 관망 ({main_reason})"

        buy_price = round_to_tick(buy_price_raw)
        target_price = round_to_tick(target_raw)
        stop_price = round_to_tick(stop_raw)
        
        result_dict['strategy'] = {
            "buy": buy_price,
            "buy_basis": buy_basis_txt,
            "target": target_price,
            "stop": stop_price,
            "action": action_txt
        }
    except: pass

    return result_dict

# --- [Tab Views] ---
with tab1:
    if st.button("🔄 화면 정리"): st.rerun()
    if st.session_state.get('preview_list'):
        st.markdown(f"### 🔍 '{st.session_state['current_theme_name']}' 분석 결과")
        with st.spinner("데이터 분석 중..."):
            results = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(analyze_pro, item['code'], item['name'], item.get('relation_tag')) for item in st.session_state['preview_list']]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): results.append(f.result())
            results.sort(key=lambda x: x['score'], reverse=True)
            
        for res in results:
            if 'ai_cache' in st.session_state and res['code'] in st.session_state['ai_cache']:
                res['news'] = st.session_state['ai_cache'][res['code']]

            st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
            
            expander_title = "🤖 AI 심층 분석 실행 (Click)" if res['news']['method'] == "standby" else f"✅ AI 분석: {res['news'].get('headline','')}"
            
            with st.expander(expander_title):
                if res['news']['method'] == "standby":
                    st.info("비용 절감을 위해 AI 분석 대기 중입니다.")
                    if st.button(f"🚀 AI 분석 시작 ({res['name']})", key=f"btn_ai_{res['code']}"):
                        st.toast(f"🤖 '{res['name']}' 분석 시작!", icon="🔥")
                        with st.spinner("AI가 뉴스, 수급, 공시를 정밀 분석 중..."):
                            ai_res = get_news_sentiment_llm(res['name'], res['ai_context'])
                            st.session_state['ai_cache'][res['code']] = ai_res
                            st.toast("✅ 분석 완료!", icon="🎉")
                            time.sleep(1)
                            st.rerun()
                else:
                    st.markdown(f"""
                    <div class='news-ai'>
                        <b>🧠 AI Analyst Opinion:</b><br>{res['news']['headline']}<br>
                        <span style='font-size:12px; color:#555;'>* 근거: {res['news'].get('catalyst','종합 분석')} / 리스크: {res['news'].get('risk','-')}</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_chart_legend()
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                with col2:
                    render_fund_scorecard(res['fund_data'])
                    render_investor_chart(res['investor_trend'])
                    if res.get('dart_disclosures'):
                        st.write("📢 <b>최근 주요 공시</b>", unsafe_allow_html=True)
                        for d in res['dart_disclosures']:
                            rpt_nm = d['report_nm']
                            if len(rpt_nm) > 28: rpt_nm = rpt_nm[:28] + "..."
                            st.markdown(f"<div class='dart-box'>{rpt_nm} <span style='color:#888'>{d['rcept_dt']}</span></div>", unsafe_allow_html=True)
                
                if st.button(f"📌 관심 등록 ({res['name']})", key=f"add_{res['code']}"):
                    st.session_state['data_store']['watchlist'][res['name']] = {'code': res['code']}
                    update_github_file(st.session_state['data_store'])
                    st.success("등록 완료")

with tab2:
    st.markdown("### 💰 내 보유 종목")
    port_items = list(st.session_state['data_store']['portfolio'].items())
    if not port_items: st.info("보유 종목이 없습니다.")
    else:
        results = []
        with st.spinner("수익률 분석 중..."):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(analyze_pro, info['code'], name, None, float(info.get('buy_price',0))) for name, info in port_items]
                for f in concurrent.futures.as_completed(futures):
                    if f.result(): results.append(f.result())
        
        for res in results:
            if 'ai_cache' in st.session_state and res['code'] in st.session_state['ai_cache']:
                res['news'] = st.session_state['ai_cache'][res['code']]

            st.markdown(create_portfolio_card_html(res), unsafe_allow_html=True)
            
            expander_title = "🤖 AI 심층 분석 실행 (Click)" if res['news']['method'] == "standby" else f"✅ AI 분석: {res['news'].get('headline','')}"

            with st.expander(expander_title):
                if res['news']['method'] == "standby":
                    if st.button(f"🚀 AI 진단 실행 ({res['name']})", key=f"port_ai_{res['code']}"):
                        st.toast(f"🤖 '{res['name']}' 분석 시작!", icon="🔥")
                        with st.spinner("분석 중..."):
                            ai_res = get_news_sentiment_llm(res['name'], res['ai_context'])
                            st.session_state['ai_cache'][res['code']] = ai_res
                            st.toast("✅ 분석 완료!", icon="🎉")
                            time.sleep(1)
                            st.rerun()
                else:
                    st.markdown(f"""
                    <div class='news-ai'>
                        <b>🧠 AI Analyst Opinion:</b><br>{res['news']['headline']}<br>
                        <span style='font-size:12px; color:#555;'>* 근거: {res['news'].get('catalyst','종합 분석')} / 리스크: {res['news'].get('risk','-')}</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_chart_legend()
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                with col2:
                    render_fund_scorecard(res['fund_data'])
                    render_investor_chart(res['investor_trend'])
                    if res.get('dart_disclosures'):
                        st.write("📢 <b>최근 주요 공시</b>", unsafe_allow_html=True)
                        for d in res['dart_disclosures']:
                            rpt_nm = d['report_nm']
                            if len(rpt_nm) > 28: rpt_nm = rpt_nm[:28] + "..."
                            st.markdown(f"<div class='dart-box'>{rpt_nm} <span style='color:#888'>{d['rcept_dt']}</span></div>", unsafe_allow_html=True)

                if st.button(f"🗑️ 삭제", key=f"del_{res['code']}"):
                    del st.session_state['data_store']['portfolio'][res['name']]
                    update_github_file(st.session_state['data_store'])
                    st.rerun()

with tab3:
    st.markdown("### 👀 관심 종목")
    wl_items = list(st.session_state['data_store']['watchlist'].items())
    if not wl_items: st.info("관심 종목이 없습니다.")
    else:
        results = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(analyze_pro, info['code'], name) for name, info in wl_items]
            for f in concurrent.futures.as_completed(futures):
                if f.result(): results.append(f.result())
        results.sort(key=lambda x: x['score'], reverse=True)
        
        for res in results:
            if 'ai_cache' in st.session_state and res['code'] in st.session_state['ai_cache']:
                res['news'] = st.session_state['ai_cache'][res['code']]

            st.markdown(create_watchlist_card_html(res), unsafe_allow_html=True)
            
            expander_title = "🤖 AI 심층 분석 실행 (Click)" if res['news']['method'] == "standby" else f"✅ AI 분석: {res['news'].get('headline','')}"

            with st.expander(expander_title):
                if res['news']['method'] == "standby":
                    if st.button(f"🚀 AI 분석 ({res['name']})", key=f"wl_ai_{res['code']}"):
                        st.toast(f"🤖 '{res['name']}' 분석 시작!", icon="🔥")
                        with st.spinner("AI 분석 중..."):
                            ai_res = get_news_sentiment_llm(res['name'], res['ai_context'])
                            st.session_state['ai_cache'][res['code']] = ai_res
                            st.toast("✅ 분석 완료!", icon="🎉")
                            time.sleep(1)
                            st.rerun()
                else:
                    st.markdown(f"""
                    <div class='news-ai'>
                        <b>🧠 AI Analyst Opinion:</b><br>{res['news']['headline']}<br>
                        <span style='font-size:12px; color:#555;'>* 근거: {res['news'].get('catalyst','종합 분석')} / 리스크: {res['news'].get('risk','-')}</span>
                    </div>
                    """, unsafe_allow_html=True)

                col1, col2 = st.columns(2)
                with col1:
                    render_tech_metrics(res['stoch'], res['vol_ratio'])
                    render_chart_legend()
                    st.altair_chart(create_chart_clean(res['history']), use_container_width=True)
                with col2:
                    render_fund_scorecard(res['fund_data'])
                    render_investor_chart(res['investor_trend'])
                    if res.get('dart_disclosures'):
                        st.write("📢 <b>최근 주요 공시</b>", unsafe_allow_html=True)
                        for d in res['dart_disclosures']:
                            rpt_nm = d['report_nm']
                            if len(rpt_nm) > 28: rpt_nm = rpt_nm[:28] + "..."
                            st.markdown(f"<div class='dart-box'>{rpt_nm} <span style='color:#888'>{d['rcept_dt']}</span></div>", unsafe_allow_html=True)

                if st.button("🗑️ 삭제", key=f"wl_del_{res['code']}"):
                    del st.session_state['data_store']['watchlist'][res['name']]
                    update_github_file(st.session_state['data_store'])
                    st.rerun()

with st.sidebar:
    st.write("### ⚙️ 기능 메뉴")
    
    if USER_DART_KEY:
        try:
            if 'dart' in globals() and dart:
                st.success(f"✅ DART 연결됨")
            else:
                from OpenDartReader import OpenDartReader 
                dart_obj = OpenDartReader(USER_DART_KEY)
                st.success(f"✅ DART 연결됨 (Reconnected)")
        except:
            st.error("⚠️ DART 연결 실패 (API Key 확인)")
    else:
        st.warning("⚠️ DART API Key 없음")
    
    with st.expander("🔍 종목/테마 검색", expanded=True):
        keyword = st.text_input("검색어 입력")
        if st.button("분석 시작") and keyword:
            st.session_state['current_theme_name'] = keyword
            if keyword.isdigit(): 
                res = analyze_pro(keyword, keyword)
                if res: st.session_state['preview_list'] = [res]
            else:
                ai_list, msg = get_ai_recommended_stocks(keyword)
                st.session_state['preview_list'] = ai_list
            st.rerun()
