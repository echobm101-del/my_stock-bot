import requests
import re
import streamlit as st  # streamlit의 금고 기능을 쓰기 위해 추가

# ==========================================
# 🔐 보안이 적용된 키 가져오기
# ==========================================
# secrets.toml 파일에서 [naver] 항목을 찾아 키를 꺼내옵니다.
try:
    CLIENT_ID = st.secrets["naver"]["client_id"]
    CLIENT_SECRET = st.secrets["naver"]["client_secret"]
except FileNotFoundError:
    # 혹시 금고 파일을 못 찾을 경우를 대비한 안전 장치
    CLIENT_ID = ""
    CLIENT_SECRET = ""

def get_naver_news_titles(keyword, display_count=3):
    """
    키워드로 네이버 뉴스를 검색하여 제목과 링크를 가져옵니다.
    """
    # 키가 제대로 없으면 바로 중단
    if not CLIENT_ID or not CLIENT_SECRET:
        return [{"title": "API 키 설정 오류: secrets.toml을 확인하세요.", "link": "#"}]

    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET
    }
    params = {
        "query": keyword,
        "display": display_count,
        "sort": "sim"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            items = response.json().get('items', [])
            news_results = []
            for item in items:
                clean_title = re.sub('<[^<]+?>', '', item['title'])
                clean_title = clean_title.replace('&quot;', '"').replace('&amp;', '&')
                
                news_results.append({
                    "title": clean_title,
                    "link": item['originallink'] or item['link']
                })
            return news_results
        else:
            return [{"title": f"뉴스 가져오기 실패 (에러코드: {response.status_code})", "link": "#"}]
    except Exception as e:
        return [{"title": f"연결 오류 발생: {str(e)}", "link": "#"}]
