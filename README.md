# InterviewForge

Local-first interview recording review reports: turn a local interview video or audio file into a structured Chinese PDF focused on interviewer questions, your real answers, concise suggested answers, sources, and follow-up learning resources.

InterviewForge ships as both:

- a reusable Codex/agent skill in `skill/interview-video-review/`;
- a small CLI wrapper named `interviewforge`.

The default workflow is privacy-first. Audio, video, transcripts, screenshots, and reports stay on your machine unless you explicitly choose a cloud route.

## What It Produces

Each run keeps a clean two-level output:

```text
interview_review.pdf
references.md
supporting_files/
  review_plan.json
  transcript_normalized.json
  interview_events.json
  source_registry.json
  interview_review.tex
  quality_report.json
```

The PDF is intentionally not a raw transcript. It prioritizes:

1. interviewer questions and cleaned real answers;
2. compact quality tags such as `passable 3/5` or `risky 2/5`;
3. short suggested answers with local/public sources;
4. coding and high-risk technical follow-up review;
5. a short list of learning resources.

## Install

```bash
git clone https://github.com/K1XE/InterviewForge.git
cd InterviewForge
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e .
```

System tools used by the full video pipeline:

- `ffmpeg` and `ffprobe`
- a local ASR backend such as `whisperx`, `mlx-whisper`, `faster-whisper`, or `openai-whisper`
- `latexmk`, `xelatex`, Chinese LaTeX support such as `texlive-lang-chinese`, `pdfinfo`, `pdffonts`, and `pdftotext`

The minimal sample only needs Python plus a working LaTeX/PDF toolchain.

## Quick Start

Generate the fictional sample report:

```bash
interviewforge sample --out /tmp/interviewforge-sample
open /tmp/interviewforge-sample/interview_review.pdf
```

Render an existing `review_plan.json`:

```bash
interviewforge render --workdir /path/to/run
interviewforge validate --workdir /path/to/run
```

Use the deterministic local pipeline directly:

```bash
interviewforge init --workdir /path/to/run --input /path/to/interview.mov
interviewforge pipeline probe --input /path/to/interview.mov --out-dir /path/to/run/supporting_files
interviewforge pipeline extract-audio --input /path/to/interview.mov --audio /path/to/run/supporting_files/audio.wav
```

For the judgment-heavy steps, use the bundled skill instructions: create a high-recall question scaffold, inspect `answer_polish_queue.json`, then write `question_cleaned` and `my_answer_cleaned` before rendering.

## Codex Skill

The skill lives at:

```text
skill/interview-video-review/SKILL.md
```

To use it from an agent environment, install or symlink that directory into your skill root. The skill contains the full report standard, privacy rules, data contracts, LaTeX template, and validation checklist.

## Example

A fictional sample plan is included in `examples/minimal/`. The generated sample PDF is committed as `examples/minimal/interview_review.pdf` after release packaging.

## Privacy Defaults

InterviewForge is designed around sensitive interview recordings:

- no upload by default;
- no real audio/video in this repository;
- no home-directory paths in final reports by default;
- local sources are referenced by event id, artifact id, and time range;
- extracted audio and LaTeX intermediates are treated as transient artifacts.

Before publishing this repository, the project is checked for private paths, real interview names, API keys, `.DS_Store`, and real run outputs.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=K1XE/InterviewForge&type=Date)](https://www.star-history.com/#K1XE/InterviewForge&Date)

## License

MIT
