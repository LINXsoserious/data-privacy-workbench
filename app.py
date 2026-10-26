"""Streamlit UI. Uploaded tables stay in the current application session."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from privacy_workbench import __version__
from privacy_workbench.detection import LABELS, apply_redactions, mask_value, scan_dataframe
from privacy_workbench.files import export_csv, read_dataset
from privacy_workbench.i18n import labels, localize_reason, normalize_lang, translate
from privacy_workbench.reporting import build_report


ROOT = Path(__file__).resolve().parent
SOURCE_OPTIONS = ["合成样例", "上传文件"]
STRATEGY_OPTIONS = ["掩码", "移除片段"]


def _option_widget_key(name: str, locale: str) -> str:
    # Keep the existing Chinese keys for callers, and remount translated choices.
    return name if locale == "zh" else f"{name}_en"


def _prepare_option_state(locale: str) -> None:
    """Separate canonical choices from frontend widgets' formatted string values."""
    previous_locale = st.session_state.get("settings_widget_locale", "zh")
    defaults = {"source": SOURCE_OPTIONS[0], "rules": list(LABELS.values()), "strategy": STRATEGY_OPTIONS[0]}
    for name, default in defaults.items():
        previous_key = _option_widget_key(name, previous_locale)
        saved_key = f"settings_{name}"
        value = st.session_state.get(previous_key, st.session_state.get(saved_key, default))
        st.session_state[saved_key] = list(value) if isinstance(value, list) else value
        next_key = _option_widget_key(name, locale)
        if previous_locale != locale or next_key not in st.session_state:
            # Explicitly seed the new display widget so Streamlit sends set_value
            # with translated raw strings, overriding any stale frontend value.
            st.session_state[next_key] = list(value) if isinstance(value, list) else value
    st.session_state.settings_widget_locale = locale


def _capture_review_selection() -> None:
    """Persist editor decisions before a language change remounts its display."""
    editor_key = st.session_state.get("review_active_editor")
    if not editor_key or editor_key not in st.session_state:
        return
    editor_state = st.session_state[editor_key]
    selected = set(st.session_state.get("review_base_ids", set()))
    finding_ids = st.session_state.get("review_finding_ids", [])
    for row, changes in editor_state.get("edited_rows", {}).items():
        index = int(row)
        if 0 <= index < len(finding_ids) and "process" in changes:
            if changes["process"]:
                selected.add(finding_ids[index])
            else:
                selected.discard(finding_ids[index])
    st.session_state.review_selected_ids = selected


_capture_review_selection()
lang = normalize_lang(st.session_state.get("ui_language", "简体中文"))
_prepare_option_state(lang)


def t(key: str, **values) -> str:
    return translate(key, lang, **values)


st.set_page_config(page_title=t("page_title"), page_icon="◈", layout="wide")
st.markdown("""
<style>
:root {--ink:#203b35; --accent:#227a65; --paper:#f7f8f3; --muted:#687a70;}
.stApp {background:var(--paper); color:var(--ink);}
.block-container {max-width:1280px; padding-top:2.8rem; padding-bottom:3rem;}
[data-testid="stSidebar"] {background:#eaf0e9; border-right:1px solid #d8e3d7;}
[data-testid="stSidebar"] .block-container {padding-top:2rem;}
h1,h2,h3 {color:var(--ink); letter-spacing:-.02em;}
.hero {border-bottom:1px solid #cfdbcf; padding:0 0 25px; margin-bottom:25px;}
.eyebrow {font:12px 'Cascadia Code',Consolas,monospace; letter-spacing:.15em; color:#547464; margin-bottom:15px;}
.hero h1 {font-family:Georgia,'Noto Serif CJK SC','SimSun',serif; font-size:42px; font-weight:600; margin:0 0 14px; line-height:1.25;}
.hero p {font-size:15px; color:#687a70; margin:0; line-height:1.8;}
.badge {display:inline-block; border:1px solid #c3d5c6; background:#eff5ee; border-radius:4px; padding:4px 9px; margin:14px 7px 0 0; font-size:11px; color:#365e4d;}
[data-testid="stMetric"] {background:#fffef9; border:1px solid #dce4d9; border-top:3px solid #55886e; border-radius:5px; padding:16px 18px;}
[data-testid="stMetricLabel"] {color:#65786c; font-size:12px;}
[data-testid="stMetricValue"] {font-family:Georgia,'Cascadia Code',serif; color:#264b3e;}
.section-label {font:11px 'Cascadia Code',Consolas,monospace; letter-spacing:.12em; color:#6a8170; margin:25px 0 7px;}
.side-brand {font:600 23px Georgia,'SimSun',serif; color:#244e3e; padding-bottom:8px;}
.footnote {border-top:1px solid #d5e0d3; padding-top:18px; margin-top:32px; font-size:11px; color:#718172; line-height:1.9;}
.stButton button,.stDownloadButton button {border-radius:5px; min-height:42px; font-weight:500;}
[data-testid="stDataFrame"],[data-testid="stDataEditor"] {border-radius:5px;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.selectbox(t("language"), ["简体中文", "English"], key="ui_language")
    st.markdown(f'<div class="side-brand">◈ {t("brand")}</div>', unsafe_allow_html=True)
    st.caption(f"PRIVACY WORKBENCH / {__version__}")
    st.divider()
    st.markdown(f'**{t("choose_data")}**')
    source = st.radio(
        t("source"), SOURCE_OPTIONS, label_visibility="collapsed", key=_option_widget_key("source", lang),
        format_func=lambda value: t("source_demo" if value == "合成样例" else "source_upload"),
    )
    st.session_state.settings_source = source
    upload = None
    if source == "上传文件":
        upload = st.file_uploader("CSV / Excel", type=["csv", "xlsx"], max_upload_size=5, key="upload")
        st.caption(t("upload_hint"))
    else:
        st.caption(t("demo_hint"))
    st.markdown(f'**{t("check_scope")}**')
    selected_labels = st.multiselect(
        t("rules"), list(LABELS.values()),
        key=_option_widget_key("rules", lang),
        format_func=lambda value: labels(lang)[next(kind for kind, label in LABELS.items() if label == value)],
    )
    st.session_state.settings_rules = list(selected_labels)
    enabled = {kind for kind, label in LABELS.items() if label in selected_labels}
    st.markdown(f'**{t("treatment")}**')
    strategy = st.radio(
        t("strategy"), STRATEGY_OPTIONS, label_visibility="collapsed", key=_option_widget_key("strategy", lang),
        format_func=lambda value: t("mask" if value == "掩码" else "redact"),
    )
    st.session_state.settings_strategy = strategy
    mode = "mask" if strategy == "掩码" else "redact"
    strategy_label = t(mode)
    st.caption(t("strategy_hint"))
    scan_clicked = st.button(t("scan"), type="primary", width="stretch", disabled=not enabled, key="scan")
    st.divider()
    st.caption(t("limits"))
    st.caption(t("session_hint"))
    st.caption(t("language_hint"))

st.markdown(f"""
<div class="hero">
  <div class="eyebrow">DATA PRIVACY / INSPECT · REVIEW · REDACT</div>
  <h1>{t("hero_title")}</h1>
  <p>{t("hero_description")}</p>
  <span class="badge">{t("phone")}</span><span class="badge">{t("email")}</span><span class="badge">{t("id_card")}</span>
</div>
""", unsafe_allow_html=True)

if source == "上传文件" and upload is None:
    st.info(t("upload_prompt"))
    st.stop()

data = (ROOT / "sample_data" / "demo.csv").read_bytes() if source == "合成样例" else upload.getvalue()
filename = t("demo_filename") if source == "合成样例" else upload.name
try:
    frame = read_dataset(data, filename, lang=lang)
except ValueError as error:
    st.error(str(error))
    st.stop()

fingerprint = hashlib.sha256(data + json.dumps(sorted(enabled)).encode()).hexdigest()
if st.session_state.get("active_fingerprint") != fingerprint:
    for state_key in list(st.session_state):
        if state_key.startswith("review_") or state_key in {"findings", "scan_revision"}:
            del st.session_state[state_key]
    st.session_state.active_fingerprint = fingerprint

st.caption(t("current_file", filename=filename, rows=len(frame), columns=len(frame.columns)))
if scan_clicked:
    try:
        st.session_state.findings = scan_dataframe(frame, enabled, lang=lang)
        st.session_state.scan_revision = st.session_state.get("scan_revision", 0) + 1
        st.session_state.review_selected_ids = {f.id for f in st.session_state.findings if f.recommended}
    except ValueError as error:
        st.error(str(error))
        st.stop()

if "findings" not in st.session_state:
    st.info(t("scan_prompt"))
    if st.checkbox(t("view_raw"), key="raw_before_scan"):
        st.dataframe(frame.head(100), hide_index=True, width="stretch")
    st.stop()

findings = st.session_state.findings
display_labels = labels(lang)
metrics = st.columns(4, gap="small")
metrics[0].metric(t("rows"), f"{len(frame):,}")
metrics[1].metric(t("candidates"), f"{len(findings):,}")
processed_metric = metrics[2].empty()
retained_metric = metrics[3].empty()

st.markdown('<div class="section-label">01 / HUMAN REVIEW</div>', unsafe_allow_html=True)
left, right = st.columns([2.8, 1], gap="large")
with left:
    st.subheader(t("review_title"))
    st.caption(t("review_hint"))
    selected_ids = set(st.session_state.get("review_selected_ids", {f.id for f in findings if f.recommended}))
    if findings:
        editor_key = f"review_{fingerprint[:12]}_{st.session_state.scan_revision}_{lang}"
        if st.session_state.get("review_active_editor") != editor_key:
            # Display changes get a fresh editor whose starting values are the saved decisions.
            # Keep that baseline fixed during subsequent edits to prevent toggling values back.
            st.session_state.review_active_editor = editor_key
            st.session_state.review_base_ids = selected_ids.copy()
            st.session_state.review_finding_ids = [f.id for f in findings]
            if editor_key in st.session_state:
                del st.session_state[editor_key]
        baseline = st.session_state.review_base_ids
        review = pd.DataFrame([{
            "process": f.id in baseline, "data_row": f.row + 1, "field": str(frame.columns[f.column_index]),
            "category": display_labels[f.kind], "preview": mask_value(f.kind, f.value),
            "rule_check": localize_reason(f.reason, lang), "_id": f.id,
        } for f in findings])
        edited = st.data_editor(
            review, hide_index=True, num_rows="fixed", width="stretch",
            height=min(430, max(210, 38 + 35 * len(review))),
            disabled=[name for name in review.columns if name != "process"],
            column_config={
                "_id": None,
                "process": st.column_config.CheckboxColumn(t("process"), width="small"),
                "data_row": st.column_config.NumberColumn(t("data_row"), width="small", format="%d"),
                "field": st.column_config.TextColumn(t("field")),
                "category": st.column_config.TextColumn(t("category")),
                "preview": st.column_config.TextColumn(t("preview"), width="medium"),
                "rule_check": st.column_config.TextColumn(t("rule_check"), width="large"),
            },
            key=editor_key,
        )
        selected_ids = set(edited.loc[edited["process"].astype(bool), "_id"])
        st.session_state.review_selected_ids = selected_ids
    else:
        st.success(t("no_findings"))

processed = apply_redactions(frame, findings, selected_ids, mode, lang=lang)
report = build_report(frame, findings, selected_ids, mode, lang=lang)
retained = len(findings) - len(selected_ids)
processed_metric.metric(t("processed"), f"{len(selected_ids):,}")
retained_metric.metric(t("retained"), f"{retained:,}")

with right:
    st.subheader(t("summary_title"))
    st.caption(t("current_mode"))
    st.write(t("affected_cells", strategy=strategy_label, count=report['summary']['affected_cells']))
    for kind, label in display_labels.items():
        count = sum(f.kind == kind for f in findings)
        st.write(f"{label}　**{count}**")
    if retained:
        st.warning(t("retained_warning", count=retained))
    else:
        st.caption(t("all_selected"))
    st.download_button(t("download_csv"), data=export_csv(processed), file_name="redacted_data.csv", mime="text/csv", width="stretch", type="primary", key="download_csv")
    st.download_button(t("download_report"), data=json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"), file_name="privacy_report.json", mime="application/json", width="stretch", key="download_report")
    st.caption(t("export_hint"))

st.markdown('<div class="section-label">02 / BEFORE & AFTER</div>', unsafe_allow_html=True)
st.subheader(t("result_title"))
show_original = st.checkbox(t("show_original"), key="show_original")
if show_original:
    before, after = st.columns(2)
    with before:
        st.caption(t("before"))
        st.dataframe(frame.head(100), hide_index=True, width="stretch")
    with after:
        st.caption(t("after"))
        st.dataframe(processed.head(100), hide_index=True, width="stretch")
else:
    st.caption(t("after_hint"))
    st.dataframe(processed.head(100), hide_index=True, width="stretch")

with st.expander(t("instructions")):
    st.markdown(t("scope_text"))

st.markdown(f'<div class="footnote">PRIVACY WORKBENCH · v{__version__}<br>{t("footer")}</div>', unsafe_allow_html=True)
