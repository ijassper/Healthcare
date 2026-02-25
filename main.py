import streamlit as st # 스트림릿 라이브러리 추가
# import base64 # 이미지를 텍스트로 변환 openia = GPT
import google.generativeai as genai
from PIL import Image # Genai

st.title("당뇨 케어 푸드 스캐너")
st.markdown("음식사진을 찍거나 올려주세요. AI가 영양소를 분석해드립니다.")

GOOGLE_API_KEY = "AIzaSyCVdVzlrPJiK0koRJiTBgXryCJW37dZTmE"
genai.configure(api_key=GOOGLE_API_KEY)

# 탭 메뉴 만들기
tab1, tab2 = st.tabs(["카메라로 촬영","갤러리에서 업로드"])

# 사진 찍기
img_file = None

# [탭 1] 카메라 기능
with tab1:
    camera_img = st.camera_input("음식을 촬영해주세요")
    if camera_img:
        img_file = camera_img

# [탭 2] 파일 업로드 기능
with tab2:
    upload_img = st.file_uploader("이미지 파일을 업로드 하세요.", tpye=['png','jpg','jpge'])
    if upload_img:
        img_file = upload_img


if img_file is not None:
    
    # 이미지를 AI가 볼 수 있도록 변환
    image = Image.open(img_file)
    
    # GPT용 이미지 확인하는 방법
    # bytes_data = img_file.getvalue()
    # base64_image = base64.b64encode(bytes_data).decode('utf-8')
    

    # 확인용 화면에 사진 띄우기
    st.image(image, caption="촬영된 음식", use_container_width=True)
    
    # st.success("이미지 변환 성공")

    # st.write("변환된 데이터 앞 100자 : ")
    # 문자열 다루기 [시작값:끝값]
    # st.code(base64_image[:-100])

    # Gemini에게 보낼 질문
    prompt = """
    너는 당뇨병 환자를 위한 전문 영양사야.
    이 음식 사진을 분석해서 다음 정보를 정리해줘:

    1. 음식 이름
    2. 추정 당류 함량 (g)
    3. 추정 탄수화물 함량 (g)
    4. 당뇨 환자를 위한 섭취 가이드 (주의할 점)

    말투는 친절하고 전문적으로 해줘.
    """

    #st.write("사용가능한 모델 확인")
    #try:
    #    for m in genai.list_models():
    #        if 'generateContent' in m.supported_generation_methods:
    #            st.write(m.name)
    #except Exception as e:
    #    st.error(f"목록 가져오기 실패 : {e}")
        
    # 실행버튼을 누르면 분석 시작
    if st.button("영양소 분석하기"):
        with st.spinner("AI 영양사가 분석 중입니다..."):
            try:
                # Gemini 모델 불러오기
                model = genai.GenerativeModel('gemini-2.5-flash')

                # AI에게 질문과 이미지 전달
                response = model.generate_content([prompt, image])

                # 결과 출력
                st.success("분석 완료!")
                st.write(response.text)
            except Exception as e:
                st.error(f"오류가 발생했습니다.: {e}")
