"""CareSpace 스타일 화면 테마: 전역 CSS와 HTML 블록 (app.py 전용).

디자인 요소 (디자인/ 폴더 참고)
- 보라 프레임 안의 크림색 패널, 짙은 보라 글자, 보라→마젠타 그라데이션 알약 버튼
- 사진 대신 보라 그라데이션 히어로 + 관절 점(마젠타 원)과 점선 장식
- 큰 숫자 하나 + 아래 지표 줄 (CareSpace의 '4,348,486' / '60% · $1,200' 구성)
- 얇은 보라 테두리의 둥근 카드, 원형 체크 아이콘 목록, 무지개 스케일 바(NPS 게이지)

HTML 문자열을 만드는 함수는 Streamlit에 의존하지 않는다. 사용자·AI·파일에서 온 글자는 모두 html.escape를 거친다.
"""
import html
import math

from core.metrics import Delta, MetricStat, NPSStat

CREAM = "#F7F4EE"
FRAME = "#5B3FBF"
INK = "#2B1352"
PURPLE = "#6D32D8"

FONT_CSS = "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"



def _svg_uri(svg: str) -> str:
    from urllib.parse import quote
    return "data:image/svg+xml," + quote(svg)


CHECK_URI = _svg_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="#3b1a78" stroke-width="1.8"/>'
    '<path d="m8 12.2 2.7 2.6L16 9.6" stroke="#3b1a78" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)
INFO_URI = _svg_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="#3b1a78" stroke-width="1.8"/>'
    '<path d="M12 11v5m0-8h.01" stroke="#3b1a78" stroke-width="2" stroke-linecap="round"/></svg>'
)
# CareSpace 로고처럼 한쪽이 열린 고리
RING_URI = _svg_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#7b3fe4"/><stop offset="1" stop-color="#b13bd9"/></linearGradient></defs>'
    '<path d="M12 3a9 9 0 1 1-8.5 6" fill="none" stroke="url(#g)" stroke-width="4" stroke-linecap="round"/></svg>'
)
# 히어로 오른쪽 장식: 관절 점(마젠타)과 점선 (디자인 사진의 동작 인식 점을 옮김)
JOINTS_URI = _svg_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 260">'
    '<path d="M70 40 L130 95 L110 165 L175 205 L240 150 L215 80" fill="none" stroke="rgba(255,255,255,.55)" stroke-width="2" stroke-dasharray="3 6"/>'
    + "".join(
        f'<circle cx="{x}" cy="{y}" r="{r}" fill="#c43fe6" stroke="rgba(255,255,255,.75)" stroke-width="2"/>'
        for x, y, r in [(70, 40, 11), (130, 95, 13), (110, 165, 10), (175, 205, 12), (240, 150, 14), (215, 80, 9)]
    )
    + "</svg>"
)
CHECK = '<span class="cs-ico check"></span>'
INFO = '<span class="cs-ico info"></span>'
RING = '<span class="cs-ico ring"></span>'


CSS = f"""
<style>
@import url('{FONT_CSS}');
:root {{
  --cream: {CREAM}; --card: #FBF9F5; --frame: {FRAME}; --ink: {INK}; --ink-2: #5d4a7e; --muted: #8c7fa3;
  --line: #e2d8f0; --purple: {PURPLE}; --magenta: #b13bd9; --grad: linear-gradient(90deg, #7b3fe4 0%, #b13bd9 100%);
}}
html, body, .stMarkdown, .cs-hero, .cs-section, .cs-big, .cs-stats, .cs-gauge, .cs-cards, .cs-trust {{
  font-family: 'Pretendard Variable', Pretendard, 'Malgun Gothic', sans-serif;
}}
/* 한국어는 단어 단위로 줄바꿈 */
.cs-hero, .cs-section, .cs-big, .cs-stats, .cs-cards, .cs-trust, h1, h2, h3, h4 {{ word-break: keep-all; }}
/* 보라 프레임 안의 크림 패널 */
[data-testid="stAppViewContainer"] {{ background: var(--frame); }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMain"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{
  background: var(--cream); border-radius: 28px; margin: 12px 14px 18px; padding: 2.4rem 2.6rem 3rem;
  box-sizing: border-box; max-width: min(1240px, calc(100% - 28px)); box-shadow: 0 1px 0 rgba(255,255,255,.4) inset;
}}
@media (max-width: 640px) {{ [data-testid="stMainBlockContainer"] {{ margin: 6px; max-width: calc(100% - 12px); padding: 1.4rem 1rem 2rem; border-radius: 20px; }} }}
[data-testid="stSidebar"] {{ background: #efe9f7; border-right: 1px solid var(--line); }}
[data-testid="stSidebar"] h3 {{ color: var(--ink); font-weight: 800; letter-spacing: -.02em; }}
h1, h2, h3, h4 {{ color: var(--ink); letter-spacing: -.025em; }}
h4 {{ font-weight: 750 !important; }}
/* 둥근 카드 (st.container(border=True)) */
[data-testid="stVerticalBlock"][class*="border"], div[data-testid="stVerticalBlockBorderWrapper"] {{
  border-color: var(--line) !important; border-radius: 22px !important; background: var(--card);
}}
/* 버튼: 그라데이션 알약 */
[data-testid="stBaseButton-primary"] {{
  background: var(--grad) !important; border: 0 !important; border-radius: 999px !important;
  font-weight: 700; padding: .55rem 1.3rem; box-shadow: 0 6px 18px rgba(123,63,228,.28);
}}
[data-testid="stBaseButton-primary"]:hover {{ filter: brightness(1.06); }}
[data-testid="stBaseButton-secondary"] {{
  border-radius: 999px !important; border: 1.5px solid var(--purple) !important; color: var(--purple) !important;
  background: transparent !important; font-weight: 700;
}}
[data-testid="stDownloadButton"] button p::after, [data-testid="stBaseButton-primary"] p::after {{ content: "  →"; }}
/* 탭 · 펼치기 · 알림 */
[data-baseweb="tab-list"] {{ gap: .4rem; }}
[data-baseweb="tab"] {{ border-radius: 999px; padding: .35rem .9rem !important; font-weight: 650; }}
[data-baseweb="tab"][aria-selected="true"], button[role="tab"][aria-selected="true"] {{ background: #ebe2fb; color: var(--purple); }}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{ display: none; }}
[data-testid="stExpander"] details {{ border-radius: 18px; border-color: var(--line); background: var(--card); }}
[data-testid="stAlert"] {{ border-radius: 16px; }}
[data-testid="stFileUploaderDropzone"] {{ border-radius: 18px; border: 1.5px dashed #c9b8ea; background: #faf7ff; }}
[data-testid="stCaptionContainer"] {{ color: var(--muted); }}

/* ---------- 커스텀 블록 ---------- */
.cs-hero {{
  position: relative; overflow: hidden; border-radius: 26px; padding: 2.6rem 2.6rem 2.4rem; color: #fff;
  background: radial-gradient(120% 140% at 85% 10%, #8f4be8 0%, #6d32d8 38%, #3b1a78 100%);
}}
.cs-hero > * {{ position: relative; z-index: 1; }}
.cs-hero .eyebrow {{ font-size: .9rem; font-weight: 650; opacity: .85; letter-spacing: .01em; }}
.cs-hero h1 {{ color: #fff; font-size: clamp(2rem, 4.2vw, 3.4rem); line-height: 1.05; font-weight: 800; letter-spacing: -.04em; margin: .5rem 0 .8rem; max-width: 14em; padding: 0; }}
.cs-hero p.sub {{ font-size: 1.05rem; font-weight: 550; opacity: .92; margin: 0 0 1.4rem; max-width: 34em; }}
.cs-hero .chips {{ display: flex; flex-wrap: wrap; gap: .5rem; position: relative; z-index: 1; }}
.cs-hero .chip {{ background: rgba(42,14,96,.62); border: 1px solid rgba(255,255,255,.28); backdrop-filter: blur(4px); border-radius: 999px; padding: .35rem .85rem; font-size: .86rem; font-weight: 600; }}
.cs-hero .chip b {{ font-weight: 800; }}
.cs-hero .cta {{ display: inline-flex; align-items: center; gap: .5rem; background: var(--grad); border-radius: 999px; padding: .7rem 1.4rem; font-weight: 700; box-shadow: 0 8px 24px rgba(177,59,217,.45); position: relative; z-index: 1; }}
.cs-sticker {{
  position: absolute; right: 2.2rem; bottom: 1.6rem; transform: rotate(-6deg); z-index: 2;
  background: linear-gradient(110deg, #c6f432, #7ff0b0 45%, #e8ff8a 70%, #c6f432); color: #1d2b05;
  border: 3px solid #fff; border-radius: 999px; padding: .45rem 1rem; font-weight: 800; font-size: .9rem;
  box-shadow: 0 6px 16px rgba(0,0,0,.18);
}}
@media (max-width: 760px) {{ .cs-sticker {{ display: none; }} }}

.cs-section {{ margin: 2.6rem 0 1rem; }}
.cs-section.center {{ text-align: center; }}
.cs-section h2 {{ font-size: clamp(1.5rem, 2.6vw, 2.1rem); font-weight: 800; letter-spacing: -.035em; color: var(--ink); margin: 0; padding: 0; }}
.cs-section p {{ color: var(--ink-2); margin: .35rem 0 0; font-size: 1rem; }}

.cs-big {{ text-align: center; padding: 1.6rem 0 .6rem; }}
.cs-big .num {{ font-size: clamp(3.2rem, 8vw, 5.6rem); font-weight: 800; letter-spacing: -.05em; line-height: 1; color: #2e1260; }}
.cs-big .num small {{ font-size: .38em; color: var(--muted); font-weight: 700; letter-spacing: -.02em; }}
.cs-big .label {{ font-size: 1.15rem; font-weight: 700; color: var(--ink); margin-top: .5rem; }}
.cs-big .meta {{ margin-top: .45rem; display: flex; gap: .5rem; justify-content: center; align-items: center; color: var(--muted); font-size: .88rem; }}

.cs-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1.2rem 1.6rem; padding: 1.4rem .4rem .4rem; border-top: 1px solid var(--line); }}
.cs-stat .num {{ font-size: 2.1rem; font-weight: 800; letter-spacing: -.04em; color: var(--purple); line-height: 1.1; }}
.cs-stat .num small {{ font-size: .5em; color: var(--muted); font-weight: 700; }}
.cs-stat .label {{ font-weight: 700; color: var(--ink); margin-top: .15rem; }}
.cs-stat .desc {{ font-size: .82rem; color: var(--muted); margin-top: .2rem; line-height: 1.35; }}
.cs-stat .row {{ display: flex; gap: .4rem; align-items: center; margin-top: .4rem; flex-wrap: wrap; }}
.cs-delta {{ display: inline-block; border-radius: 999px; padding: .12rem .55rem; font-size: .78rem; font-weight: 750; }}
.cs-delta.up {{ background: #e3f5e8; color: #0b6b2f; }}
.cs-delta.down {{ background: #fde8e7; color: #b42318; }}
.cs-delta.flat {{ background: #efeaf6; color: #6a5d82; }}
.cs-n {{ font-size: .78rem; color: var(--muted); }}

.cs-gauge {{ margin: .6rem 0 .2rem; padding-top: 2.1rem; position: relative; }}
.cs-gauge .flag {{
  position: absolute; top: 0; transform: translateX(-50%); background: #3b1a78; color: #fff; border-radius: 999px;
  padding: .2rem .7rem; font-size: .82rem; font-weight: 800; white-space: nowrap;
}}
.cs-gauge .bar {{
  position: relative; height: 44px; border-radius: 999px; border: 1.5px solid #3b1a78;
  background: linear-gradient(90deg, #ef6a5b 0%, #f5a35c 25%, #ead768 50%, #9be0a2 75%, #6ad6ea 100%);
}}
.cs-gauge .marker {{
  position: absolute; top: 50%; width: 26px; height: 26px; margin-left: -13px; transform: translateY(-50%);
  background: #fff; border: 4px solid #3b1a78; border-radius: 50%; box-shadow: 0 2px 8px rgba(0,0,0,.25);
}}
.cs-gauge .ticks {{ display: flex; justify-content: space-between; margin-top: .55rem; font-size: .85rem; font-weight: 750; color: #3b1a78; }}
.cs-gauge .ticks span {{ display: inline-flex; gap: .3rem; align-items: center; }}

.cs-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; }}
.cs-card {{ border: 1.5px solid var(--line); border-radius: 24px; padding: 1.5rem 1.5rem 1.3rem; background: var(--card); }}
.cs-card.active {{ border-color: #7b3fe4; }}
.cs-card .head {{ display: flex; align-items: center; gap: .55rem; font-size: 1.5rem; font-weight: 800; letter-spacing: -.03em; color: var(--ink); }}
.cs-card .sub {{ color: var(--purple); font-weight: 650; font-size: 1.05rem; margin: .7rem 0 .4rem; }}
.cs-card .body {{ color: var(--ink-2); line-height: 1.55; font-size: .95rem; }}
.cs-check {{ list-style: none; padding: 0 !important; margin: .9rem 0 0 !important; }}
.cs-check li {{ margin: 0 !important; display: flex; gap: .55rem; align-items: flex-start; padding: .38rem 0; color: var(--ink-2); font-size: .93rem; line-height: 1.45; border-bottom: 1px solid #ece4f6; }}
.cs-check li:last-child {{ border-bottom: 0; }}
.cs-check li b {{ color: var(--ink); }}
.cs-check li .basis {{ display: block; color: var(--muted); font-size: .84rem; margin-top: .1rem; }}

.cs-trust {{ display: flex; flex-wrap: wrap; gap: .4rem 1.4rem; margin: 1.4rem 0 0; }}
.cs-trust span {{ display: inline-flex; gap: .5rem; align-items: center; font-weight: 700; color: var(--ink); }}
.cs-quote {{ color: var(--ink-2); font-size: .92rem; margin: .15rem 0; }}
.cs-quote-title {{ font-weight: 750; color: var(--ink); margin-top: .7rem; }}

/* ---------- 아이콘 (st.html이 인라인 SVG를 지우므로 CSS 배경으로 그린다) ---------- */
.cs-ico {{ display: inline-block; flex: none; background-repeat: no-repeat; background-position: center; background-size: contain; }}
.cs-ico.check {{ width: 18px; height: 18px; margin-top: .15rem; background-image: url("{CHECK_URI}"); }}
.cs-ico.ring {{ width: 26px; height: 26px; background-image: url("{RING_URI}"); }}
.cs-ico.info {{ width: 15px; height: 15px; background-image: url("{INFO_URI}"); }}
.cs-hero::after {{
  content: ""; position: absolute; right: -10px; top: 0; height: 100%; width: 46%; pointer-events: none;
  background: url("{JOINTS_URI}") no-repeat right center / contain;
}}
@media (max-width: 760px) {{ .cs-hero::after {{ opacity: .35; width: 70%; }} }}
.cs-hero .cta::after {{ content: "→"; font-weight: 800; }}
</style>
"""


def _e(text) -> str:
    return html.escape(str(text), quote=True)


def hero_html(eyebrow: str, title: str, subtitle: str = "", chips: list[str] | None = None,
              cta: str | None = None, sticker: str | None = None) -> str:
    """보라 그라데이션 히어로. chips는 '<b>값</b>'을 쓰지 않도록 일반 글자만 받는다(전부 이스케이프)."""
    parts = ['<div class="cs-hero">', f'<div class="eyebrow">{_e(eyebrow)}</div>', f"<h1>{_e(title)}</h1>"]
    if subtitle:
        parts.append(f'<p class="sub">{_e(subtitle)}</p>')
    if chips:
        parts.append('<div class="chips">' + "".join(f'<span class="chip">{_e(c)}</span>' for c in chips) + "</div>")
    if cta:
        parts.append(f'<span class="cta">{_e(cta)}</span>')
    if sticker:
        parts.append(f'<span class="cs-sticker">{_e(sticker)}</span>')
    parts.append("</div>")
    return "".join(parts)


def section_html(title: str, caption: str = "", center: bool = False) -> str:
    cls = "cs-section center" if center else "cs-section"
    cap = f"<p>{_e(caption)}</p>" if caption else ""
    return f'<div class="{cls}"><h2>{_e(title)}</h2>{cap}</div>'


def _value(stat: MetricStat) -> str:
    if not stat.available:
        return "–"
    if stat.scale is None:
        return f"{stat.score:+.1f}"
    return f"{stat.score:.2f}<small> / {stat.scale}</small>"


def delta_html(delta: Delta | None) -> str:
    """전년 대비 증감 알약. 비교가 없으면 빈 문자열."""
    if delta is None or not delta.available:
        return ""
    return f'<span class="cs-delta {delta.direction}">{_e(delta.label())} 전년 대비</span>'


def _n(stat: MetricStat) -> str:
    return f'<span class="cs-n">{"데이터 없음" if not stat.available else f"응답 {stat.n}명"}</span>'


def headline_html(stat: MetricStat, delta: Delta | None) -> str:
    """큰 숫자 하나 (CareSpace의 '4,348,486 Covered Lives' 자리)."""
    return (
        f'<div class="cs-big"><div class="num">{_value(stat)}</div>'
        f'<div class="label">{_e(stat.name)}</div>'
        f'<div class="meta">{delta_html(delta)}{_n(stat)}</div></div>'
    )


def stats_html(stats: list[MetricStat], deltas: dict[str, Delta] | None, descriptions: dict[str, str]) -> str:
    """지표 줄 (CareSpace의 '60% · $1,200 · 95%' 줄)."""
    items = []
    for stat in stats:
        d = deltas.get(stat.name) if deltas else None
        items.append(
            f'<div class="cs-stat"><div class="num">{_value(stat)}</div>'
            f'<div class="label">{_e(stat.name)}</div>'
            f'<div class="desc">{_e(descriptions.get(stat.name, ""))}</div>'
            f'<div class="row">{delta_html(d)}{_n(stat)}</div></div>'
        )
    return f'<div class="cs-stats">{"".join(items)}</div>'


def nps_gauge_html(nps: NPSStat) -> str:
    """무지개 스케일 바 위에 NPS 위치를 표시한다 (−100 왼쪽 ~ +100 오른쪽). 점수는 표식 위 말풍선."""
    score = nps.score
    pos = 50.0 if math.isnan(score) else min(100.0, max(0.0, (score + 100) / 2))
    flag_pos = min(90.0, max(10.0, pos))  # 말풍선이 패널 밖으로 나가지 않게
    label = "NPS –" if math.isnan(score) else f"NPS {score:+.1f}"
    return (
        '<div class="cs-gauge">'
        f'<span class="flag" style="left:{flag_pos:.1f}%">{label}</span>'
        f'<div class="bar"><span class="marker" style="left:{pos:.1f}%" title="{label}"></span></div>'
        f'<div class="ticks"><span>−100 비추천 우세 {INFO}</span><span>0</span><span>추천 우세 +100 {INFO}</span></div>'
        "</div>"
    )


def check_list_html(items: list[tuple[str, str]]) -> str:
    """원형 체크 목록. items = [(굵은 글자, 보조 설명)]. 보조 설명은 비워도 된다."""
    lis = []
    for title, basis in items:
        sub = f'<span class="basis">{_e(basis)}</span>' if basis else ""
        lis.append(f"<li>{CHECK}<span><b>{_e(title)}</b>{sub}</span></li>")
    return f'<ul class="cs-check">{"".join(lis)}</ul>'


def card_html(title: str, subtitle: str, body: str = "", checks: list[str] | None = None, active: bool = False) -> str:
    """Triage/Prehab/Rehab 카드 모양: 고리 아이콘 + 제목 + 보라 부제 + 설명 + 체크 목록."""
    check_part = ""
    if checks:
        check_part = '<ul class="cs-check">' + "".join(
            f"<li>{CHECK}<span>{_e(c)}</span></li>" for c in checks
        ) + "</ul>"
    body_part = f'<div class="body">{_e(body)}</div>' if body else ""
    return (
        f'<div class="cs-card{" active" if active else ""}">'
        f'<div class="head">{RING}{_e(title)}</div>'
        f'<div class="sub">{_e(subtitle)}</div>{body_part}{check_part}</div>'
    )


def cards_html(cards: list[str]) -> str:
    return f'<div class="cs-cards">{"".join(cards)}</div>'


def trust_html(items: list[str]) -> str:
    """'HIPAA Compliant' 줄처럼 원형 체크 + 굵은 글자를 가로로 나열한다."""
    return '<div class="cs-trust">' + "".join(f"<span>{CHECK}{_e(t)}</span>" for t in items) + "</div>"


def quotes_html(themes: list[dict]) -> str:
    """주제별 대표 응답."""
    out = []
    for t in themes:
        out.append(f'<div class="cs-quote-title">{_e(t["theme"])} · {t["count"]}건</div>')
        out += [f'<div class="cs-quote">“{_e(e)}”</div>' for e in t["examples"]]
    return "".join(out)
