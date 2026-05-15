---
name: interview-video-review
description: Turn local interview videos, interview recordings, or interview audio files into local-first Chinese interview review PDFs focused on interviewer questions, the candidate's answers, concise sourced standard answers, compact coding/technical follow-up review, and short follow-up learning resources. Use when the user provides a local .mov/.mp4/.m4a/.wav recording and asks for 面试复盘, 面经整理, 面试官问题, 我的回答, 建议答案, 标准答法, 回答评价, 代码题复盘, 后续巩固资料, Q&A extraction, speaker/role inference, source-backed corrections, or a polished LaTeX/PDF report. The skill extracts audio locally, transcribes locally when possible, infers interviewer/candidate roles, registers local/public sources, renders a wdkns-style LaTeX report, and validates the final PDF with pdfinfo/pdftotext/pdffonts.
---

# Interview Video Review

Use this skill to convert any local interview video or audio recording into a Chinese interview review PDF. Optimize for: `面试官问题覆盖率 + 我的回答 > 简短建议答案 > 一句评价/关键扣分点 > 后续巩固资料`.

The output is not a course note, not a raw transcript, and not a long training plan. Keep the report compact enough to review before the next interview.

## Local-First Rule

Do not upload interview audio, video, transcripts, screenshots, resume details, or company-sensitive content unless the user explicitly asks for a cloud route.

Preferred ASR order:

1. `whisperx` with diarization when available.
2. `mlx-whisper` or `faster-whisper` for local ASR.
3. `openai-whisper` CLI fallback.
4. If diarization is unavailable, infer roles from dialogue structure and mark speaker confidence.

## Privacy Defaults

Treat the skill package as reusable and non-personal:

- do not include real interview transcripts, company names, candidate names, usernames, home directories, or absolute local paths in bundled examples;
- do not show local absolute paths in the final PDF or `references.md` by default;
- record local evidence with `event_id`, `artifact_id`, basename-only paths, and time ranges;
- keep full paths only in transient internal commands or when the user explicitly asks for a debug/provenance bundle;
- remove extracted audio, LaTeX intermediates, temporary text extracts, and OS metadata files after validation.

## Output Contract

Create one work directory per recording. Keep the final output clean and two-level:

```text
interview_review.pdf
references.md
supporting_files/
  interview_review.tex
  review_plan.json
  source_registry.json
  question_candidates.json
  interview_events.json
  transcript_normalized.json
  transcript_raw.json
  transcript_raw.srt
  speaker_map.json
  media_probe.json
  run_manifest.json
  evidence_frames.json
  quality_report.json
  build_log.md
  <evidence-frame>.png
```

Keep Markdown output as a draft only. The final deliverable is `<run-dir>/interview_review.pdf`, with human-readable citations in `<run-dir>/references.md`. Put rebuild/provenance files in `<run-dir>/supporting_files/`. Do not leave user-facing output split across `audio/`, `source/`, `logs/`, `analysis/`, `transcript/`, `report/`, and `frames/` directories.

Delete or avoid retaining bulky/transient files after the report is validated unless the user asks for them: extracted `audio.wav`, LaTeX `.aux/.fls/.fdb_latexmk/.out/.toc/.xdv/.log`, duplicate ASR `.txt/.tsv/.vtt`, `.DS_Store`, and temporary run directories.

Use natural report titles in `metadata.title`, such as `<company/team/topic> 面试复盘`. Keep `metadata.subtitle` empty by default unless the user asks for a specific subtitle. Do not expose internal style names, version labels, or pipeline labels in user-facing PDF titles.

## Workflow

Use `scripts/local_interview_pipeline.py` for deterministic local steps:

```bash
SUPPORT=<run-dir>/supporting_files
python scripts/local_interview_pipeline.py init-run --workdir <run-dir> --input <video>
python scripts/local_interview_pipeline.py probe --input <video> --out-dir "$SUPPORT"
python scripts/local_interview_pipeline.py extract-audio --input <video> --audio "$SUPPORT/audio.wav"
python scripts/local_interview_pipeline.py transcribe-local --audio "$SUPPORT/audio.wav" --out-dir "$SUPPORT"
python scripts/local_interview_pipeline.py normalize-transcript --json "$SUPPORT/transcript_raw.json" --out-dir "$SUPPORT"
python scripts/local_interview_pipeline.py infer-speakers --transcript "$SUPPORT/transcript_normalized.json" --out-dir "$SUPPORT"
python scripts/local_interview_pipeline.py extract-question-candidates --transcript "$SUPPORT/transcript_normalized.json" --out-dir "$SUPPORT"
python scripts/local_interview_pipeline.py draft-review-plan --workdir <run-dir>
python scripts/local_interview_pipeline.py extract-frames --input <video> --events "$SUPPORT/interview_events.json" --out-dir "$SUPPORT"
python scripts/local_interview_pipeline.py enrich-real-answers --workdir <run-dir>
python scripts/local_interview_pipeline.py build-answer-polish-queue --workdir <run-dir>
# Agent/LLM reviews answer_polish_queue.json and writes cleaned questions/answers back to review_plan.json.
python scripts/render_interview_tex.py --review-plan "$SUPPORT/review_plan.json" --template assets/interview-review-template.tex --out "$SUPPORT/interview_review.tex"
python scripts/local_interview_pipeline.py compile-pdf --tex "$SUPPORT/interview_review.tex"
python scripts/local_interview_pipeline.py finalize-layout --workdir <run-dir>
python scripts/local_interview_pipeline.py validate-report --workdir <run-dir>
```

The agent owns the judgment-heavy parts:

- inspect transcript segments and evidence frames;
- inspect `supporting_files/question_candidates.json`;
- write `supporting_files/interview_events.json`;
- write `supporting_files/source_registry.json`;
- write or refine `supporting_files/review_plan.json`;
- rerun render/compile/validate until the report is useful and clean.

`draft-review-plan` is a high-recall scaffold step, not final judgment. It should create enough question cards from `question_candidates.json` and nearby transcript context so the agent can refine wording rather than starting from a 5-question summary. Review and merge noisy candidates, but keep substantive follow-ups as separate cards.

`enrich-real-answers` fills each question with a transcript-grounded answer window. `build-answer-polish-queue` creates the evidence package that an agent/LLM must review before writing `question_cleaned` and `my_answer_cleaned`. Do not treat raw ASR text as final prose or as a final interviewer question. `question_cleaned` should be the interviewer's concrete question in normal Chinese, close to the evidence window, and not a generic topic title. The cleaned answer must preserve the candidate's answer order and facts while fixing obvious ASR typos, terms, repetition, punctuation, and filler. Review low-confidence answers for ASR noise before final delivery.

## Compact Sourced Report Standard

Set `metadata.report_style` to `compact_sourced`.

The PDF must contain these main sections:

1. `首页摘要`
2. `面试官问题与我的回答`
3. `重点追问复盘`
4. `代码题复盘`
5. `高风险技术点速记`
6. `参考来源`
7. `后续巩固资料`

Do not add `7天训练计划`, `证据与转写说明`, or long raw transcript sections unless the user explicitly asks.

Each question card should include:

- `时间`
- `面试官问题`
- `我的回答`
- `建议答案`
- `来源`
- optional `一句评价`

`面试官问题` must use `question_cleaned`, not the raw ASR fragment. Fix ASR spelling and missing words only when supported by the nearby transcript and answer window; if the exact question is unrecoverable, write a bounded form such as `面试官追问：这里的 X 具体指什么？` instead of rendering nonsense.

`我的回答` must be a cleaned version of the candidate's real answer from the transcript window, not a one-sentence evaluation. Keep the original order and concrete details; remove only obvious ASR hallucinations, long repeated phrases, filler, and screen-share noise. Use `answer_summary` only as an internal short summary or overview signal.

Each question card should show a compact top-left quality tag like `passable 3/5`, `risky 2/5`, or `strong 5/5`, plus an importance tag like `key` or `covered`. The score is a review aid based on answer completeness, clarity, and ASR confidence; it is not an absolute interview outcome.

Keep `建议答案` short. Use 1-3 sentences unless the user asks for deeper teaching notes.

Coverage rules:

- Preserve most substantive interviewer questions and follow-ups. Do not collapse a long technical discussion into one broad card.
- Only filter greetings, logistics, ASR hallucinations, and repeated acknowledgements.
- For interviews longer than 30 minutes, default targets are: 10-16 question cards for <=35 minute interviews, 14-20 for 35-65 minute interviews, and 18-28 for longer interviews. Actual count should follow transcript evidence.
- Mark 5-8 high-risk/high-value questions with `is_key: true`; those receive fuller review in `重点追问复盘`.
- Non-key questions can use 1-2 sentence `建议答案`; key questions should get 2-5 sentences.

Add `learning_resources` for `后续巩固资料` at the end of the report:

- include 5-8 items, grouped by topics revealed in this interview;
- each item needs `topic`, `title`, `type`, `url` or `citation`, `why`, and `priority`;
- optional fields: `language`, `duration`;
- use traceable sources: papers, official docs, official repositories/docs, university/course notes, original blogs, Zhihu articles, YouTube videos, Bilibili videos, or comparable knowledge-sharing pages;
- keep each `why` to one concise sentence explaining the exact gap it helps fix;
- do not invent links or source titles. If reliable material is unavailable, write `来源不足，建议补材料` in the report rather than fabricating a resource.

## Source Rules

Use `supporting_files/source_registry.json` and mirror it into `review_plan.json` as `source_registry`.

- Interview facts must cite local sources: `transcript_normalized.json`, `interview_events.json`, or evidence frames.
- Technical corrections must cite public traceable sources: papers, official docs, official repositories/docs, course notes, or original blog posts.
- Project ownership, exact work done, experimental numbers, and company-specific claims must cite local video/transcript or user-provided materials. If not sourced, phrase as `建议表达方式`, not as a fact.
- If no reliable source exists, the answer must say `来源不足，建议补材料`. Do not invent citations.
- Use short refs in body, e.g. `[L-q03]`, `[PPO]`, `[DAPO]`.
- Follow-up learning resources are not evidence for what happened in the interview. They should be selected after reading the current transcript/events and should not be hard-coded for a company, team, or candidate.

## Writing Rules

- Write in Chinese unless the user requests another language.
- Keep interviewer questions concrete and close to the original wording.
- Filter greetings, repeated acknowledgements, screen-share logistics, silence hallucinations, and ordinary small talk unless they affect interview signal.
- Evaluate as an interviewer would, but keep the critique short.
- For high-risk technical points, include only the formula/rule needed to fix the answer.
- For code, prefer a compact interview-writeable version, invariant, complexity, and next-time oral script.
- Mark uncertainty rather than pretending diarization or ASR is perfect.

## Visual Evidence Rules

Use screenshots only when they carry evidence value:

- code editor or judge result;
- whiteboard or shared-screen formula;
- architecture diagram;
- table/plot/benchmark;
- system design sketch.

Do not insert random face frames or decorative images. Every included image must have a time provenance footnote on the same page. Use `frames/evidence_frames.json` to record path, timestamp, caption, and reason.

## Bundled Resources

- `assets/interview-review-template.tex`: wdkns-style LaTeX template with `verdictbox`, `riskbox`, `betterbox`, `evidencebox`, `drillbox`, and `codebox`.
- `scripts/render_interview_tex.py`: render `review_plan.json` into complete LaTeX. It supports both legacy V2 and `compact_sourced`.
- `scripts/validate_report.py`: validate PDF existence, extractable text, compact headings, source backing, timestamps, placeholders, image paths, fonts, and page metadata.
- `scripts/local_interview_pipeline.py`: local probing, audio extraction, transcript normalization, role inference, frame extraction, LaTeX compilation, validation orchestration.
- `references/data-contracts.md`: JSON contracts for transcript, events, source registry, and review plan.
- `references/report-rubric.md`: scoring dimensions and interviewer-signal interpretation.
- `references/formulas/ppo_grpo_clipping.md`: PPO/GRPO/DAPO clipping formula card.
- `references/formulas/kl_direction_cheatsheet.md`: KL direction and mode/mean-seeking cheatsheet.
- `references/answer_rewrites/project_claim_defense.md`: project claim defense templates.
- `examples/minimal/`: non-sensitive transcript -> review plan -> PDF smoke-test sample.

## Final Checklist

Before delivery:

- compile with `latexmk -xelatex -interaction=nonstopmode -halt-on-error`;
- run `pdfinfo`, `pdffonts`, and `pdftotext`;
- run `scripts/validate_report.py --workdir <run-dir>`;
- ensure extracted text contains `首页摘要`, `面试官问题与我的回答`, `重点追问复盘`, `代码题复盘`, `高风险技术点速记`, `参考来源`, `后续巩固资料`;
- ensure extracted text does not contain `7天训练计划` or `证据与转写说明`;
- fail on placeholders such as `TODO`, `TBD`, `[在此填写]`, `<<...>>`;
- check every question has `建议答案` and at least one source ref;
- check question coverage against `question_candidates.json` / `interview_events.json`;
- check public sources have URL/citation and local sources have path/event id;
- check `learning_resources` contains 5-8 useful traceable items;
- check all `\includegraphics{...}` paths exist;
- record commands, fallbacks, and limitations in `supporting_files/build_log.md`.
