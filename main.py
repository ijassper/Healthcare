import streamlit as st # 스트림릿 라이브러리 추가
# import base64 # 이미지를 텍스트로 변환 openia = GPT
import google.generativeai as genai
from PIL import Image # Genai
from notion_client import Client

# 노션 설정
notion = Client(auth="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")

st.title("혈당 가이드")
st.markdown("음식사진을 찍거나 올려주세요. AI가 영양소를 분석해드립니다.")

GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)

# 사이드 바 : 사용자 프로필 작성
with st.sidebar:
    st.header("사용자 프로필")
    st.write("개인 정보를 입력하면 맞춤형 분석을 제공합니다.")

    # 정보입력
    user_name = st.text_input("이름")
    user_age = st.number_input("나이", value=20)
    user_gender = st.selectbox("성별",["남성","여성"])

    st.header("목표 설정")
    daily_goal = st.text_input("하루 목표 당 섭취량(g)", value=25)
    
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
    upload_img = st.file_uploader("이미지 파일을 업로드 하세요.", type=['png','jpg','jpge'])
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
    prompt = f"""
    너는 {user_name}님의 전담 임상 영양사야.
    사용자의 정보는 다음과 같아:
    - 이름: {user_name}
    - 나이: {user_age}
    - 성별: {user_gender}
    - 오늘 목표 당 섭취량: {daily_goal}g
        
    분석을 수행한 뒤, 사용자가 읽기 좋은 결과와 데이터베이스 기록용 JSON 결과를 함께 제공해줘.
    
    1. [인사 및 요약]: {user_name}님, 보여주신 음식의 정보를 알려드릴게요.
    2. [영양소 정보]: 추정 당류 함량 (g), 추정 탄수화물 함량 (g), 칼로리(kcal)
    3. [개인 맞춤 분석]: 이 음식이 사용자의 목표치({daily_goal}g)에서 몇 %나 차지하는지 계산해줘.
       (예: 이 쿠기 한 개는 {user_name}님의 하루 목표 섭취량의 60%에 달합니다!)
    4. [영영사의 조언]: 사용자의 나이와 목표를 고려해서 혈당을 덜 올리는 섭취 꿀팁을 알려줘.

    [분석 리포트] : 위 1~4번 형식으로 사용자에게 보여줄 친절한 메세지를 작성해줘.
    [JSON 데이터] : 아래 JSON 형식으로만 데이터를 작성해줘. JSON 외에 다른 설명은 절대 추가하지 마.
    {{
        "식단명": "음식 이름",
        "영양정보": "당류 0g, 탄수화물 0g",
        "칼로리": 0
    }}
    """

    #st.write("사용가능한 모델 확인")
    #try:
    #    for m in genai.list_models():
    #        if 'generateContent' in m.supported_generation_methods:
    #            st.write(m.name)
    #except Exception as e:
    #    st.error(f"목록 가져오기 실패 : {e}")
        
    # 분석 버튼 로직
    if st.button("영양소 분석하기"):
        with st.spinner("AI 영양사가 분석 중입니다..."):
            try:
                # Gemini 모델 불러오기
                model = genai.GenerativeModel('gemini-2.5-flash')

                # AI에게 질문과 이미지 전달
                response = model.generate_content([prompt, image])
                
                # 분석결과 세션에 저장
                st.session_state.ai_result = response.text
                st.success("분석 완료!")    
            except Exception as e:
                st.error(f"오류가 발생했습니다.: {e}")
    
    # 저장 로직 (노션에 분석 결과 저장)
    if 'ai_result' in st.session_state:
        st.write(st.session_state.ai_result)
        
        if st.button("노션에 저장"):
        
            # AI의 결과(JSON)를 파이썬 딕셔너리 자료형으로 변환
            data = json.loads(st.session_state.ai_result)
            
            notion.pages.create(
                parent={"database_id": "3ab9ad098eee80b5a5d4e5b18f75802b"},
                properties={
                    "Name": {"title": [{"text": {"content": data["식단명"]}}]},
                    "영양정보": {"rich_text": [{"text": {"content": data["영양정보"]}}]},
                    "칼로리": {"number": int(data["칼로리"])}
                }
            )
            st.success("노션 저장 완료")
