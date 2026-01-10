import streamlit as st

# 1. CSS 스타일 (화면 꾸미기)
def get_css():
    return """
    <style>
        .stApp { background-color: #FFFFFF; color: #191F28; font-family: 'Pretendard', sans-serif; }
        .toss-card { background: #FFFFFF; border-radius: 20px; padding: 24px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #F2F4F6; margin-bottom: 16px; }
        .stock-name { font-size: 20px; font-weight: 700; color: #333; }
        .stock-code { font-size: 13px; color: #999; margin-left: 6px; }
        .badge { font-size: 11px; padding: 4px 8px; border-radius: 6px; font-weight: 600; display: inline-block; margin-right: 5px; }
        
        /* AI 분석 박스 스타일 */
        .ai-box {
            background-color: #F9FAFB;
            border-radius: 12px;
            padding: 16px;
            margin-top: 16px;
            border: 1px solid #E5E8EB;
        }
        .ai-title {
            font-size: 14px;
            font-weight: 700;
            color: #6B7684;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
        }
        .ai-content {
            font-size: 14px;
            line-height: 1.6;
            color: #333;
            white-space: pre-wrap; /* 줄바꿈 허용 */
        }
    </style>
    """

# 2. 관심종목 카드 HTML 생성 (AI 포함)
def create_watchlist_card_html(res):
    # 색상 결정
    color = "#F04452" if res['change_rate'] > 0 else ("#3182F6" if res['change_rate'] < 0 else "#333")
    score_col = "#F04452" if res['score'] >= 70 else ("#3182F6" if res['score'] <= 30 else "#333")
    
    # AI 코멘트 HTML 만들기 (데이터가 있을 때만)
    ai_html = ""
    if 'news' in res and res['news']:
        ai_html = f"""
        <div class='ai-box'>
            <div class='ai-title'>🤖 {res['news'].get('headline', 'AI 분석')}</div>
            <div class='ai-content'>{res['news'].get('opinion', '분석 내용이 없습니다.')}</div>
        </div>
        """

    html = f"""
    <div class='toss-card' style='border-left: 5px solid {score_col};'>
        <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
            <div>
                <span class='stock-name'>{res['name']}</span>
                <span class='stock-code'>{res['code']}</span>
                <div style='font-size:24px; font-weight:800; color:{color}; margin-top:8px;'>
                    {res['price']:,}원 <span style='font-size:16px; font-weight:500;'>({res['change_rate']:.2f}%)</span>
                </div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:28px; font-weight:900; color:{score_col};'>{res['score']}점</div>
                <div class='badge' style='background:{score_col}15; color:{score_col};'>{res['strategy']['action']}</div>
            </div>
        </div>
        
        <div style='margin-top:16px; font-size:13px; color:#555; display:flex; align-items:center;'>
            📊 {res['trend_txt']}
        </div>

        {ai_html}
    </div>
    """
    return html

# 3. 포트폴리오 카드 HTML (심플 버전)
def create_portfolio_card_html(res):
    profit_rate = 0
    if res['my_buy_price'] > 0:
        profit_rate = (res['price'] - res['my_buy_price']) / res['my_buy_price'] * 100
        
    color = "#F04452" if profit_rate > 0 else "#3182F6"
    
    html = f"""
    <div class='toss-card' style='border: 1px solid {color}40; background-color: {color}03;'>
        <div style='display:flex; justify-content:space-between; align-items:center;'>
            <div>
                <span style='font-size:12px; font-weight:bold; color:#6B7684;'>내 보유 종목</span>
                <div class='stock-name' style='font-size:18px;'>{res['name']}</div>
                <div style='font-size:14px; color:#555; margin-top:4px;'>현재 {res['price']:,}원</div>
            </div>
            <div style='text-align:right;'>
                <div style='font-size:20px; font-weight:800; color:{color};'>
                    {profit_rate:+.2f}%
                </div>
                <div style='font-size:12px; color:#888;'>매수 {int(res['my_buy_price']):,}원</div>
            </div>
        </div>
    </div>
    """
    return html
