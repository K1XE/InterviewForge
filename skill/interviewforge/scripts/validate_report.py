#!/usr/bin/env python3
"""Validate an interview-review LaTeX/PDF report."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


V2_REQUIRED_HEADINGS = ["首页诊断", "逐题复盘", "高风险技术补课", "项目答辩模板", "代码题复盘", "7天训练计划"]
COMPACT_REQUIRED_HEADINGS = ["首页摘要", "面试官问题与我的回答", "重点追问复盘", "代码题复盘", "高风险技术点速记", "参考来源", "后续巩固资料"]
FORBIDDEN_COMPACT_HEADINGS = ["7天训练计划", "证据与转写说明"]
PLACEHOLDER_PATTERNS = ["TODO", "TBD", "[在此填写]", "PLACEHOLDER", "未填写课程"]
ANGLE_PLACEHOLDER_RE = re.compile(r"<<[^>\n]{1,120}>>")
TIMESTAMP_RE = re.compile(r"(\d{1,2}:)?\d{2}:\d{2}(--|–|-)(\d{1,2}:)?\d{2}:\d{2}")
QUALITY_LABELS = {"strong", "passable", "risky", "weak"}
IMPORTANCE_LABELS = {"key", "covered"}
ASR_NOISE_MARKERS = [
    "我看你",
    "我們來看看",
    "小伙伴们",
    "红色的红色",
    "看不着",
    "能收到",
    "海鲲",
    "言一",
    "年期",
    "科长量",
    "没说完那",
    "大不行",
]
QUESTION_ASR_NOISE_MARKERS = [
    "大意的科",
    "科上好",
    "提供和思组",
    "默庆风",
    "日网",
    "搜购办",
    "蛮不累",
    "巴佛",
    "造数局",
    "AZ的AZ",
    "实际经济",
    "历细数",
    "Sdubon",
    "检所检案",
    "管理房亚",
    "利益的是巧予",
    "男子没你调用",
    "特别大的评计",
]


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def which(name: str) -> str | None:
    return shutil.which(name)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def first_existing(candidates: list[Path]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def infer_paths(workdir: Path, pdf: str | None, tex: str | None, review_plan: str | None) -> tuple[Path, Path, Path, Path]:
    workdir = workdir.expanduser().resolve()
    support_dir = workdir / "supporting_files"
    pdf_path = Path(pdf).expanduser().resolve() if pdf else first_existing([
        workdir / "interview_review.pdf",
        workdir / "report" / "interview_review.pdf",
    ])
    tex_path = Path(tex).expanduser().resolve() if tex else first_existing([
        support_dir / "interview_review.tex",
        workdir / "report" / "interview_review.tex",
    ])
    plan_path = Path(review_plan).expanduser().resolve() if review_plan else first_existing([
        support_dir / "review_plan.json",
        workdir / "analysis" / "review_plan.json",
    ])
    report_dir = plan_path.parent if plan_path.parent.name == "supporting_files" else pdf_path.parent
    return workdir, pdf_path, tex_path, plan_path, report_dir


def parse_pdfinfo(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def extract_image_paths_from_tex(tex_text: str) -> list[str]:
    paths: list[str] = []
    pattern = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{((?:\\detokenize\{[^{}]+\})|[^{}]+)\}")
    for match in pattern.finditer(tex_text):
        raw = match.group(1).strip()
        detok = re.fullmatch(r"\\detokenize\{(.+)\}", raw)
        paths.append(detok.group(1) if detok else raw)
    return paths


def collect_plan_images(plan_path: Path) -> list[str]:
    if not plan_path.exists():
        return []
    plan = read_json(plan_path)
    paths: list[str] = []
    for q in plan.get("questions") or []:
        for item in q.get("evidence") or []:
            if item.get("path"):
                paths.append(str(item["path"]))
    for c in plan.get("coding_reviews") or []:
        for item in c.get("evidence") or []:
            if item.get("path"):
                paths.append(str(item["path"]))
    return paths


def is_compact_sourced(plan: dict[str, Any]) -> bool:
    metadata = plan.get("metadata") or {}
    return metadata.get("report_style") == "compact_sourced" or bool(plan.get("source_registry"))


def collect_sources(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    registry = plan.get("source_registry") or {}
    sources = registry.get("sources") if isinstance(registry, dict) else registry
    out: dict[str, dict[str, Any]] = {}
    for src in sources or []:
        if isinstance(src, dict) and src.get("id"):
            out[str(src["id"])] = src
    return out


def refs_from_item(item: dict[str, Any]) -> list[str]:
    refs = item.get("refs") or item.get("source_refs") or []
    if isinstance(refs, str):
        refs = [refs]
    return [str(ref) for ref in refs if str(ref).strip()]


def plan_questions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    questions = plan.get("questions") or plan.get("question_inventory") or []
    return [q for q in questions if isinstance(q, dict)]


def check_refs(location: str, refs: list[str], sources: dict[str, dict[str, Any]], failures: list[str]) -> None:
    if not refs:
        failures.append(f"{location} missing refs")
    for ref in refs:
        if ref not in sources:
            failures.append(f"{location} references unknown source: {ref}")


def duration_to_minutes(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) / 60.0 if value > 180 else float(value)
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        number = float(text)
        return number / 60.0 if number > 180 else number
    parts = text.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        return nums[0] * 60 + nums[1] + nums[2] / 60
    if len(nums) == 2:
        return nums[0] + nums[1] / 60
    return None


def validate_source_backing(plan: dict[str, Any], failures: list[str]) -> None:
    sources = collect_sources(plan)
    if not sources:
        failures.append("compact report missing source_registry.sources")
        return

    for sid, src in sources.items():
        source_type = str(src.get("type") or "")
        if source_type.startswith("local"):
            if not (src.get("path") or src.get("event_id") or src.get("artifact_id")):
                failures.append(f"local source missing path/event_id/artifact_id: {sid}")
        else:
            if not (src.get("url") or src.get("citation")):
                failures.append(f"public source missing url/citation: {sid}")

    for q in plan_questions(plan):
        qid = q.get("id") or q.get("title") or "question"
        if not (q.get("suggested_answer") or q.get("standard_answer")):
            failures.append(f"question missing suggested_answer: {qid}")
        check_refs(f"question {qid}", refs_from_item(q), sources, failures)


def validate_real_answers(plan: dict[str, Any], failures: list[str], warnings: list[str]) -> None:
    questions = plan_questions(plan)
    if not questions:
        return
    short_answer_ids: list[str] = []
    missing_cleaned_ids: list[str] = []
    missing_score_ids: list[str] = []
    missing_quality_ids: list[str] = []
    noisy_answer_ids: list[str] = []
    noisy_question_ids: list[str] = []
    for q in questions:
        qid = str(q.get("id") or q.get("title") or "question")
        question = str(q.get("question_cleaned") or q.get("question") or "").strip()
        if not q.get("question_cleaned"):
            noisy_question_ids.append(qid)
        if any(marker in question for marker in QUESTION_ASR_NOISE_MARKERS):
            noisy_question_ids.append(qid)
        question_compact = re.sub(r"[\s，。,.？?；;:：、]", "", question)
        if len(question_compact) >= 16 and not any(mark in question for mark in "？?"):
            # A cleaned interviewer question should read like a question, not
            # a raw ASR fragment. Short imperatives such as "讲一下项目" are
            # still allowed by the length guard.
            warnings.append(f"question may need punctuation cleanup: {qid}")
        answer = str(q.get("my_answer_cleaned") or q.get("my_answer") or q.get("answer_cleaned") or q.get("answer_summary") or "").strip()
        if not q.get("my_answer_cleaned"):
            missing_cleaned_ids.append(qid)
        if len(answer) < 80:
            short_answer_ids.append(qid)
        score = str(q.get("score") or "").strip()
        if not re.fullmatch(r"[1-5]/5", score):
            missing_score_ids.append(qid)
        quality_label = str(q.get("quality_label") or "").strip()
        if quality_label not in QUALITY_LABELS:
            missing_quality_ids.append(qid)
        importance_label = str(q.get("importance_label") or "").strip()
        if importance_label and importance_label not in IMPORTANCE_LABELS:
            failures.append(f"question invalid importance_label: {qid}")
        if q.get("answer_confidence") == "low":
            warnings.append(f"question low answer_confidence: {qid}")
        compact = re.sub(r"[\s，。,.？?；;:：、]", "", answer)
        if re.search(r"([一-龥A-Za-z])\1{4,}", compact) or any(marker in answer for marker in ASR_NOISE_MARKERS):
            noisy_answer_ids.append(qid)
        if len(compact) > 120 and not any(mark in answer for mark in "。！？；"):
            noisy_answer_ids.append(qid)
        if not q.get("answer_source_window"):
            warnings.append(f"question missing answer_source_window: {qid}")
    if len(short_answer_ids) > max(2, len(questions) // 4):
        failures.append(f"too many short real answers: {', '.join(short_answer_ids[:12])}")
    if len(missing_cleaned_ids) > max(2, len(questions) // 4):
        failures.append(f"too many questions missing my_answer_cleaned: {', '.join(missing_cleaned_ids[:12])}")
    if missing_score_ids:
        failures.append(f"questions missing 1-5 score: {', '.join(missing_score_ids[:12])}")
    if missing_quality_ids:
        failures.append(f"questions missing quality_label: {', '.join(missing_quality_ids[:12])}")
    if noisy_question_ids:
        failures.append(f"questions contain ASR-like question text: {', '.join(sorted(set(noisy_question_ids))[:12])}")
    if len(noisy_answer_ids) > max(1, len(questions) // 5):
        failures.append(f"too many noisy ASR-like answers: {', '.join(noisy_answer_ids[:12])}")

    sources = collect_sources(plan)
    for item in plan.get("technical_remediation") or []:
        check_refs(f"technical {item.get('topic') or 'item'}", refs_from_item(item), sources, failures)

    for item in plan.get("coding_reviews") or []:
        check_refs(f"coding {item.get('problem') or 'item'}", refs_from_item(item), sources, failures)


def validate_learning_resources(plan: dict[str, Any], failures: list[str]) -> None:
    resources = plan.get("learning_resources") or []
    if not isinstance(resources, list):
        failures.append("learning_resources must be a list")
        return
    if not (5 <= len(resources) <= 8):
        failures.append(f"learning_resources must contain 5-8 items, found {len(resources)}")
    required = ["topic", "title", "type", "why", "priority"]
    for idx, item in enumerate(resources, start=1):
        if not isinstance(item, dict):
            failures.append(f"learning_resource {idx} must be an object")
            continue
        for key in required:
            if not str(item.get(key) or "").strip():
                failures.append(f"learning_resource {idx} missing {key}")
        if not (str(item.get("url") or "").strip() or str(item.get("citation") or "").strip()):
            failures.append(f"learning_resource {idx} missing url/citation")


def validate_question_coverage(plan: dict[str, Any], plan_path: Path, failures: list[str], warnings: list[str]) -> None:
    questions = plan_questions(plan)
    if not questions:
        return
    support_dir = plan_path.parent
    events_path = support_dir / "interview_events.json"
    candidates_path = support_dir / "question_candidates.json"
    event_count = 0
    candidate_count = 0
    if events_path.exists():
        events = read_json(events_path).get("events") or []
        event_count = sum(1 for e in events if e.get("type") in {"question", "followup", "project"})
    if candidates_path.exists():
        candidate_count = len(read_json(candidates_path).get("candidates") or [])

    metadata = plan.get("metadata") or {}
    duration_minutes = duration_to_minutes(metadata.get("duration"))

    expected = event_count
    if candidate_count:
        if duration_minutes is not None:
            if duration_minutes <= 35:
                candidate_expected = 10 if candidate_count >= 15 else min(candidate_count, 8)
            elif duration_minutes <= 65:
                candidate_expected = 14 if candidate_count >= 35 else 10
            else:
                candidate_expected = 18 if candidate_count >= 35 else 12
        elif candidate_count >= 60:
            candidate_expected = 18
        elif candidate_count >= 35:
            candidate_expected = 12
        elif candidate_count >= 15:
            candidate_expected = 8
        else:
            candidate_expected = 0
        expected = max(expected, candidate_expected)
    if expected and len(questions) < expected:
        failures.append(f"question coverage too low: {len(questions)} questions, expected at least {expected}")
    if not candidates_path.exists():
        warnings.append("question_candidates.json missing; coverage check used interview_events only")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--pdf")
    parser.add_argument("--tex")
    parser.add_argument("--review-plan")
    args = parser.parse_args()

    workdir, pdf_path, tex_path, plan_path, report_dir = infer_paths(Path(args.workdir), args.pdf, args.tex, args.review_plan)
    failures: list[str] = []
    warnings: list[str] = []
    evidence: dict[str, Any] = {
        "workdir": str(workdir),
        "pdf": str(pdf_path),
        "tex": str(tex_path),
        "review_plan": str(plan_path),
    }

    if not pdf_path.exists():
        failures.append(f"PDF missing: {pdf_path}")
    elif pdf_path.stat().st_size < 1000:
        failures.append(f"PDF too small: {pdf_path.stat().st_size} bytes")
    evidence["pdf_size"] = pdf_path.stat().st_size if pdf_path.exists() else 0

    tex_text = ""
    if not tex_path.exists():
        failures.append(f"TeX missing: {tex_path}")
    else:
        tex_text = tex_path.read_text(encoding="utf-8", errors="replace")
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern in tex_text:
                failures.append(f"placeholder found in TeX: {pattern}")
        for match in ANGLE_PLACEHOLDER_RE.finditer(tex_text):
            failures.append(f"angle placeholder found in TeX: {match.group(0)}")

    if not plan_path.exists():
        failures.append(f"review_plan missing: {plan_path}")
        plan = {}
    else:
        plan = read_json(plan_path)
        if not plan.get("source_registry"):
            registry_path = plan.get("source_registry_path")
            candidate = Path(registry_path).expanduser().resolve() if registry_path else plan_path.parent / "source_registry.json"
            if candidate.exists():
                plan["source_registry"] = read_json(candidate)
        compact = is_compact_sourced(plan)
        questions = plan_questions(plan)
        if questions and not all(q.get("time_range") for q in questions):
            failures.append("one or more question cards are missing time_range")
        required_plan_keys = ["metadata", "dashboard", "overview", "questions", "technical_remediation", "coding_reviews"]
        if compact:
            required_plan_keys.append("source_registry")
            validate_source_backing(plan, failures)
            validate_learning_resources(plan, failures)
            validate_question_coverage(plan, plan_path, failures, warnings)
            validate_real_answers(plan, failures, warnings)
        else:
            required_plan_keys.extend(["training_plan", "appendix"])
        for key in required_plan_keys:
            if key not in plan:
                failures.append(f"review_plan missing key: {key}")
    if "compact" not in locals():
        compact = False

    image_paths = extract_image_paths_from_tex(tex_text) + collect_plan_images(plan_path)
    missing_images = sorted({p for p in image_paths if p and not Path(p).exists()})
    if missing_images:
        failures.extend([f"image path missing: {p}" for p in missing_images])
    evidence["image_paths_checked"] = sorted(set(image_paths))

    extracted_text = ""
    extracted_path = report_dir / "interview_review_extracted.txt"
    if pdf_path.exists() and which("pdftotext"):
        res = run(["pdftotext", str(pdf_path), str(extracted_path)])
        evidence["pdftotext_returncode"] = res.returncode
        if res.returncode != 0:
            failures.append("pdftotext failed")
            evidence["pdftotext_output"] = res.stdout
        elif extracted_path.exists():
            extracted_text = extracted_path.read_text(encoding="utf-8", errors="replace")
            evidence["extracted_text_path"] = str(extracted_path)
            evidence["extracted_text_chars"] = len(extracted_text)
            if len(extracted_text.strip()) < 500:
                failures.append("extracted PDF text is too short")
    else:
        warnings.append("pdftotext unavailable or PDF missing")

    search_text = tex_text + "\n" + extracted_text
    required_headings = COMPACT_REQUIRED_HEADINGS if compact else V2_REQUIRED_HEADINGS
    for heading in required_headings:
        if heading not in search_text:
            failures.append(f"required heading missing: {heading}")
    if compact:
        for heading in FORBIDDEN_COMPACT_HEADINGS:
            if heading in search_text:
                failures.append(f"forbidden compact heading found: {heading}")
    for pattern in PLACEHOLDER_PATTERNS:
        if extracted_text and pattern in extracted_text:
            failures.append(f"placeholder found in extracted PDF text: {pattern}")
    if extracted_text:
        for match in ANGLE_PLACEHOLDER_RE.finditer(extracted_text):
            failures.append(f"angle placeholder found in extracted PDF text: {match.group(0)}")
    if plan_questions(plan) and not TIMESTAMP_RE.search(search_text):
        failures.append("no question timestamp range found")

    if pdf_path.exists() and which("pdfinfo"):
        res = run(["pdfinfo", str(pdf_path)])
        evidence["pdfinfo_returncode"] = res.returncode
        evidence["pdfinfo"] = res.stdout
        info = parse_pdfinfo(res.stdout)
        pages = int(info.get("Pages", "0") or 0)
        evidence["pages"] = pages
        if pages <= 0:
            failures.append("pdfinfo reports zero pages")
    else:
        warnings.append("pdfinfo unavailable or PDF missing")

    if pdf_path.exists() and which("pdffonts"):
        res = run(["pdffonts", str(pdf_path)])
        evidence["pdffonts_returncode"] = res.returncode
        evidence["pdffonts"] = res.stdout
        if res.returncode != 0:
            failures.append("pdffonts failed")
    else:
        warnings.append("pdffonts unavailable or PDF missing")

    quality = {
        "status": "fail" if failures else "pass",
        "failures": failures,
        "warnings": warnings,
        "evidence": evidence,
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "quality_report.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(quality, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
