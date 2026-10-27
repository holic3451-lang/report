"""교육 결과보고 대시보드 - Streamlit 진입점."""
import os
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

import ui_theme as ui

from config import COLORS, MIN_RESPONSES_WARNING, QUESTIONS, SCORE_FIELDS, TEXT_FIELDS, TEXT_QUESTION_NAMES
from core import charts
from core.ai_summary import AIError, build_user_prompt, detect_provider, prepare_texts, summarize
from core.loader import LoaderError, SurveyData, course_options, load_survey
from core.markdown import md_escape
from core.metrics import (
    Delta,
    SurveyMetrics,
    compare,
    comparison_table,
    compute_metrics,
    match_course,
    metrics_table,
)
from core.report import ReportContext, build_docx, build_markdown, report_filename

st.set_page_config(page_title="교육 결과보고 대시보드", page_icon="📊", layout="wide")

NO_COMPARE = "(비교 안 함)"
PRIVACY_NOTE = "🔒 업로드한 파일은 저장되지 않으며, 사번·이름은 읽는 즉시 삭제되어 화면·보고서·AI 요청에 사용되지 않습니다."
PLOTLY_CONFIG = {"displayModeBar": False}
FILE_TYPES = ["xlsx", "xls", "csv"]
METRIC_HELP = {
    "강사 만족도": "전문성·강의 열의도 평균 (5점 만점)",
    "난이도": "5점에 가까울수록 난이도가 적절 (5점 만점)",
    "강의자료": "강의자료가 업무에 도움이 되는 정도 (5점 만점)",
    "전반 만족도": "커리큘럼 체계성·업무 도움·전반 유익성 평균 (5점 만점)",
    "지식 향상도": "수강 전 대비 지식 수준 향상 (10점 만점)",
    "NPS": "추천(9~10점) 비율 − 비추천(0~6점) 비율 (−100 ~ +100)",
}

# CareSpace 스타일 전역 CSS (보라 프레임 · 크림 패널 · Pretendard · 알약 버튼). 내용은 ui_theme.py
st.html(ui.CSS)


@st.cache_data(show_spinner=False)
def load(data: bytes, filename: str, overrides: tuple[tuple[str, int], ...] = ()) -> SurveyData:
    return load_survey(data, filename, dict(overrides))


@dataclass
class Loaded:
    survey: SurveyData  # 수동 매핑까지 반영한 결과
    base: SurveyData  # 자동 매핑만 한 결과. 수동 매핑 선택지(찾지 못한 문항·남은 열)는 이걸 기준으로 보여 준다.
    widget_prefix: str  # 수동 매핑 선택 위젯 키 접두사. 파일이 바뀌면 선택이 초기화된다.
    duplicates: list[str] = field(default_factory=list)  # 이미 쓴 열을 또 고른 문항


@st.cache_data(show_spinner=False)
def run_ai(prompt_key: str, provider: str, model: str | None, _course: str, _texts: dict, _metrics: SurveyMetrics, _api_key: str) -> dict:
    """prompt_key(실제로 전송되는 비식별 프롬프트)가 같으면 다시 호출하지 않는다."""
    return summarize(_course, _texts, _metrics, api_key=_api_key, model=model, provider=provider)


def setting(name: str) -> str | None:
    """st.secrets → 환경변수 순서로 설정값을 읽는다."""
    try:
        value = st.secrets.get(name)
    except Exception:  # secrets.toml이 없으면 예외가 난다
        value = None
    return value or os.environ.get(name)


def load_upload(uploaded, which: str) -> Loaded | None:
    """파일을 읽고, 사이드바에서 직접 지정한 열이 있으면 반영해 다시 읽는다 (둘 다 캐시됨)."""
    if uploaded is None:
        return None
    data = uploaded.getvalue()
    try:
        base = load(data, uploaded.name)
    except LoaderError as e:
        st.sidebar.error(f"{uploaded.name}: {e}")
        return None
    prefix = f"map::{which}::{getattr(uploaded, 'file_id', uploaded.name)}::"
    overrides, duplicates, used = {}, [], set()
    for key in base.missing:
        col = st.session_state.get(prefix + key)
        if col is None:
            continue
        if col in used:
            duplicates.append(key)
            continue
        used.add(col)
        overrides[key] = col
    survey = load(data, uploaded.name, tuple(sorted(overrides.items()))) if overrides else base
    return Loaded(survey, base, prefix, duplicates)


def period_text(df: pd.DataFrame) -> str:
    ts = df["submitted_at"].dropna()
    return f"{ts.min():%Y-%m-%d} ~ {ts.max():%Y-%m-%d}" if len(ts) else ""


def mapping_expander(title: str, loaded: Loaded) -> None:
    """자동 매핑 결과를 보여 주고, 찾지 못한 문항만 직접 열을 고르게 한다 (PRD 3.4 ③)."""
    survey, base = loaded.survey, loaded.base
    with st.expander(title + (" ⚠️" if survey.missing else " ✅"), expanded=bool(base.missing)):
        if base.missing:
            labels = dict(base.meta["unassigned"])
            if labels:
                st.caption("자동으로 찾지 못한 문항입니다. 해당하는 열을 직접 고르세요. 사번·이름으로 보이는 열은 목록에서 뺐습니다.")
                for key in base.missing:
                    st.selectbox(
                        QUESTIONS[key].label,
                        [None, *labels],
                        format_func=lambda i: "(선택 안 함)" if i is None else labels[i],
                        key=loaded.widget_prefix + key,
                    )
            else:
                st.caption("직접 지정할 수 있는 남은 열이 없습니다.")
            for key in loaded.duplicates:
                st.warning(f"{QUESTIONS[key].label}: 이미 다른 문항에 지정한 열이라 적용하지 않았습니다.")
            if survey.missing:
                st.warning("지정하지 않은 문항은 '데이터 없음'으로 표시됩니다: " + ", ".join(QUESTIONS[k].label for k in survey.missing))
        for key, cols in survey.mapping.items():
            manual = " · 직접 지정" if key in survey.meta["manual"] else ""
            st.caption(f"**{QUESTIONS[key].label}**{manual} ← {md_escape(' / '.join(c[:30] for c in cols))}")


def stop_with_mapping(loaded: Loaded, message: str) -> None:
    """대시보드를 그릴 수 없을 때: 사이드바에 매핑 화면을 남기고 안내 후 멈춘다."""
    with st.sidebar:
        st.divider()
        mapping_expander("컬럼 매핑 확인 (올해)", loaded)
        st.caption(PRIVACY_NOTE)
    st.html(ui.hero_html("교육 결과보고 대시보드", "파일을 확인해 주세요", "왼쪽 '컬럼 매핑 확인'에서 문항을 직접 지정할 수 있습니다."))
    st.warning(message)
    st.stop()


def section(title: str, caption: str | None = None, center: bool = False) -> None:
    st.html(ui.section_html(title, caption or "", center))


def render_landing() -> None:
    st.html(ui.hero_html(
        "교육 결과보고 대시보드",
        "설문 파일만 올리면 결과보고서까지 바로",
        "교육 만족도 설문 로데이터를 올리면 지표 집계, 전년 비교, AI 주관식 요약, 결과보고서 초안을 한 번에 만들어 줍니다.",
        cta="왼쪽에서 설문 파일 업로드",
        sticker="업로드 즉시 결과",
    ))
    st.html(ui.trust_html(["사번·이름 자동 비식별", "작년 같은 과정 자동 비교", "AI 주관식 분류·요약"]))
    section("이렇게 사용합니다", "올리고, 확인하고, 내려받으면 끝입니다.", center=True)
    st.html(ui.cards_html([
        ui.card_html("업로드", "설문 파일 올리기", "왼쪽 사이드바에 올해 설문 파일을 올립니다.", [
            "Excel(.xlsx·.xls)과 CSV 모두 지원",
            "설문 시스템 원본(3행 헤더) 그대로 사용",
            "작년 파일도 올리면 같은 과정끼리 비교",
        ], active=True),
        ui.card_html("확인", "지표와 인사이트 보기", "지표별 점수, 점수 분포, NPS, 주관식 인사이트를 확인합니다.", [
            "강사·난이도·강의자료·전반 만족도 5점 평균",
            "지식 향상도 10점, NPS −100~+100",
            "AI가 좋았던 점·보완할 점을 분류·요약",
        ]),
        ui.card_html("다운로드", "결과보고서 초안", "맨 아래에서 결과보고서 초안을 내려받아 다듬습니다.", [
            "Word(.docx)·Markdown(.md)",
            "교육 개요부터 차기 교육 니즈까지 6개 목차",
            "사번·이름은 보고서에 들어가지 않음",
        ]),
    ]))
    st.caption(
        "필요 문항: 과정명, 객관식 9개(강사 전문성·열의도, 난이도, 강의자료, 커리큘럼, 업무 도움, 유익성, 지식 향상, 추천 의향), 주관식 3개 · "
        "CSV는 UTF-8/CP949 모두 가능"
    )


def render_kpis(m: SurveyMetrics, deltas: dict[str, Delta] | None) -> None:
    """큰 숫자(전반 만족도) 하나 + 나머지 지표 줄. 데이터가 없는 지표는 '–'와 '데이터 없음'."""
    stats = list(m.metrics.values())
    headline = next((s for s in stats if s.name == "전반 만족도" and s.available), None) or next(
        (s for s in stats if s.available), stats[0]
    )
    st.html(ui.headline_html(headline, deltas.get(headline.name) if deltas else None))
    rest = [s for s in stats if s is not headline]
    st.html(ui.stats_html(rest, deltas, METRIC_HELP))


def render_ai(ai: dict) -> None:
    st.html(ui.cards_html([
        '<div class="cs-card active"><div class="head">' + ui.RING + "핵심 인사이트</div>"
        + ui.check_list_html([(s, "") for s in ai["insights"]]) + "</div>",
        '<div class="cs-card"><div class="head">' + ui.RING + "개선점</div>"
        + ui.check_list_html([(i["action"], f"근거: {i['basis']}") for i in ai["improvements"]]) + "</div>",
    ]))
    st.caption(":violet[■] 긍정 · :red[■] 개선요청 · :gray[■] 기타 — 막대는 같은 주제로 묶인 응답 수입니다.")
    tabs = st.tabs([f"{TEXT_QUESTION_NAMES[k]} ({ai['questions'][k]['n']})" for k in TEXT_FIELDS])
    for tab, key in zip(tabs, TEXT_FIELDS):
        with tab:
            render_question(key, ai["questions"][key], ai["wanted_trainings"])


def render_question(key: str, q: dict, wanted: list[dict]) -> None:
    """주제 차트 + 대표 응답. '받고 싶은 교육'은 긍정/개선 분류가 의미 없으므로 희망 교육 Top 5를 대신 보여준다."""
    if not q["n"]:
        st.info("유효 응답이 없습니다.")
        return
    if key == "wanted":
        st.markdown(f"응답 **{q['n']}건**")
        title = "희망 교육 Top 5"
        fig = charts.count_bar_chart(
            [w["topic"] for w in wanted], [w["count"] for w in wanted], [COLORS["current"]] * len(wanted)
        ) if wanted else None
    else:
        counts = q["counts"]
        st.markdown(
            f"응답 **{q['n']}건** · :violet[긍정 {counts['긍정']}] · :red[개선요청 {counts['개선요청']}] · :gray[기타 {counts['기타']}]"
        )
        title = "주제별 언급 수"
        fig = charts.theme_chart(q) if q["themes"] else None
    if fig is None and not q["themes"]:
        st.caption("반복해서 나온 주제가 없습니다.")
        return
    chart_col, quote_col = st.columns([3, 2], gap="large")
    if fig is not None:
        with chart_col:
            st.markdown(f"**{title}**")
            st.plotly_chart(fig, config=PLOTLY_CONFIG, key=f"chart_{key}")
    with quote_col:
        st.markdown("**대표 응답**")
        st.html(ui.quotes_html(q["themes"]))


# ---------- 사이드바: 업로드 ----------
with st.sidebar:
    st.markdown("### 교육 결과보고")
    current_file = st.file_uploader("올해 설문 데이터 (필수)", type=FILE_TYPES)
    previous_file = st.file_uploader("작년 설문 데이터 (선택)", type=FILE_TYPES, help="올리면 같은 과정의 지표를 비교합니다.")

current = load_upload(current_file, "current")
previous = load_upload(previous_file, "previous")
survey = current.survey if current else None
previous_survey = previous.survey if previous else None

if survey is None:
    render_landing()
    with st.sidebar:
        st.caption(PRIVACY_NOTE)
    st.stop()

if survey.df.empty:
    stop_with_mapping(
        current,
        f"집계할 적격 응답이 없습니다. (전체 {survey.meta['n_rows']}건 중 적격 0건) "
        "'답변 적격성' 값이나 파일에 응답 행이 있는지 확인해 주세요.",
    )
if not any(k in survey.df.columns for k in SCORE_FIELDS):
    stop_with_mapping(
        current,
        "객관식 문항을 하나도 찾지 못했습니다. 설문 결과 파일이 맞는지 확인하거나, "
        "왼쪽 '컬럼 매핑 확인'에서 문항별 열을 직접 지정해 주세요.",
    )

# ---------- 사이드바: 과정 선택 · 매핑 ----------
courses = course_options(survey.df)
with st.sidebar:
    st.divider()
    course = st.selectbox("과정 선택", courses)
    previous_course = None
    if previous_survey is not None and previous_survey.df.empty:
        st.warning("작년 파일에 적격 응답이 없어 비교하지 않습니다.")
    elif previous_survey is not None:
        prev_courses = course_options(previous_survey.df)
        matched = match_course(course, prev_courses)
        options = [NO_COMPARE] + prev_courses
        previous_course = st.selectbox(
            "비교할 작년 과정",
            options,
            index=options.index(matched) if matched else 0,
            key=f"prev_course::{course}",
            help="과정명에서 연도·공백·특수문자를 빼고 같은 과정을 자동으로 찾습니다.",
        )
        if matched is None and previous_course == NO_COMPARE:
            st.warning("같은 과정을 자동으로 찾지 못했습니다. 비교할 작년 과정을 직접 선택하세요.")
        elif matched is None:
            st.caption("직접 선택한 과정과 비교합니다.")
        elif previous_course == matched:
            st.caption("✅ 같은 과정을 자동으로 찾았습니다.")
        if previous_course == NO_COMPARE:
            previous_course = None
    st.divider()
    mapping_expander("컬럼 매핑 확인 (올해)", current)
    if previous is not None:
        mapping_expander("컬럼 매핑 확인 (작년)", previous)
    st.caption(PRIVACY_NOTE)

df = survey.df[survey.df["course"] == course]
m = compute_metrics(df)
prev_m = None
if previous_course is not None:
    prev_m = compute_metrics(previous_survey.df[previous_survey.df["course"] == previous_course])
deltas = compare(m, prev_m) if prev_m else None
instructors = sorted(set(survey.meta["sub_labels"].values()))

# ---------- 헤더 ----------
chips = [f"응답 {m.n_responses}명"]
if period := period_text(df):
    chips.append(f"응답 기간 {period}")
if instructors:
    chips.append("강사 " + ", ".join(instructors))
if prev_m:
    chips.append(f"비교 대상 {previous_course} ({prev_m.n_responses}명)")
st.html(ui.hero_html("교육 결과보고", course, chips=chips))  # hero_html이 모든 글자를 이스케이프한다
excluded = survey.meta["ineligible_by_course"].get(course, 0)
if excluded:
    st.caption(f"부적격 응답 {excluded}건은 집계에서 제외했습니다.")
if m.n_responses < MIN_RESPONSES_WARNING:
    st.warning(f"응답 수가 {m.n_responses}명으로 적어 평균과 NPS의 신뢰도가 낮습니다.")
if prev_m and prev_m.n_responses < MIN_RESPONSES_WARNING:
    st.warning(f"작년 응답 수가 {prev_m.n_responses}명으로 적어 비교 결과의 신뢰도가 낮습니다.")

# ---------- ① KPI ----------
render_kpis(m, deltas)
st.caption("강사 만족도·난이도·강의자료·전반 만족도는 5점, 지식 향상도는 10점 만점 · NPS는 −100~+100")

# ---------- ② 지표별 점수 ----------
section(
    "지표별 점수" + (" · 올해 vs 작년" if prev_m else ""),
    "5점 만점 지표만 표시합니다. 지식 향상도(10점)와 NPS는 위 카드를 참고하세요.",
)
st.plotly_chart(charts.metric_bar_chart(m, prev_m), config=PLOTLY_CONFIG)
with st.expander("지표별 점수표 · 지표 정의 보기"):
    for name, desc in METRIC_HELP.items():
        st.caption(f"**{name}**: {desc}")
    table = comparison_table(m, prev_m) if prev_m else metrics_table(m)
    score_cols = [c for c in ("점수", "작년") if c in table.columns]
    st.dataframe(
        table.drop(columns="key"),
        hide_index=True,
        height=(len(table) + 1) * 35 + 3,
        column_config={c: st.column_config.NumberColumn(format="%.2f") for c in score_cols},
    )

# ---------- ③ 문항 분포 · ④ NPS ----------
left, right = st.columns([3, 2], gap="large")
with left:
    section("문항별 점수 분포", "각 문항에서 1~5점을 준 응답 비율")
    st.plotly_chart(charts.distribution_chart(m), config=PLOTLY_CONFIG)
with right:
    section("NPS 구성", "동료 추천 의향 (0~10점)")
    if m.nps and m.nps.n:
        nps = m.nps
        st.html(ui.nps_gauge_html(nps))
        st.plotly_chart(charts.nps_chart(nps), config=PLOTLY_CONFIG)
        st.caption(
            f"추천 {nps.promoters}명({nps.pct(nps.promoters):.0f}%) · 중립 {nps.passives}명({nps.pct(nps.passives):.0f}%) · "
            f"비추천 {nps.detractors}명({nps.pct(nps.detractors):.0f}%) — "
            f"NPS = 추천 {nps.pct(nps.promoters):.1f}% − 비추천 {nps.pct(nps.detractors):.1f}% = **{nps.score:+.1f}**"
        )
    else:
        st.info("추천 의향 문항 데이터가 없습니다.")

# ---------- ⑤⑥ 주관식 AI 분석 ----------
section("주관식 인사이트", "좋았던 점/보완할 점, 솔직한 소감, 받고 싶은 교육을 AI가 분류·요약했습니다.")
texts = prepare_texts(df)
# OPENAI → GEMINI → ANTHROPIC 순서로 처음 설정된 키를 쓴다. 제공자는 키 형식으로 정한다.
api_key = setting("OPENAI_API_KEY") or setting("GEMINI_API_KEY") or setting("ANTHROPIC_API_KEY")
provider = detect_provider(api_key)
# 형식을 알 수 없는 키면 응답을 외부로 보내지 않고 안내만 한다.
wrong_key = bool(api_key) and provider is None
ai_enabled = bool(api_key) and not wrong_key and any(texts.values())
ai_box = st.container()  # AI 결과 자리. 보고서 버튼을 먼저 그린 뒤 채운다.

with st.expander("주관식 응답 원문 보기 (비식별 처리)", expanded=not ai_enabled and any(texts.values())):
    tabs = st.tabs([f"{TEXT_QUESTION_NAMES[k]} ({len(texts[k])})" for k in TEXT_FIELDS])
    for tab, key in zip(tabs, TEXT_FIELDS):
        with tab:
            if not texts[key]:
                st.caption("유효 응답이 없습니다.")
            for t in texts[key]:
                st.markdown(f"- {md_escape(t)}")

# ---------- ⑦ 보고서 ----------
section("결과보고서 초안", "교육 개요 · 종합 결과 · NPS · 주관식 분석 · 인사이트와 개선 방향 · 차기 교육 니즈")
report_box = st.empty()


def render_report(ai_result: dict | None, pending: bool) -> None:
    """보고서 다운로드 버튼. AI 분석 중(pending)에도 정량 결과로 먼저 받을 수 있게 한다."""
    ctx = ReportContext(
        course=course,
        current=m,
        period=period_text(df),
        instructors=instructors,
        previous=prev_m,
        previous_course=previous_course,
        ai=ai_result,
        texts=texts,
    )
    phase = "pending" if pending else "final"
    with report_box.container():
        d1, d2, _ = st.columns([1, 1, 2])
        d1.download_button(
            "Word 보고서 (.docx)",
            data=build_docx(ctx),
            file_name=report_filename(course, "docx"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
            width="stretch",
            key=f"docx_{phase}",
        )
        d2.download_button(
            "Markdown (.md)",
            data=build_markdown(ctx).encode("utf-8"),
            file_name=report_filename(course, "md"),
            mime="text/markdown",
            width="stretch",
            key=f"md_{phase}",
        )
        # 두 단계 모두 같은 자리에 캡션을 하나씩 쓴다. 한쪽만 쓰면 같은 실행 안에서
        # 먼저 그린(pending) 캡션이 지워지지 않고 남는다.
        if pending:
            st.caption("AI 분석이 끝나면 주관식 분석이 보고서에 자동으로 반영됩니다. 지금 받으면 주관식 부분은 응답 원문으로 채워집니다.")
        elif ai_result is None:
            st.caption("AI 분석 결과가 없어 보고서의 주관식 부분은 비식별 처리된 응답 원문으로 채워집니다.")
        else:
            st.caption("AI 주관식 분석이 반영된 보고서입니다.")


# ---------- ⑤⑥ 주관식 AI 분석 ----------
ai_result = None
# 실패한 요청은 세션에 기억해 두고, 사용자가 '다시 시도'를 누를 때만 다시 호출한다.
# (st.cache_data는 예외를 캐시하지 않아, 그대로 두면 화면이 바뀔 때마다 재호출된다)
ai_failures: dict[str, str] = st.session_state.setdefault("ai_failures", {})
with ai_box:
    if not any(texts.values()):
        st.info("분석할 주관식 응답이 없습니다.")
    elif not api_key:
        st.info("AI API 키가 설정되지 않아 AI 분석을 건너뛰었습니다. `.streamlit/secrets.toml`에 `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` 중 하나를 넣으면 자동으로 분석합니다. 아래에서 응답 원문을 확인할 수 있습니다.")
    elif wrong_key:
        st.warning(
            "설정된 API 키의 형식을 알 수 없습니다. OpenAI 키는 `sk-`(예: `sk-proj-`), Gemini 키는 `AIza` 또는 `AQ.`, Claude 키는 `sk-ant-`로 시작합니다. "
            "`.streamlit/secrets.toml`의 키를 확인해 주세요. 형식이 맞지 않는 키로는 응답을 외부로 보내지 않았습니다."
        )
    else:
        model = setting({"openai": "OPENAI_MODEL", "gemini": "GEMINI_MODEL"}.get(provider, "CLAUDE_MODEL"))
        prompt_key = build_user_prompt(course, texts, m)
        failure_key = f"{provider}::{model}::{prompt_key}"
        if failure_key not in ai_failures:
            render_report(None, pending=True)
            with st.spinner("AI가 주관식 응답을 분류·요약하고 있습니다. 30초 정도 걸릴 수 있습니다..."):
                try:
                    ai_result = run_ai(prompt_key, provider, model, course, texts, m, api_key)
                except AIError as e:
                    ai_failures[failure_key] = str(e)
        if failure_key in ai_failures:
            st.error(f"AI 분석 실패: {ai_failures[failure_key]}")
            if st.button("AI 분석 다시 시도", key="ai_retry"):
                ai_failures.pop(failure_key, None)
                st.rerun()
    if ai_result:
        render_ai(ai_result)
        st.caption(f"분석 모델: {md_escape(ai_result.get('model', ''))}")

render_report(ai_result, pending=False)
