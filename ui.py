import streamlit as st
import altair as alt
import pandas as pd

def get_css_style():
    return """
<style>
    /* 기본 설정 */
    .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
    
    /* 카드 디자인 */
    .toss-card { 
        background: #FFFFFF; border-radius: 24px; padding: 24px; 
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; 
        margin-bottom: 16px; transition: all 0.3s ease; 
    }
    
    /* 텍스트 스타일 */
    .stock-name { font-size: 20px; font-weight: 800; color: #333; margin-right: 6px; }
    .stock-code { font-size: 14px; color: #8B95A1; }
    .big-price { font-size: 24px; font-weight: 800; color: #333; margin-top: 4px; }
    .tech-summary { background: #F2F4F6; padding: 10px; border-radius: 8px; font-size: 13px; color: #4E5968; margin-bottom: 10px; font-weight: 600; }

    /* 배지 스타일 */
    .cycle-badge { background-color:#E6FCF5; color:#087F5B; padding:4px 8px; border-radius:6px; font-size:11px; font-weight:bold; border:1px solid #B2F2BB; display:inline-block; margin-top:4px; }
    .cycle-badge.bear { background-color:#FFF5F5; color:#F04452; border-color:#FFD8A8; }
    .relation-badge { background-color:#F3F0FF; color:#7950F2; padding:3px 6px; border-radius:4px; font-size:10px; font-weight:700; border:1px solid #E5DBFF; margin-left:6px; vertical-align: middle; }
    
    /* 기술적 지표 박스 */
    .tech-status-box { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
    .status-badge { flex: 1; min-width: 120px; padding: 12px 10px; border-radius: 12px; text-align: center; font-size: 13px; font-weight: 700; color: #4E5968; background: #F2F4F6; border: 1px solid #E5E8EB; }
    .status-badge.buy { background-color: #E8F3FF; color: #3182F6; border-color: #3182F6; }
    .status-badge.sell { background-color: #FFF1F1; color: #F04452; border-color: #F04452; }
    .status-badge.vol { background-color: #FFF8E1; color: #D9480F; border-color: #FFD8A8; }
    .status-badge.neu { background-color: #FFF9DB; color: #F08C00; border-color: #FFEC99; }
    
    .ma-status-container { display: flex; gap: 5px; margin-bottom: 10px; flex-wrap: wrap; }
    .ma-status-badge { font-size: 11px; padding: 4px 8px; border-radius: 6px; font-weight: 700; color: #555; background-color: #F2F4F6; border: 1px solid #E5E8EB; }
    .ma-status-badge.on { background-color: #FFF1F1; color: #F04452; border-color: #F04452; }

    /* 재무 그리드 */
    .fund-grid-v2 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-top: 10px; background-color: #F9FAFB; padding: 15px; border-radius: 12px; }
    .fund-item-v2 { text-align: center; }
    .fund-title-v2 { font-size: 12px; color: #8B95A1; margin-bottom: 5px; }
    .fund-value-v2 { font-size: 18px; font-weight: 800; color: #333D4B; }
    .fund-desc-v2 { font-size: 11px; font-weight: 600; margin-top: 4px; display: inline-block; padding: 2px 6px; border-radius: 4px;}

    /* AI 뉴스 */
    .news-ai { background: #F3F9FE; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #D0EBFF; color: #333; }
    .ai-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; margin-bottom: 6px; }
    .ai-opinion-buy { background-color: #E8F3FF; color: #3182F6; border: 1px solid #3182F6; }
    .ai-opinion-sell { background-color: #FFF1F1; color: #F04452; border: 1px solid #F04452; }
    .ai-opinion-hold { background-color: #F2F4F6; color: #4E5968; border: 1px solid #4E5968; }
    .news-fallback { background: #FFF4E6; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #FFD8A8; color: #D9480F; font-weight: 600; }
    
    /* 뉴스 리스트 */
    .news-scroll-box { max-height: 200px; overflow-y: auto; border: 1px solid #F2F4F6; border-radius: 8px; padding: 10px; margin-top:5px; }
    .news-box { padding: 10px 0; border-bottom: 1px solid #F2F4F6; font-size: 13px; line-height: 1.4; }
    .news-link { color: #333; text-decoration: none; font-weight: 500; display: block; margin-bottom: 2px;}
    .news-link:hover { color: #3182F6; text-decoration: underline; }
    .news-date { font-size: 11px; color: #999; }

    /* 전략 배지 */
    .badge-clean { background-color:#F2F4F6; color:#4E5968; font-weight:700; padding:4px 8px; border-radius:6px; font-size:12px; display:inline-block; }

    /* 수급 테이블 */
    .investor-table-container { margin-top: 10px; border: 1px solid #F2F4F6; border-radius: 8px; overflow: hidden; overflow-x: auto; }
    .investor-table { width: 100%; font-size: 11px; text-align: center; border-collapse: collapse; min-width: 300px; }
    .investor-table th { background-color: #F9FAFB; padding: 6px; color: #666; font-weight: 600; border-bottom: 1px solid #E5E8EB; white-space: nowrap; }
    .investor-table td { padding: 6px; border-bottom: 1px solid #F2F4F6; color: #333; }

    /* 재무 테이블 */
    .fin-table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; margin-bottom: 10px; border: 1px solid #E5E8EB; }
    .fin-table th { background-color: #F9FAFB; padding: 8px; border-bottom: 1px solid #E5E8EB; color: #4E5968; font-weight: 600; white-space: nowrap; }
    .fin-table td { padding: 8px; border-bottom: 1px solid #F2F4F6; color: #333; font-weight: 500; }
    .text-red { color: #F04452; font-weight: 700; }
    .text-blue { color: #3182F6; font-weight: 700; }
    .change-rate { font-size: 10px; color: #888; font-weight: 400; margin-left: 4px; }

    /* 매크로 지표 */
    .metric-box { background: #F9FAFB; border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #E5E8EB; height: 100%; display: flex; flex-direction: column; justify-content: center; }
    .metric-title { font-size: 12px; color: #666; margin-bottom: 4px; }
    .metric-value { font-size: 16px; font-weight: bold; color: #333; margin-bottom: 2px;}
    .metric-badge { font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 700; display: inline-block; margin-top: 4px; }

    /* 포트폴리오 수익률 */
    .profit-positive { color: #F04452; font-weight: 800; font-size: 20px; }
    .profit-negative { color: #3182F6; font-weight: 800; font-size: 20px; }

    /* 전략 가이드 (오버드라이브 등) */
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
    }
</style>
"""

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
      <div style='color:#3182F6; background-color:#E8F3FF; padding:6px; border-radius:6px;'>🛒 진입 {buy_price:,}<br><span style='font-size:10px; opacity:0.7;'>({buy_basis})</span></div>
      <div style='color:#F04452; background-color:#FFF1F1; padding:6px; border-radius:6px;'>💰 목표 {target_price:,}<br><span style='font-size:10px; opacity:0.7;'>(익절)</span></div>
      <div style='color:#4E5968; background-color:#F2F4F6; padding:6px; border-radius:6px;'>🛡️ 손절 {stop_price:,}<br><span style='font-size:10px; opacity:0.7;'>(방어)</span></div>
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
    stop_color = "#3182F6"; target_color = "#F04452"
    progress_cls = "progress-fill"; action_btn_cls = "action-badge-default"
    action_text = strategy.get('action', '분석 대기')
    strategy_bg = "#F9FAFB"

    if is_overdrive:
        base_target_2nd = int(buy_price * 1.20)
        final_target = int(curr_price * 1.10) if curr_price >= base_target_2nd else base_target_2nd
        target_label = "🔥 무한 질주 (추세 추종)" if curr_price >= base_target_2nd else "🌟 2차 목표가 (+20%)"
        final_stop = int(buy_price * 1.05)
        status_msg = f"🎉 목표 초과 달성 중 (+{profit_rate:.2f}%)"
        stop_label = "🔒 익절 보존선 (+5%)"; stop_color = "#7950F2"
        progress_cls = "progress-fill overdrive"; action_btn_cls = "action-badge-strong"
        action_text = "🔥 강력 홀딩 (수익 극대화)"; strategy_bg = "#F3F0FF"
    elif is_rescue:
        final_target = int(curr_price * 1.15)
        final_stop = int(curr_price * 0.95)
        status_msg = f"🚨 위기 관리: 단기 반등 목표 {final_target:,}원"
        stop_label = "🛑 2차 방어선 (-5%)"; target_label = "📈 반등 목표 (+15%)"
        stop_color = "#555"; target_color = "#3182F6"
        progress_cls = "progress-fill rescue"; action_btn_cls = "action-badge-rescue"
        action_text = "⛑️ 리스크 관리 (반등 시 축소)"; strategy_bg = "#E8F3FF"

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
    if rsi <= 35: rsi_cls = "buy"; rsi_icon = "🟢"; rsi_msg = "저평가 (싸다!)"
    elif rsi >= 70: rsi_cls = "sell"; rsi_icon = "🔴"; rsi_msg = "과열권 (비싸다!)"
    else: rsi_cls = "neu"; rsi_icon = "🟡"; rsi_msg = "중립 (특이사항 없음)"

    if macd > macd_sig: macd_cls = "buy"; macd_icon = "🟢"; macd_msg = "상승 추세 (골든크로스)"
    else: macd_cls = "sell"; macd_icon = "🔴"; macd_msg = "하락 반전 (데드크로스)"

    st.markdown(f"""
    <div class='tech-status-box'>
        <div class='status-badge {rsi_cls}'><div>📊 RSI ({rsi:.1f})</div><div style='font-size:15px; margin-top:4px; font-weight:800;'>{rsi_icon} {rsi_msg}</div></div>
        <div class='status-badge {macd_cls}'><div>🌊 MACD 추세</div><div style='font-size:15px; margin-top:4px; font-weight:800;'>{macd_icon} {macd_msg}</div></div>
    </div>
    """, unsafe_allow_html=True)

def render_tech_metrics(stoch, vol_ratio):
    k = stoch['k']
    if k < 20: stoch_txt = f"🟢 침체 구간 ({k:.1f}%)"; stoch_cls = "buy"
    elif k > 80: stoch_txt = f"🔴 과열 구간 ({k:.1f}%)"; stoch_cls = "sell"
    else: stoch_txt = f"⚪ 중립 구간 ({k:.1f}%)"; stoch_cls = "neu"

    if vol_ratio >= 2.0: vol_txt = f"🔥 거래량 폭발 ({vol_ratio*100:.0f}%)"; vol_cls = "vol"
    elif vol_ratio >= 1.2: vol_txt = f"📈 거래량 증가 ({vol_ratio*100:.0f}%)"; vol_cls = "buy"
    else: vol_txt = "☁️ 거래량 평이"; vol_cls = "neu"

    st.markdown(f"""
    <div class='tech-status-box'>
        <div class='status-badge {stoch_cls}'><div>📉 스토캐스틱</div><div style='font-size:15px; margin-top:4px; font-weight:800;'>{stoch_txt}</div></div>
        <div class='status-badge {vol_cls}'><div>📢 거래강도(전일비)</div><div style='font-size:15px; margin-top:4px; font-weight:800;'>{vol_txt}</div></div>
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
       <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#FF4B4B; margin-right:4px;'></div>5일선(단기)</div>
       <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#F2A529; margin-right:4px;'></div>20일선(생명)</div>
       <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#3182F6; margin-right:4px;'></div>60일선(수급)</div>
       <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#9C27B0; margin-right:4px;'></div>120일선(경기)</div>
       <div style='display:flex; align-items:center;'><div style='width:12px; height:2px; background:#999; border-top:1px dashed #999; margin-right:4px;'></div>240일선(대세)</div>
       <div style='display:flex; align-items:center;'><div style='width:12px; height:10px; background:#868E96; opacity:0.5; margin-right:4px;'></div>볼린저밴드</div>
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
    
    html = f"<div class='fund-grid-v2'>"
    html += f"  <div class='fund-item-v2'><div class='fund-title-v2'>PER</div><div class='fund-value-v2' style='color:{per_col}'>{per:.1f}배</div><div class='fund-desc-v2' style='background-color:{per_col}20; color:{per_col}'>{fund_data['per']['txt']}</div></div>"
    html += f"  <div class='fund-item-v2'><div class='fund-title-v2'>PBR</div><div class='fund-value-v2' style='color:{pbr_col}'>{pbr:.1f}배</div><div class='fund-desc-v2' style='background-color:{pbr_col}20; color:{pbr_col}'>{fund_data['pbr']['txt']}</div></div>"
    html += f"  <div class='fund-item-v2'><div class='fund-title-v2'>배당률</div><div class='fund-value-v2' style='color:{div_col}'>{div:.1f}%</div><div class='fund-desc-v2' style='background-color:{div_col}20; color:{div_col}'>{fund_data['div']['txt']}</div></div>"
    html += f"</div>"
    st.markdown(html, unsafe_allow_html=True)

def render_financial_table(df):
    if df.empty: return
    html = "<table class='fin-table'><thead><tr><th>구분</th>"
    for d in df['Date']: html += f"<th>{d}</th>"
    html += "</tr></thead><tbody>"
    for m in ['매출액', '영업이익', '당기순이익']:
        html += f"<tr><td>{m}</td>"
        for i, val in enumerate(df[m]):
            color_class = ""; arrow = ""; change_txt = ""
            if i > 0:
                prev = df[m].iloc[i-1]
                if prev != 0:
                    pct = (val - prev) / abs(prev) * 100
                    if pct > 0: color_class = "text-red"; arrow = "▲"; change_txt = f"<span class='change-rate'>(+{pct:.1f}%)</span>"
                    elif pct < 0: color_class = "text-blue"; arrow = "▼"; change_txt = f"<span class='change-rate'>({pct:.1f}%)</span>"
            html += f"<td class='{color_class}'>{int(val):,} {arrow} {change_txt}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)
    st.caption("※ 단위: 억 원 / (괄호): 전분기/전년 대비 증감률")

def render_investor_chart(df):
    if df.empty:
        st.caption("수급 데이터가 없습니다.")
        return
    
    df = df.reset_index()
    if '날짜' not in df.columns: 
        if 'index' in df.columns: df.rename(columns={'index': '날짜'}, inplace=True)
    try: df['날짜'] = pd.to_datetime(df['날짜'])
    except: pass 

    df_line = df.melt('날짜', value_vars=['Cum_Individual', 'Cum_Foreigner', 'Cum_Institution'], var_name='Key', value_name='Cumulative')
    type_map = {'Cum_Individual': '개인', 'Cum_Foreigner': '외국인', 'Cum_Institution': '기관'}
    df_line['Type'] = df_line['Key'].map(type_map)
    
    chart = alt.Chart(df_line).mark_line().encode(
        x=alt.X('날짜:T', axis=alt.Axis(format='%m-%d', title=None)), 
        y=alt.Y('Cumulative:Q', axis=alt.Axis(title='누적 순매수')), 
        color=alt.Color('Type:N', legend=alt.Legend(title="투자자", orient="top"))
    ).properties(height=250)
    st.altair_chart(chart, use_container_width=True)

    st.markdown("###### 📊 최근 5거래일 수급 (단위: 원)", unsafe_allow_html=True)
    recent = df.tail(5).sort_values('날짜', ascending=False)
    html = "<div class='investor-table-container'><table class='investor-table'><thead><tr><th>날짜</th><th>외국인</th><th>기관</th><th>개인</th></tr></thead><tbody>"
    for _, row in recent.iterrows():
        d_str = row['날짜'].strftime('%m-%d')
        frgn = f"<span style='color:{'#F04452' if row.get('외국인',0)>0 else '#3182F6'}'>{int(row.get('외국인',0)):,}</span>"
        inst = f"<span style='color:{'#F04452' if row.get('기관',0)>0 else '#3182F6'}'>{int(row.get('기관',0)):,}</span>"
        indv = f"<span style='color:{'#F04452' if row.get('개인',0)>0 else '#3182F6'}'>{int(row.get('개인',0)):,}</span>"
        html += f"<tr><td>{d_str}</td><td>{frgn}</td><td>{inst}</td><td>{indv}</td></tr>"
    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)
