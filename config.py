"""문항 매핑, 지표 정의 등 앱 전역 설정.

설문 양식이나 지표 구성이 바뀌면 이 파일만 수정한다.
"""
from dataclasses import dataclass

# Excel에서 응답이 들어있는 시트명 (없으면 첫 번째 시트 사용)
RESPONSE_SHEET = "all responses"

# 과정명 컬럼이 없거나 비어 있을 때 쓰는 값
COURSE_PLACEHOLDER = "(과정명 미기재)"

# '답변 적격성' 컬럼에서 집계 대상으로 남길 값
ELIGIBLE_VALUE = "적격"


@dataclass(frozen=True)
class Question:
    label: str
    kind: str  # "id" | "meta" | "score" | "text"
    codes: tuple[str, ...] = ()  # 설문 시스템 문항 코드 (1순위 매핑)
    keywords: tuple[str, ...] = ()  # 문항 원문 부분 일치 (2순위, 공백 무시)
    exact: tuple[str, ...] = ()  # 문항 원문 완전 일치 (2순위, 공백 무시)
    exclude: tuple[str, ...] = ()  # 원문에 이 단어가 있으면 키워드가 맞아도 매핑하지 않음
    scale: tuple[int, int] | None = None  # 점수 문항의 (최소, 최대)
    multi: bool = False  # 여러 컬럼이 같은 문항인 경우


# 키워드 매핑은 이 순서대로 진행된다.
# 같은 컬럼은 한 문항에만 배정되므로, 키워드가 겹치는 문항은 더 구체적인 쪽을 앞에 둔다.
# (예: 강의자료 문항에도 '업무에 도움'이 들어 있으므로 material을 job_help보다 앞에 둔다)
QUESTIONS: dict[str, Question] = {
    # 식별 정보: 로드 직후 삭제 (PRD F7)
    "emp_id": Question("사번", "id", codes=("P1B2",), keywords=("사번", "직번")),
    "name": Question("이름", "id", codes=("P1B3",), keywords=("이름", "성명")),
    "respondent_id": Question("응답자ID", "id", keywords=("응답자ID",)),
    "answer_id": Question("답변ID", "id", keywords=("답변ID",)),
    # 메타
    "course": Question("과정명", "meta", codes=("P2B2",), keywords=("과정명",), exact=("과정",)),
    "started_at": Question("시작일시", "meta", keywords=("시작일시",)),
    "ended_at": Question("종료일시", "meta", keywords=("종료일시",)),
    "eligibility": Question("답변 적격성", "meta", keywords=("적격성",)),
    # 객관식 9개
    "expertise": Question("전문성", "score", codes=("P2B4",), keywords=("전문성",), scale=(1, 5)),
    "enthusiasm": Question("강의 열의도", "score", codes=("P2B5",), keywords=("열의",), scale=(1, 5)),
    # NPS 문항 원문에도 '난이도'가 들어 있으므로 '추천'이 있는 문항은 제외한다.
    "difficulty": Question("난이도", "score", codes=("P2B6",), keywords=("난이도", "난의도"), exclude=("추천",), scale=(1, 5)),
    "material": Question("강의자료", "score", codes=("P2B7",), keywords=("강의자료", "참고자료"), scale=(1, 5)),
    "curriculum": Question("커리큘럼 체계성", "score", codes=("P3B2",), keywords=("커리큘럼", "체계"), scale=(1, 5)),
    "job_help": Question("업무 도움", "score", codes=("P3B3",), keywords=("업무에실제로", "업무에도움"), exclude=("강의자료", "참고자료"), scale=(1, 5)),
    "usefulness": Question("전반 유익성", "score", codes=("P3B4",), keywords=("유익",), scale=(1, 5)),
    "knowledge": Question("지식 향상", "score", codes=("P3B5",), keywords=("지식수준", "함양"), scale=(0, 10)),
    "recommend": Question("추천 의향", "score", codes=("P3B6",), keywords=("추천",), scale=(0, 10)),
    # 주관식 3종 (강사 피드백은 원본에서 두 컬럼으로 나뉘어 있음)
    "feedback": Question("좋았던 점/보완할 점", "text", codes=("P2B8", "P2B9"), keywords=("좋았던점과보완",), multi=True),
    "impression": Question("솔직한 소감", "text", codes=("P3B7",), keywords=("솔직한소감",)),
    "wanted": Question("받고 싶은 교육", "text", codes=("P3B8",), keywords=("받고싶은교육",)),
}

ID_FIELDS = [k for k, q in QUESTIONS.items() if q.kind == "id"]

# 수동 매핑 후보에서 뺄 열. 자동 감지에 실패한 사번·이름 열을 사용자가 실수로 과정명·주관식으로
# 지정해 화면에 노출하는 일을 막는다. (영문 id/name은 단어 단위로만 본다)
ID_HEADER_HINT = r"사번|직번|사원\s*번호|이름|성명|응답자\s*id|답변\s*id|\bid\b|\bname\b|\bemp"
SCORE_FIELDS = [k for k, q in QUESTIONS.items() if q.kind == "score"]
TEXT_FIELDS = [k for k, q in QUESTIONS.items() if q.kind == "text"]

# 지표 정의 (PRD F2). 복수 문항 지표는 '문항별 평균의 평균'으로 계산한다.
METRICS: dict[str, dict] = {
    "강사 만족도": {"items": ["expertise", "enthusiasm"], "scale": 5},
    "난이도": {"items": ["difficulty"], "scale": 5},
    "강의자료": {"items": ["material"], "scale": 5},
    "전반 만족도": {"items": ["curriculum", "job_help", "usefulness"], "scale": 5},
    "지식 향상도": {"items": ["knowledge"], "scale": 10},
    "NPS": {"items": ["recommend"], "type": "nps"},
}

# NPS 구간 (0~10점 척도)
NPS_PROMOTER_MIN = 9
NPS_DETRACTOR_MAX = 6

# 응답 수가 이보다 적으면 신뢰도 경고 (PRD 9장)
MIN_RESPONSES_WARNING = 10

# 전년 대비 차이가 이보다 작으면 '변동 없음'
DELTA_EPSILON = 0.01

# 주관식 문항의 화면/보고서 표시명
TEXT_QUESTION_NAMES = {
    "feedback": "강사 피드백",
    "impression": "솔직한 소감",
    "wanted": "받고 싶은 교육",
}

# 의미 없는 주관식 응답 (공백·문장부호 제거 후 비교)
MEANINGLESS_ANSWERS = {
    "없음", "없습니다", "없어요", "없다", "없음니다", "특이사항없음", "해당없음",
    "x", "무", "na", "n/a", "-", ".",
}

# AI 모델 (키 형식으로 제공자를 고른다: sk-ant- → Claude, 그 밖의 sk- → OpenAI, AIza·AQ. → Gemini)
DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
# 경량(lite) 모델을 기본으로 쓴다. 상위 모델(gemini-3.8-flash 등)은 혼잡(503)·시간 초과(504)가 잦았고,
# lite는 같은 요청에 수 초 안에 응답했다 (2026-10 확인). 상위 모델을 쓰려면 GEMINI_MODEL로 지정한다.
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
# 혼잡·시간 초과(500/503/504)면 차례로 바꿔 시도한다. 사용 가능한 모델은 키·시점에 따라 달라진다.
GEMINI_FALLBACK_MODELS = ["gemini-flash-lite-latest", "gemini-3.1-flash-lite"]

# 차트 색상. 모든 차트가 이 값만 쓴다. CareSpace 스타일(보라 강조) 라이트 테마의 크림 배경(#F7F4EE) 기준으로
# dataviz 검증 스크립트를 돌린 값이다. 대비가 낮은 칸(주황·회색)은 막대 위 % 라벨·호버·점수표로 보완한다.
COLORS = {
    "current": "#6d32d8",  # 올해 (보라)
    "previous": "#b8adcc",  # 작년 (중립 라벤더 회색)
    "up": "#0ca30c",
    "down": "#d03b3b",
    "promoter": "#6d32d8",
    "passive": "#b8adcc",
    "detractor": "#e5584f",
    "ink": "#2b1352",  # 차트 글자색 (짙은 보라)
    "muted": "#7d6f96",  # 축 눈금 등 보조 글자색
}
# 1~5점 분포: 1·2점 빨강·주황, 3점 중립 회색, 4·5점 보라 계열 (만족 방향이 보라)
SCORE_COLORS = {1: "#e5584f", 2: "#f2a55e", 3: "#b8adcc", 4: "#9a76e8", 5: "#6d32d8"}
