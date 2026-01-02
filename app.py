import streamlit as st
import sys

st.set_page_config(page_title="긴급 AI 연결 진단", page_icon="🚑")

st.title("🚑 AI 연결 진단 모드")

# 1. 라이브러리 설치 확인
st.write("### 1. 라이브러리 설치 확인")
try:
    import google.generativeai as genai
    st.success("✅ google-generativeai 라이브러리 설치 완료!")
except ImportError as e:
    st.error(f"❌ 라이브러리 설치 실패: {e}")
    st.info("GitHub의 requirements.txt 파일에 'google-generativeai'가 있는지 다시 확인해주세요.")
    st.stop()

# 2. API 키 확인
st.write("### 2. API 키 확인")
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
    # 키가 비어있거나 이상한지 체크
    if not api_key:
        st.error("❌ Secrets에 키가 있지만 내용이 비어있습니다.")
    elif api_key.startswith(" "):
        st.error("❌ API 키 앞부분에 공백(띄어쓰기)이 포함되어 있습니다. Secrets를 수정해주세요.")
    else:
        st.success("✅ API 키 감지됨")
        
        # 3. 실제 연결 테스트
        st.write("### 3. 제미나이 연결 테스트")
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            with st.spinner("제미나이에게 인사하는 중..."):
                response = model.generate_content("안녕? 짧게 대답해줘.")
                
            st.success("🎉 연결 성공! 제미나이의 응답:")
            st.info(response.text)
            st.balloons()
            
        except Exception as e:
            st.error("❌ 연결 실패 (이 에러 메시지를 캡쳐해서 보여주세요!)")
            st.code(str(e)) # 에러 내용을 있는 그대로 보여줌
            
else:
    st.error("❌ Secrets에 'GOOGLE_API_KEY'가 없습니다.")
    st.info("Streamlit 설정(Settings) -> Secrets 메뉴에 키를 등록했는지 확인해주세요.")
