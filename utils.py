import FinanceDataReader as fdr
import pandas as pd
import datetime
import streamlit as st
import google.generativeai as genai

# 1. Gemini AI 설정
def configure_genai():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            genai.configure(api_key=api_key)
            return True
        else:
            return False
    except Exception as e:
        return False

# 2. 종목 검색
@st.cache_data(ttl=3600*24)
def get_krx_list():
    try:
        df = fdr.StockListing('KRX')
        return df[['Code', 'Name']]
    except:
        return pd.DataFrame()

def find_stock_code(keyword):
    df = get_krx_list()
    if df.empty: return None, None
    keyword = keyword.strip()
    
    exact = df[df['Name'] == keyword]
    if not exact.empty: return exact.iloc[0]['Name'], exact.iloc[0]['Code']
    
    if keyword.isdigit():
        match = df[df['Code'] == keyword]
        if not match.empty: return match.iloc[0]['Name'], match.iloc[0]['Code']
        
    contains = df[df['Name'].str.contains(keyword, case=False)]
    if not contains.empty: return contains.iloc[0]['Name'], contains.iloc[0]['Code']
    
    return None, None

# 3. AI 한줄평 (안전한 gemini-pro 사용)
def get_ai_summary(name, price, change_rate, rsi, trend):
    if not configure_genai():
        return "⚠️ AI API 키가 설정되지 않았습니다."

    try:
        prompt = f"""
        주식 전문가로서 '{name}'(현재가 {price}원)을 분석해줘.
        [데이터] 등락률: {change_rate:.2f}%, RSI: {rsi:.2f}, 추세: {trend}
        [조건] 3줄 요약. 1.상황 2.기술적분석 3.매수/매도/관망 의견. 명확하게.
        """
        
        # 🔥 [핵심 수정] 1.5-flash 대신 가장 호환성 좋은 'gemini-pro' 사용
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"AI 분석 불가: {str(e)}"

# 4. 통합 분석
def analyze_basic(input_val, name_override=None, my_buy_price=0):
    found_name, code = find_stock_code(input_val)
    if not code:
        if str(input_val).isdigit() and len(str(input_val)) >= 6:
            code = str(input_val)
            found_name = name_override if name_override else code
        else:
            return None

    final_name = name_override if name_override else found_name

    try:
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty: return None
        
        df['MA20'] = df['Close'].rolling(20).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        curr = df.iloc[-1]
        price = int(curr['Close'])
        rsi = df['RSI'].iloc[-1]
        ma20 = df['MA20'].iloc[-1]
        
        trend_txt = "상승 추세" if price > ma20 else "하락/조정세"
        if rsi < 30: trend_txt += " (과매도)"
        elif rsi > 70: trend_txt += " (과열)"
        
        if len(df) > 1:
            prev = df.iloc[-2]
            chg_rate = (price - prev['Close']) / prev['Close'] * 100
        else:
            chg_rate = 0.0

        score = 50
        if price > ma20: score += 20
        if rsi < 30: score += 20
        if rsi > 70: score -= 10
        if chg_rate > 0: score += 10

        with st.spinner(f'🤖 AI가 {final_name} 차트를 분석하고 있습니다...'):
            ai_comment = get_ai_summary(final_name, price, chg_rate, rsi, trend_txt)

        return {
            "code": code,
            "name": final_name,
            "price": price,
            "change_rate": chg_rate,
            "score": score,
            "history": df,
            "trend_txt": trend_txt,
            "news": {
                "headline": "Gemini AI 투자 코멘트", 
                "opinion": ai_comment,              
                "risk": "투자 판단은 본인의 책임입니다."
            },
            "strategy": {"action": "매수" if score>=70 else "관망"},
            "my_buy_price": float(my_buy_price)
        }

    except Exception as e:
        print(f"Error: {e}")
        return None
