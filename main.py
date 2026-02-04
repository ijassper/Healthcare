import streamlit as st # 스트림릿 라이브러리 추가
import base64 # 이미지를 텍스트로 변환

st.title("당뇨 케어 푸드 스캐너")

# 사진 찍기
img_file = st.camera_input("음식을 촬영해주세요")

if img_file is not None:
    # 이미지를 AI가 볼 수 있도록 변환
    bytes_data = img_file.getvalue()
    base64_image = base64.b64encode(bytes_data).decode('utf-8')

    st.success("이미지 변환 성공")

    st.write("변환된 데이터 앞 100자 : ")
    st.code(base64_image[:100])
