import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ------------------------------------------------------------------------------
# 1. 구글 시트 연결 함수 (비밀번호 박스에서 열쇠 꺼내서 문 열기)
# ------------------------------------------------------------------------------
def get_connection():
    try:
        # Streamlit Secrets에서 저장해둔 구글 시트 정보 가져오기
        conf = st.secrets["google_sheets"]
        
        # 연결을 위한 인증 정보 만들기
        # (줄바꿈 문자 \n 처리를 확실하게 하기 위해 replace를 사용합니다)
        creds_dict = {
            "type": conf["type"],
            "project_id": conf["project_id"],
            "private_key_id": conf["private_key_id"],
            "private_key": conf["private_key"].replace("\\n", "\n"), 
            "client_email": conf["client_email"],
            "client_id": conf["client_id"],
            "auth_uri": conf["auth_uri"],
            "token_uri": conf["token_uri"],
            "auth_provider_x509_cert_url": conf["auth_provider_x509_cert_url"],
            "client_x509_cert_url": conf["client_x509_cert_url"]
        }
        
        # 구글 드라이브와 스프레드시트 권한 설정
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # 인증 및 로그인
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 시트 주소로 파일 열기
        sheet_url = conf["sheet_url"]
        doc = client.open_by_url(sheet_url)
        return doc
        
    except Exception as e:
        st.error(f"❌ 구글 시트 연결 실패: {str(e)}")
        return None

# ------------------------------------------------------------------------------
# 2. 데이터 불러오기 (Load): 구글 시트 -> 앱으로 가져오기
# ------------------------------------------------------------------------------
def load_db():
    doc = get_connection()
    # 연결 실패 시 빈 깡통 반환 (에러 방지)
    if not doc: return {"portfolio": {}, "watchlist": {}}
    
    try:
        # --- [1] 포트폴리오(내 잔고) 읽기 ---
        ws_port = doc.worksheet("portfolio")
        port_rows = ws_port.get_all_records() # 엑셀 내용을 리스트로 가져옴
        
        portfolio_dict = {}
        for row in port_rows:
            # 이름이 비어있지 않은 줄만 가져오기
            if str(row['Name']).strip():
                portfolio_dict[row['Name']] = {
                    "code": str(row['Code']).zfill(6), # 005930 처럼 6자리 유지
                    "buy_price": float(row['BuyPrice']) if row['BuyPrice'] != "" else 0.0
                }
        
        # --- [2] 관심종목 읽기 ---
        ws_watch = doc.worksheet("watchlist")
        watch_rows = ws_watch.get_all_records()
        
        watchlist_dict = {}
        for row in watch_rows:
            if str(row['Name']).strip():
                watchlist_dict[row['Name']] = {
                    "code": str(row['Code']).zfill(6)
                }
                
        # 앱에서 쓰던 데이터 형태로 묶어서 반환
        return {"portfolio": portfolio_dict, "watchlist": watchlist_dict}
        
    except Exception as e:
        st.error(f"📉 데이터 읽기 오류: {str(e)}")
        # 오류 나면 빈 데이터 반환
        return {"portfolio": {}, "watchlist": {}}

# ------------------------------------------------------------------------------
# 3. 데이터 저장하기 (Save): 앱 -> 구글 시트로 쓰기
# ------------------------------------------------------------------------------
def save_db(data):
    doc = get_connection()
    if not doc: return False
    
    try:
        # --- [1] 포트폴리오 저장 ---
        ws_port = doc.worksheet("portfolio")
        ws_port.clear() # 기존 내용 싹 지우기 (덮어쓰기 위해)
        ws_port.append_row(["Name", "Code", "BuyPrice"]) # 첫 줄(제목) 다시 쓰기
        
        # 데이터 한 줄씩 만들기
        port_rows = []
        for name, info in data.get('portfolio', {}).items():
            port_rows.append([
                name, 
                str(info.get('code')), 
                info.get('buy_price', 0)
            ])
        
        # 한꺼번에 입력 (속도 향상)
        if port_rows: ws_port.append_rows(port_rows)
        
        # --- [2] 관심종목 저장 ---
        ws_watch = doc.worksheet("watchlist")
        ws_watch.clear()
        ws_watch.append_row(["Name", "Code"]) # 첫 줄(제목)
        
        watch_rows = []
        for name, info in data.get('watchlist', {}).items():
            watch_rows.append([
                name, 
                str(info.get('code'))
            ])
            
        if watch_rows: ws_watch.append_rows(watch_rows)
            
        return True # 저장 성공!
        
    except Exception as e:
        st.error(f"💾 데이터 저장 오류: {str(e)}")
        return False
