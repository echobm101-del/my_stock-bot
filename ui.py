import streamlit as st
import altair as alt
import pandas as pd

# 1. CSS 스타일 (화면 꾸미기)
def get_css():
    return """
    <style>
        .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
        .toss-card { background: #FFFFFF; border-radius: 24px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
        .stock-name { font-size: 18px; font-weight: 700; color: #333; }
        .stock-code { font-size: 12px; color: #888; margin-left: 4px; }
        .price-up { color: #F04452; font-weight: 700; }
        .price-down { color: #3182F6; font-weight: 700; }
        .badge-clean { font-size: 11px; padding: 4px 8px; border-radius: 6px; font-weight: 700; display: inline-block; }
    </style>
    """

# 2. 관심종목 카드 HTML 생성
def create_watchlist_card_html(res):
    # 가격 색상 결정
    color = "#F04452" if res['change_rate'] > 0 else ("#3182F6" if res['change_rate'] < 0 else "#333")
    score_col = "#F04452" if res['score'] >= 60 else "#3182F6"
    
    html = f"""
    <div class='toss-card' style='border-left: 5px solid {score_col};'>
        <div style='display:flex; justify-content:space-between;'>
            <div>
                <span class='stock-name'>{res['name']}</span>
                <span class='stock-code'>{res['code']}</span>
                <div style='font-size:20px; font-weight:800; color:{color};'>
                    {res['price']:,}원 <span style='font-size:14px;'>({res['change_rate']:.2f}%)</span>
                </div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:24px; font-weight:800; color:{score_col};'>{res['score']}점</div>
                <div class='badge-clean' style='background:{score_col}20; color:{score_col};'>{res['strategy']['action']}</div>
            </div>
        </div>
        <div style='margin-top:12px; font-size:12px; color:#555;'>
            📊 {res['trend_txt']}
        </div>
    </div>
    """
    return html

# 3. 포트폴리오 카드 HTML 생성
def create_portfolio_card_html(res):
    profit_rate = 0
    if res['my_buy_price'] > 0:
        profit_rate = (res['price'] - res['my_buy_price']) / res['my_buy_price'] * 100
        
    color = "#F04452" if profit_rate > 0 else "#3182F6"
    
    html = f"""
    <div class='toss-card' style='border: 2px solid {color}40; background-color: {color}05;'>
        <div style='display:flex; justify-content:space-between;'>
            <div>
                <span style='font-size:11px; font-weight:bold; color:#555;'>내 보유 종목</span><br>
                <span class='stock-name'>{res['name']}</span>
                <div style='font-size:13px; color:#666;'>현재 {res['price']:,}원</div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:18px; font-weight:800; color:{color};'>
                    {profit_rate:+.2f}%
                </div>
                <div style='font-size:11px; color:#888;'>평단 {int(res['my_buy_price']):,}원</div>
            </div>
        </div>
    </div>
    """
    return html
