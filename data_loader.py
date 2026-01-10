import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------------------------------------------------
# 1. 구글 시트 연결 (인증) - 에러 메시지 강화
# ---------------------------------------------------------
def get_db_connection():
    try:
        # Streamlit Secrets에서 [gcp_service_account] 가져오기
        # st.secrets는 딕셔너리처럼 동작하지만, 안전하게 dict()로 변환
        credentials_dict = dict(st.secrets["gcp_service_account"])
        
        # 봇 인증 범위 설정
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # JSON 키 내용으로 인증 객체 생성
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        
        # gspread 인증 실행
        gc = gspread.authorize(credentials)
        
        # 스프레드시트 열기 (이름 정확해야 함: QuantSniper_DB)
        sh = gc.open("QuantSniper_DB") 
        return sh

    except Exception as e:
        # 🚨 여기가 중요합니다! 에러가 나면 화면에 빨간 박스로 보여줍니다.
        st.error(f"⚠️ 구글 시트 연결 오류 발생:\n{str(e)}")
        return None

# ---------------------------------------------------------
# 2. 데이터 불러오기 (Read)
# ---------------------------------------------------------
def load_data():
    sh = get_db_connection()
    # 연결 실패 시 빈 딕셔너리 반환 (앱이 멈추지 않도록)
    if not sh: return {"portfolio": {}, "watchlist": {}}

    data_store = {"portfolio": {}, "watchlist": {}}

    # (1) Portfolio 시트 읽기
    try:
        ws_port = sh.worksheet("Portfolio")
        records = ws_port.get_all_records() 
        
        for row in records:
            if row.get('Name'):
                name = row['Name']
                # 코드는 문자열로, 작은따옴표(') 제거
                code = str(row['Code']).replace("'", "")
                # 가격은 숫자로 (빈칸이면 0)
                buy_price = float(row['BuyPrice']) if row['BuyPrice'] != "" else 0
                
                data_store["portfolio"][name] = {
                    "code": code.zfill(6), 
                    "buy_price": buy_price
                }
    except Exception as e:
        # 시트가 없거나 읽기 에러 시
        # st.warning(f"Portfolio 시트 읽기 실패: {e}") # 필요 시 주석 해제
        pass

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
        # st.warning(f"Watchlist 시트 읽기 실패: {e}") # 필요 시 주석 해제
        pass

    return data_store

# ---------------------------------------------------------
# 3. 데이터 추가하기 (Create/Update)
# ---------------------------------------------------------
def add_stock_to_db(category, name, code, buy_price=0):
    sh = get_db_connection()
    if not sh: return False

    try:
        str_code = f"'{code}" # 엑셀에서 숫자가 짤리지 않게 ' 붙임
        
        if category == "portfolio":
            ws = sh.worksheet("Portfolio")
            try:
                # 이미 있는 종목인지 확인
                cell = ws.find(name)
                # 있다면 가격 수정 (3번째 열)
                ws.update_cell(cell.row, 3, buy_price) 
            except:
                # 없다면 새로 추가
                ws.append_row([name, str_code, buy_price])
                
        else: # watchlist
            ws = sh.worksheet("Watchlist")
            try:
                cell = ws.find(name)
                # 이미 있으면 통과
            except:
                ws.append_row([name, str_code])
                
        return True

    except Exception as e:
        # 저장 실패 시 상세 에러 출력
        st.error(f"❌ 데이터 저장 실패:\n{str(e)}")
        return False

# ---------------------------------------------------------
# 4. 데이터 삭제하기 (Delete)
# ---------------------------------------------------------
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
            # 시트에 없으면 이미 삭제된 것으로 간주
            return True
            
    except Exception as e:
        st.error(f"❌ 데이터 삭제 실패:\n{str(e)}")
        return False
