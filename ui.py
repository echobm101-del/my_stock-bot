import streamlit as st

# 1. CSS 스타일 (화면 꾸미기 - AI 박스 디자인 추가됨)
def get_css():
    return """
    <style>
        .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
        .toss-card { background: #FFFFFF; border-radius: 20px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
        .stock-name { font-size: 20px; font-weight: 700; color: #333; }
        .stock-code { font-size: 13px; color: #999; margin-left: 6px; }
        .price-box { font-size: 24px; font-weight: 800; margin: 8px 0; }
        .ai-box { background-color: #F9FAFB; border-radius: 12px; padding: 16px; margin-top: 16px; border: 1px solid #E5E8EB; }
        .ai-title { font-size: 14px; font-weight: 700; color: #3182F6; margin-bottom: 8px; display: flex; align-items: center; }
        .ai-content { font-size: 14px; line-height: 1.6; color: #4E5968; white-space: pre-line; }
        .badge { padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; margin-left: 8px; }
    </style>
    """

# 2. 관심종목 카드 HTML 생성 (AI 내용 포함)
def create_watchlist_card_html(res):
    color = "#F04452" if res['change_rate'] > 0 else ("#3182F6" if res['change_rate'] < 0 else "#333")
    sign = "+" if res['change_rate'] > 0 else ""
    
    # AI 코멘트가 있는지 확인
    ai_html = ""
    if res.get('news'):
        ai_html = f"""
        <div class='ai-box'>
            <div class='ai-title'>🤖 Gemini AI 투자 분석</div>
            <div class='ai-content'>{res['news']['opinion']}</div>
        </div>
        """

    html = f"""
    <div class='toss-card'>
        <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
            <div>
                <span class='stock-name'>{res['name']}</span>
                <span class='stock-code'>{res['code']}</span>
            </div>
            <div style='text-align:right;'>
                <span style='font-size:20px; font-weight:800; color:{color};'>{res['score']}점</span>
                <br>
                <span style='font-size:12px; font-weight:bold; color:#666; background-color:#f2f4f6; padding:4px 8px; border-radius:6px;'>
                    {res['strategy']['action']}
                </span>
            </div>
        </div>
        
        <div class='price-box' style='color:{color};'>
            {res['price']:,}원 <span style='font-size:16px; font-weight:500;'>({sign}{res['change_rate']:.2f}%)</span>
        </div>
        
        <div style='font-size:13px; color:#666; margin-bottom:10px;'>
            📊 {res['trend_txt']}
        </div>

        {ai_html}
    </div>
    """
    return html

# 3. 포트폴리오 카드 HTML (간단 버전)
def create_portfolio_card_html(res):
    color = "#F04452" if res['price'] > res['my_buy_price'] else "#3182F6"
    profit = (res['price'] - res['my_buy_price']) / res['my_buy_price'] * 100
    
    html = f"""
    <div class='toss-card' style='border-left: 4px solid {color};'>
        <div style='display:flex; justify-content:space-between;'>
            <div>
                <span class='stock-name'>{res['name']}</span>
                <div style='margin-top:4px; font-size:14px; color:#555;'>현재 {res['price']:,}원</div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:18px; font-weight:800; color:{color};'>{profit:+.2f}%</div>
                <div style='font-size:12px; color:#888;'>평단 {int(res['my_buy_price']):,}원</div>
            </div>
        </div>
    </div>
    """
    return html
