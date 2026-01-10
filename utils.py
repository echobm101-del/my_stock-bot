import FinanceDataReader as fdr
import pandas as pd
import datetime
import requests
import json

# 1. 기술적 분석 (기존 코드의 핵심 로직)
def analyze_basic(code, name, my_buy_price=0):
    try:
        # 1년치 데이터 가져오기
        df = fdr.DataReader(code, datetime.datetime.now() - datetime.timedelta(days=365))
        if df.empty: return None
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 보조지표 계산 (간소화 버전)
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        
        # 점수 계산 로직
        score = 50
        trend_txt = "관망세"
        
        if curr['Close'] > ma20:
            score += 20
            trend_txt = "상승 추세 (20일선 위)"
        else:
            score -= 10
            trend_txt = "하락/조정세"
            
        change_rate = (curr['Close'] - prev['Close']) / prev['Close'] * 100
        
        return {
            "code": code,
            "name": name,
            "price": int(curr['Close']),
            "change_rate": change_rate,
            "score": score,
            "history": df, # 차트 그리기용
            "trend_txt": trend_txt,
            "strategy": {"action": "매수" if score >= 70 else "관망"},
            "my_buy_price": float(my_buy_price) if my_buy_price else 0
        }
    except Exception as e:
        print(f"Error analyzing {name}: {e}")
        return None

# 원래 있던 AI 뉴스 분석 함수 등은 여기에 계속 추가하면 됩니다.
