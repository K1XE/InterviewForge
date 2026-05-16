#!/usr/bin/env python3
"""Local interview video review pipeline helpers.

The script owns deterministic local steps only:
- create the clean run layout
- probe media with ffprobe
- extract mono 16 kHz WAV with ffmpeg
- run local ASR when an installed backend is available
- normalize common transcript JSON shapes
- write conservative speaker/role inference artifacts
- extract evidence frames from event timestamps
- render/compile/validate the final LaTeX/PDF report

It never uploads audio, video, transcripts, or frames.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
SUPPORT_DIR_NAME = "supporting_files"
RUN_SUBDIRS = [SUPPORT_DIR_NAME]
LEGACY_RUN_SUBDIRS = ["source", "audio", "transcript", "analysis", "frames", "report", "logs"]
LATEX_TRANSIENT_SUFFIXES = {".aux", ".fdb_latexmk", ".fls", ".log", ".out", ".toc", ".xdv"}
TRANSIENT_NAMES = {
    ".DS_Store",
    "audio.wav",
    "interview_review.pdf",
    "interview_review_extracted.txt",
    "transcript_normalized.md",
    "transcript_raw.txt",
    "transcript_raw.tsv",
    "transcript_raw.vtt",
}


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def which(name: str) -> str | None:
    return shutil.which(name)


def require(name: str) -> str:
    path = which(name)
    if not path:
        raise SystemExit(f"missing required executable: {name}")
    return path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_path(value: Any) -> str:
    text = "" if value is None else str(value)
    if not text:
        return ""
    return Path(text).name or "<local-file>"


def redact_media_probe(data: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(data))
    fmt = redacted.get("format")
    if isinstance(fmt, dict) and fmt.get("filename"):
        fmt["filename"] = redact_path(fmt.get("filename"))
    return redacted


def source_detail(src: dict[str, Any], public: bool = False) -> str:
    if src.get("url"):
        return str(src["url"])
    if src.get("citation"):
        return str(src["citation"])
    if src.get("artifact_id"):
        return str(src["artifact_id"])
    if src.get("event_id"):
        return str(src["event_id"])
    if src.get("path"):
        path = str(src["path"])
        if public:
            return Path(path).name
        return path
    return ""


def infer_run_root(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.is_file():
        path = path.parent
    if path.name in RUN_SUBDIRS or path.name in LEGACY_RUN_SUBDIRS:
        return path.parent
    for parent in [path, *path.parents]:
        if (parent / SUPPORT_DIR_NAME).exists():
            return parent
        if (parent / "logs").exists() and (parent / "report").exists():
            return parent
    return path


def append_log(run_root: Path, title: str, body: str) -> None:
    support_dir = run_root / SUPPORT_DIR_NAME
    log_dir = support_dir if support_dir.exists() else run_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / "build_log.md").open("a", encoding="utf-8") as f:
        f.write(f"## {title}\n\n{body.rstrip()}\n\n")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def format_time(seconds: float | int | None) -> str:
    if seconds is None:
        return "??:??"
    total = max(0, int(float(seconds)))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def parse_time(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    parts = text.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return None


def parse_duration_minutes(value: Any) -> float | None:
    seconds = parse_time(value)
    if seconds is None:
        return None
    if isinstance(value, str) and ":" in value:
        return seconds / 60
    return seconds / 60 if seconds > 180 else seconds


def transcript_duration_minutes(segments: list[dict[str, Any]]) -> float | None:
    ends = [parse_time(seg.get("end")) for seg in segments]
    valid = [end for end in ends if end is not None]
    if not valid:
        return None
    return max(valid) / 60


def target_question_range(duration_minutes: float | None, candidate_count: int) -> tuple[int, int]:
    if duration_minutes is None:
        if candidate_count >= 60:
            return 18, 28
        if candidate_count >= 35:
            return 12, 20
        return 8, 16
    if duration_minutes <= 35:
        return 10, 16
    if duration_minutes <= 65:
        return 14, 20
    return 18, 28


def segment_window_summary(segments: list[dict[str, Any]], start: float | None, end: float | None, limit: int = 220) -> str:
    if start is None:
        start = 0.0
    if end is None or end <= start:
        end = start + 90
    texts: list[str] = []
    for seg in segments:
        seg_start = parse_time(seg.get("start"))
        if seg_start is None or seg_start < start or seg_start > end:
            continue
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        if len(text) > 100 and len(set(text)) < 10:
            continue
        texts.append(text)
    summary = " ".join(texts)
    summary = re.sub(r"\s+", " ", summary).strip()
    if len(summary) > limit:
        summary = summary[: limit - 1].rstrip() + "…"
    return summary or "本段回答需要结合转写人工复核。"


def is_repetitive_noise(text: str) -> bool:
    clean = re.sub(r"[\s，。,.!?！？、]", "", str(text or ""))
    if not clean:
        return True
    if len(clean) >= 18 and len(set(clean)) <= 5:
        return True
    if len(clean) >= 24:
        for size in range(2, min(8, len(clean) // 3) + 1):
            unit = clean[:size]
            if unit * (len(clean) // size) == clean[: size * (len(clean) // size)]:
                return True
    return False


def normalize_asr_text(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = re.sub(r"([一-龥A-Za-z])\1{5,}", r"\1", text)
    text = re.sub(r"((?:我看你|小伙伴们|可以用这个红色的红色|我們來看看)[，, ]*){2,}", "", text)
    replacements = {
        "Promom": "prompt",
        "ProM": "prompt",
        "老皮": "logprob",
        "老婆脾": "logprob",
        "凱尔": "KL",
        "JRPO": "GRPO",
        "加PLOS": "GRPO loss",
        "Azentic": "agentic",
        "MAMRI": "memory",
        "Mammory": "memory",
        "Took Nizer": "tokenizer",
        "ambitting": "embedding",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def cleaned_transcript_window(
    segments: list[dict[str, Any]],
    start: float | None,
    end: float | None,
    *,
    max_chars: int = 320,
) -> tuple[str, str]:
    if start is None:
        start = 0.0
    if end is None or end <= start:
        end = start + 120
    pieces: list[str] = []
    for seg in segments:
        seg_start = parse_time(seg.get("start"))
        if seg_start is None or seg_start < start or seg_start > end:
            continue
        text = normalize_asr_text(seg.get("text") or "")
        if not text or is_repetitive_noise(text):
            continue
        if any(noise in text.lower() for noise in QUESTION_NOISE):
            continue
        pieces.append(text)
    raw = " ".join(pieces)
    raw = re.sub(r"\b(好|嗯|对|OK|ok)([ ，。])", "", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    if len(raw) > max_chars:
        cut = raw[:max_chars]
        for mark in ["。", "；", "，", " "]:
            idx = cut.rfind(mark)
            if idx > max_chars * 0.65:
                cut = cut[:idx]
                break
        raw = cut.rstrip("，。；; ") + "…"
    if not raw:
        raw = "本段回答在转写中噪声较高，需要结合原视频复核。"
    return raw, f"{format_time(start)}--{format_time(end)}"


def enrich_real_answers(workdir: Path) -> None:
    workdir = workdir.expanduser().resolve()
    support_dir = workdir / SUPPORT_DIR_NAME
    transcript_path = support_dir / "transcript_normalized.json"
    plan_path = support_dir / "review_plan.json"
    if not transcript_path.exists():
        raise SystemExit(f"missing transcript_normalized.json: {transcript_path}")
    if not plan_path.exists():
        raise SystemExit(f"missing review_plan.json: {plan_path}")
    transcript = read_json(transcript_path)
    segments = transcript.get("segments", transcript if isinstance(transcript, list) else [])
    plan = read_json(plan_path)
    questions = plan.get("questions") or plan.get("question_inventory") or []
    for q in questions:
        time_range = str(q.get("time_range") or "")
        if "--" in time_range:
            left, right = time_range.split("--", 1)
            start = parse_time(left)
            end = parse_time(right)
        else:
            start = parse_time(q.get("start"))
            end = parse_time(q.get("end"))
        question_end = parse_time(q.get("question_end"))
        if question_end is None:
            question_end = start
            for seg in segments:
                seg_start = parse_time(seg.get("start"))
                if seg_start is not None and start is not None and abs(seg_start - start) < 1.5:
                    question_end = parse_time(seg.get("end")) or question_end
                    break
        answer_start = (question_end + 0.2) if question_end is not None else start
        answer_text, answer_window = cleaned_transcript_window(
            segments,
            answer_start,
            end,
            max_chars=720 if q.get("is_key") else 480,
        )
        q.setdefault("question_original", q.get("question") or "")
        q.setdefault("question_cleaned", q.get("question") or "")
        q["my_answer_raw"] = answer_text
        q["my_answer_cleaned"] = answer_text
        q["answer_source_window"] = answer_window
        q["answer_confidence"] = "medium" if len(answer_text) >= 100 and "需要结合原视频复核" not in answer_text else "low"
    plan["questions"] = questions
    plan["question_inventory"] = questions
    write_json(plan_path, plan)

    events_path = support_dir / "interview_events.json"
    if events_path.exists():
        events_data = read_json(events_path)
        by_id = {event.get("id"): event for event in events_data.get("events") or []}
        for q in questions:
            event = by_id.get(q.get("id"))
            if event:
                event["candidate_answer"] = q.get("my_answer_cleaned") or event.get("candidate_answer") or ""
                event["answer_source_window"] = q.get("answer_source_window") or event.get("time_range")
        write_json(events_path, events_data)
    append_log(workdir, "Real Answer Enrichment", f"Updated {len(questions)} question cards with cleaned transcript-grounded answers.")


ANSWER_TRANSITIONS = (
    "但是",
    "所以",
    "因此",
    "因为",
    "如果",
    "然后",
    "同时",
    "另外",
    "最后",
    "这里",
    "这个",
    "我当时",
    "我们",
)

HIGH_SIGNAL_TERMS = (
    "PPO",
    "GRPO",
    "DAPO",
    "DPO",
    "KL",
    "logprob",
    "reward",
    "teacher",
    "student",
    "token",
    "tokenizer",
    "sequence",
    "prompt",
    "response",
    "agentic",
    "memory",
    "experience",
    "trajectory",
    "BaseModel",
    "embedding",
    "Transformer",
    "模型",
    "训练",
    "推理",
    "轨迹",
    "经验",
    "教师",
    "学生",
    "词表",
    "序列",
    "概率",
    "环境",
    "交互",
    "成功率",
    "实验",
    "对比",
)

ACTION_TERMS = (
    "构建",
    "生成",
    "训练",
    "更新",
    "选择",
    "计算",
    "比较",
    "维护",
    "总结",
    "加入",
    "对齐",
    "蒸馏",
    "评估",
    "验证",
    "优化",
)

SUSPECT_ASR_MARKERS = (
    "我看你",
    "我們來看看",
    "小伙伴们",
    "红色的红色",
    "看不着",
    "收得到",
    "能收到",
    "海鲲",
    "言一",
    "年期",
    "科长量",
    "没说完那",
    "不恐懼",
    "什么东西",
    "日网",
    "叫火",
    "大不行",
)


def strip_question_echo(answer: str, question: str) -> str:
    answer = str(answer or "").strip()
    question = str(question or "").strip()
    if not answer or not question:
        return answer
    compact_answer = re.sub(r"[\s，。,.？?；;:：、]", "", answer)
    compact_question = re.sub(r"[\s，。,.？?；;:：、]", "", question)
    if compact_question and compact_answer.startswith(compact_question[: min(len(compact_question), 28)]):
        for sep in ["。", "，", " ", "；", ";"]:
            idx = answer.find(sep)
            if 0 <= idx < max(8, len(question) + 8):
                return answer[idx + 1 :].strip()
        return answer[len(question) :].strip(" ，。；;")
    prefix = compact_question[:12]
    if len(prefix) >= 6 and compact_answer.startswith(prefix):
        return re.sub(r"^.{0,40}?[，。；; ]", "", answer, count=1).strip()
    return answer


def normalize_answer_phrase(text: str) -> str:
    text = normalize_asr_text(text)
    replacements = {
        "人物智能": "人工智能",
        "人为智能": "人工智能",
        "Agen以": "agentic",
        "Agen的": "agentic 的",
        "AZNT": "agentic",
        "AZT": "agentic",
        "Azent": "agentic",
        "GAPO": "GRPO",
        "JAPO": "DAPO",
        "加Q": "GRPO",
        "加幼": "GRPO",
        "RBR": "RLVR",
        "RVR": "RLVR",
        "RII": "RL",
        "RR": "RL",
        "MAMERI": "memory",
        "玛丽": "memory",
        "玛丽怎么": "memory 怎么",
        "LogoProb": "logprob",
        "Logp": "logprob",
        "LogP": "logprob",
        "偷偷": "token",
        "偷拿子": "tokenizer",
        "Toucher": "teacher",
        "Teacher": "teacher",
        "Steelton": "student",
        "Sdubon": "student",
        "BaseModel": "base model",
        "Prom": "prompt",
        "斐波": "feedback",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\b(ok|OK)\b", "", text)
    text = re.sub(r"(嗯|呃|啊|额|唔)[，, ]*", "", text)
    text = re.sub(r"(对|是的|好的|好)+[，, ]*", "", text)
    text = re.sub(r"(就是|然后)([，, ]*\1){1,}", r"\1", text)
    text = re.sub(r"([一-龥A-Za-z]{1,4})(?:[ ，,]+\1){2,}", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip(" ，。；;")
    return text


def clause_signal_score(phrase: str, question_terms: set[str]) -> int:
    compact = re.sub(r"[\s，。,.？?；;:：、]", "", phrase)
    if not compact or len(compact) < 4:
        return -3
    score = 0
    lower = phrase.lower()
    if any(marker in phrase for marker in SUSPECT_ASR_MARKERS):
        score -= 4
    if is_repetitive_noise(compact):
        score -= 4
    for term in HIGH_SIGNAL_TERMS:
        if term.lower() in lower:
            score += 2
    for term in ACTION_TERMS:
        if term in phrase:
            score += 1
    for term in question_terms:
        if len(term) >= 2 and term in compact:
            score += 1
    if 8 <= len(compact) <= 90:
        score += 1
    if len(compact) > 120:
        score -= 1
    return score


def question_terms(question: str) -> set[str]:
    compact = re.sub(r"[\s，。,.？?；;:：、]", "", normalize_answer_phrase(question))
    terms: set[str] = set()
    for term in HIGH_SIGNAL_TERMS:
        if term.lower() in compact.lower():
            terms.add(term)
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9_-]{1,18}", compact):
        terms.add(m.group(0))
    for m in re.finditer(r"[\u4e00-\u9fff]{2,6}", compact):
        token = m.group(0)
        if token not in {"这个", "就是", "然后", "可以", "一下", "什么", "怎么", "为什么", "能不能"}:
            terms.add(token)
    return terms


def split_answer_phrases(text: str) -> list[str]:
    parts = re.split(r"[。！？!?；;\n]+", text)
    phrases: list[str] = []
    for part in parts:
        part = normalize_answer_phrase(part)
        if not part:
            continue
        chunks = re.split(r"(?=(?:但是|所以|因此|因为|如果|然后|同时|另外|最后|包括|主要|我们|我当时))", part)
        for chunk in chunks:
            phrase = normalize_answer_phrase(chunk)
            if not phrase or is_repetitive_noise(phrase):
                continue
            if len(phrase) <= 1:
                continue
            if len(phrase) > 95:
                tokens = phrase.split()
                current = ""
                for token in tokens:
                    joiner = " " if re.search(r"[A-Za-z]$", current) and re.match(r"^[A-Za-z]", token) else ""
                    candidate = (current + joiner + token).strip() if current else token
                    if current and len(candidate) > 70:
                        phrases.append(current)
                        current = token
                    else:
                        current = candidate
                if current:
                    phrases.append(current)
            else:
                phrases.append(phrase)
    return phrases


def dedupe_phrases(phrases: list[str]) -> list[str]:
    kept: list[str] = []
    for phrase in phrases:
        compact = re.sub(r"[\s，。,.？?；;:：、]", "", phrase)
        if not compact:
            continue
        duplicate = False
        for previous in kept[-4:]:
            prev_compact = re.sub(r"[\s，。,.？?；;:：、]", "", previous)
            if compact == prev_compact:
                duplicate = True
                break
            if len(compact) >= 10 and (compact in prev_compact or prev_compact in compact):
                duplicate = True
                break
        if not duplicate:
            kept.append(phrase)
    return kept


def compact_answer_by_clauses(raw_answer: str, question: str, max_chars: int) -> str:
    q_terms = question_terms(question)
    phrases = dedupe_phrases(split_answer_phrases(raw_answer))
    scored: list[tuple[int, int, str]] = []
    for idx, phrase in enumerate(phrases):
        score = clause_signal_score(phrase, q_terms)
        if score >= 1:
            scored.append((idx, score, phrase))
    if not scored:
        scored = [
            (idx, clause_signal_score(phrase, q_terms), phrase)
            for idx, phrase in enumerate(phrases)
            if len(re.sub(r"[\s，。,.？?；;:：、]", "", phrase)) >= 6 and not any(marker in phrase for marker in SUSPECT_ASR_MARKERS)
        ]
    scored = sorted(scored, key=lambda item: (-item[1], item[0]))[:6]
    selected = [phrase for _, _, phrase in sorted(scored, key=lambda item: item[0])]
    if not selected:
        return ""
    clauses = [phrase.strip(" ，。；;") for phrase in selected if phrase.strip(" ，。；;")]
    text = "我当时主要回答了：" + "；".join(clauses) + "。"
    text = re.sub(r"；+", "；", text)
    text = re.sub(r"，；", "；", text)
    if len(text) > max_chars:
        cut = text[:max_chars]
        idx = cut.rfind("；")
        text = (cut[:idx] if idx > max_chars * 0.55 else cut).rstrip("；，。 ") + "。"
    return text


def sentence_join_phrases(phrases: list[str], max_chars: int) -> str:
    sentences: list[str] = []
    current = ""
    for phrase in phrases:
        starts_new = phrase.startswith(ANSWER_TRANSITIONS)
        if current and (len(current) >= 36 or (starts_new and len(current) >= 18)):
            sentences.append(current.rstrip("，, ") + "。")
            current = phrase
        else:
            if current:
                current += "，" + phrase
            else:
                current = phrase
    if current:
        sentences.append(current.rstrip("，, ") + "。")
    text = "".join(sentences)
    text = re.sub(r"，。", "。", text)
    text = re.sub(r"。+", "。", text)
    if len(text) > max_chars:
        cut = text[:max_chars]
        idx = cut.rfind("。")
        if idx > max_chars * 0.65:
            text = cut[: idx + 1]
        else:
            text = cut.rstrip("，。；; ") + "…"
    return text


def polish_answer_text(raw_answer: str, question: str, *, max_chars: int) -> tuple[str, str]:
    raw_answer = normalize_answer_phrase(raw_answer)
    raw_answer = strip_question_echo(raw_answer, question)
    if not raw_answer:
        return "本段回答在转写中噪声较高，需要结合原视频复核。", "low"
    phrases = dedupe_phrases(split_answer_phrases(raw_answer))
    polished = sentence_join_phrases(phrases, max_chars=max_chars)
    compacted = compact_answer_by_clauses(raw_answer, question, max_chars=max_chars)
    if compacted and (answer_noise_score(polished) >= 1 or len(polished) > 420):
        polished = compacted
    if not polished:
        polished = raw_answer[:max_chars].strip(" ，。；;")
        if polished and not polished.endswith(("。", "！", "？", "…")):
            polished += "。"
    confidence = "medium"
    if len(polished) < 80 or "需要结合原视频复核" in polished or answer_noise_score(polished) >= 3:
        confidence = "low"
    return polished, confidence


def answer_noise_score(text: str) -> int:
    compact = re.sub(r"[\s，。,.？?；;:：、]", "", str(text or ""))
    score = 0
    if not compact:
        return 5
    if is_repetitive_noise(compact):
        score += 2
    if re.search(r"([一-龥A-Za-z])\1{4,}", compact):
        score += 2
    if any(marker in text for marker in SUSPECT_ASR_MARKERS):
        score += 2
    if len(compact) >= 60 and "。" not in text and "，" not in text:
        score += 1
    return score


def score_question_card(q: dict[str, Any]) -> tuple[str, str]:
    answer = str(q.get("my_answer_cleaned") or q.get("answer_summary") or "")
    confidence = str(q.get("answer_confidence") or "")
    is_key = bool(q.get("is_key") or q.get("risk") == "high")
    score = 3
    if len(answer) >= 180:
        score += 1
    if len(answer) >= 360 and answer_noise_score(answer) == 0:
        score += 1
    if len(answer) < 90:
        score -= 1
    if confidence == "low":
        score -= 1
    if answer_noise_score(answer) >= 2:
        score -= 1
    if is_key and len(answer) < 140:
        score -= 1
    score = max(1, min(5, score))
    if score >= 4:
        reason = "回答覆盖了主要思路，但下次仍要把结论、依据和边界放得更靠前。"
    elif score == 3:
        reason = "回答有有效信息，但表达需要更聚焦，避免让面试官从细节里反推主线。"
    else:
        reason = "本题回答不够稳定，建议先补一句直接结论，再展开关键依据。"
    return f"{score}/5", reason


def score_to_quality(score: str, confidence: str = "medium") -> str:
    m = re.fullmatch(r"([1-5])/5", str(score or "").strip())
    value = int(m.group(1)) if m else 3
    if confidence == "low" and value > 2:
        value -= 1
    if value >= 5:
        return "strong"
    if value >= 3:
        return "passable"
    if value == 2:
        return "risky"
    return "weak"


def transcript_context_for_window(segments: list[dict[str, Any]], start: float | None, end: float | None, pad: float = 18.0) -> list[dict[str, Any]]:
    if start is None:
        start = 0.0
    if end is None or end <= start:
        end = start + 90
    rows: list[dict[str, Any]] = []
    for seg in segments:
        seg_start = parse_time(seg.get("start"))
        if seg_start is None or seg_start < start - pad or seg_start > end + pad:
            continue
        rows.append(
            {
                "time": format_time(seg_start),
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text": normalize_asr_text(seg.get("text") or ""),
            }
        )
    return rows


def answer_keywords(text: str, limit: int = 12) -> list[str]:
    text = normalize_answer_phrase(text)
    candidates: list[str] = []
    for term in HIGH_SIGNAL_TERMS:
        if term.lower() in text.lower():
            candidates.append(term)
    for match in re.finditer(r"[A-Za-z][A-Za-z0-9_-]{2,24}", text):
        token = match.group(0)
        if token not in candidates:
            candidates.append(token)
    for match in re.finditer(r"[\u4e00-\u9fff]{2,6}", text):
        token = match.group(0)
        if token in {"这个", "就是", "然后", "可以", "一下", "因为", "所以", "但是", "我们", "他们", "主要"}:
            continue
        if token not in candidates:
            candidates.append(token)
    return candidates[:limit]


def build_answer_polish_queue(workdir: Path) -> None:
    workdir = workdir.expanduser().resolve()
    support_dir = workdir / SUPPORT_DIR_NAME
    transcript_path = support_dir / "transcript_normalized.json"
    plan_path = support_dir / "review_plan.json"
    if not transcript_path.exists():
        raise SystemExit(f"missing transcript_normalized.json: {transcript_path}")
    if not plan_path.exists():
        raise SystemExit(f"missing review_plan.json: {plan_path}")
    transcript = read_json(transcript_path)
    segments = transcript.get("segments", transcript if isinstance(transcript, list) else [])
    plan = read_json(plan_path)
    items: list[dict[str, Any]] = []
    for q in plan.get("questions") or plan.get("question_inventory") or []:
        time_range = str(q.get("answer_source_window") or q.get("time_range") or "")
        if "--" in time_range:
            left, right = time_range.split("--", 1)
            start = parse_time(left)
            end = parse_time(right)
        else:
            start = parse_time(q.get("start"))
            end = parse_time(q.get("end"))
        raw = q.get("my_answer_raw") or q.get("my_answer_cleaned") or q.get("answer_summary") or ""
        items.append(
            {
                "id": q.get("id"),
                "time_range": q.get("time_range"),
                "answer_source_window": q.get("answer_source_window"),
                "question_original": q.get("question_original") or q.get("question"),
                "question_cleaned": q.get("question_cleaned") or q.get("question"),
                "raw_answer": raw,
                "context_segments": transcript_context_for_window(segments, start, end),
                "keywords": answer_keywords(raw),
                "importance_label": "key" if q.get("is_key") or q.get("risk") == "high" else "covered",
                "existing_suggested_answer": q.get("suggested_answer") or q.get("standard_answer") or "",
                "rules": [
                    "Rewrite question_cleaned as the interviewer's concrete question in natural Chinese.",
                    "Keep question_cleaned close to the evidence window; do not invent a different topic.",
                    "Write my_answer_cleaned in natural Chinese prose.",
                    "Preserve the candidate's answer facts and order; do not insert the suggested answer.",
                    "Fix obvious ASR term errors only when supported by local context.",
                    "If the transcript is too noisy, summarize only the confirmable gist and mark low confidence.",
                ],
            }
        )
    payload = {
        "schema": "question_answer_polish_queue.v2",
        "created_at": now_iso(),
        "items": items,
    }
    write_json(support_dir / "answer_polish_queue.json", payload)
    append_log(workdir, "Question/Answer Polish Queue", f"Wrote {len(items)} items to `supporting_files/answer_polish_queue.json` for LLM-constrained question and answer cleanup.")


def polish_real_answers(workdir: Path) -> None:
    workdir = workdir.expanduser().resolve()
    support_dir = workdir / SUPPORT_DIR_NAME
    plan_path = support_dir / "review_plan.json"
    events_path = support_dir / "interview_events.json"
    if not plan_path.exists():
        raise SystemExit(f"missing review_plan.json: {plan_path}")
    plan = read_json(plan_path)
    questions = plan.get("questions") or plan.get("question_inventory") or []
    for q in questions:
        raw_answer = q.get("my_answer_raw") or q.get("my_answer_cleaned") or q.get("answer_summary") or ""
        question = q.get("question_cleaned") or q.get("question") or ""
        q["question_original"] = q.get("question_original") or q.get("question") or question
        q["question_cleaned"] = q.get("question_cleaned") or clean_question_text(question)
        polished, confidence = polish_answer_text(raw_answer, question, max_chars=760 if q.get("is_key") else 520)
        q["my_answer_cleaned"] = polished
        q["answer_confidence"] = "low" if q.get("answer_confidence") == "low" and len(polished) < 120 else confidence
        q["answer_polish_method"] = "heuristic_cleaned_original"
        q["importance_label"] = "key" if q.get("is_key") or q.get("risk") == "high" else "covered"
        q["level"] = q.get("level") or q["importance_label"]
        q["score"], q["score_reason"] = score_question_card(q)
        q["quality_label"] = score_to_quality(q["score"], q.get("answer_confidence") or "medium")
        q["comment"] = q.get("score_reason") or q.get("comment") or ""
    plan["questions"] = questions
    plan["question_inventory"] = questions
    write_json(plan_path, plan)

    if events_path.exists():
        events_data = read_json(events_path)
        by_id = {event.get("id"): event for event in events_data.get("events") or []}
        for q in questions:
            event = by_id.get(q.get("id"))
            if event:
                event["candidate_answer"] = q.get("my_answer_cleaned") or event.get("candidate_answer") or ""
                event["answer_confidence"] = q.get("answer_confidence")
                event["score"] = q.get("score")
        write_json(events_path, events_data)
    append_log(workdir, "Real Answer Polish", f"Polished {len(questions)} answers as cleaned transcript-grounded originals and assigned 1-5 scores.")


def clean_question_text(text: str) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    clean = clean.strip("，。,. ")
    if len(clean) > 120:
        clean = clean[:119].rstrip() + "…"
    return clean or "本段提问需人工复核"


def title_from_question(text: str, fallback: str) -> str:
    clean = re.sub(r"[？?。；;，,]", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return fallback
    return clean[:24]


def suggested_answer_for_question(question: str, key: bool) -> str:
    q = question.lower()
    if any(word in question for word in ["代码", "写", "算法", "二分", "DP", "复杂度", "Transformer", "tokenizer", "Embedding"]):
        return "先复述题目和输入输出，再给最小可运行思路、关键不变量和复杂度；写完后用一个 toy case 口述验证。"
    if any(word in question for word in ["项目", "工作", "实习", "介绍", "讲一下", "展开"]):
        return "按“背景/目标、我的职责、方法、实验或结果、限制”五步回答，先给结论，再补细节。"
    if any(word in question for word in ["为什么", "机制", "区别", "关系", "怎么", "如何"]):
        return "先给一句直接结论，再拆成定义、关键机制、边界条件和一个例子；不确定的项目事实只表述为本场材料中的建议说法。"
    if any(word in q for word in ["ppo", "grpo", "dpo", "kl", "dapo", "reward", "teacher", "student"]):
        return "先把优化目标、采样分布、是否 on-policy、是否需要 critic/reward model 说清楚，再说明它解决的具体问题。"
    if key:
        return "先用一句话回答面试官真正问的点，再补依据和边界；避免从背景讲起导致主结论被淹没。"
    return "建议先正面回答，再用一到两句补充依据、限制和下一步验证方式。"


def candidate_quality(candidate: dict[str, Any]) -> bool:
    text = clean_question_text(candidate.get("text") or "")
    if len(text) < 6:
        return False
    if len(text) > 80 and len(set(text)) < 12:
        return False
    if any(noise in text.lower() for noise in QUESTION_NOISE):
        return False
    repeated = re.sub(r"[，。,. ]", "", text)
    if len(repeated) > 20 and len(set(repeated)) <= 5:
        return False
    return question_likelihood(text) >= 3.0


def select_question_candidates(candidates: list[dict[str, Any]], min_count: int, max_count: int) -> list[dict[str, Any]]:
    filtered = [c for c in candidates if candidate_quality(c)]
    if not filtered:
        filtered = candidates[:max_count]
    selected: list[dict[str, Any]] = []
    last_time = -99999.0
    min_gap = 75.0
    for candidate in filtered:
        start = parse_time(candidate.get("start"))
        if start is None:
            start = parse_time(candidate.get("time")) or 0.0
        if selected and start - last_time < min_gap and len(selected) >= min_count:
            continue
        if selected and start - last_time < 35:
            continue
        selected.append(candidate)
        last_time = start
        if len(selected) >= max_count:
            break
    if len(selected) < min_count:
        seen = {c.get("id") for c in selected}
        for candidate in filtered:
            if candidate.get("id") in seen:
                continue
            selected.append(candidate)
            seen.add(candidate.get("id"))
            if len(selected) >= min_count:
                break
    selected.sort(key=lambda c: parse_time(c.get("start")) if parse_time(c.get("start")) is not None else (parse_time(c.get("time")) or 0.0))
    return selected[:max_count]


def draft_review_plan(workdir: Path, overwrite: bool = False) -> None:
    workdir = workdir.expanduser().resolve()
    support_dir = workdir / SUPPORT_DIR_NAME
    transcript_path = support_dir / "transcript_normalized.json"
    if not transcript_path.exists():
        raise SystemExit(f"missing transcript_normalized.json: {transcript_path}")
    transcript = read_json(transcript_path)
    segments = transcript.get("segments", transcript if isinstance(transcript, list) else [])

    candidates_path = support_dir / "question_candidates.json"
    if candidates_path.exists():
        candidates = read_json(candidates_path).get("candidates") or []
    else:
        candidates = extract_question_candidates_from_segments(segments)
        write_json(candidates_path, {"candidates": candidates})

    existing_plan_path = support_dir / "review_plan.json"
    existing_plan = read_json(existing_plan_path) if existing_plan_path.exists() else {}
    metadata = dict(existing_plan.get("metadata") or {})
    duration_minutes = parse_duration_minutes(metadata.get("duration")) or transcript_duration_minutes(segments)
    min_count, max_count = target_question_range(duration_minutes, len(candidates))
    selected = select_question_candidates(candidates, min_count, max_count)

    old_questions = existing_plan.get("questions") or []
    key_titles = {str(q.get("title") or ""): q for q in old_questions if q.get("is_key") or q.get("risk") == "high"}
    questions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    old_preserved_sources = []
    for src in ((existing_plan.get("source_registry") or {}).get("sources") or []):
        if not isinstance(src, dict):
            continue
        sid = str(src.get("id") or "")
        source_type = str(src.get("type") or "")
        # Regenerate question-local sources because question ids/time windows are rebuilt.
        # Preserve public sources and non-question local artifacts such as coding review evidence.
        if re.fullmatch(r"L-q\d+", sid):
            continue
        if not source_type.startswith("local") or sid.startswith("L-code") or sid.startswith("L-tech"):
            old_preserved_sources.append(src)
    old_preserved_by_id = {str(src.get("id") or ""): src for src in old_preserved_sources if src.get("id")}

    for idx, candidate in enumerate(selected, start=1):
        start = parse_time(candidate.get("start")) or parse_time(candidate.get("time")) or 0.0
        end = parse_time(candidate.get("end")) or start + 90
        next_start = None
        if idx < len(selected):
            next_start = parse_time(selected[idx].get("start")) or parse_time(selected[idx].get("time"))
        event_end = min(next_start - 5, start + 150) if next_start and next_start > start else end + 90
        qid = f"q{idx:02d}"
        question_end = parse_time(candidate.get("end")) or start
        question = clean_question_text(candidate.get("text") or "")
        title = title_from_question(question, f"问题 {idx}")
        is_key = idx <= 6 or any(marker in question for marker in ["为什么", "怎么", "如何", "区别", "代码", "reward", "PPO", "GRPO", "DPO", "KL", "DAPO"])
        answer_summary = segment_window_summary(segments, end, event_end)
        matched_old = None
        for old_title, old_q in key_titles.items():
            old_range = old_q.get("time_range") or ""
            old_start = parse_time(str(old_range).split("--")[0]) if "--" in str(old_range) else None
            if old_start is not None and abs(old_start - start) < 180:
                matched_old = old_q
                break
        if matched_old:
            suggested = matched_old.get("suggested_answer") or suggested_answer_for_question(question, is_key)
            comment = matched_old.get("comment") or ""
            intent = matched_old.get("intent") or ""
        else:
            suggested = suggested_answer_for_question(question, is_key)
            comment = "普通覆盖题，重点是下次先给直接结论。" if not is_key else "高价值追问，建议把定义、机制和边界讲清楚。"
            intent = "验证候选人能否正面回答问题，并把依据、边界和项目事实说清楚。"
        time_range = f"{format_time(start)}--{format_time(event_end)}"
        events.append(
            {
                "id": qid,
                "type": "question",
                "start": start,
                "end": event_end,
                "time_range": time_range,
                "interviewer_question": question,
                "candidate_answer": answer_summary,
                "technical_topics": [],
                "evidence_frames": [],
                "notes": "Drafted from question_candidates.json and transcript context; review before final delivery.",
            }
        )
        sources.append(
            {
                "id": f"L-{qid}",
                "type": "local_event",
                "title": f"{qid} {question}",
                "artifact_id": "interview_events.json",
                "event_id": qid,
                "time_range": time_range,
            }
        )
        questions.append(
            {
                "id": qid,
                "time_range": time_range,
                "title": title,
                "question": question,
                "question_original": question,
                "question_cleaned": question,
                "question_end": question_end,
                "intent": intent,
                "answer_summary": answer_summary,
                "suggested_answer": suggested,
                "refs": [f"L-{qid}"],
                "level": "key" if is_key else "covered",
                "comment": comment if is_key else "",
                "is_key": is_key,
            }
        )

    plan = dict(existing_plan)
    plan["metadata"] = metadata
    plan.setdefault("dashboard", existing_plan.get("dashboard") or {})
    plan.setdefault("overview", existing_plan.get("overview") or [])
    plan["questions"] = questions
    plan["question_inventory"] = questions
    merged_sources = sources + [src for sid, src in old_preserved_by_id.items() if sid not in {s.get("id") for s in sources}]
    plan["source_registry"] = {"sources": merged_sources}
    if not plan.get("technical_remediation"):
        plan["technical_remediation"] = []
    if not plan.get("coding_reviews"):
        plan["coding_reviews"] = []
    if not plan.get("learning_resources"):
        plan["learning_resources"] = []

    if existing_plan_path.exists() and not overwrite:
        backup = support_dir / "review_plan.before_draft.json"
        if not backup.exists():
            write_json(backup, existing_plan)
    write_json(support_dir / "interview_events.json", {"events": events})
    write_json(support_dir / "source_registry.json", plan["source_registry"])
    write_json(existing_plan_path, plan)
    append_log(workdir, "Draft Review Plan", f"Drafted {len(questions)} question cards from {len(candidates)} candidates. Target range: {min_count}-{max_count}.")


def init_run(workdir: Path, input_path: Path | None) -> None:
    workdir = workdir.expanduser().resolve()
    for name in RUN_SUBDIRS:
        (workdir / name).mkdir(parents=True, exist_ok=True)
    support_dir = workdir / SUPPORT_DIR_NAME
    manifest = {
        "created_at": now_iso(),
        "source_video_name": redact_path(input_path) if input_path else "",
        "layout": [SUPPORT_DIR_NAME, "interview_review.pdf", "references.md"],
        "local_first": True,
        "privacy": "absolute source paths are not recorded by default",
    }
    write_json(support_dir / "run_manifest.json", manifest)
    append_log(workdir, "Run Initialized", f"Created interview-review layout at `{workdir}`.\n\n```json\n{json.dumps(manifest, ensure_ascii=False, indent=2)}\n```")


def probe(input_path: Path, out_dir: Path) -> dict[str, Any]:
    require("ffprobe")
    out_dir.mkdir(parents=True, exist_ok=True)
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=filename,duration,size:stream=index,codec_type,codec_name,width,height,avg_frame_rate,channels,sample_rate",
            "-of",
            "json",
            str(input_path),
        ]
    )
    data = redact_media_probe(json.loads(result.stdout))
    write_json(out_dir / "media_probe.json", data)
    append_log(infer_run_root(out_dir), "Media Probe", f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```")
    return data


def extract_audio(input_path: Path, audio_path: Path) -> None:
    require("ffmpeg")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(audio_path),
        ]
    )
    append_log(infer_run_root(audio_path), "Audio Extraction", f"Created `{audio_path}` at {now_iso()}.")


def transcribe_local(audio_path: Path, out_dir: Path, model: str | None = None, language: str = "zh") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    run_root = infer_run_root(out_dir)

    if which("whisperx"):
        backend = "whisperx"
        cmd = [
            "whisperx",
            str(audio_path),
            "--model",
            model or "large-v3",
            "--language",
            language,
            "--output_dir",
            str(out_dir),
            "--output_format",
            "all",
        ]
        run(cmd)
    elif which("mlx_whisper"):
        backend = "mlx-whisper"
        cmd = [
            "mlx_whisper",
            str(audio_path),
            "--model",
            model or "mlx-community/whisper-large-v3-turbo",
            "--language",
            language,
            "--output-format",
            "all",
            "--output-dir",
            str(out_dir),
            "--output-name",
            "transcript_raw",
            "--verbose",
            "True",
            "--condition-on-previous-text",
            "False",
        ]
        run(cmd)
    elif which("whisper"):
        backend = "openai-whisper"
        cmd = [
            "whisper",
            str(audio_path),
            "--model",
            model or "large-v3",
            "--language",
            language,
            "--output_dir",
            str(out_dir),
            "--output_format",
            "all",
        ]
        run(cmd)
    else:
        raise SystemExit("No local ASR backend found. Install whisperx, mlx_whisper, faster-whisper CLI, or openai-whisper.")

    append_log(run_root, "Local ASR", f"Backend: `{backend}`\n\nNo cloud transcription API was used.")


def load_segments(json_path: Path) -> list[dict[str, Any]]:
    raw = read_json(json_path)
    if isinstance(raw, dict) and isinstance(raw.get("segments"), list):
        segments = raw["segments"]
    elif isinstance(raw, list):
        segments = raw
    else:
        raise SystemExit(f"unsupported transcript JSON shape: {json_path}")

    normalized: list[dict[str, Any]] = []
    for idx, seg in enumerate(segments):
        text = str(seg.get("text") or seg.get("sentence") or "").strip()
        if not text:
            continue
        start = seg.get("start", seg.get("start_time"))
        end = seg.get("end", seg.get("end_time"))
        speaker = seg.get("speaker") or seg.get("label") or seg.get("speaker_id") or ""
        role = seg.get("role") or ""
        start_f = float(start) if start is not None else None
        end_f = float(end) if end is not None else None
        normalized.append(
            {
                "id": seg.get("id", idx),
                "start": start_f,
                "end": end_f,
                "time": format_time(start_f),
                "speaker": speaker,
                "role": role,
                "text": text,
            }
        )
    return normalized


def write_transcript_md(segments: list[dict[str, Any]], out_path: Path) -> None:
    lines = ["# Timestamped Transcript", ""]
    for seg in segments:
        speaker = f" {seg['speaker']}" if seg.get("speaker") else ""
        role = f" ({seg['role']})" if seg.get("role") else ""
        lines.append(f"- [{seg['time']}]{speaker}{role}: {seg['text']}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def normalize_transcript(json_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    segments = load_segments(json_path)
    norm_path = out_dir / "transcript_normalized.json"
    md_path = out_dir / "transcript_normalized.md"
    write_json(norm_path, {"segments": segments})
    write_transcript_md(segments, md_path)
    append_log(infer_run_root(out_dir), "Transcript Normalization", f"Normalized {len(segments)} segments from `{json_path}`.")


QUESTION_HINTS = (
    "吗",
    "么",
    "为什么",
    "怎么",
    "如何",
    "什么",
    "哪些",
    "能不能",
    "是不是",
    "有没有",
    "为啥",
    "多少",
    "几个",
    "区别",
    "关系",
    "考虑",
    "知道",
    "了解",
    "解释",
    "介绍",
    "讲一下",
    "说一下",
    "展开",
)
QUESTION_NOISE = (
    "可以听到",
    "能听到",
    "可以看到",
    "能看到",
    "喂",
    "hello",
    "测试",
    "共享",
    "屏幕",
    "稍等",
)

SELF_NARRATION_MARKERS = (
    "我们主要",
    "我们在",
    "我们要",
    "我们能",
    "我们做",
    "我們主要",
    "我們在",
    "我們要",
    "我們能",
    "我們做",
    "我主要",
    "我这边",
    "我的",
    "我的回答",
    "这个工作",
    "這個工作",
    "这篇",
    "這篇",
    "这个项目",
    "這個項目",
    "所以说",
    "所以說",
    "第一件事",
    "第二件事",
    "主要是",
    "发现",
    "發現",
)

QUESTION_START_PATTERNS = (
    "能不能",
    "可不可以",
    "可以.*讲",
    "可以.*说",
    "简单.*讲",
    "简单.*说",
    "介绍一下",
    "讲一下",
    "说一下",
    "展开一下",
    "解释一下",
    "那你",
    "你.*怎么",
    "你.*如何",
    "你.*为什么",
    "你.*什么",
    "你.*吗",
    "这个.*怎么",
    "这个.*为什么",
    "为什么",
    "怎么",
    "如何",
    "什么",
    "区别",
    "关系",
)


def question_likelihood(text: str) -> float:
    clean = normalize_asr_text(text)
    clean = re.sub(r"\s+", "", clean.strip())
    if not (4 <= len(clean) <= 140):
        return 0.0
    lowered = clean.lower()
    if any(noise in lowered for noise in QUESTION_NOISE):
        return 0.0
    if is_repetitive_noise(clean):
        return 0.0
    score = 0.0
    if clean.endswith(("?", "？")):
        score += 3.0
    if any(re.search(pattern, clean) for pattern in QUESTION_START_PATTERNS):
        score += 2.4
    if any(marker in clean for marker in ("吗", "么", "呢")):
        score += 1.5
    if any(marker in clean for marker in ("为什么", "怎么", "如何", "能不能", "是不是", "有没有", "区别", "关系")):
        score += 1.8
    if any(marker in clean for marker in ("讲一下", "说一下", "介绍一下", "展开一下", "解释一下")):
        score += 1.4
    if any(marker in clean for marker in SELF_NARRATION_MARKERS):
        score -= 3.8
    if clean.startswith(("现在我们", "現在我們", "所以说我们", "所以說我們", "我们", "我們", "我这边", "我這邊", "我的")):
        score -= 3.0
    if "第一" in clean or "第二" in clean:
        score -= 1.4
    if "第一" in clean and "第二" in clean:
        score -= 2.0
    if len(clean) > 90:
        score -= 1.8
    if len(clean) < 8 and not clean.endswith(("?", "？")):
        score -= 0.7
    return score


def looks_like_question(text: str) -> bool:
    return question_likelihood(text) >= 3.0


def extract_question_candidates_from_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for seg in segments:
        text = str(seg.get("text") or "").strip()
        score = question_likelihood(text)
        if score < 3.0:
            continue
        idx = len(candidates) + 1
        candidates.append(
            {
                "id": f"qc{idx:03d}",
                "segment_id": seg.get("id"),
                "start": seg.get("start"),
                "end": seg.get("end"),
                "time": format_time(seg.get("start")),
                "speaker": seg.get("speaker") or "",
                "role": seg.get("role") or "unknown",
                "text": normalize_asr_text(text),
                "question_score": round(score, 2),
                "confidence": "heuristic",
                "notes": "Review and merge adjacent follow-ups before final report.",
            }
        )
    return candidates


def extract_question_candidates(transcript_path: Path, out_dir: Path) -> None:
    data = read_json(transcript_path)
    segments = data.get("segments", data if isinstance(data, list) else [])
    candidates = extract_question_candidates_from_segments(segments)
    write_json(out_dir / "question_candidates.json", {"candidates": candidates})
    append_log(infer_run_root(out_dir), "Question Candidates", f"Extracted {len(candidates)} heuristic question-like transcript segments.")


def infer_speakers(transcript_path: Path, out_dir: Path) -> None:
    data = read_json(transcript_path)
    segments = data.get("segments", data if isinstance(data, list) else [])
    speaker_counts: dict[str, int] = {}
    for seg in segments:
        speaker = str(seg.get("speaker") or "")
        if speaker:
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1

    if speaker_counts:
        ordered = sorted(speaker_counts.items(), key=lambda item: item[1], reverse=True)
        candidate_speaker = ordered[0][0]
        speaker_map = {
            "method": "diarization-label-majority heuristic",
            "confidence": "medium",
            "speakers": {
                speaker: ("candidate" if speaker == candidate_speaker else "interviewer")
                for speaker, _ in ordered
            },
            "note": "Review manually. Interview recordings can invert this heuristic when the interviewer speaks more.",
        }
    else:
        speaker_map = {
            "method": "dialogue-structure heuristic",
            "confidence": "low",
            "speakers": {},
            "note": "No diarization labels found. Role assignment must be reviewed while building interview_events.json.",
        }

    events: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for seg in segments:
        text = str(seg.get("text") or "")
        if looks_like_question(text):
            if current:
                events.append(current)
            idx = len(events) + 1
            current = {
                "id": f"q{idx:02d}",
                "type": "question",
                "start": seg.get("start"),
                "end": seg.get("end"),
                "time_range": f"{format_time(seg.get('start'))}--{format_time(seg.get('end'))}",
                "interviewer_question": text,
                "candidate_answer": "",
                "technical_topics": [],
                "evidence_frames": [],
                "notes": "Heuristic event candidate; inspect and merge before final report.",
            }
        elif current and len(current["candidate_answer"]) < 500:
            current["candidate_answer"] = (current["candidate_answer"] + " " + text).strip()
            current["end"] = seg.get("end")
            current["time_range"] = f"{format_time(current.get('start'))}--{format_time(current.get('end'))}"
    if current:
        events.append(current)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "speaker_map.json", speaker_map)
    write_json(out_dir / "question_candidates.json", {"candidates": extract_question_candidates_from_segments(segments)})
    write_json(out_dir / "interview_events.json", {"events": events})
    append_log(infer_run_root(out_dir), "Speaker and Event Inference", f"Wrote `speaker_map.json` with `{speaker_map['confidence']}` confidence and {len(events)} heuristic events. Manual review is required before final PDF.")


def extract_frames(input_path: Path, events_path: Path, out_dir: Path) -> None:
    require("ffmpeg")
    out_dir.mkdir(parents=True, exist_ok=True)
    events_data = read_json(events_path) if events_path.exists() else {"events": []}
    frames: list[dict[str, Any]] = []
    for event in events_data.get("events", []):
        frame_times = event.get("frame_times") or []
        if not frame_times and event.get("type") in {"coding", "project"}:
            start = parse_time(event.get("start"))
            end = parse_time(event.get("end"))
            if start is not None and end is not None:
                frame_times = [(start + end) / 2]
        for idx, ts in enumerate(frame_times):
            seconds = parse_time(ts)
            if seconds is None:
                continue
            frame_id = f"{event.get('id', 'event')}_{idx + 1}_{int(seconds):06d}"
            frame_path = out_dir / f"{frame_id}.png"
            run([
                "ffmpeg",
                "-y",
                "-ss",
                f"{seconds:.3f}",
                "-i",
                str(input_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(frame_path),
            ])
            frames.append(
                {
                    "id": frame_id,
                    "path": str(frame_path),
                    "time": format_time(seconds),
                    "time_range": event.get("time_range") or format_time(seconds),
                    "caption": event.get("frame_caption") or event.get("interviewer_question") or "Evidence frame",
                    "reason": event.get("frame_reason") or "Extracted from a reviewed interview event.",
                }
            )
    write_json(out_dir / "evidence_frames.json", {"frames": frames})
    append_log(infer_run_root(out_dir), "Evidence Frames", f"Extracted {len(frames)} evidence frames.")


def compile_pdf(tex_path: Path) -> None:
    require("latexmk")
    tex_path = tex_path.expanduser().resolve()
    run(
        [
            "latexmk",
            "-xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            tex_path.name,
        ],
        cwd=tex_path.parent,
    )
    append_log(infer_run_root(tex_path), "PDF Compilation", f"Compiled `{tex_path}` with latexmk/xelatex.")


def render_tex(review_plan: Path, template: Path, out_path: Path) -> None:
    renderer = SKILL_DIR / "scripts" / "render_interview_tex.py"
    run([sys.executable, str(renderer), "--review-plan", str(review_plan), "--template", str(template), "--out", str(out_path)])
    append_log(infer_run_root(out_path), "LaTeX Render", f"Rendered `{out_path}` from `{review_plan}`.")


def validate_report(workdir: Path) -> int:
    validator = SKILL_DIR / "scripts" / "validate_report.py"
    result = run([sys.executable, str(validator), "--workdir", str(workdir)], check=False)
    print(result.stdout)
    return result.returncode


def _copy_if_exists(src: Path, dst: Path, overwrite: bool = False) -> None:
    if not src.exists():
        return
    if dst.exists() and not overwrite:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _move_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    shutil.move(str(src), str(dst))


def _load_optional_json(path: Path) -> Any:
    return read_json(path) if path.exists() else None


def _collect_path_names(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            names.update(_collect_path_names(item))
    elif isinstance(value, list):
        for item in value:
            names.update(_collect_path_names(item))
    elif isinstance(value, str):
        suffix = Path(value).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".pdf"}:
            names.add(Path(value).name)
    return names


def _write_references_md(workdir: Path, support_dir: Path) -> None:
    registry = _load_optional_json(support_dir / "source_registry.json") or {}
    plan = _load_optional_json(support_dir / "review_plan.json") or {}
    sources = registry.get("sources") if isinstance(registry, dict) else []
    question_titles = {
        str(q.get("id") or ""): str(q.get("question_cleaned") or q.get("question") or "").strip()
        for q in plan.get("questions") or []
        if isinstance(q, dict)
    }
    lines = ["# 参考来源", ""]
    if not sources:
        lines.append("未登记来源。")
    for src in sources or []:
        sid = src.get("id", "")
        event_id = str(src.get("event_id") or "")
        title = question_titles.get(event_id) or src.get("title") or src.get("artifact_id") or redact_path(src.get("path")) or src.get("url") or sid
        typ = src.get("type") or "source"
        detail = source_detail(src, public=True)
        accessed = f"，访问日期：{src.get('accessed')}" if src.get("accessed") else ""
        time_range = f"，时间：{src.get('time_range')}" if src.get("time_range") else ""
        event_id = f"，事件：{src.get('event_id')}" if src.get("event_id") else ""
        lines.append(f"- [{sid}] **{title}**（{typ}）：{detail}{event_id}{time_range}{accessed}")
    resources = plan.get("learning_resources") or []
    if resources:
        lines.extend(["", "# 后续巩固资料", ""])
        for item in resources:
            if not isinstance(item, dict):
                lines.append(f"- {item}")
                continue
            topic = item.get("topic") or "待巩固主题"
            title = item.get("title") or item.get("url") or item.get("citation") or "学习资料"
            typ = item.get("type") or "resource"
            priority = item.get("priority") or "建议"
            detail = item.get("url") or item.get("citation") or "来源不足，建议补材料"
            why = item.get("why") or ""
            lines.append(f"- **{topic}**｜{title}（{typ}，{priority}）：{detail}。{why}")
    (workdir / "references.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def finalize_layout(workdir: Path) -> None:
    workdir = workdir.expanduser().resolve()
    support_dir = workdir / SUPPORT_DIR_NAME
    support_dir.mkdir(parents=True, exist_ok=True)

    legacy_files = {
        workdir / "analysis" / "review_plan.json": support_dir / "review_plan.json",
        workdir / "analysis" / "source_registry.json": support_dir / "source_registry.json",
        workdir / "analysis" / "interview_events.json": support_dir / "interview_events.json",
        workdir / "analysis" / "speaker_map.json": support_dir / "speaker_map.json",
        workdir / "transcript" / "transcript_normalized.json": support_dir / "transcript_normalized.json",
        workdir / "transcript" / "transcript_raw.json": support_dir / "transcript_raw.json",
        workdir / "transcript" / "transcript_raw.srt": support_dir / "transcript_raw.srt",
        workdir / "source" / "media_probe.json": support_dir / "media_probe.json",
        workdir / "source" / "run_manifest.json": support_dir / "run_manifest.json",
        workdir / "frames" / "evidence_frames.json": support_dir / "evidence_frames.json",
        workdir / "logs" / "build_log.md": support_dir / "build_log.md",
        workdir / "report" / "interview_review.tex": support_dir / "interview_review.tex",
        workdir / "report" / "quality_report.json": support_dir / "quality_report.json",
    }
    for src, dst in legacy_files.items():
        _copy_if_exists(src, dst)

    for frame in (workdir / "frames").glob("*.png") if (workdir / "frames").exists() else []:
        _copy_if_exists(frame, support_dir / frame.name)

    report_pdf = workdir / "report" / "interview_review.pdf"
    support_pdf = support_dir / "interview_review.pdf"
    root_pdf = workdir / "interview_review.pdf"
    if support_pdf.exists():
        _copy_if_exists(support_pdf, root_pdf, overwrite=True)
    elif report_pdf.exists():
        _copy_if_exists(report_pdf, root_pdf, overwrite=True)

    _write_references_md(workdir, support_dir)

    referenced_images: set[str] = set()
    for json_name in ["review_plan.json", "source_registry.json", "evidence_frames.json"]:
        data = _load_optional_json(support_dir / json_name)
        if data is not None:
            referenced_images.update(_collect_path_names(data))
    if referenced_images:
        for image in list(support_dir.glob("*.png")) + list(support_dir.glob("*.jpg")) + list(support_dir.glob("*.jpeg")):
            if image.name not in referenced_images:
                image.unlink()

    for transient in support_dir.iterdir():
        if transient.name in TRANSIENT_NAMES or transient.suffix in LATEX_TRANSIENT_SUFFIXES:
            if transient.is_file():
                transient.unlink()
    for name in LEGACY_RUN_SUBDIRS:
        path = workdir / name
        if path.exists():
            shutil.rmtree(path)
    for name in [".DS_Store", "interview_review_extracted.txt", "quality_report.json"]:
        path = workdir / name
        if path.exists():
            path.unlink()
    append_log(workdir, "Final Layout", f"Finalized clean two-level layout at `{workdir}`.")


def build_pdf_legacy(md_path: Path, pdf_path: Path) -> None:
    require("pandoc")
    require("xelatex")
    run(
        [
            "pandoc",
            str(md_path),
            "-o",
            str(pdf_path),
            "--pdf-engine=xelatex",
            "-V",
            "CJKmainfont=PingFang SC",
            "-V",
            "geometry:margin=0.8in",
            "-V",
            "fontsize=11pt",
            "-V",
            "colorlinks=true",
        ],
        cwd=md_path.parent,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init-run")
    p_init.add_argument("--workdir", required=True)
    p_init.add_argument("--input")

    p_probe = sub.add_parser("probe")
    p_probe.add_argument("--input", required=True)
    p_probe.add_argument("--out-dir", required=True)

    p_audio = sub.add_parser("extract-audio")
    p_audio.add_argument("--input", required=True)
    p_audio.add_argument("--audio", required=True)

    p_asr = sub.add_parser("transcribe-local")
    p_asr.add_argument("--audio", required=True)
    p_asr.add_argument("--out-dir", required=True)
    p_asr.add_argument("--model")
    p_asr.add_argument("--language", default="zh")

    p_norm = sub.add_parser("normalize-transcript")
    p_norm.add_argument("--json", required=True)
    p_norm.add_argument("--out-dir", required=True)

    p_speaker = sub.add_parser("infer-speakers")
    p_speaker.add_argument("--transcript", required=True)
    p_speaker.add_argument("--out-dir", required=True)

    p_candidates = sub.add_parser("extract-question-candidates")
    p_candidates.add_argument("--transcript", required=True)
    p_candidates.add_argument("--out-dir", required=True)

    p_draft = sub.add_parser("draft-review-plan")
    p_draft.add_argument("--workdir", required=True)
    p_draft.add_argument("--overwrite", action="store_true")

    p_enrich = sub.add_parser("enrich-real-answers")
    p_enrich.add_argument("--workdir", required=True)

    p_queue = sub.add_parser("build-answer-polish-queue")
    p_queue.add_argument("--workdir", required=True)

    p_polish = sub.add_parser("polish-real-answers")
    p_polish.add_argument("--workdir", required=True)

    p_frames = sub.add_parser("extract-frames")
    p_frames.add_argument("--input", required=True)
    p_frames.add_argument("--events", required=True)
    p_frames.add_argument("--out-dir", required=True)

    p_render = sub.add_parser("render-tex")
    p_render.add_argument("--review-plan", required=True)
    p_render.add_argument("--template", default=str(SKILL_DIR / "assets" / "interview-review-template.tex"))
    p_render.add_argument("--out", required=True)

    p_compile = sub.add_parser("compile-pdf")
    p_compile.add_argument("--tex", required=True)

    p_validate = sub.add_parser("validate-report")
    p_validate.add_argument("--workdir", required=True)

    p_finalize = sub.add_parser("finalize-layout")
    p_finalize.add_argument("--workdir", required=True)

    p_pdf = sub.add_parser("build-pdf")
    p_pdf.add_argument("--md", required=True)
    p_pdf.add_argument("--pdf", required=True)

    args = parser.parse_args()

    if args.cmd == "init-run":
        init_run(Path(args.workdir), Path(args.input) if args.input else None)
        return 0
    if args.cmd == "probe":
        probe(Path(args.input).expanduser().resolve(), Path(args.out_dir).expanduser().resolve())
        return 0
    if args.cmd == "extract-audio":
        extract_audio(Path(args.input).expanduser().resolve(), Path(args.audio).expanduser().resolve())
        return 0
    if args.cmd == "transcribe-local":
        transcribe_local(Path(args.audio).expanduser().resolve(), Path(args.out_dir).expanduser().resolve(), args.model, args.language)
        return 0
    if args.cmd == "normalize-transcript":
        normalize_transcript(Path(args.json).expanduser().resolve(), Path(args.out_dir).expanduser().resolve())
        return 0
    if args.cmd == "infer-speakers":
        infer_speakers(Path(args.transcript).expanduser().resolve(), Path(args.out_dir).expanduser().resolve())
        return 0
    if args.cmd == "extract-question-candidates":
        extract_question_candidates(Path(args.transcript).expanduser().resolve(), Path(args.out_dir).expanduser().resolve())
        return 0
    if args.cmd == "extract-frames":
        extract_frames(Path(args.input).expanduser().resolve(), Path(args.events).expanduser().resolve(), Path(args.out_dir).expanduser().resolve())
        return 0
    if args.cmd == "render-tex":
        render_tex(Path(args.review_plan).expanduser().resolve(), Path(args.template).expanduser().resolve(), Path(args.out).expanduser().resolve())
        return 0
    if args.cmd == "compile-pdf":
        compile_pdf(Path(args.tex).expanduser().resolve())
        return 0
    if args.cmd == "validate-report":
        return validate_report(Path(args.workdir).expanduser().resolve())
    if args.cmd == "finalize-layout":
        finalize_layout(Path(args.workdir).expanduser().resolve())
        return 0
    if args.cmd == "draft-review-plan":
        draft_review_plan(Path(args.workdir).expanduser().resolve(), overwrite=args.overwrite)
        return 0
    if args.cmd == "enrich-real-answers":
        enrich_real_answers(Path(args.workdir).expanduser().resolve())
        return 0
    if args.cmd == "build-answer-polish-queue":
        build_answer_polish_queue(Path(args.workdir).expanduser().resolve())
        return 0
    if args.cmd == "polish-real-answers":
        polish_real_answers(Path(args.workdir).expanduser().resolve())
        return 0
    if args.cmd == "build-pdf":
        build_pdf_legacy(Path(args.md).expanduser().resolve(), Path(args.pdf).expanduser().resolve())
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
