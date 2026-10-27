# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A **training survey results dashboard** (교육 결과보고 대시보드) built with Python, Streamlit, and the OpenAI, Gemini, or Claude API. You upload survey raw data (Excel/CSV) and get metric scores, a year-over-year comparison, an AI summary of the free-text answers, and a Word/Markdown report draft. All features in the PRD are implemented and have been reviewed end to end.

- `PRD.md` is the source of truth for requirements (F1–F7, metric formulas, layout, AI output schema §7.4, acceptance criteria §11). Read the relevant section before changing behavior, and update the PRD in the same change when behavior changes.
- `현대제철_AI_Agent_문제정의서_임재혁 매니저.docx` is the original problem statement. The PRD supersedes it.
- `26년 재무제표이해 만족도결과 로데이터.xlsx` is **real survey data with real employee IDs and names. Never print, log, or copy those values.** When inspecting it, skip P1B2/P1B3 and the first two ID columns. Build test and edge-case files from `samples/25년_가상_작년데이터.xlsx` instead, which has dummy IDs and names.
- Real API status:
  - Gemini: the full app flow succeeded end to end with a made-up 12-response CSV (~5 s on `gemini-3.5-flash-lite`). Larger models (`gemini-3.8-flash`, 3.7, 3.6) were often 503 (overloaded) or 504 (~60 s timeout), which is why lite is the default.
  - OpenAI: the key authenticated but had no credits (`insufficient_quota`).
  - Claude: never called for real.
  - Only send made-up text when testing real APIs. Don't send survey content without the user's go-ahead.

The user communicates in Korean. UI text, reports, and AI output are Korean.

## Commands

```bash
pip install -r requirements.txt
streamlit run app.py
python -m pytest -q                                          # all tests (no network; AI uses a fake client)
python -m pytest tests/test_compare.py::test_delta_labels   # single test
python scripts/verify_metrics.py [file]   # recompute metrics from raw codes independently of core/; also checks for ID/name leaks. Exit 1 on failure
python scripts/make_fake_last_year.py     # regenerate samples/25년_가상_작년데이터.xlsx (dummy IDs/names, lowered scores)
```

- `대시보드 실행.bat` is the double-click launcher for the user. It installs `requirements.txt` if packages are missing, then runs Streamlit on port 8501. The file is UTF-8 with CRLF line endings and uses `chcp 65001`, so keep that encoding if you edit it.
- On Windows, set `PYTHONIOENCODING=utf-8` when running Python from Bash, or the Korean output breaks.
- Streamlit doesn't reliably reload edited `core/` modules. Restart the server after changing them (`app.py` edits apply on rerun).
- Settings are read from `.streamlit/secrets.toml` first, then from environment variables:
  - The first of `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` that is set.
  - `OPENAI_MODEL` (default `gpt-5-mini`), `GEMINI_MODEL` (default `gemini-3.5-flash-lite`), `CLAUDE_MODEL` (default `claude-opus-5-5`).
  - The provider comes from the key format (`detect_provider`: `sk-ant-` → anthropic, other `sk-` → openai, `AIza`/`AQ.` → gemini).
  - The app must stay fully usable without a key.
  - Streamlit copies root-level secrets into `os.environ`, so an empty `ANTHROPIC_API_KEY = ""` in `secrets.toml` overwrites a real environment variable. Leave the line commented out when there is no key.
  - A key in an unknown format is rejected in `app.py` with a message, and nothing is sent.

## Architecture

Pipeline: upload → `core/loader.py` → `core/metrics.py` → `core/charts.py` / `core/ai_summary.py` / `core/report.py` → `app.py`. Everything under `core/` is pure Python with no Streamlit dependency, and `app.py` is the only UI layer.

**Loading (`core/loader.py`, `config.py`)**
- `config.QUESTIONS` defines every field: codes, keywords, `exclude` words, and scale. Mapping matches by code first, then by keyword in `QUESTIONS` order, and each column is used once. Order and `exclude` matter: the NPS question text contains "난이도", and the 강의자료 text contains "업무에 도움". `config.METRICS` defines the metric composition.
- Header detection: a 3-row survey-system header (code / text / sub-label), a 1-row header, or a code-only 1-row header. The last is recognized by numeric values under the score codes (`_is_data_row`).
- Whitelist: only mapped columns survive, renamed to `QUESTIONS` keys. Multi-column text becomes `feedback_1`, `feedback_2` (use `text_columns()`).
- The order inside `load_survey` matters:
  1. Drop ID columns (`privacy.deidentify`).
  2. Normalize course names.
  3. Apply the eligibility filter (`meta["ineligible_by_course"]`).
  4. Coerce scores and set out-of-range values to NaN.
  5. Mask free text with the respondent-name list, then discard the list.
- Manual mapping: `load_survey(data, name, overrides={field: col_index})`.
  - It applies only to fields auto-mapping missed. It never applies to columns already used or to ID-like headers (`config.ID_HEADER_HINT`).
  - `meta["unassigned"]` holds the choosable columns as `(index, "F열 · 문항 원문")` pairs. `meta["manual"]` lists the fields that were applied.
  - A file with no score columns loads without error, so the user can map columns manually.
- `SurveyData` is cached by `st.cache_data` (pickled), so it must never hold identifiers.

**Metrics (`core/metrics.py`)**
- Composite metrics are the mean of item means. NPS = %(9–10) − %(0–6).
- `compare()` returns `Delta` objects keyed by metric name or item key. `Delta.label()` gives `▲ 0.12` / `▼ 8.3pt` / `– 0.00` (flat when |diff| < 0.01).
- `metrics_table()` has a `key` column. Drop it before display.
- Course matching (`normalize_course`) strips year tokens, whitespace, and symbols. When there is no match, the user picks the course manually.

**AI (`core/ai_summary.py`)**
- `summarize(..., provider="openai" | "gemini" | "anthropic")` makes one call for all three free-text questions. Both providers get the same system prompt, user prompt, and `OUTPUT_SCHEMA`.
  - OpenAI: `chat.completions.create` with `response_format` json_schema `strict`, and `max_completion_tokens`.
  - Gemini (`google-genai`): `models.generate_content` with `config.response_json_schema` and `response_mime_type=application/json`, with `thinking_level: low` on non-2.x models, through `http_options` (timeout 60000 ms, 1 attempt). On 500/503/504 or a timeout, it falls back through `config.GEMINI_FALLBACK_MODELS` (`AIOverloaded`). `result["model"]` records the model that answered, and the UI shows it.
  - Anthropic: `beta.messages.create` with `output_config.format`, effort `medium`, and `fallbacks: "default"`.
  - Both use `timeout=120` and `max_retries=1`. SDK exceptions are translated in `_to_ai_error`. Out-of-credit errors (OpenAI 429 `insufficient_quota`, Anthropic 400 credit balance, Gemini 429 quota/billing) map to `CREDIT_MESSAGE`.
- On a parse failure it retries the JSON request once. It does not resend a truncated response (`max_tokens` / `finish_reason == "length"` / Gemini `MAX_TOKENS`).
- Claude returns only response **ids** (classification, theme membership, wanted-training topics). `postprocess()` computes counts and quotes the original text by id, deduplicating identical answers, so counts and quotes can't be hallucinated (PRD §7.4).
- `build_request()` is the single place outbound content is built, and the privacy tests check it.
- `prepare_texts()` only filters meaningless answers (≤1 char, "없음" variants) and deduplicates within a row. Masking has already happened in the loader.

**Report (`core/report.py`)**: `build_blocks()` builds the content once, and `build_docx` / `build_markdown` only format it. Without AI results, section 4 lists the de-identified raw answers.

**UI (`app.py`)**
- Order: landing → header → KPI cards (score, delta, n or "데이터 없음") → score chart → distribution | NPS → AI insights/tabs → raw answers → downloads.
- `load_upload()` loads each file twice: auto-mapped, then with manual overrides. Both are cached. Manual-mapping selections live in `st.session_state` keyed `map::{current|previous}::{file_id}::{field}`.
- The app stops early with the mapping UI still visible when there are 0 eligible rows or no score columns (`stop_with_mapping`).
- AI: `run_ai` caches successes only. Failures go to `st.session_state["ai_failures"]` and are retried only through the "AI 분석 다시 시도" button, so reruns don't re-hit the API.
- Download buttons render first into an `st.empty()` placeholder (pending phase) and are replaced once AI finishes. Both phases must write the same element structure (one caption each), or pending-phase elements linger.
- Look and feel (`ui_theme.py`, `.streamlit/config.toml`): the app follows the CareSpace-style design in `디자인/`.
  - Light-only theme: purple frame around a cream panel, deep-purple ink, purple→magenta pill buttons, Pretendard web font. Dark mode was dropped on purpose.
  - `ui_theme.py` holds the global CSS (injected with `st.html(ui.CSS)`) and pure functions that return HTML strings (hero, headline number + stat row, NPS gauge, cards, check lists, quotes).
  - Every dynamic string goes through `html.escape` there (`tests/test_ui_theme.py`).
  - `st.html` strips inline `<svg>`, so icons and decorations (check, ring, joint dots, info) are CSS backgrounds with data-URI SVGs (`*_URI` constants and the `.cs-ico` classes).
  - The CSS targets Streamlit internals (`stMainBlockContainer`, `stBaseButton-primary`, …), so re-check in the browser after Streamlit upgrades.
  - Don't override `font-family` on `[class*="st-"]`. That breaks the Material icon font (uploader buttons render "uploadUpload").
- Chart data colors live only in `config.COLORS` / `SCORE_COLORS`, which were validated with the dataviz `validate_palette.js` against the cream surface `#F7F4EE`. The low-contrast orange and gray segments rely on in-bar % labels, hover, and the score table. Charts use transparent backgrounds and the `COLORS["ink"]` text color. Charts with a legend need top margin (`_layout` adds it).
## Survey file format (verified against the sample)

- Sheet `all responses` (the `index` sheet holds metadata). Row 1 is the code, row 2 the question text, row 3 the sub-label (instructor name, `1 ~ 5`, `0 ~ 10`, or `응답`). Data starts at row 4.
- Codes: P1B2 employee ID, P1B3 name, P2B2 course. P2B4–P2B7 and P3B2–P3B4 use a 1–5 scale. **P3B5 (knowledge) and P3B6 (NPS) use a 0–10 scale.** Free text: P2B8+P2B9 (one instructor-feedback question split into two columns, merged), P3B7, P3B8.
- The last column is `답변 적격성`. Only `적격` rows count (63 in the sample). The first two columns are respondent and answer IDs, followed by start and end timestamps.
- Question text contains the typo `난의도`, so keywords must cover it. Instructor names in sub-labels are not PII and may be displayed.

## Privacy invariants (PRD F7)

- ID and name columns are dropped right after reading. The name list is used for masking inside `load_survey()` and never leaves it.
- Free-text masking: 6–8 digit numbers become `[ID]`, and respondent names become `○○○`.
  - Exception: numbers followed by `원` or `만원` (amounts) stay as-is.
  - Known trade-off: an ID immediately followed by a word starting with 원 (e.g. `2019496원천징수`) is not masked.
- Any user- or AI-supplied text shown through `st.markdown` / `st.caption` / `st.header` must go through `core.markdown.md_escape`. It blocks links, images, headings, `:color[]`, and GFM autolinks; autolinks are broken with a zero-width space, because backslash escapes alone don't stop them.
- Uploaded files are never written to disk. Raw responses are never logged. `.streamlit/config.toml` disables usage stats.
- Tests that use real PII compare **counts** only (`conftest.count_leaks`), so a failure never prints names or IDs. Keep this pattern.

## Verifying UI changes

Unit tests don't cover rendering (markdown escaping, placeholders, and theming have all broken while the tests passed), so check UI changes in a browser with Playwright:

- Run `streamlit run app.py --server.headless true --server.port 8599`, then upload with `page.locator('[data-testid="stSidebar"] input[type=file]').nth(0|1).setInputFiles(...)`. Upload files must sit inside the project folder (Playwright's allowed root), so put temporary files in a dotted folder such as `.review_tmp/` and delete it afterward, along with `.playwright-mcp/`.
- The main content scrolls inside Streamlit, so `fullPage` screenshots don't capture the whole page. Enlarge the viewport and crop instead.
- To test the AI failure path without sending data out, set a dummy `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL=http://127.0.0.1:9`. With `ANTHROPIC_LOG=info`, each call logs one `Retrying request` line, so the call count can be read from the server log.
- To preview the AI result UI without a key, run a scratch script that replaces `core.ai_summary.summarize` with a fake and then runs `app.py` with `runpy`. Don't add preview code to the project.
