"""Streamlit UI. Uploaded tables stay in the current application session."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from privacy_workbench import __version__
from privacy_workbench.detection import LABELS, apply_redactions, mask_value, scan_dataframe
from privacy_workbench.files import export_csv, read_dataset
from privacy_workbench.reporting import build_report


ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="隐私体检台 · Privacy Workbench", page_icon="◈", layout="wide")
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
    st.markdown('<div class="side-brand">◈ 隐私体检台</div>', unsafe_allow_html=True)
    st.caption(f"PRIVACY WORKBENCH / {__version__}")
    st.divider()
    st.markdown("**01　选择数据**")
    source = st.radio("数据来源", ["合成样例", "上传文件"], label_visibility="collapsed", key="source")
    upload = None
    if source == "上传文件":
        upload = st.file_uploader("CSV / Excel", type=["csv", "xlsx"], max_upload_size=5, key="upload")
        st.caption("首行是唯一列名。XLSX 读取首个工作表。")
    else:
        st.caption("6 条合成记录，含一个订单号误报和一个无效校验位示例。")
    st.markdown("**02　检查范围**")
    selected_labels = st.multiselect("识别规则", list(LABELS.values()), default=list(LABELS.values()), key="rules")
    enabled = {kind for kind, label in LABELS.items() if label in selected_labels}
    st.markdown("**03　处理方式**")
    strategy = st.radio("脱敏方式", ["掩码", "移除片段"], label_visibility="collapsed", key="strategy")
    mode = "mask" if strategy == "掩码" else "redact"
    st.caption("掩码保留部分特征；移除片段替换为「[已删除]」。")
    scan_clicked = st.button("开始检查", type="primary", width="stretch", disabled=not enabled, key="scan")
    st.divider()
    st.caption("最多 5 MB · 20,000 行 · 50 列\n\n最多 100,000 个数据单元格。")
    st.caption("文件在当前应用会话内处理，不调用外部模型，不自动保存上传文件。")

st.markdown("""
<div class="hero">
  <div class="eyebrow">DATA PRIVACY / INSPECT · REVIEW · REDACT</div>
  <h1>让数据分享，多一道确认。</h1>
  <p>识别候选，核对误报，再导出需要分享的版本。每一次处理，都有记录可查。</p>
  <span class="badge">手机号</span><span class="badge">电子邮箱</span><span class="badge">18 位身份证候选</span>
</div>
""", unsafe_allow_html=True)

if source == "上传文件" and upload is None:
    st.info("从左侧上传 CSV / XLSX，或切换到合成样例体验完整流程。")
    st.stop()

data = (ROOT / "sample_data" / "demo.csv").read_bytes() if source == "合成样例" else upload.getvalue()
filename = "合成演示数据.csv" if source == "合成样例" else upload.name
try:
    frame = read_dataset(data, filename)
except ValueError as error:
    st.error(str(error))
    st.stop()

fingerprint = hashlib.sha256(data + json.dumps(sorted(enabled)).encode()).hexdigest()
if st.session_state.get("active_fingerprint") != fingerprint:
    for state_key in list(st.session_state):
        if state_key.startswith("review_") or state_key in {"findings", "scan_revision"}:
            del st.session_state[state_key]
    st.session_state.active_fingerprint = fingerprint

st.caption(f"当前文件：{filename}　·　{len(frame):,} 行 × {len(frame.columns)} 列　·　首行为表头")
if scan_clicked:
    try:
        st.session_state.findings = scan_dataframe(frame, enabled)
        st.session_state.scan_revision = st.session_state.get("scan_revision", 0) + 1
    except ValueError as error:
        st.error(str(error))
        st.stop()

if "findings" not in st.session_state:
    st.info("点击左侧「开始检查」。系统会列出候选，你可以取消误报后再导出。")
    if st.checkbox("查看原始数据（可能包含敏感内容）", key="raw_before_scan"):
        st.dataframe(frame.head(100), hide_index=True, width="stretch")
    st.stop()

findings = st.session_state.findings
metrics = st.columns(4, gap="small")
metrics[0].metric("数据记录", f"{len(frame):,}")
metrics[1].metric("识别候选", f"{len(findings):,}")
processed_metric = metrics[2].empty()
retained_metric = metrics[3].empty()

st.markdown('<div class="section-label">01 / HUMAN REVIEW</div>', unsafe_allow_html=True)
left, right = st.columns([2.8, 1], gap="large")
with left:
    st.subheader("复核候选")
    st.caption("取消「处理」即可保留原值。内容默认展示掩码；可在下方按需查看原始表格。")
    selected_ids = set()
    if findings:
        review = pd.DataFrame([{
            "处理": f.recommended, "数据行": f.row + 1, "字段": str(frame.columns[f.column_index]),
            "类型": LABELS[f.kind], "内容预览": mask_value(f.kind, f.value),
            "校验与说明": f.reason, "_id": f.id,
        } for f in findings])
        edited = st.data_editor(
            review, hide_index=True, num_rows="fixed", width="stretch",
            height=min(430, max(210, 38 + 35 * len(review))),
            disabled=[name for name in review.columns if name != "处理"],
            column_config={
                "_id": None,
                "处理": st.column_config.CheckboxColumn("处理", width="small"),
                "数据行": st.column_config.NumberColumn("数据行", width="small", format="%d"),
                "内容预览": st.column_config.TextColumn("内容预览", width="medium"),
                "校验与说明": st.column_config.TextColumn("校验与说明", width="large"),
            },
            key=f"review_{fingerprint[:12]}_{st.session_state.scan_revision}",
        )
        selected_ids = set(edited.loc[edited["处理"].astype(bool), "_id"])
    else:
        st.success("本次未发现所选规则的候选。其他类型的信息仍需结合用途检查。")

processed = apply_redactions(frame, findings, selected_ids, mode)
report = build_report(frame, findings, selected_ids, mode)
retained = len(findings) - len(selected_ids)
processed_metric.metric("本次处理", f"{len(selected_ids):,}")
retained_metric.metric("保留候选", f"{retained:,}")

with right:
    st.subheader("处理摘要")
    st.caption("当前方式")
    st.write(f"**{strategy}** · {report['summary']['affected_cells']} 个单元格")
    for kind, label in LABELS.items():
        count = sum(f.kind == kind for f in findings)
        st.write(f"{label}　**{count}**")
    if retained:
        st.warning(f"有 {retained} 个候选保留原值。导出前请确认这是你的复核选择。")
    else:
        st.caption("已选择处理本次识别的全部候选。")
    st.download_button("↓ 下载处理后 CSV", data=export_csv(processed), file_name="redacted_data.csv", mime="text/csv", width="stretch", type="primary", key="download_csv")
    st.download_button("↓ 下载检查报告 JSON", data=json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"), file_name="privacy_report.json", mime="application/json", width="stretch", key="download_report")
    st.caption("CSV 对公式起始字符加文本前缀。报告不复制原始完整命中值，掩码仍保留部分特征。")

st.markdown('<div class="section-label">02 / BEFORE & AFTER</div>', unsafe_allow_html=True)
st.subheader("检查处理结果")
show_original = st.checkbox("显示原始数据（可能包含敏感内容）", key="show_original")
if show_original:
    before, after = st.columns(2)
    with before:
        st.caption("处理前 · 前 100 条")
        st.dataframe(frame.head(100), hide_index=True, width="stretch")
    with after:
        st.caption("处理后 · 前 100 条")
        st.dataframe(processed.head(100), hide_index=True, width="stretch")
else:
    st.caption("处理后预览 · 前 100 条。未勾选的候选会在这里保留原值。")
    st.dataframe(processed.head(100), hide_index=True, width="stretch")

with st.expander("识别范围与使用说明"):
    st.markdown("""
- **手机号**：中国大陆 11 位手机号格式，支持前置 `86` / `+86`；订单号也可能命中，需要复核。
- **邮箱**：常见 ASCII 邮箱格式。掩码保留域名，不代表完成匿名化。
- **身份证候选**：18 位结构，核验日期与校验位；未核验行政区、签发记录或真实身份。无效项默认不勾选。
- 本版不识别所有姓名、地址、银行卡号、图片或其他敏感信息。候选为零不等于不存在敏感信息。
- XLSX 读取首个工作表。文本编号保留前导零；Excel 已按数值存储而丢失的精度无法恢复。
- 掩码与移除只作用于勾选的命中片段，不删除整行、整列，也不改变其他内容。
""")

st.markdown('<div class="footnote">PRIVACY WORKBENCH · v0.1.0<br>基于 awesome-llm-apps 上传示例二次开发 · 无模型调用 · 无自动上传文件落盘</div>', unsafe_allow_html=True)
