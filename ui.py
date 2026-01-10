import streamlit as st

# 1. CSS 스타일 (화면 꾸미기)
def get_css():
    return """
    <style>
        .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
        .toss-card { background: #FFFFFF; border-radius: 20px; padding: 24px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08); border: 1px solid #F2F4F6; margin-bottom: 16px; }
        .stock-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
        .stock-name { font-size: 20px; font-weight: 700; color: #333; }
        .stock-code { font-size: 13px; color: #999; margin-left: 6px; font-weight: 400; }
        .price-up { color: #F04452; }
        .price-down { color: #3182F6; }
        
        /* AI 분석 박스 스타일 */
        .ai-box { background-color: #F9FAFB; border-radius: 12px; padding: 16px; margin-top: 16px; border: 1px solid #E5E8EB; }
        .ai-title { font-size: 14px; font-weight: 700; color: #6B7684; margin-bottom: 8px; display: flex; align-items: center; }
        .ai-content { font-size: 14px; line-height: 1.6; color: #333; white-space: pre-line; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; margin-left: 8px; }
    </style>
    """

# 2. 관심종목 카드 HTML 생성 (AI 포함 버전)
def create_watchlist_card_html(res):
    # 가격 색상 및 부호 설정
    if res['change_rate'] > 0:
        color_class = "price-up"
        sign = "+"
    elif res['change_rate'] < 0:
        color_class = "price-down"
        sign = ""
    else:
        color_class = ""
        sign = ""
        
    score_color = "#F04452" if res['score'] >= 60 else "#3182F6"
    
    # AI 멘트 가져오기 (없으면 기본값)
    ai_text = res.get('news', {}).get('opinion', '분석 대기 중...')
    
    html = f"""
    <div class='toss-card'>
        <div class='stock-header'>
            <div>
                <span class='stock-name'>{res['name']}</span>
                <span class='stock-code'>{res['code']}</span>
                <div style='margin-top: 4px; font-size: 22px; font-weight: 800;' class='{color_class}'>
                    {res['price']:,}원 <span style='font-size:15px; font-weight:500;'>({sign}{res['change_rate']:.2f}%)</span>
                </div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:24px; font-weight:800; color:{score_color};'>{res['score']}점</div>
                <div class='badge' style='background-color:{score_color}15; color:{score_color};'>
                    {res['strategy']['action']}
                </div>
            </div>
        </div>
        
        <div style='font-size:13px; color:#555; margin-bottom:12px;'>
            📊 {res['trend_txt']}
        </div>
        
        <div class='ai-box'>
            <div class='ai-title'>🤖 Gemini AI 투자 코멘트</div>
            <div class='ai-content'>{ai_text}</div>
        </div>
    </div>
    """
    return html

# 3. 포트폴리오 카드 (심플 버전)
def create_portfolio_card_html(res):
    profit_rate = 0
    if res['my_buy_price'] > 0:
        profit_rate = (res['price'] - res['my_buy_price']) / res['my_buy_price'] * 100
    
    color = "#F04452" if profit_rate > 0 else "#3182F6"
    
    html = f"""
    <div class='toss-card' style='padding: 16px;'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <span style='font-weight:bold; font-size:16px;'>{res['name']}</span>
                <span style='color:#888; font-size:12px; margin-left:4px;'>{res['code']}</span>
                <div style='font-size:13px; color:#555; margin-top:2px;'>현재 {res['price']:,}원</div>
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
