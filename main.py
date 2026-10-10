import streamlit as st
import google.generativeai as genai
import pandas as pd
import json, re
from PIL import Image
from supabase import create_client, Client
from datetime import datetime, timedelta
from streamlit_calendar import calendar

st.set_page_config(layout="centered", initial_sidebar_state="collapsed")

st.title("혈당 가이드")
st.markdown("음식사진을 찍거나 올려주세요. AI가 영양소를 분석하고 Supabase에 안전하게 기록합니다.")

# Gemini AI 설정
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)

# Supabase 설정 (독립적인 'healthcare' 스키마 사용)
supabase_url = st.secrets["supabase"]["url"]
supabase_key = st.secrets["supabase"]["key"]
supabase: Client = create_client(supabase_url, supabase_key)

# -------------------------------------------------------------
# 프로필 관리 함수
# -------------------------------------------------------------
def get_user_profile(user_name: str):
    """healthcare.profiles 테이블에서 사용자 프로필을 조회합니다."""
    if not user_name.strip():
        return None
    try:
        response = supabase.schema("healthcare").table("profiles").select("*").eq("user_name", user_name.strip()).order("created_at", desc=True).limit(1).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
    except Exception as e:
        st.sidebar.warning(f"프로필 조회 실패: {e}")
    return None

def save_user_profile(user_name: str, age: int, gender: str, target_sugar: float):
    """healthcare.profiles 테이블에 사용자 프로필을 생성하거나 업데이트합니다."""
    if not user_name.strip():
        return False, "이름을 입력해주세요."
    try:
        payload = {
            "user_name": user_name.strip(),
            "age": int(age),
            "gender": gender,
            "target_sugar": float(target_sugar)
        }
        # 기존 프로필 존재 여부 확인
        existing = get_user_profile(user_name.strip())
        if existing and "id" in existing:
            response = supabase.schema("healthcare").table("profiles").update(payload).eq("id", existing["id"]).execute()
        else:
            response = supabase.schema("healthcare").table("profiles").insert(payload).execute()
        return True, "프로필이 성공적으로 저장되었습니다."
    except Exception as e:
        return False, f"프로필 저장 실패: {e}"

# -------------------------------------------------------------
# 사이드 바 : 사용자 프로필 작성
# -------------------------------------------------------------
with st.sidebar:
    st.header("사용자 프로필")
    st.write("개인 정보를 입력하면 맞춤형 분석을 제공합니다.")

    user_name = st.text_input("이름", value=st.session_state.get("profile_user_name", "홍길동"))
    
    # 프로필 불러오기 버튼
    if st.button("프로필 불러오기", use_container_width=True):
        profile = get_user_profile(user_name)
        if profile:
            st.session_state.profile_age = profile.get("age", 20)
            st.session_state.profile_gender = profile.get("gender", "남성")
            st.session_state.profile_target_sugar = float(profile.get("target_sugar", 25))
            st.success("프로필을 불러왔습니다!")
        else:
            st.info("등록된 프로필이 없어 기본값을 사용합니다.")

    user_age = st.number_input("나이", value=st.session_state.get("profile_age", 20), min_value=1, max_value=120)
    user_gender = st.selectbox("성별", ["남성", "여성"], index=0 if st.session_state.get("profile_gender", "남성") == "남성" else 1)

    st.header("목표 설정")
    daily_goal = st.number_input("하루 목표 당 섭취량(g)", value=float(st.session_state.get("profile_target_sugar", 25.0)), min_value=0.0, step=1.0)

    if st.button("프로필 저장", type="primary", use_container_width=True):
        ok, msg = save_user_profile(user_name, user_age, user_gender, daily_goal)
        if ok:
            st.session_state.profile_user_name = user_name
            st.session_state.profile_age = user_age
            st.session_state.profile_gender = user_gender
            st.session_state.profile_target_sugar = daily_goal
            st.success(msg)
        else:
            st.error(msg)

# -------------------------------------------------------------
# 식단 데이터 DB 함수 (healthcare 스키마 적용)
# -------------------------------------------------------------
def fetch_supabase_data(filter_user: str = None):
    """healthcare.meal_logs 테이블에서 식단 기록을 조회합니다."""
    try:
        query = supabase.schema("healthcare").table("meal_logs").select("*").order("created_at", desc=True)
        if filter_user and filter_user.strip():
            query = query.eq("user_name", filter_user.strip())
        response = query.execute()
        return response.data or []
    except Exception as e:
        st.error(f"Supabase healthcare.meal_logs 데이터 조회 중 오류 발생: {e}")
        return []

def save_to_supabase(data: dict, current_user: str = ""):
    """Gemini 분석 결과를 healthcare.meal_logs 테이블에 저장합니다."""
    try:
        # 안전한 숫자 변환 헬퍼
        def to_float(val, default=0.0):
            try:
                if val is None:
                    return default
                if isinstance(val, (int, float)):
                    return float(val)
                # 문자열에서 숫자 추출
                extracted = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", str(val))
                return float(extracted[0]) if extracted else default
            except Exception:
                return default

        payload = {
            "user_name": current_user.strip() if current_user.strip() else "홍길동",
            "meal_name": str(data.get("meal_name") or data.get("식단명") or "식단"),
            "calories": to_float(data.get("calories") or data.get("칼로리")),
            "sugar": to_float(data.get("sugar") or data.get("당류")),
            "carbs": to_float(data.get("carbs") or data.get("탄수화물")),
            "protein": to_float(data.get("protein") or data.get("단백질")),
            "fat": to_float(data.get("fat") or data.get("지방")),
            "ai_feedback": str(data.get("ai_feedback") or data.get("분석내용") or ""),
            "image_url": None
        }

        response = supabase.schema("healthcare").table("meal_logs").insert(payload).execute()
        return True, response
    except Exception as e:
        return False, f"healthcare.meal_logs 저장 오류: {e}"

# 탭 메뉴 만들기
tab1, tab2, tab3, tab4 = st.tabs(["대시보드", "혈당 관리", "카메라로 촬영", "갤러리에서 업로드"])

# 사진 파일 변수
img_file = None

# -------------------------------------------------------------
# [탭 1] 대시보드
# -------------------------------------------------------------
with tab1:
    st.subheader(f"📊 {user_name}님의 건강 리포트")

    try:
        items = fetch_supabase_data(user_name)
        if not items:
            # 해당 사용자의 기록이 없다면 전체 기록도 함께 확인
            items = fetch_supabase_data()

        if items:
            today = datetime.now()
            week_ago = today - timedelta(days=7)

            weekly_data = []
            for item in items:
                created_at_str = item.get("created_at")
                if not created_at_str:
                    continue

                try:
                    record_date = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    try:
                        record_date = datetime.strptime(created_at_str[:10], "%Y-%m-%d")
                    except Exception:
                        continue

                if record_date >= week_ago:
                    weekly_data.append({
                        "식단명": item.get("meal_name") or "식단",
                        "칼로리(kcal)": float(item.get("calories") or 0),
                        "당류(g)": float(item.get("sugar") or 0),
                        "탄수화물(g)": float(item.get("carbs") or 0),
                        "단백질(g)": float(item.get("protein") or 0),
                        "지방(g)": float(item.get("fat") or 0)
                    })

            st.write(f"최근 7일간 **{len(weekly_data)}개**의 식단 기록이 있습니다.")

            if weekly_data:
                df = pd.DataFrame(weekly_data)

                # 메트릭 표시 (칼로리 및 당류 섭취 현황)
                total_cal = df["칼로리(kcal)"].sum()
                total_sugar = df["당류(g)"].sum()
                avg_sugar_per_meal = df["당류(g)"].mean()

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("이번 주 누적 칼로리", f"{int(total_cal):,} kcal")
                with col2:
                    st.metric("이번 주 누적 당류", f"{total_sugar:.1f} g")
                with col3:
                    st.metric("식사당 평균 당류", f"{avg_sugar_per_meal:.1f} g")

                # 식단별 칼로리 가로형 바 차트
                st.write("##### 🍽️ 식단별 칼로리 비교")
                st.bar_chart(df.set_index("식단명")[["칼로리(kcal)"]], horizontal=True)

                # 영양소 구성 비교 차트
                st.write("##### 🥗 식단별 주요 영양소 (당류/탄수화물/단백질/지방)")
                st.bar_chart(df.set_index("식단명")[["당류(g)", "탄수화물(g)", "단백질(g)", "지방(g)"]])
            else:
                st.info("최근 7일간 기록된 식단이 없습니다.")
        else:
            st.info("아직 기록된 식단이 없어요. 사진을 업로드하여 첫 식단 기록을 시작해보세요.")
    except Exception as e:
        st.error(f"데이터를 불러오지 못했습니다: {e}")

# -------------------------------------------------------------
# [탭 2] 혈당 관리 (캘린더 뷰)
# -------------------------------------------------------------
with tab2:
    st.subheader(f"📅 {user_name}님의 식단 및 혈당 캘린더")

    # 1. 데이터 조회 (현재 사용자 기준 및 폴백)
    raw_data = fetch_supabase_data(user_name)
    if not raw_data and user_name.strip():
        raw_data = fetch_supabase_data()

    # 2. 데이터가 없을 경우 안내 문구 표시
    if not raw_data:
        st.info("아직 등록된 식단 기록이 없습니다. 사진을 촬영하거나 업로드하여 첫 식단을 기록해 보세요!")
    else:
        st.caption(f"총 {len(raw_data)}건의 식단 기록이 캘린더에 표시됩니다.")

    # 3. 캘린더 이벤트 매핑 (FullCalendar 표준 포맷)
    events = []
    for item in raw_data:
        try:
            meal_name = item.get("meal_name") or "식단"
            calories = int(float(item.get("calories") or 0))
            created_at_val = item.get("created_at") or ""
            
            # 한국 시간(KST) 및 YYYY-MM-DD 날짜 추출
            date_str = datetime.now().strftime("%Y-%m-%d")
            time_str = ""
            iso_start = date_str
            if created_at_val:
                try:
                    if "T" in str(created_at_val):
                        dt = datetime.fromisoformat(str(created_at_val).replace("Z", "+00:00"))
                        date_str = dt.strftime("%Y-%m-%d")
                        time_str = dt.strftime("%H:%M")
                        iso_start = dt.strftime("%Y-%m-%dT%H:%M:%S")
                    else:
                        date_str = str(created_at_val)[:10]
                        iso_start = date_str
                except Exception:
                    date_str = str(created_at_val)[:10]
                    iso_start = date_str

            event_title = f"🍽️ {meal_name} ({calories} kcal)"
            if time_str:
                event_title = f"[{time_str}] 🍽️ {meal_name} ({calories} kcal)"

            events.append({
                "title": event_title,
                "start": iso_start,
                "end": iso_start,
                "allDay": True,
                "backgroundColor": "#2563EB",
                "borderColor": "#1D4ED8",
                "textColor": "#FFFFFF",
                "resourceId": item.get("user_name") or user_name,
                "extendedProps": {
                    "id": item.get("id"),
                    "meal_name": meal_name,
                    "calories": calories,
                    "sugar": float(item.get("sugar") or 0),
                    "carbs": float(item.get("carbs") or 0),
                    "protein": float(item.get("protein") or 0),
                    "fat": float(item.get("fat") or 0),
                    "ai_feedback": item.get("ai_feedback") or "분석 내용 없음",
                    "user_name": item.get("user_name") or user_name,
                    "record_date": date_str,
                    "record_time": time_str
                }
            })
        except Exception:
            continue

    calendar_options = {
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek",
        },
        "initialDate": datetime.now().strftime("%Y-%m-%d"),
        "initialView": "dayGridMonth",
        "selectable": True,
        "navLinks": True,
        "contentHeight": 550,
        "height": "auto",
        "aspectRatio": 1.4,
    }

    custom_css = """
        .fc {
            min-height: 550px !important;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        .fc-view-harness {
            min-height: 500px !important;
        }
        .fc-header-toolbar {
            margin-bottom: 0.8rem !important;
        }
        .fc-event {
            cursor: pointer !important;
            border-radius: 4px !important;
            padding: 3px 6px !important;
            font-size: 0.85rem !important;
            font-weight: 500 !important;
        }
    """

    # 4. 캘린더 컴포넌트 렌더링
    state = calendar(
        events=events,
        options=calendar_options,
        custom_css=custom_css,
        key="healthcare_calendar"
    )

    if 'show_detail' not in st.session_state:
        st.session_state.show_detail = False

    if state and state.get("eventClick"):
        st.session_state.show_detail = True
        st.session_state.selected_event = state["eventClick"]["event"]["extendedProps"]

    if st.session_state.get("show_detail") and 'selected_event' in st.session_state:
        event_props = st.session_state.selected_event
        st.divider()
        st.write(f"### 📋 {event_props.get('meal_name')} 상세 분석 리포트")
        if event_props.get("record_time"):
            st.caption(f"기록 일시: {event_props.get('record_date')} {event_props.get('record_time')} | 사용자: {event_props.get('user_name')}")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("칼로리", f"{event_props.get('calories', 0)} kcal")
        c2.metric("당류", f"{event_props.get('sugar', 0)} g")
        c3.metric("탄수화물", f"{event_props.get('carbs', 0)} g")
        c4.metric("단백질/지방", f"{event_props.get('protein', 0)}g / {event_props.get('fat', 0)}g")

        st.write("#### 👩‍⚕️ 임상 영양사 AI 피드백")
        st.info(event_props.get("ai_feedback", ""))

    # 5. 하단 식단 기록 타임라인 및 상세 리스트 (상시 확인 가능한 폴백 뷰)
    st.divider()
    st.write("### 📜 식단 기록 목록 및 피드백")
    if raw_data:
        for idx, item in enumerate(raw_data):
            meal_title = item.get("meal_name") or "식단"
            cal = item.get("calories") or 0
            sug = item.get("sugar") or 0
            carb = item.get("carbs") or 0
            prot = item.get("protein") or 0
            fat = item.get("fat") or 0
            c_at = item.get("created_at") or ""
            feedback = item.get("ai_feedback") or "분석 내용 없음"
            
            # 시간 표시 포맷
            time_label = str(c_at)[:19].replace("T", " ") if c_at else "날짜 미상"
            
            with st.expander(f"🍽️ [{time_label}] {meal_title} ({cal} kcal, 당류 {sug}g)", expanded=(idx == 0)):
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("칼로리", f"{cal} kcal")
                col_b.metric("당류", f"{sug} g")
                col_c.metric("탄수화물", f"{carb} g")
                col_d.metric("단백질 / 지방", f"{prot}g / {fat}g")
                
                st.markdown("##### 👩‍⚕️ AI 임상 영양사 코칭")
                st.markdown(feedback)

# -------------------------------------------------------------
# [탭 3] 카메라 촬영 기능
# -------------------------------------------------------------
with tab3:
    camera_img = st.camera_input("음식을 촬영해주세요")
    if camera_img:
        img_file = camera_img

# -------------------------------------------------------------
# [탭 4] 파일 업로드 기능
# -------------------------------------------------------------
with tab4:
    upload_img = st.file_uploader("이미지 파일을 업로드 하세요.", type=['png', 'jpg', 'jpeg'])
    if upload_img:
        img_file = upload_img

# -------------------------------------------------------------
# AI 분석 및 healthcare.meal_logs 저장 처리
# -------------------------------------------------------------
if img_file is not None:
    image = Image.open(img_file)
    st.image(image, caption="분석할 음식 이미지", use_container_width=True)

    # Gemini 정밀 영양소 분석 프롬프트
    prompt = f"""
    너는 {user_name}님의 전담 임상 영양사야.
    사용자의 정보:
    - 이름: {user_name}
    - 나이: {user_age}세
    - 성별: {user_gender}
    - 하루 목표 당 섭취량: {daily_goal}g
        
    제공된 음식 사진을 분석하여 영양소를 정밀 추정하고 피드백을 제공해줘.
    
    1. [인사 및 요약]: {user_name}님, 보여주신 음식의 정보를 알려드릴게요.
    2. [영양소 정보]: 추정 칼로리(kcal), 당류(g), 탄수화물(g), 단백질(g), 지방(g)
    3. [개인 맞춤 분석]: 이 음식이 사용자의 하루 목표 당 섭취량({daily_goal}g)에서 몇 %나 차지하는지 계산해줘.
    4. [영양사의 조언]: 사용자의 나이와 목표를 고려해 혈당 스파이크를 줄이는 구체적인 섭취 꿀팁을 제시해줘.

    [분석 리포트] : 위 1~4번 형식으로 사용자에게 친절한 줄글 메시지를 작성해줘.
    [JSON 데이터] : 아래 JSON 구조로만 반드시 작성해줘. JSON 외의 다른 텍스트는 코드블록 안에 넣지 마.
    {{
        "meal_name": "음식 이름",
        "calories": 350.0,
        "sugar": 15.0,
        "carbs": 45.0,
        "protein": 12.0,
        "fat": 8.0,
        "ai_feedback": "1~4번 전체 분석 리포트 내용"
    }}
    """

    if st.button("영양소 분석하기", type="primary", use_container_width=True):
        with st.spinner("AI 영양사가 영양 성분 및 혈당 영향을 분석 중입니다..."):
            try:
                model = genai.GenerativeModel('gemini-2.5-flash')
                response = model.generate_content([prompt, image])
                st.session_state.ai_result = response.text
                st.success("분석 완료!")
            except Exception as e:
                st.error(f"AI 분석 중 오류가 발생했습니다: {e}")

    # 결과 표시 및 Supabase 저장 버튼
    if 'ai_result' in st.session_state:
        result_text = st.session_state.ai_result

        st.write("### 🔍 AI 분석 결과")
        st.markdown(result_text)

        if st.button("💾 Supabase에 식단 기록 저장", type="primary", use_container_width=True):
            try:
                # JSON 파싱
                json_match = re.search(r'\{[\s\S]*\}', result_text)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = result_text[result_text.find("{"):result_text.rfind("}")+1]

                data = json.loads(json_str)

                success, res = save_to_supabase(data, user_name)
                if success:
                    st.success("✅ Supabase 'healthcare.meal_logs'에 식단 기록이 성공적으로 저장되었습니다!")
                    st.rerun()
                else:
                    st.error(f"❌ 저장 실패: {res}")
            except Exception as e:
                st.error(f"데이터 파싱 및 저장 중 오류가 발생했습니다: {e}")
