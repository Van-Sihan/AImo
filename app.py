# =====================================================================
# app.py  -  불 앞에서 (요리 음성 비서)
#
# 손에 기름이 묻은 채로, 한 걸음 떨어져서 보는 화면
# 타이머와 계량 환산은 Gemini를 쓰지 않으므로 API 한도가 줄지 않음
# =====================================================================

# 웹 화면을 만들어주는 라이브러리를 가져옴
import streamlit as st

# Gemini API를 사용하기 위한 라이브러리를 가져옴
from google import genai
from google.genai import types

# 텍스트를 음성으로 바꾸기 위한 라이브러리를 가져옴
from gtts import gTTS

# 음성 데이터를 메모리에서 다루기 위한 모듈을 가져옴
import io

# 한글 검사와 문자열 분리를 위해 정규식 모듈을 가져옴
import re

# 레시피 단계를 구조화된 형태로 주고받기 위해 가져옴
import json

# 타이머의 남은 시간을 계산하기 위해 가져옴
import time

# 레시피북 파일을 다루기 위해 가져옴
from pathlib import Path

# 저장한 날짜를 기록하기 위해 가져옴
from datetime import datetime


# ---------------------------------------------------------------------
# 1. 설정
# ---------------------------------------------------------------------

# 사용자가 고를 수 있는 모델 목록
MODELS = {
    "빠르게 (Flash-Lite)": "gemini-flash-lite-latest",
    "꼼꼼하게 (Flash)": "gemini-flash-latest",
}

# 답변의 최대 길이. 요리 중에는 짧아야 하므로 낮게 잡음
MAX_TOKENS = 400

# 모델이 속으로 고민하는 깊이. low면 빠름
THINKING = "low"

# 모델에게 함께 보낼 지난 대화의 개수
# 이 값을 넘는 옛 대화는 보내지 않아 요청이 무거워지는 것을 막음
KEEP_TURNS = 6

# 화면에 오디오 플레이어를 남겨둘 답변의 개수
# 플레이어가 계속 쌓이면 브라우저가 느려지기 때문임
KEEP_AUDIO = 3

# 비서의 성격을 정하는 지시문
SYSTEM_PROMPT = (
    "너는 AI모다. 요리를 오래 해 온 이모처럼 옆에서 알려주는 요리 보조다. "
    "상대는 지금 불 앞에 서 있고 손이 바쁘다. 화면을 오래 볼 수 없다. "
    "친근한 존댓말로 짧게 말한다. 답은 두세 문장으로 끝낸다. "
    "불 세기, 시간, 양은 반드시 구체적인 숫자로 말한다. "
    "예를 들어 '중불에서 3분' 처럼 말한다. "
    "확신이 없으면 아는 척하지 말고 모른다고 말한다. "
    "목록 기호, 마크다운, 이모지는 쓰지 않는다. "
    "말로 듣는 답이므로 소리 내어 읽기 좋게 쓴다. "
    "타는 냄새나 화상처럼 위험한 상황이면 그것부터 말한다."
)

# 계량 도구별 부피를 밀리리터로 정리해 둠
UNITS = {
    "큰술": 15,
    "작은술": 5,
    "밥숟가락": 12,
    "종이컵": 180,
    "계량컵": 200,
    "소주잔": 50,
}

# 재료마다 1밀리리터가 몇 그램인지 정리해 둠
# 같은 한 큰술이라도 재료에 따라 무게가 두 배 넘게 차이나기 때문임
DENSITY = {
    "물": 1.00,
    "간장": 1.15,
    "설탕": 0.80,
    "소금(고운)": 1.20,
    "고춧가루": 0.45,
    "밀가루": 0.53,
    "식용유": 0.92,
    "참기름": 0.92,
    "고추장": 1.30,
    "된장": 1.20,
    "다진마늘": 1.00,
    "맛술": 1.00,
    "식초": 1.00,
    "꿀": 1.40,
    "물엿": 1.40,
    "케첩": 1.10,
    "마요네즈": 0.91,
}

# 브라우저 탭 제목과 아이콘을 설정하고 화면을 넓게 씀
st.set_page_config(page_title="AI모네 밥상", page_icon="🔥", layout="wide")


# ---------------------------------------------------------------------
# 2. 디자인
# ---------------------------------------------------------------------

# 색은 모두 어두운 배경에서 대비 4.5 이상이 나오도록 고른 값임
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Gothic+A1:wght@400;500;700;900&family=IBM+Plex+Mono:wght@500;600&display=swap');

:root {
    --bg:        #0F1115;
    --surface:   #191C22;
    --surface-2: #21252D;
    --line:      #2E333D;
    --ink:       #F4F2ED;
    --ink-2:     #C3C9D4;
    --ink-3:     #98A0AE;
    --flame:     #FF8340;
    --mint:      #6FE0C6;
}

.stApp { background: var(--bg); }

html, body, [class*="css"], .stMarkdown, p, span, label, div {
    font-family: 'Gothic A1', -apple-system, sans-serif;
}
.stApp, .stMarkdown p, .stMarkdown li { color: var(--ink); }

label, .stSelectbox label, .stNumberInput label, .stTextInput label,
[data-testid="stWidgetLabel"] p {
    color: var(--ink-2) !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
    color: var(--ink-3) !important;
    font-size: 0.85rem !important;
}

section[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--line);
}
section[data-testid="stSidebar"] .stMarkdown p { color: var(--ink-2); }

.hood {
    font-family: 'Black Han Sans', sans-serif;
    font-size: clamp(2rem, 4vw, 2.9rem);
    line-height: 1.05;
    letter-spacing: -0.02em;
    color: var(--ink);
    margin: 0;
}
.hood span { color: var(--flame); }
.hood-sub { color: var(--ink-3); font-size: 0.95rem; margin: 6px 0 28px 0; }

.burner {
    background: var(--surface);
    border: 1px solid var(--line);
    border-left: 5px solid var(--flame);
    border-radius: 6px;
    padding: 26px 28px 22px 28px;
    margin-bottom: 18px;
}
.bar { display: flex; gap: 4px; margin-bottom: 18px; }
.bar i { flex: 1; height: 3px; border-radius: 2px; background: var(--line); }
.bar i.on { background: var(--flame); }
.bar i.past { background: #7A4526; }

.burner-tag {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    letter-spacing: 0.16em;
    color: var(--flame);
    margin-bottom: 10px;
}
.burner-body {
    font-size: clamp(1.3rem, 2.4vw, 1.7rem);
    font-weight: 700;
    line-height: 1.45;
    color: var(--ink);
    word-break: keep-all;
}
.burner-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.95rem;
    color: var(--mint);
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid var(--line);
}
.burner-empty {
    background: var(--surface);
    border: 1px dashed var(--line);
    border-radius: 6px;
    padding: 40px 28px;
    text-align: center;
    color: var(--ink-2);
    line-height: 1.8;
}
.burner-empty b { color: var(--flame); font-weight: 700; }

/* ---------- 마이크 ---------- */
/* 젖은 손으로 한 번에 누를 수 있도록 크게 키움 */
[data-testid="stAudioInput"] {
    background: var(--surface);
    border: 1px solid var(--line);
    border-left: 5px solid var(--flame);
    border-radius: 6px;
    padding: 16px 18px;
    margin-bottom: 6px;
}

/* 안쪽 녹음 버튼을 큼직하게 */
[data-testid="stAudioInput"] button {
    min-width: 56px !important;
    min-height: 56px !important;
    border-radius: 50% !important;
    background: var(--flame) !important;
    border: none !important;
    color: #1A0E06 !important;
}
[data-testid="stAudioInput"] button:hover {
    background: #FF9459 !important;
}

/* 버튼 안의 그림도 함께 키움 */
[data-testid="stAudioInput"] button svg {
    width: 26px !important;
    height: 26px !important;
}

/* 소리 파형이 보이는 자리를 넓힘 */
[data-testid="stAudioInput"] > div {
    min-height: 60px;
}

/* 마이크 위에 붙는 안내 문구 */
.mic-cue {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 10px;
}
.mic-cue span {
    font-size: 1.5rem;
    line-height: 1;
}

/* 요소 사이에 숨 쉴 틈을 주는 빈 칸 */
.gap { height: 10px; }

.timer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-left: 4px solid var(--mint);
    border-radius: 5px;
    padding: 12px 16px;
    margin-bottom: 8px;
}
.timer.done {
    border-left-color: var(--flame);
    border-color: #4A2E1C;
    background: #241812;
}
.timer-name {
    color: var(--ink-2);
    font-size: 0.95rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.timer-left {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.6rem;
    font-weight: 600;
    color: var(--mint);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
}
.timer.done .timer-left { color: var(--flame); }

.rail {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.75rem;
    letter-spacing: 0.18em;
    color: var(--ink-3);
    margin: 26px 0 12px 0;
}
.rail::after { content: ""; flex: 1; height: 1px; background: var(--line); }

.scale-out {
    background: var(--surface-2);
    border: 1px solid var(--line);
    border-radius: 5px;
    padding: 18px 20px;
    margin-top: 6px;
}
.scale-big {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.9rem;
    font-weight: 600;
    color: var(--mint);
    font-variant-numeric: tabular-nums;
}
.scale-sub { color: var(--ink-3); font-size: 0.88rem; margin-top: 6px; }

.step-line {
    display: flex;
    gap: 12px;
    color: var(--ink-2);
    font-size: 0.95rem;
    padding: 9px 0;
    border-bottom: 1px solid var(--line);
    word-break: keep-all;
}
.step-line em {
    font-family: 'IBM Plex Mono', monospace;
    font-style: normal;
    color: var(--ink-3);
    flex-shrink: 0;
}
.step-line.now { color: var(--ink); font-weight: 700; }
.step-line.now em { color: var(--flame); }

.stButton > button {
    background: var(--surface-2);
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 5px;
    font-weight: 700;
    font-size: 0.92rem;
    min-height: 46px;
    transition: border-color .12s ease, color .12s ease;
}
.stButton > button:hover { border-color: var(--flame); color: var(--flame); }
.stButton > button:focus-visible {
    outline: 2px solid var(--flame);
    outline-offset: 2px;
}
.stButton > button:disabled {
    color: var(--ink-3);
    border-color: var(--line);
    opacity: .45;
}
.stForm .stButton > button {
    background: var(--flame);
    border-color: var(--flame);
    color: #1A0E06;
}
.stForm .stButton > button:hover {
    background: #FF9459;
    border-color: #FF9459;
    color: #1A0E06;
}

.stTextInput input, .stNumberInput input {
    background: var(--surface-2) !important;
    color: var(--ink) !important;
    border: 1px solid var(--line) !important;
    border-radius: 5px !important;
    min-height: 44px;
}
.stTextInput input::placeholder { color: var(--ink-3) !important; }

[data-testid="stExpander"] {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 6px;
}
[data-testid="stExpander"] summary { color: var(--ink-2) !important; }

[data-testid="stChatMessage"] {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 6px;
}
[data-testid="stChatMessage"] p { color: var(--ink); }

hr { border-color: var(--line) !important; }

@media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
}
</style>
"""

# 준비한 스타일을 화면에 적용함
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------
# 3. 기억 공간 준비
# ---------------------------------------------------------------------

# 화면이 새로 그려져도 유지되어야 하는 값들을 미리 만들어 둠
for key, value in {
    "history": [],        # 화면에 보여줄 대화 기록
    "turns": [],          # 모델에게 보낼 글자만 담은 대화 기록
    "last_audio": None,   # 이미 처리한 녹음의 고유 번호
    "dish": "",           # 지금 만들고 있는 요리 이름
    "steps": [],          # 요리 단계 목록
    "ingredients": [],    # 재료와 분량 목록
    "cursor": 0,          # 지금 몇 번째 단계인지
    "step_audio": None,   # 현재 단계를 읽어주는 음성
    "play_next": False,   # 새 답변이 도착했을 때만 자동 재생하기 위한 표시
    "step_play": False,   # 단계가 바뀌었을 때만 자동 재생하기 위한 표시
    "timers": [],         # 돌아가고 있는 타이머 목록
    "timer_seq": 0,       # 타이머마다 번호를 붙이기 위한 값
}.items():
    if key not in st.session_state:
        st.session_state[key] = value

# 저장해 둔 레시피는 파일에서 한 번만 읽어옴
if "book" not in st.session_state:
    st.session_state.book = None   # 함수 정의 뒤에 실제로 채움


# ---------------------------------------------------------------------
# 4. 공통 기능
# ---------------------------------------------------------------------

# @st.cache_resource 는 같은 키에 대해 클라이언트를 한 번만 만들어 재사용함
@st.cache_resource
def get_client(api_key):
    """사용자가 입력한 키로 Gemini 클라이언트를 만들어 돌려줌"""
    return genai.Client(api_key=api_key)


def base_config():
    """모델에게 넘길 기본 설정을 만들어 돌려줌"""

    # 생각 깊이를 낮춘 설정을 먼저 시도함
    try:
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=MAX_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING),
        )

    # 모델이 이 설정을 지원하지 않으면 해당 옵션 없이 만듦
    except Exception:
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=MAX_TOKENS,
        )


def voice_config():
    """음성 질문에 쓸 설정을 만들어 돌려줌"""

    # 받아쓴 질문과 답변을 두 칸으로 나눠 받도록 형식을 강제함
    # 글로 형식을 부탁하면 모델이 지키지 않을 때가 있어 아예 틀을 지정함
    schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "question": types.Schema(
                type=types.Type.STRING,
                description="들린 말을 그대로 받아쓴 문장",
            ),
            "answer": types.Schema(
                type=types.Type.STRING,
                description="그 질문에 대한 답. 질문 내용을 되풀이하지 않는다.",
            ),
        },
        required=["question", "answer"],
    )

    # 형식을 지정한 설정을 먼저 시도함
    try:
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=MAX_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_level=THINKING),
            response_mime_type="application/json",
            response_schema=schema,
        )

    # 모델이 이 방식을 지원하지 않으면 형식 지정 없이 만듦
    except Exception:
        return base_config()


def parse_voice(raw):
    """음성 응답에서 받아쓴 질문과 답변을 갈라 돌려줌"""

    # 첫째, 정해진 형식으로 온 경우
    try:
        clean = re.sub(r"^```(?:json)?|```$", "", raw,
                       flags=re.MULTILINE).strip()
        data = json.loads(clean)
        q = str(data.get("question", "")).strip()
        a = str(data.get("answer", "")).strip()
        if q and a:
            return q, a
    except Exception:
        pass

    # 둘째, 질문과 답변을 글자로 표시해 온 경우
    parts = re.split(r"답변\s*[:：]", raw, maxsplit=1)
    if len(parts) == 2:
        q = re.sub(r"^\s*질문\s*[:：]\s*", "", parts[0]).strip()
        a = parts[1].strip()
        if q and a:
            return q, a

    # 셋째, 질문을 되풀이한 뒤 답한 경우
    # 첫 물음표까지를 질문으로 보고 나머지를 답변으로 씀
    m = re.match(r"\s*(.{2,60}?\?)\s*(.+)", raw, flags=re.S)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # 넷째, 어느 것도 아니면 전체를 답변으로 둠
    return "말로 물어봄", raw.strip()


# 레시피북을 저장할 파일 위치
# app.py 와 같은 폴더에 만들어짐
BOOK_FILE = Path("recipes.json")


def load_book():
    """저장해 둔 레시피 목록을 읽어 돌려줌"""

    # 파일이 없거나 내용이 깨졌으면 빈 목록으로 시작함
    try:
        if BOOK_FILE.exists():
            data = json.loads(BOOK_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def save_book(book):
    """레시피 목록을 파일로 저장함"""

    # 배포 환경에서는 파일 쓰기가 막힐 수 있으므로 실패해도 앱은 계속 돌아감
    try:
        BOOK_FILE.write_text(
            json.dumps(book, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True
    except Exception:
        return False


def add_to_book(dish, steps, servings, source, items=None):
    """지금 보고 있는 레시피를 레시피북에 넣음"""

    # 저장할 내용을 한 덩어리로 만듦
    st.session_state.book.append({
        "id": int(time.time() * 1000),          # 겹치지 않는 번호
        "dish": dish,
        "servings": servings,
        "source": source,                        # 직접 입력인지 영상인지
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ingredients": items or [],
        "steps": steps,
    })

    # 파일로도 남김
    return save_book(st.session_state.book)


def to_speech(text):
    """글자를 음성 데이터로 바꿔 돌려줌"""

    # 읽을 내용이 없으면 아무것도 만들지 않음
    if not text:
        return None

    # 한글이 하나라도 있으면 한국어, 없으면 영어로 판단함
    lang = "ko" if re.search(r"[가-힣]", text) else "en"

    # 텍스트를 구글 TTS로 보내 음성 데이터를 만듦
    tts = gTTS(text=text, lang=lang)

    # 파일로 저장하지 않고 메모리 공간에 담음
    buffer = io.BytesIO()
    tts.write_to_fp(buffer)

    # 읽기 위치를 처음으로 되돌린 뒤 데이터를 돌려줌
    buffer.seek(0)
    return buffer.read()


def esc(text):
    """화면에 안전하게 넣기 위해 특수문자를 바꿔줌"""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_contents(audio_bytes=None, text=""):
    """모델에게 보낼 내용을 조립해 돌려줌"""

    # 보낼 내용을 담을 목록을 준비함
    contents = []

    # 최근 대화만 글자 형태로 함께 보냄
    # 옛 대화를 다 보내면 요청이 무거워지고 결국 실패하기 때문임
    for turn in st.session_state.turns[-KEEP_TURNS:]:
        contents.append(
            types.Content(
                role=turn["role"],
                parts=[types.Part.from_text(text=turn["text"])],
            )
        )

    # 이번에 보낼 내용을 담을 조각 목록을 준비함
    parts = []

    # 녹음이 있으면 이번 요청에만 넣음
    # 오디오는 대화 기록에 남기지 않으므로 다음 요청부터는 빠짐
    if audio_bytes:
        parts.append(
            types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
        )

    # 지시문이나 질문 글자를 넣음
    parts.append(types.Part.from_text(text=text))

    # 이번 차례를 목록 끝에 붙임
    contents.append(types.Content(role="user", parts=parts))

    return contents


def remember(question, answer):
    """이번 대화를 글자 형태로만 기억해 둠"""

    # 질문과 답변을 각각 저장함
    st.session_state.turns.append({"role": "user", "text": question})
    st.session_state.turns.append({"role": "model", "text": answer})

    # 기억이 너무 길어지지 않게 뒤에서부터 잘라 둠
    st.session_state.turns = st.session_state.turns[-(KEEP_TURNS * 2):]


# ---------------------------------------------------------------------
# 5. 타이머 기능
# ---------------------------------------------------------------------

def parse_seconds(text):
    """문장에서 시간을 읽어 초 단위로 바꿔 돌려줌"""

    # 시, 분, 초를 각각 찾아냄
    hour = re.search(r"(\d+)\s*시간", text)
    minute = re.search(r"(\d+)\s*분", text)
    second = re.search(r"(\d+)\s*초", text)

    # 찾은 값을 모두 초로 바꿔 더함
    total = 0
    if hour:
        total += int(hour.group(1)) * 3600
    if minute:
        total += int(minute.group(1)) * 60
    if second:
        total += int(second.group(1))

    return total


def is_timer_request(text):
    """이 말이 타이머를 걸어달라는 뜻인지 판단함"""

    # 타이머를 뜻하는 표현이 들어 있는지 확인함
    keywords = ["타이머", "알려줘", "알람", "맞춰", "세줘", "재줘", "뒤에"]
    has_keyword = any(k in text for k in keywords)

    # 표현도 있고 시간도 읽혔을 때만 타이머 요청으로 봄
    return has_keyword and parse_seconds(text) > 0


def dur_phrase(seconds):
    """걸린 시간을 말로 읽기 좋은 표현으로 바꿔 돌려줌"""

    # 정수로 맞춤
    seconds = int(seconds)

    # 시, 분, 초로 나눔
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60

    # 값이 있는 단위만 골라 이어 붙임
    parts = []
    if h:
        parts.append(f"{h}시간")
    if m:
        parts.append(f"{m}분")
    if s:
        parts.append(f"{s}초")

    # 전부 0이면 0초로 표시함
    return " ".join(parts) if parts else "0초"


def add_timer(name, seconds):
    """타이머를 하나 만들어 목록에 넣음"""

    # 타이머마다 번호를 하나씩 올려 붙임
    st.session_state.timer_seq += 1

    # 걸린 시간을 말로 읽을 표현으로 미리 바꿔둠
    phrase = dur_phrase(seconds)

    # 이름이 기본값이면 시간만 말하고, 이름이 있으면 함께 말함
    if name and name != "타이머":
        line = f"{name}, {phrase} 지났습니다."
    else:
        line = f"{phrase} 지났습니다."

    # 끝나는 시각을 미리 계산해 저장함
    # 매초 빼는 방식보다 정확하고, 화면이 멈춰도 시간이 흐름
    st.session_state.timers.append({
        "id": st.session_state.timer_seq,
        "name": name,
        "total": seconds,          # 원래 걸어둔 시간
        "end": time.time() + seconds,
        "rang": False,
        "audio": to_speech(line),  # 알림 음성을 미리 만들어 둠
    })


def fmt(seconds):
    """남은 초를 분과 초 모양으로 바꿔 돌려줌"""
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


# @st.fragment 는 이 부분만 1초마다 다시 그림
# 화면 전체를 새로 그리지 않으므로 입력하던 내용이 사라지지 않음
@st.fragment(run_every="1s")
def timer_panel():
    """돌아가는 타이머들을 표시하고 시간이 되면 알림"""

    # 타이머가 하나도 없으면 안내만 표시함
    if not st.session_state.timers:
        st.caption("걸어둔 타이머 없음")
        return

    # 지금 시각을 한 번만 읽어 모든 타이머에 같이 씀
    now = time.time()

    for t in list(st.session_state.timers):

        # 남은 시간을 계산하고 다 됐는지 확인함
        left = t["end"] - now
        done = left <= 0
        css = "timer done" if done else "timer"

        # 타이머 한 줄을 그림
        st.markdown(
            f'<div class="{css}">'
            f'<span class="timer-name">{esc(t["name"])}</span>'
            f'<span class="timer-left">{"완료" if done else fmt(left)}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

        # 시간이 됐는데 아직 안 울렸으면 소리를 냄
        if done and not t["rang"]:
            t["rang"] = True
            if t["audio"]:
                st.audio(t["audio"], format="audio/mp3", autoplay=True)

        # 돌아가는 중이면 중지, 다 됐으면 지우기 버튼을 보여줌
        # 어느 쪽이든 목록에서 빼는 동작은 같음
        label = "지우기" if done else "중지"
        if st.button(label, key=f"kill_{t['id']}", use_container_width=True):
            st.session_state.timers = [
                x for x in st.session_state.timers if x["id"] != t["id"]
            ]
            st.rerun(scope="fragment")


# ---------------------------------------------------------------------
# 6. 레시피 기능
# ---------------------------------------------------------------------

def is_youtube(url):
    """유튜브 주소가 맞는지 확인함"""

    # 두 가지 주소 형태를 모두 인정함
    return bool(re.match(r"https?://(www\.)?(youtube\.com|youtu\.be)/", url.strip()))


def recipe_schema():
    """레시피를 받을 틀을 만들어 돌려줌"""

    # 재료 한 줄의 모양을 정함
    # 분량을 따로 받아야 대충 뭉뚱그리지 않음
    item = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "name": types.Schema(
                type=types.Type.STRING, description="재료 이름"
            ),
            "amount": types.Schema(
                type=types.Type.STRING,
                description=(
                    "영상에서 말하거나 보여준 분량을 그대로. "
                    "예: 300g, 2큰술, 종이컵 1컵. "
                    "영상에 분량이 없으면 '영상에 없음'"
                ),
            ),
        },
        required=["name", "amount"],
    )

    # 한 단계의 모양을 정함
    step = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "do": types.Schema(
                type=types.Type.STRING,
                description=(
                    "그 단계에서 할 일. 넣는 재료가 있으면 분량까지 함께 쓴다. "
                    "예: 간장 2큰술과 설탕 1큰술을 넣고 볶는다"
                ),
            ),
            "meta": types.Schema(
                type=types.Type.STRING,
                description="불 세기와 시간을 짧게. 없으면 빈 문자열",
            ),
            "sec": types.Schema(
                type=types.Type.INTEGER,
                description="이 단계에 필요한 시간을 초로. 없으면 0",
            ),
            "at": types.Schema(
                type=types.Type.STRING,
                description=(
                    "이 단계가 영상에서 시작되는 시각을 MM:SS 형식으로. "
                    "영상이 아니면 빈 문자열"
                ),
            ),
        },
        required=["do", "meta", "sec", "at"],
    )

    # 요리 이름, 재료, 단계를 함께 받음
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "dish": types.Schema(
                type=types.Type.STRING, description="요리 이름"
            ),
            "ingredients": types.Schema(type=types.Type.ARRAY, items=item),
            "steps": types.Schema(type=types.Type.ARRAY, items=step),
        },
        required=["dish", "ingredients", "steps"],
    )


def make_recipe(client, model, dish="", servings=2, video_url=""):
    """요리 이름이나 유튜브 영상에서 조리 순서를 만들어 돌려줌"""

    # 모델에게 보낼 조각들을 담을 목록
    parts = []

    # 영상 주소가 있으면 영상을 먼저 넣음
    # Gemini는 유튜브 주소를 그대로 받아 화면과 소리를 함께 이해함
    if video_url:
        parts.append(
            types.Part(file_data=types.FileData(file_uri=video_url.strip()))
        )
        prompt = (
            "이 요리 영상을 처음부터 끝까지 보고 레시피를 옮겨 적어라.\n"
            "\n"
            "가장 중요한 규칙은 분량이다.\n"
            "영상에서 말이나 자막이나 화면 표시로 나온 숫자를 그대로 옮긴다.\n"
            "'적당히', '조금' 같은 표현으로 바꾸지 않는다.\n"
            "'2큰술', '300그램', '종이컵 반 컵' 처럼 영상에 나온 그대로 쓴다.\n"
            "영상이 분량을 말하지 않은 재료는 추측하지 말고 "
            "amount 를 '영상에 없음' 으로 둔다.\n"
            "일반적인 레시피 지식으로 빈칸을 채우지 않는다.\n"
            "\n"
            "ingredients 에는 영상에 나온 모든 재료를 빠짐없이 적는다.\n"
            "양념은 하나로 묶지 말고 간장, 설탕, 고춧가루처럼 따로 적는다.\n"
            "\n"
            "steps 의 do 에는 그 단계에서 넣는 재료와 분량을 함께 쓴다.\n"
            "at 에는 그 장면이 시작되는 영상 시각을 MM:SS 로 적는다.\n"
            "6단계에서 12단계로 나눈다."
        )

    # 영상이 없으면 요리 이름으로 만듦
    else:
        prompt = (
            f"{servings}인분 {dish} 레시피를 만들어라.\n"
            "dish 에는 요리 이름을 쓴다.\n"
            "ingredients 에는 필요한 재료를 분량과 함께 모두 적는다.\n"
            "분량은 그램이나 큰술처럼 셀 수 있는 단위로 쓴다.\n"
            "steps 의 do 에는 그 단계에서 넣는 재료와 분량을 함께 쓴다.\n"
            "at 은 빈 문자열로 둔다.\n"
            "재료 손질부터 완성까지 6단계에서 10단계로 나눈다.\n"
            "sec 에는 그 단계에 필요한 시간을 초로 쓰고, "
            "시간을 잴 필요가 없으면 0으로 둔다."
        )

    # 지시문을 뒤에 붙임
    parts.append(types.Part.from_text(text=prompt))

    # 정해진 틀로만 답하도록 지정함
    # 글로 부탁하는 것보다 형식이 훨씬 안정적임
    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            max_output_tokens=4000,
            response_mime_type="application/json",
            response_schema=recipe_schema(),
        ),
    )

    # 응답에서 텍스트를 꺼내고 코드 표시가 붙었으면 떼어냄
    raw = (response.text or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()

    # 글자를 파이썬 자료로 바꿈
    # 형식이 어긋나면 빈 결과를 돌려줘 앱이 멈추지 않게 함
    try:
        data = json.loads(raw)
        steps = [
            s for s in data.get("steps", [])
            if isinstance(s, dict) and s.get("do")
        ]
        items = [
            g for g in data.get("ingredients", [])
            if isinstance(g, dict) and g.get("name")
        ]
        return data.get("dish", dish).strip(), items, steps
    except Exception:
        return dish, [], []


def reset_all():
    """모든 기억을 비움"""
    for key in ["history", "turns", "steps", "timers", "ingredients"]:
        st.session_state[key] = []
    st.session_state.last_audio = None
    st.session_state.dish = ""
    st.session_state.cursor = 0
    st.session_state.step_audio = None


def speak_current_step():
    """현재 단계를 음성으로 만들어 저장함"""

    # 단계 목록이 없으면 아무것도 하지 않음
    if not st.session_state.steps:
        return

    # 현재 단계를 꺼내 읽을 문장을 만듦
    step = st.session_state.steps[st.session_state.cursor]
    line = step.get("do", "")
    if step.get("meta"):
        line = f"{line}. {step['meta']}"

    # 음성으로 바꿔 저장함. 이 작업은 Gemini를 쓰지 않아 한도와 무관함
    st.session_state.step_audio = to_speech(line)

    # 이번 화면에서 한 번만 자동 재생하도록 표시해 둠
    st.session_state.step_play = True


def context_line():
    """지금 무슨 요리의 몇 번째 단계인지 한 줄로 만들어 돌려줌"""

    # 진행 중인 요리가 없으면 빈 문자열을 돌려줌
    if not st.session_state.steps:
        return ""

    i = st.session_state.cursor
    step = st.session_state.steps[i]

    # 재료와 분량을 함께 알려주면 "이거 얼마나 넣어?" 에 정확히 답할 수 있음
    items = st.session_state.ingredients
    item_line = ""
    if items:
        joined = ", ".join(
            f'{g["name"]} {g.get("amount", "")}'.strip() for g in items[:20]
        )
        item_line = f"[재료] {joined}. "

    return (
        f"[상황] 지금 {st.session_state.dish}를 만들고 있고, "
        f"{i + 1}번째 단계인 '{step['do']}'를 하는 중이다. "
        + item_line
        + "재료 분량을 물으면 위 재료 목록의 값을 그대로 알려준다. "
        "목록에 없으면 모른다고 말한다. "
    )


# ---------------------------------------------------------------------
# 7. 사이드바
# ---------------------------------------------------------------------

with st.sidebar:

    # 아직 안 읽었으면 파일에서 레시피북을 불러옴
    if st.session_state.book is None:
        st.session_state.book = load_book()

    # 키 입력 영역
    st.markdown('<div class="rail" style="margin-top:0">API 키</div>',
                unsafe_allow_html=True)
    api_key = st.text_input(
        "Gemini API 키",
        type="password",
        placeholder="키를 붙여넣으세요",
        label_visibility="collapsed",
    )
    st.caption("aistudio.google.com/apikey 에서 무료 발급")

    # 모델 선택 영역
    st.markdown('<div class="rail">답변 속도</div>', unsafe_allow_html=True)
    choice = st.radio("모델", list(MODELS.keys()), label_visibility="collapsed")
    model = MODELS[choice]

    # 오늘 만들 요리를 입력받는 영역
    st.markdown('<div class="rail">오늘 만들 요리</div>', unsafe_allow_html=True)
    dish_input = st.text_input(
        "요리 이름", placeholder="예: 제육볶음", label_visibility="collapsed"
    )
    servings = st.number_input("몇 인분", min_value=1, max_value=10, value=2)
    start = st.button("조리 순서 받기", use_container_width=True)

    # 저장해 둔 레시피를 꺼내 쓰는 영역
    book = st.session_state.book
    st.markdown(f'<div class="rail">레시피북 {len(book)}</div>',
                unsafe_allow_html=True)

    # 저장된 게 없으면 안내만 표시함
    if not book:
        st.caption("아직 저장한 레시피가 없습니다")
        load_pick = None
    else:
        # 고르기 쉽도록 요리 이름과 저장 날짜를 함께 보여줌
        labels = {
            f'{r["dish"]}  ·  {r["saved_at"][5:]}': r["id"] for r in book
        }
        pick = st.selectbox("저장된 레시피", list(labels.keys()),
                            label_visibility="collapsed")
        load_pick = labels[pick]

        # 불러오기와 삭제 버튼을 나란히 둠
        b1, b2 = st.columns(2)
        do_load = b1.button("불러오기", use_container_width=True)
        do_drop = b2.button("삭제", use_container_width=True)

    # 레시피북 전체를 파일로 내려받고 올리는 영역
    # 배포 환경에서는 서버에 파일이 남지 않으므로 이 방법으로 보관함
    with st.expander("레시피북 백업"):

        # 지금 목록을 파일로 내려받음
        st.download_button(
            "내려받기",
            data=json.dumps(book, ensure_ascii=False, indent=2),
            file_name="recipes.json",
            mime="application/json",
            use_container_width=True,
            disabled=not book,
        )

        # 예전에 내려받은 파일을 다시 올려 되살림
        up = st.file_uploader("불러오기", type="json",
                              label_visibility="collapsed")
        if up is not None:
            try:
                data = json.loads(up.read().decode("utf-8"))
                if isinstance(data, list):
                    st.session_state.book = data
                    save_book(data)
                    st.success(f"{len(data)}개를 되살렸습니다")
            except Exception:
                st.error("파일을 읽지 못했습니다")

    st.divider()

    # 지금까지 몇 번 물었는지 보여줌. 무료 한도를 가늠하는 데 도움이 됨
    asked = len(st.session_state.turns) // 2
    st.caption(f"이번 세션 질문 {asked}회")

    # 처음부터 다시 시작하는 버튼
    if st.button("전부 지우기", use_container_width=True):
        reset_all()
        st.rerun()


# ---------------------------------------------------------------------
# 8. 상단 제목
# ---------------------------------------------------------------------

st.markdown(
    '<div class="hood"><span>AI모</span>네 밥상</div>'
    '<div class="hood-sub">물어보면 알려주는 AI 요리비서</div>',
    unsafe_allow_html=True,
)


# 키를 입력하지 않았으면 안내만 하고 아래 코드를 멈춤
if not api_key:
    st.markdown(
        '<div class="burner-empty">'
        '왼쪽에 <b>API 키</b>를 넣으면 시작합니다<br>'
        'aistudio.google.com/apikey 에서 무료로 받을 수 있습니다'
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()


# 입력받은 키로 클라이언트를 준비함
try:
    client = get_client(api_key)
except Exception as e:
    st.error(f"키를 확인해 주세요. {e}")
    st.stop()


# 유튜브 링크로 레시피를 받는 줄
# 요리의 시작점이므로 제목 바로 아래에 둠
st.markdown('<div class="rail" style="margin-top:0">영상에서 가져오기</div>',
            unsafe_allow_html=True)

# 입력칸과 버튼을 한 줄에 나란히 놓음
# 폼으로 감싸면 엔터만 쳐도 실행됨
with st.form("video_form"):
    v1, v2 = st.columns([3, 1])
    video_url = v1.text_input(
        "유튜브 링크",
        placeholder="유튜브 링크를 붙여넣으세요",
        label_visibility="collapsed",
    )
    start_video = v2.form_submit_button("순서 받기", use_container_width=True)

st.caption("공개 영상만 됩니다. 10분 이내 영상을 권합니다")


# 조리 순서를 받아 화면에 적용하는 함수
def apply_recipe(dish_name, steps, items=None):
    """받아온 순서를 저장하고 첫 단계를 읽어줌"""
    st.session_state.dish = dish_name
    st.session_state.steps = steps
    st.session_state.ingredients = items or []
    st.session_state.cursor = 0
    st.session_state.history = []
    st.session_state.turns = []
    speak_current_step()
    st.rerun()


# 레시피북에서 불러오기를 눌렀으면 그 레시피를 화면에 올림
if st.session_state.book and load_pick and do_load:
    for r in st.session_state.book:
        if r["id"] == load_pick:
            apply_recipe(r["dish"], r["steps"], r.get("ingredients", []))

# 삭제를 눌렀으면 목록에서 빼고 파일에도 반영함
if st.session_state.book and load_pick and do_drop:
    st.session_state.book = [
        r for r in st.session_state.book if r["id"] != load_pick
    ]
    save_book(st.session_state.book)
    st.rerun()


# 요리 이름으로 순서를 받는 경우
if start and dish_input.strip():

    with st.spinner("순서를 정리하는 중..."):
        try:
            name, items, steps = make_recipe(
                client, model, dish=dish_input.strip(), servings=servings
            )
        except Exception as e:
            name, items, steps = "", [], []
            st.error(f"순서를 받지 못했습니다. {e}")

    # 단계를 받아왔으면 화면에 적용함
    if steps:
        apply_recipe(name or dish_input.strip(), steps, items)


# 유튜브 영상에서 순서를 받는 경우
if start_video:

    # 주소 형태가 아니면 안내만 하고 넘어감
    if not is_youtube(video_url):
        st.error("유튜브 링크를 넣어주세요.")

    else:
        # 영상은 글자보다 오래 걸리므로 안내를 다르게 씀
        with st.spinner("영상을 보는 중... 길면 1분쯤 걸립니다"):
            try:
                name, items, steps = make_recipe(
                    client, model, video_url=video_url, servings=servings
                )
            except Exception as e:
                name, items, steps = "", [], []
                st.error(f"영상을 읽지 못했습니다. 비공개 영상이거나 너무 길 수 있습니다. {e}")

        # 단계를 받아왔으면 화면에 적용함
        if steps:
            apply_recipe(name or "영상 레시피", steps, items)


# ---------------------------------------------------------------------
# 9. 화면 본문
# ---------------------------------------------------------------------

# 왼쪽은 지금 할 일, 오른쪽은 타이머와 대화
left, right = st.columns([1.3, 1], gap="large")


with left:

    # 조리 순서가 있으면 현재 단계를 크게 보여줌
    if st.session_state.steps:

        i = st.session_state.cursor
        total = len(st.session_state.steps)
        step = st.session_state.steps[i]

        # 진행 막대를 만듦. 지난 단계, 현재 단계, 남은 단계를 색으로 구분함
        bar = "".join(
            f'<i class="{"past" if n < i else "on" if n == i else ""}"></i>'
            for n in range(total)
        )

        # 부가 정보가 있을 때만 아랫줄을 표시함
        meta = step.get("meta", "")
        meta_html = f'<div class="burner-meta">{esc(meta)}</div>' if meta else ""

        # 영상에서 가져온 경우 그 장면의 시각을 함께 보여줌
        at = step.get("at", "")
        at_html = f' · {esc(at)}' if at else ""

        # 지금 할 일을 패널로 표시함
        st.markdown(
            f'<div class="burner">'
            f'<div class="bar">{bar}</div>'
            f'<div class="burner-tag">{esc(st.session_state.dish)} · '
            f'{i + 1:02d} / {total:02d}{at_html}</div>'
            f'<div class="burner-body">{esc(step["do"])}</div>'
            f"{meta_html}"
            f"</div>",
            unsafe_allow_html=True,
        )

        # 현재 단계를 읽어주는 음성을 재생함
        # 단계가 막 바뀐 경우에만 자동으로 재생함
        if st.session_state.step_audio:
            st.audio(st.session_state.step_audio, format="audio/mp3",
                     autoplay=st.session_state.step_play)
            st.session_state.step_play = False

        # 이 단계에 시간이 정해져 있으면 타이머를 바로 걸 수 있게 함
        sec = int(step.get("sec") or 0)
        if sec > 0:
            if st.button(f"이 단계 타이머 걸기  {fmt(sec)}",
                         use_container_width=True):
                add_timer(step["do"][:14], sec)
                st.rerun()

        # 패널과 버튼이 붙어 보이지 않도록 빈 칸을 둠
        st.markdown('<div class="gap"></div>', unsafe_allow_html=True)

        # 단계를 앞뒤로 옮기는 버튼
        back, fwd = st.columns(2)
        with back:
            if st.button("← 이전", use_container_width=True, disabled=(i == 0)):
                st.session_state.cursor -= 1
                speak_current_step()
                st.rerun()
        with fwd:
            if st.button("다음 →", use_container_width=True,
                         disabled=(i >= total - 1)):
                st.session_state.cursor += 1
                speak_current_step()
                st.rerun()

        # 재료와 분량을 접어서 보여줌
        # 장 볼 때와 계량할 때 여기만 보면 됨
        if st.session_state.ingredients:
            with st.expander(f"재료 {len(st.session_state.ingredients)}가지"):
                for g in st.session_state.ingredients:

                    # 영상에 분량이 없던 재료는 흐리게 표시해 구분함
                    amount = g.get("amount", "")
                    missing = "영상에 없" in amount
                    color = "#98A0AE" if missing else "#6FE0C6"

                    st.markdown(
                        f'<div class="step-line">'
                        f'<span style="flex:1">{esc(g["name"])}</span>'
                        f'<span style="color:{color};'
                        f'font-family:IBM Plex Mono,monospace">'
                        f'{esc(amount)}</span></div>',
                        unsafe_allow_html=True,
                    )

        # 전체 순서를 접어서 보여줌
        with st.expander("전체 순서 보기"):
            for n, s in enumerate(st.session_state.steps):
                now = " now" if n == i else ""
                st.markdown(
                    f'<div class="step-line{now}">'
                    f'<em>{n + 1:02d}</em><span>{esc(s["do"])}</span></div>',
                    unsafe_allow_html=True,
                )

        # 지금 보고 있는 레시피를 레시피북에 저장하는 버튼
        # 이미 저장된 요리면 버튼 대신 안내를 보여줌
        saved = any(
            r["dish"] == st.session_state.dish
            and len(r["steps"]) == len(st.session_state.steps)
            for r in st.session_state.book
        )

        if saved:
            st.caption("이 레시피는 레시피북에 있습니다")
        else:
            if st.button("레시피북에 저장", use_container_width=True):
                ok = add_to_book(
                    st.session_state.dish,
                    st.session_state.steps,
                    servings,
                    "영상" if video_url.strip() else "직접",
                    st.session_state.ingredients,
                )
                # 파일로 못 남겼으면 화면에만 남는다고 알려줌
                if not ok:
                    st.warning("파일로 저장하지 못했습니다. 백업으로 내려받으세요")
                st.rerun()

    # 아직 요리를 고르지 않았으면 안내를 표시함
    else:
        st.markdown(
            '<div class="burner-empty">'
            '왼쪽에 요리 이름을 적고 <b>조리 순서 받기</b>를 누르세요<br>'
            '순서 없이 바로 물어봐도 됩니다'
            "</div>",
            unsafe_allow_html=True,
        )

    # 질문 영역
    st.markdown('<div class="rail">물어보기</div>', unsafe_allow_html=True)

    # 마이크가 어디 있는지 한눈에 보이도록 안내를 크게 붙임
    st.markdown(
        '<div class="mic-cue"><span>🎤</span>동그란 버튼을 누르고 물어보세요</div>',
        unsafe_allow_html=True,
    )

    # 마이크 녹음 버튼
    audio = st.audio_input("눌러서 말하기", label_visibility="collapsed")
    st.caption('"3분 뒤에 알려줘" 처럼 말하면 타이머가 걸립니다')

    # 자주 묻는 질문을 버튼으로 만들어 둠
    quick = None
    q1, q2, q3 = st.columns(3)
    with q1:
        if st.button("다 익었나", use_container_width=True):
            quick = "지금 상태가 다 익은 건지 어떻게 확인해?"
    with q2:
        if st.button("간이 안 맞아", use_container_width=True):
            quick = "간이 안 맞는데 지금 뭘 더 넣어야 해?"
    with q3:
        if st.button("재료가 없어", use_container_width=True):
            quick = "이번 단계 재료가 없는데 뭘로 대신할 수 있어?"

    # 계량 환산 영역
    # 표만으로 계산하므로 즉시 답이 나오고 API 한도도 안 씀
    with st.expander("계량 환산"):
        c1, c2, c3 = st.columns([1.2, 1, 0.8])
        ing = c1.selectbox("재료", list(DENSITY.keys()))
        unit = c2.selectbox("도구", list(UNITS.keys()))
        qty = c3.number_input("수량", 0.5, 30.0, 1.0, 0.5)

        # 부피와 무게를 계산함
        ml = UNITS[unit] * qty
        gram = ml * DENSITY[ing]
        cups = ml / UNITS["종이컵"]

        st.markdown(
            f'<div class="scale-out">'
            f'<div class="scale-big">{gram:.0f} g<span style="color:#98A0AE">'
            f' / {ml:.0f} ml</span></div>'
            f'<div class="scale-sub">{esc(ing)} {qty:g}{unit} 기준 · '
            f'종이컵으로 약 {cups:.2f}컵</div>'
            f"</div>",
            unsafe_allow_html=True,
        )


with right:

    # 타이머 영역
    st.markdown('<div class="rail" style="margin-top:0">타이머</div>',
                unsafe_allow_html=True)

    # 타이머를 직접 추가하는 칸
    with st.form("timer_form", clear_on_submit=True):
        t1, t2 = st.columns([1.5, 1])
        t_name = t1.text_input("무엇", placeholder="예: 면 삶기",
                               label_visibility="collapsed")
        t_min = t2.number_input("분", 0.0, 180.0, 3.0, 0.5,
                                label_visibility="collapsed")
        t_add = st.form_submit_button("타이머 시작", use_container_width=True)

    # 버튼을 눌렀고 시간이 0보다 크면 타이머를 만듦
    if t_add and t_min > 0:
        add_timer(t_name.strip() or "타이머", int(t_min * 60))
        st.rerun()

    # 1초마다 갱신되는 타이머 목록을 그림
    timer_panel()

    # 대화 영역
    st.markdown('<div class="rail">주고받은 말</div>', unsafe_allow_html=True)

    # 대화가 없으면 안내 문구만 표시함
    if not st.session_state.history:
        st.caption("아직 주고받은 말 없음")

    # 질문과 답변을 한 쌍으로 묶음
    # 쌍 단위로 뒤집어야 최근 대화가 위로 오면서도
    # 쌍 안에서는 질문이 답변보다 위에 남음
    pairs = [
        st.session_state.history[n:n + 2]
        for n in range(0, len(st.session_state.history), 2)
    ]

    # 가장 최근 쌍인지 표시하는 값
    newest = True

    for pair in reversed(pairs):

        # 쌍 안에서는 저장된 순서 그대로 그림 (질문 → 답변)
        for role, text, speech in pair:
            with st.chat_message(role):
                st.write(text)

                # 방금 도착한 답변만 자동으로 재생함
                # 화면이 다시 그려질 때마다 옛 답변이 울리는 것을 막기 위함임
                if speech:
                    st.audio(
                        speech,
                        format="audio/mp3",
                        autoplay=(newest and st.session_state.play_next),
                    )

        # 첫 쌍을 그린 뒤로는 최신이 아님
        newest = False

    # 자동 재생 표시를 꺼서 다음 화면부터는 울리지 않게 함
    st.session_state.play_next = False


# ---------------------------------------------------------------------
# 10. 실행 흐름
# ---------------------------------------------------------------------

# 이번 차례에 보낼 내용을 담을 변수를 미리 비워둠
audio_bytes = None   # 이번에만 보낼 녹음 데이터
ask_text = None      # 모델에게 보낼 글자
shown = None         # 화면에 표시할 질문 내용


# 녹음된 음성이 있으면 그것을 우선 처리함
if audio is not None:

    # 녹음 데이터를 읽고 고유 번호를 만듦
    raw_audio = audio.read()
    fingerprint = hash(raw_audio)

    # 아직 처리하지 않은 새 녹음일 때만 진행함
    # 이 조건이 없으면 같은 녹음을 계속 다시 답변하는 무한 반복이 생김
    if fingerprint != st.session_state.last_audio:

        # 이 녹음을 처리했다고 먼저 기록해 둠
        st.session_state.last_audio = fingerprint

        # 이번 요청에만 녹음을 실어 보냄
        audio_bytes = raw_audio

        # 받아쓰기와 답변을 한 번에 받아 호출 횟수를 절반으로 줄임
        # 형식은 아래 voice_config 가 강제하므로 여기서는 할 일만 알려줌
        ask_text = (
            context_line()
            + "이 오디오에 담긴 말을 듣고 답하라. "
            "question 에는 들린 말을 그대로 받아쓴다. "
            "answer 에는 그 질문에 대한 답만 쓴다. "
            "answer 에 질문 내용을 다시 적지 않는다."
        )

# 빠른 질문 버튼을 눌렀으면 그 문장을 사용함
elif quick:
    ask_text = context_line() + quick
    shown = quick


# 보낼 내용이 준비되었으면 답변 과정을 진행함
if ask_text is not None:

    with st.spinner("듣는 중..."):

        # 통신 오류나 한도 초과가 나도 앱이 죽지 않도록 감쌈
        try:
            # 음성 질문이면 형식을 강제하는 설정을 씀
            config = voice_config() if audio_bytes else base_config()

            # 최근 대화와 이번 질문을 합쳐 요청을 만듦
            response = client.models.generate_content(
                model=model,
                contents=build_contents(audio_bytes, ask_text),
                config=config,
            )
            raw = (response.text or "").strip()

            # 음성으로 물은 경우에는 응답 안에 질문과 답변이 함께 들어 있음
            if shown is None:
                shown, answer = parse_voice(raw)

            # 버튼이나 글자로 물은 경우에는 응답 전체가 곧 답변임
            else:
                answer = raw

            # 받아쓴 말이 타이머 요청이었으면 타이머도 함께 걸어줌
            if shown and is_timer_request(shown):
                add_timer(shown[:14], parse_seconds(shown))

            # 답변을 음성으로 바꿈
            speech = to_speech(answer)

            # 이번 대화를 글자 형태로만 기억해 둠
            # 오디오는 저장하지 않으므로 다음 요청이 무거워지지 않음
            remember(shown, answer)

        except Exception as e:
            # 오류 내용을 답변 자리에 표시하고 음성은 만들지 않음
            shown = shown or "말로 물어봄"
            answer = f"답을 받지 못했습니다. {e}"
            speech = None

    # 질문과 답변을 화면 기록에 추가함
    st.session_state.history.append(("user", shown, None))
    st.session_state.history.append(("assistant", answer, speech))

    # 오래된 답변의 음성 데이터를 지움
    # 플레이어와 음성이 계속 쌓이면 화면이 무거워지기 때문임
    kept = 0
    for n in range(len(st.session_state.history) - 1, -1, -1):
        role, text, sp = st.session_state.history[n]
        if sp:
            kept += 1
            if kept > KEEP_AUDIO:
                st.session_state.history[n] = (role, text, None)

    # 답변 음성이 나오도록 단계 음성은 꺼둠
    # 두 개가 동시에 재생되면 알아들을 수 없기 때문임
    st.session_state.step_audio = None
    st.session_state.step_play = False

    # 다음 화면에서 이 답변을 자동으로 재생하도록 표시함
    st.session_state.play_next = True

    # 화면을 새로 그려 방금 추가한 대화를 표시함
    st.rerun()