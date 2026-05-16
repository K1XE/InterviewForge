#!/usr/bin/env python3
"""Render interview review_plan.json into a complete LaTeX report."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def tex_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return "".join(SPECIALS.get(ch, ch) for ch in text)


def tex_paragraph(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    parts = [tex_escape(p.strip()) for p in re.split(r"\n\s*\n", text) if p.strip()]
    return "\n\n".join(parts)


def tex_itemize(items: Any) -> str:
    if not items:
        return r"\begin{itemize}\item 未记录。\end{itemize}"
    if isinstance(items, str):
        items = [items]
    lines = [r"\begin{itemize}"]
    for item in items:
        lines.append(r"\item " + tex_paragraph(item))
    lines.append(r"\end{itemize}")
    return "\n".join(lines)


def ref_text(refs: Any) -> str:
    if not refs:
        return ""
    if isinstance(refs, str):
        refs = [refs]
    return " ".join(f"[{tex_escape(ref)}]" for ref in refs if str(ref).strip())


def answer_text(q: dict[str, Any]) -> str:
    return (
        q.get("my_answer_cleaned")
        or q.get("my_answer")
        or q.get("answer_cleaned")
        or q.get("answer_summary")
        or ""
    )


def tex_enumerate(items: Any) -> str:
    if not items:
        return r"\begin{enumerate}\item 未记录。\end{enumerate}"
    lines = [r"\begin{enumerate}"]
    for item in items:
        if isinstance(item, dict):
            day = item.get("day") or item.get("title") or "训练项"
            task = item.get("task") or item.get("content") or ""
            deliverable = item.get("deliverable") or ""
            text = rf"\textbf{{{tex_escape(day)}}}：{tex_paragraph(task)}"
            if deliverable:
                text += rf"\par \textbf{{产出}}：{tex_paragraph(deliverable)}"
            lines.append(r"\item " + text)
        else:
            lines.append(r"\item " + tex_paragraph(item))
    lines.append(r"\end{enumerate}")
    return "\n".join(lines)


def latex_block_formula(formula: str) -> str:
    formula = (formula or "").strip()
    if not formula:
        return ""
    return "\n\\[\n" + formula + "\n\\]\n"


def image_path(path: str) -> str:
    return r"\detokenize{" + path + "}"


def display_source_detail(src: dict[str, Any]) -> tuple[str, bool]:
    if src.get("url"):
        return str(src["url"]), True
    if src.get("citation"):
        return str(src["citation"]), False
    if src.get("artifact_id"):
        return str(src["artifact_id"]), False
    if src.get("event_id"):
        return str(src["event_id"]), False
    if src.get("path"):
        return Path(str(src["path"])).name, False
    return "", False


def render_evidence(evidence: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for item in evidence or []:
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        caption = tex_escape(item.get("caption") or item.get("reason") or "证据截图")
        time_range = tex_escape(item.get("time_range") or item.get("time") or "未记录")
        blocks.append(
            "\n".join(
                [
                    r"\begin{figure}[H]",
                    r"\centering",
                    rf"\includegraphics[width=0.92\textwidth,height=0.36\textheight,keepaspectratio]{{{image_path(path)}}}",
                    rf"\caption{{{caption}\protect\footnotemark}}",
                    r"\end{figure}",
                    rf"\footnotetext{{视频画面时间区间：{time_range}。若为裁剪图，时间区间仍对应原视频画面。}}",
                ]
            )
        )
    return "\n\n".join(blocks)


def render_dashboard_placeholder_list(items: Any) -> str:
    return tex_itemize(items)


def render_overview(plan: dict[str, Any]) -> str:
    overview = plan.get("overview") or []
    lines = [r"\section{面试概览}"]
    if isinstance(overview, list):
        lines.append(tex_itemize(overview))
    else:
        lines.append(tex_paragraph(overview))
    return "\n\n".join(lines)


def render_compact_summary(plan: dict[str, Any]) -> str:
    overview = plan.get("overview") or []
    lines = [r"\section{首页摘要}"]
    if isinstance(overview, list):
        lines.append(tex_itemize(overview))
    else:
        lines.append(tex_paragraph(overview))
    return "\n\n".join(lines)


def render_questions(plan: dict[str, Any]) -> str:
    lines = [r"\section{逐题复盘}"]
    for idx, q in enumerate(plan.get("questions") or [], start=1):
        time_range = tex_escape(q.get("time_range") or "??:??")
        title = tex_escape(q.get("title") or f"问题 {idx}")
        level = tex_escape(q.get("level") or "未评级")
        score = tex_escape(q.get("score") or "")
        header = rf"{idx}. {title} \hfill {time_range}"
        lines.extend(
            [
                rf"\begin{{questioncard}}{{{header}}}",
                rf"\scoretag{{{level}}}" + (rf" \risktag{{{score}}}" if score else ""),
                "",
                rf"\textbf{{面试官问题}}：{tex_paragraph(q.get('question'))}",
                "",
                rf"\textbf{{真正想验证什么}}：{tex_paragraph(q.get('intent'))}",
                "",
                rf"\textbf{{我的回答摘要}}：{tex_paragraph(q.get('answer_summary'))}",
                "",
                r"\textbf{扣分点}",
                tex_itemize(q.get("deductions") or []),
                "",
                r"\textbf{更优回答}",
            ]
        )
        better = q.get("better_answer") or {}
        lines.append(r"\begin{itemize}")
        lines.append(r"\item \textbf{30秒版}：" + tex_paragraph(better.get("30s") or better.get("short") or ""))
        lines.append(r"\item \textbf{深入版}：" + tex_paragraph(better.get("deep") or ""))
        lines.append(r"\item \textbf{被追问时展开版}：" + tex_paragraph(better.get("followup") or ""))
        lines.append(r"\end{itemize}")
        lines.append(r"\textbf{追问 drill}")
        lines.append(tex_itemize(q.get("drills") or []))
        evidence = render_evidence(q.get("evidence") or [])
        if evidence:
            lines.append(evidence)
        lines.append(r"\end{questioncard}")
    return "\n\n".join(lines)


def render_compact_questions(plan: dict[str, Any]) -> str:
    lines = [r"\section{面试官问题与我的回答}"]
    for idx, q in enumerate(plan.get("questions") or [], start=1):
        time_range = tex_escape(q.get("time_range") or "??:??")
        title = tex_escape(q.get("title") or f"问题 {idx}")
        header = rf"{idx}. {title} \hfill {time_range}"
        refs = ref_text(q.get("refs") or q.get("source_refs") or [])
        is_key = bool(q.get("is_key") or q.get("risk") == "high")
        importance = tex_escape(q.get("importance_label") or q.get("level") or ("key" if is_key else "covered"))
        quality = tex_escape(q.get("quality_label") or q.get("level") or "passable")
        score = tex_escape(q.get("score") or "")
        suggested = q.get("suggested_answer") or q.get("standard_answer") or ""
        comment = q.get("comment") or q.get("one_line_review") or ""
        source_window = q.get("answer_source_window") or ""
        tag_text = f"{quality} {score}".strip()
        lines.extend([rf"\begin{{questioncard}}{{{header}}}", rf"\scoretag{{{tag_text}}} \oktag{{{importance}}}", ""])
        lines.extend(
            [
                rf"\textbf{{面试官问题}}：{tex_paragraph(q.get('question_cleaned') or q.get('question'))}",
                "",
                rf"\textbf{{我的回答}}：{tex_paragraph(answer_text(q))}",
            ]
        )
        if source_window:
            lines.extend(["", rf"\textbf{{回答来源窗口}}：{tex_escape(source_window)}"])
        lines.extend(
            [
                "",
                rf"\textbf{{建议答案}}：{tex_paragraph(suggested)}",
                "",
                rf"\textbf{{来源}}：{refs or '来源不足，建议补材料'}",
            ]
        )
        if comment:
            lines.extend(["", rf"\textbf{{一句评价}}：{tex_paragraph(comment)}"])
        evidence = render_evidence(q.get("evidence") or [])
        if evidence:
            lines.append(evidence)
        lines.append(r"\end{questioncard}")
    return "\n\n".join(lines)


def render_key_followups(plan: dict[str, Any]) -> str:
    lines = [r"\section{重点追问复盘}"]
    key_questions = [q for q in plan.get("questions") or [] if q.get("is_key") or q.get("risk") == "high"]
    key_questions = key_questions[:8]
    if not key_questions:
        lines.append(tex_paragraph("本轮没有单独标出的高风险追问。"))
        return "\n\n".join(lines)
    for q in key_questions:
        title = tex_escape(q.get("title") or q.get("id") or "追问")
        refs = ref_text(q.get("refs") or q.get("source_refs") or [])
        lines.extend(
            [
                rf"\begin{{riskbox}}{{{title} \hfill {tex_escape(q.get('time_range') or '')}}}",
                rf"\textbf{{追问信号}}：{tex_paragraph(q.get('intent') or q.get('signal') or '')}",
                "",
                rf"\textbf{{关键扣分点}}：{tex_paragraph(q.get('comment') or '; '.join(q.get('deductions') or []))}",
                "",
                rf"\textbf{{下次一句话先答}}：{tex_paragraph(q.get('suggested_answer') or q.get('standard_answer') or '')}",
                "",
                rf"\textbf{{来源}}：{refs or '来源不足，建议补材料'}",
                r"\end{riskbox}",
            ]
        )
    return "\n\n".join(lines)


def render_technical(plan: dict[str, Any]) -> str:
    lines = [r"\section{高风险技术补课}"]
    for item in plan.get("technical_remediation") or []:
        topic = tex_escape(item.get("topic") or "技术点")
        risk = tex_paragraph(item.get("risk") or "")
        rule = tex_paragraph(item.get("rule") or "")
        lines.extend([rf"\begin{{riskbox}}{{{topic}}}", rf"\textbf{{风险}}：{risk}", "", rf"\textbf{{规则}}：{rule}"])
        formula = item.get("formula_latex") or ""
        if formula:
            lines.append(latex_block_formula(formula))
        symbols = item.get("symbols") or []
        if symbols:
            lines.append(r"\textbf{符号解释}")
            lines.append(tex_itemize(symbols))
        pitfalls = item.get("pitfalls") or []
        if pitfalls:
            lines.append(r"\textbf{面试避坑}")
            lines.append(tex_itemize(pitfalls))
        lines.append(r"\end{riskbox}")
        how = item.get("how_to_say") or ""
        if how:
            lines.extend([rf"\begin{{betterbox}}{{{topic}：面试中怎么说}}", tex_paragraph(how), r"\end{betterbox}"])
    return "\n\n".join(lines)


def render_compact_technical(plan: dict[str, Any]) -> str:
    lines = [r"\section{高风险技术点速记}"]
    for item in plan.get("technical_remediation") or []:
        topic = tex_escape(item.get("topic") or "技术点")
        refs = ref_text(item.get("refs") or item.get("source_refs") or [])
        rule = tex_paragraph(item.get("rule") or "")
        how = tex_paragraph(item.get("how_to_say") or item.get("suggested_answer") or "")
        lines.extend(
            [
                rf"\begin{{drillbox}}{{{topic}}}",
                rf"\textbf{{规则}}：{rule}",
            ]
        )
        formula = item.get("formula_latex") or ""
        if formula:
            lines.append(latex_block_formula(formula))
        if how:
            lines.extend(["", rf"\textbf{{面试说法}}：{how}"])
        lines.extend(["", rf"\textbf{{来源}}：{refs or '来源不足，建议补材料'}", r"\end{drillbox}"])
    return "\n\n".join(lines)


def render_project_templates(plan: dict[str, Any]) -> str:
    lines = [r"\section{项目答辩模板}"]
    for idx, item in enumerate(plan.get("project_defense_templates") or [], start=1):
        title = tex_escape(item.get("title") or f"模板 {idx}")
        lines.extend([rf"\begin{{betterbox}}{{{title}}}"])
        for key, label in [
            ("claim", "一句话 claim"),
            ("implementation", "实现细节"),
            ("metric", "证据/指标"),
            ("limitation", "限制"),
            ("followup", "被追问时展开"),
            ("answer", "可直接背的回答"),
        ]:
            if item.get(key):
                lines.append(rf"\textbf{{{label}}}：{tex_paragraph(item.get(key))}")
                lines.append("")
        lines.append(r"\end{betterbox}")
    return "\n\n".join(lines)


def render_coding(plan: dict[str, Any]) -> str:
    lines = [r"\section{代码题复盘}"]
    for idx, item in enumerate(plan.get("coding_reviews") or [], start=1):
        problem = tex_escape(item.get("problem") or f"代码题 {idx}")
        time_range = tex_escape(item.get("time_range") or "")
        lines.extend([rf"\begin{{codebox}}{{{problem} \hfill {time_range}}}"])
        for key, label in [
            ("observed_behavior", "现场表现"),
            ("mistakes", "扣分点"),
            ("interviewer_feedback", "面试官反馈"),
            ("invariant", "正确 invariant"),
            ("complexity", "复杂度"),
            ("next_script", "下一次口述稿"),
        ]:
            value = item.get(key)
            if not value:
                continue
            lines.append(rf"\textbf{{{label}}}")
            lines.append(tex_itemize(value) if isinstance(value, list) else tex_paragraph(value))
            lines.append("")
        code = item.get("standard_code") or ""
        if code:
            lines.extend([r"\textbf{标准代码}", r"\begin{lstlisting}[language=Python]", str(code).rstrip(), r"\end{lstlisting}"])
        lines.append(r"\end{codebox}")
        evidence = render_evidence(item.get("evidence") or [])
        if evidence:
            lines.append(evidence)
    return "\n\n".join(lines)


def render_compact_coding(plan: dict[str, Any]) -> str:
    lines = [r"\section{代码题复盘}"]
    for idx, item in enumerate(plan.get("coding_reviews") or [], start=1):
        problem = tex_escape(item.get("problem") or f"代码题 {idx}")
        time_range = tex_escape(item.get("time_range") or "")
        refs = ref_text(item.get("refs") or item.get("source_refs") or [])
        lines.extend([rf"\begin{{codebox}}{{{problem} \hfill {time_range}}}"])
        for key, label in [
            ("observed_behavior", "现场表现"),
            ("mistakes", "关键问题"),
            ("standard_approach", "标准思路"),
            ("complexity", "复杂度"),
            ("next_script", "下一次口述稿"),
        ]:
            value = item.get(key)
            if not value:
                continue
            lines.append(rf"\textbf{{{label}}}")
            lines.append(tex_itemize(value) if isinstance(value, list) else tex_paragraph(value))
            lines.append("")
        code = item.get("standard_code") or ""
        if code:
            lines.extend([r"\textbf{参考代码}", r"\begin{lstlisting}[language=Python]", str(code).rstrip(), r"\end{lstlisting}"])
        lines.append(rf"\textbf{{来源}}：{refs or '来源不足，建议补材料'}")
        lines.append(r"\end{codebox}")
        evidence = render_evidence(item.get("evidence") or [])
        if evidence:
            lines.append(evidence)
    return "\n\n".join(lines)


def render_training(plan: dict[str, Any]) -> str:
    return "\n\n".join([r"\section{7天训练计划}", tex_enumerate(plan.get("training_plan") or [])])


def render_appendix(plan: dict[str, Any]) -> str:
    appendix = plan.get("appendix") or {}
    lines = [r"\section{证据与转写说明}"]
    if isinstance(appendix, dict):
        if appendix.get("notes"):
            lines.append(tex_itemize(appendix.get("notes")))
        if appendix.get("artifacts"):
            lines.append(r"\begin{evidencebox}{交付物与本地路径}")
            lines.append(tex_itemize(appendix.get("artifacts")))
            lines.append(r"\end{evidencebox}")
        if appendix.get("limitations"):
            lines.append(r"\begin{riskbox}{限制与置信度}")
            lines.append(tex_itemize(appendix.get("limitations")))
            lines.append(r"\end{riskbox}")
    else:
        lines.append(tex_paragraph(appendix))
    return "\n\n".join(lines)


def render_sources(plan: dict[str, Any]) -> str:
    registry = plan.get("source_registry") or {}
    sources = registry.get("sources") if isinstance(registry, dict) else registry
    if not sources:
        sources = plan.get("sources") or []
    lines = [r"\section{参考来源}"]
    if not sources:
        lines.append(tex_paragraph("未登记来源。"))
        return "\n\n".join(lines)
    lines.append(r"\begin{enumerate}")
    question_titles = {
        str(q.get("id") or ""): str(q.get("question_cleaned") or q.get("question") or "").strip()
        for q in plan.get("questions") or []
        if isinstance(q, dict)
    }
    for src in sources:
        if not isinstance(src, dict):
            lines.append(r"\item " + tex_paragraph(src))
            continue
        sid = tex_escape(src.get("id") or "")
        detail, is_url = display_source_detail(src)
        event_id = str(src.get("event_id") or "")
        title_text = question_titles.get(event_id) or src.get("title") or src.get("artifact_id") or Path(str(src.get("path") or "")).name or src.get("url") or "来源"
        title = tex_escape(title_text)
        typ = tex_escape(src.get("type") or "source")
        accessed = tex_escape(src.get("accessed") or src.get("date") or "")
        suffix = rf"；访问日期：{accessed}" if accessed else ""
        rendered_detail = rf"\url{{{tex_escape(detail)}}}" if is_url else tex_escape(detail)
        lines.append(rf"\item [{sid}] \textbf{{{title}}}（{typ}）：{rendered_detail}{suffix}")
    lines.append(r"\end{enumerate}")
    return "\n".join(lines)


def render_learning_resources(plan: dict[str, Any]) -> str:
    resources = plan.get("learning_resources") or []
    lines = [r"\section{后续巩固资料}"]
    if not resources:
        lines.append(tex_paragraph("未登记后续巩固资料。"))
        return "\n\n".join(lines)

    lines.append(r"\begin{enumerate}")
    for item in resources:
        if not isinstance(item, dict):
            lines.append(r"\item " + tex_paragraph(item))
            continue
        topic = tex_escape(item.get("topic") or "待巩固主题")
        title = tex_escape(item.get("title") or item.get("url") or item.get("citation") or "学习资料")
        typ = tex_escape(item.get("type") or "resource")
        priority = tex_escape(item.get("priority") or "建议")
        why = tex_paragraph(item.get("why") or "")
        language = tex_escape(item.get("language") or "")
        duration = tex_escape(item.get("duration") or "")
        detail = item.get("url") or item.get("citation") or ""
        meta = "，".join(part for part in [typ, priority, language, duration] if part)
        if item.get("url"):
            link = rf"\url{{{tex_escape(detail)}}}"
        else:
            link = tex_paragraph(detail or "来源不足，建议补材料")
        lines.append(
            rf"\item \textbf{{{topic}}}｜{title}（{meta}）\par "
            rf"\textbf{{为什么看}}：{why}\par "
            rf"\textbf{{链接}}：{link}"
        )
    lines.append(r"\end{enumerate}")
    return "\n".join(lines)


def is_compact_sourced(plan: dict[str, Any]) -> bool:
    metadata = plan.get("metadata") or {}
    return metadata.get("report_style") == "compact_sourced" or bool(plan.get("source_registry"))


def render_body(plan: dict[str, Any]) -> str:
    if is_compact_sourced(plan):
        return "\n\n".join(
            [
                render_compact_summary(plan),
                render_compact_questions(plan),
                render_key_followups(plan),
                render_compact_coding(plan),
                render_compact_technical(plan),
                render_sources(plan),
                render_learning_resources(plan),
            ]
        )
    return "\n\n".join(
        [
            render_overview(plan),
            render_questions(plan),
            render_technical(plan),
            render_project_templates(plan),
            render_coding(plan),
            render_training(plan),
            render_appendix(plan),
        ]
    )


def replace(template: str, values: dict[str, str]) -> str:
    out = template
    for key, value in values.items():
        out = out.replace("<<" + key + ">>", value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-plan", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    plan_path = Path(args.review_plan).expanduser().resolve()
    template_path = Path(args.template).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if not plan.get("source_registry"):
        registry_path = plan.get("source_registry_path")
        candidate = Path(registry_path).expanduser().resolve() if registry_path else plan_path.parent / "source_registry.json"
        if candidate.exists():
            plan["source_registry"] = json.loads(candidate.read_text(encoding="utf-8"))
    metadata = plan.get("metadata") or {}
    dashboard = plan.get("dashboard") or {}

    title = metadata.get("title") or "面试复盘报告"
    values = {
        "PDF_TITLE": tex_escape(title),
        "SHORT_TITLE": tex_escape(metadata.get("short_title") or title[:24]),
        "REPORT_TITLE": tex_escape(title),
        "REPORT_SUBTITLE": tex_escape(metadata.get("subtitle") or ""),
        "GENERATED_AT": tex_escape(metadata.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M")),
        "DURATION": tex_escape(metadata.get("duration") or "未记录"),
        "ASR_BACKEND": tex_escape(metadata.get("asr_backend") or "local ASR"),
        "DASHBOARD_TITLE": tex_escape("首页摘要" if is_compact_sourced(plan) else "首页诊断"),
        "DASHBOARD_VERDICT": "\n\n".join(
            [
                rf"\textbf{{总体通过概率}}：{tex_escape(dashboard.get('pass_probability') or '未评估')}",
                rf"\textbf{{总体结论}}：{tex_paragraph(dashboard.get('verdict') or '')}",
                rf"\textbf{{致命风险}}：{tex_paragraph(dashboard.get('fatal_risks') or '')}",
            ]
        ),
        "TOP_DEDUCTIONS": render_dashboard_placeholder_list(dashboard.get("top_deductions") or []),
        "TOP_STRENGTHS": render_dashboard_placeholder_list(dashboard.get("top_strengths") or []),
        "HIGH_RISK_TOPICS": render_dashboard_placeholder_list(dashboard.get("high_risk_topics") or []),
        "NEXT_PRIORITIES": render_dashboard_placeholder_list(dashboard.get("next_priorities") or []),
        "LOCAL_EVIDENCE": tex_paragraph(dashboard.get("local_evidence") or "本报告使用本地音视频、转写与截图证据生成。"),
        "BODY": render_body(plan),
    }

    rendered = replace(template_path.read_text(encoding="utf-8"), values)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
