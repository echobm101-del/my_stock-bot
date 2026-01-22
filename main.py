import yfinance as yf
import pandas as pd

# 1. 삼성전자(005930.KS) 데이터를 가져옵니다.
ticker = "005930.KS"
print(f"--- {ticker} 데이터를 분석합니다 ---")

# 2. 2023년부터 오늘까지의 가격 데이터를 다운로드합니다.
df = yf.download(ticker, start="2023-01-01")

# 3. 전략: 20일 이동평균선 계산 (최근 20일간의 평균 가격)
# 이 선 위에 주가가 있으면 '상승 추세', 아래에 있으면 '하락 추세'로 봅니다.
df['MA20'] = df['Close'].rolling(window=20).mean()

# 4. 가장 최근 날짜의 데이터만 뽑아서 보여줍니다.
latest = df.iloc[-1] # 맨 마지막 줄 가져오기

print(f"\n기준 날짜: {latest.name.date()}")
print(f"종가(현재가): {latest['Close']:.0f}원")
print(f"20일 평균가: {latest['MA20']:.0f}원")

# 5. 매매 신호 판단
if latest['Close'] > latest['MA20']:
    print("\n[결과] 📈 상승 추세입니다. (매수/보유 추천)")
else:
    print("\n[결과] 📉 하락 추세입니다. (매도/관망 추천)")
