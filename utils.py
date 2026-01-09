import requests
import json
import base64
import datetime
import re
import pandas as pd
import streamlit as st
import config  # 방금 만든 config.py를 불러옵니다

def parse_relative_date(date_text):
    """'1시간 전' 같은 텍스트를 날짜로 변환"""
    now = datetime.datetime.now()
    date_text = str(date_text).strip()
    try:
        if "분 전" in date_text:
            minutes = int(re.search(r'(\d+)', date_text).group(1))
            return now - datetime.timedelta(minutes=minutes)
        elif "시간 전" in date_text:
            hours = int(re.search(r'(\d+)', date_text).group(1))
            return now - datetime.timedelta(hours=hours)
        elif "일 전" in date_text:
            days = int(re.search(r'(\d+)', date_text).group(1))
            return now - datetime.timedelta(days=days)
        elif "어제" in date_text:
            return now - datetime.timedelta(days=1)
        else:
            clean_date = date_text.replace('.', '-').rstrip('-')
            return pd.to_datetime(clean_date)
    except:
        return now - datetime.timedelta(days=365)

def round_to_tick(price):
    """주식 호가 단위 반올림"""
    if price < 2000: return int(round(price, -1))
    elif price < 5000: return int(round(price / 5) * 5)
    elif price < 20000: return int(round(price, -1))
    elif price < 50000: return int(round(price / 50) * 50)
    elif price < 200000: return int(round(price, -2))
    elif price < 500000: return int(round(price / 500) * 500)
    else: return int(round(price, -3))

def load_from_github():
    """깃허브에서 데이터 불러오기"""
    try:
        token = config.USER_GITHUB_TOKEN
        if not token: return {"portfolio": {}, "watchlist": {}}
        
        url = f"https://api.github.com/repos/{config.REPO_OWNER}/{config.REPO_NAME}/contents/{config.FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            data = json.loads(content)
            if "portfolio" not in data and "watchlist" not in data:
                return {"portfolio": {}, "watchlist": data}
            return data
        return {"portfolio": {}, "watchlist": {}}
    except:
        return {"portfolio": {}, "watchlist": {}}

def update_github_file(new_data):
    """깃허브에 데이터 저장하기"""
    try:
        token = config.USER_GITHUB_TOKEN
        if not token: return False
        
        url = f"https://api.github.com/repos/{config.REPO_OWNER}/{config.REPO_NAME}/contents/{config.FILE_PATH}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        
        r_get = requests.get(url, headers=headers)
        sha = r_get.json().get('sha') if r_get.status_code == 200 else None
        
        json_str = json.dumps(new_data, ensure_ascii=False, indent=4)
        b64_content = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        
        data = {
            "message": "Update data via Streamlit App",
            "content": b64_content
        }
        if sha: data["sha"] = sha
        
        r_put = requests.put(url, headers=headers, json=data)
        return r_put.status_code in [200, 201]
    except Exception as e:
        print(f"GitHub Save Error: {e}")
        return False

def send_telegram_msg(msg):
    """텔레그램 메시지 전송"""
    try:
        token = config.USER_TELEGRAM_TOKEN
        chat_id = config.USER_CHAT_ID
        if token and chat_id:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage", 
                data={"chat_id": chat_id, "text": msg}
            )
    except: pass
