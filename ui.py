import streamlit as st

def get_css():
    return """
    <style>
        .stApp { background-color: #FFFFFF; font-family: 'Pretendard', sans-serif; }
        .toss-card { background: white; border-radius: 16px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border: 1px solid #eee; margin-bottom: 15px; }
        .price-up { color: #E8382F; font-weight: bold; }
        .price-down { color: #2D65F0; font-weight: bold; }
        .ai-box { background-color: #F3F5F9; padding: 15px; border-radius: 10px; margin-top: 15px; border: 1px solid #E1E4E8; }
        .ai-title { font-size: 13px; font-weight: bold; color: #555; margin-bottom: 5px; }
        .ai-content { font-size: 14px; line-height: 1.5; color: #333; white-space: pre-line; }
    </style>
    """

def create_watchlist_card_html(res):
    color_class = "price-up" if res['change_rate'] > 0 else "price-down"
    sign = "+" if res['change_rate'] > 0 else ""
    
    # AI 멘트 처리
    ai_text = res.get('news', {}).get('opinion', '분석 중...')
    
    html = f"""
    <div class='toss-card'>
        <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
            <div>
                <span style='font-size:18px; font-weight:bold;'>{res['name']}</span>
                <span style='color:#999; font-size:12px; margin-left:5px;'>{res['code']}</span>
                <div style='font-size:20px; margin-top:5px;' class='{color_class}'>
                    {res['price']:,}원 <span style='font-size:14px;'>({sign}{res['change_rate']:.2f}%)</span>
                </div>
            </div>
            <div style='text-align:right;'>
                <span style='font-size:20px; font-weight:bold; color:#333;'>{res['score']}점</span><br>
                <span style='font-size:12px; background:#f0f0f0; padding:3px 6px; border-radius:4px;'>{res['strategy']['action']}</span>
            </div>
        </div>
        
        <div style='margin-top:10px; font-size:13px; color:#666;'>
            📊 {res['trend_txt']}
        </div>
        
        <div class='ai-box'>
            <div class='ai-title'>🤖 Gemini AI 투자 의견</div>
            <div class='ai-content'>{ai_text}</div>
        </div>
    </div>
    """
    return html

def create_portfolio_card_html(res):
    profit = 0
    if res['my_buy_price'] > 0:
        profit = (res['price'] - res['my_buy_price']) / res['my_buy_price'] * 100
        
    color = "#E8382F" if profit > 0 else "#2D65F0"
    
    html = f"""
    <div class='toss-card'>
        <div style='display:flex; justify-content:space-between;'>
            <div>
                <span style='font-weight:bold;'>{res['name']}</span>
                <span style='font-size:12px; color:#888;'> 보유중</span>
                <div style='font-size:13px; color:#555;'>현재 {res['price']:,}원</div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:16px; font-weight:bold; color:{color};'>
                    {profit:+.2f}%
                </div>
                <div style='font-size:11px; color:#888;'>매수 {int(res['my_buy_price']):,}원</div>
            </div>
        </div>
    </div>
    """
    return html
