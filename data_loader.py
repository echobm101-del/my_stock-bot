import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. 구글 시트 연결 (인증)
def get_db_connection():
    try:
        # Streamlit Secrets에서 키 정보 가져오기
        # secrets.toml에 등록한 [gcp_service_account] 섹션을 딕셔너리로 가져옵니다.
        credentials_dict = dict(st.secrets["gcp_service_account"])
        
        # 봇 인증 처리
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        
        # gspread 인증
        gc = gspread.authorize(credentials)
        
        # 스프레드시트 이름으로 열기 (반드시 'QuantSniper_DB'여야 함)
        sh = gc.open("QuantSniper_DB") 
        return sh
    except Exception as e:
        # 연결 실패 시 에러 메시지 출력 (디버깅용)
        print(f"DB Connection Error: {e}")
        return None

# 2. 데이터 불러오기 (Read)
def load_data():
    sh = get_db_connection()
    # 연결 실패 시 빈 깡통 반환 (앱이 멈추지 않게)
    if not sh: return {"portfolio": {}, "watchlist": {}}

    data_store = {"portfolio": {}, "watchlist": {}}

    # (1) Portfolio 시트 읽기
    try:
        ws_port = sh.worksheet("Portfolio")
        # 모든 데이터를 리스트 형태로 가져옴 (첫 줄 헤더 제외)
        records = ws_port.get_all_records() 
        
        for row in records:
            # 구글 시트는 빈 칸도 읽을 수 있으므로 이름이 있는 경우만 처리
            if row.get('Name'):
                name = row['Name']
                # 코드는 문자열로 변환하고, 저장할 때 붙인 ' 제거
                code = str(row['Code']).replace("'", "")
                # 가격은 숫자로 변환 (빈칸이면 0)
                buy_price = float(row['BuyPrice']) if row['BuyPrice'] != "" else 0
                
                data_store["portfolio"][name] = {
                    "code": code.zfill(6), # 005930 처럼 6자리 유지
                    "buy_price": buy_price
                }
    except Exception as e:
        print(f"Portfolio Load Error: {e}")

    # (2) Watchlist 시트 읽기
    try:
        ws_watch = sh.worksheet("Watchlist")
        records = ws_watch.get_all_records()
        
        for row in records:
            if row.get('Name'):
                name = row['Name']
                code = str(row['Code']).replace("'", "")
                
                data_store["watchlist"][name] = {
                    "code": code.zfill(6)
                }
    except Exception as e:
        print(f"Watchlist Load Error: {e}")

    return data_store

# 3. 데이터 추가하기 (Create/Update)
def add_stock_to_db(category, name, code, buy_price=0):
    sh = get_db_connection()
    if not sh: return False

    try:
        # 001234 같은 코드가 1234로 변하는 걸 막기 위해 앞에 '를 붙임
        str_code = f"'{code}"
        
        if category == "portfolio":
            ws = sh.worksheet("Portfolio")
            # 이미 있는지 확인 (Name 열에서 검색)
            try:
                cell = ws.find(name)
                # 있다면? -> 가격만 수정 (Update)
                # 3번째 열(C열)이 BuyPrice라고 가정
                ws.update_cell(cell.row, 3, buy_price) 
            except:
                # 없다면? -> 새 줄 추가 (Append)
                ws.append_row([name, str_code, buy_price])
                
        else: # watchlist
            ws = sh.worksheet("Watchlist")
            try:
                cell = ws.find(name)
                # 이미 있으면 아무것도 안 함
            except:
                # 없으면 추가
                ws.append_row([name, str_code])
                
        return True
    except Exception as e:
        st.error(f"구글 시트 저장 실패: {e}")
        return False

# 4. 데이터 삭제하기 (Delete)
def delete_stock_from_db(category, name):
    sh = get_db_connection()
    if not sh: return False

    try:
        sheet_name = "Portfolio" if category == "portfolio" else "Watchlist"
        ws = sh.worksheet(sheet_name)
        
        try:
            cell = ws.find(name)
            ws.delete_rows(cell.row)
            return True
        except:
            # 못 찾았으면 이미 삭제된 것으로 간주
            return True
            
    except Exception as e:
        st.error(f"구글 시트 삭제 실패: {e}")
        return False
