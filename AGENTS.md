# InterviewForge Agent Installation Guide

Use this file when a user asks an AI coding agent to install or configure InterviewForge, for example:

```text
请你帮我安装一下 https://github.com/K1XE/InterviewForge
```

InterviewForge is both a Python CLI and an agent skill. The CLI handles deterministic local steps such as rendering, compiling, and validating reports. The skill tells an agent how to recover interviewer questions, clean candidate answers, write concise suggestions, cite sources, and produce a useful interview review PDF.

## Install The Project

```bash
git clone https://github.com/K1XE/InterviewForge.git
cd InterviewForge
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e .
```

Verify the CLI:

```bash
interviewforge sample --out /tmp/interviewforge-sample
interviewforge validate --workdir /tmp/interviewforge-sample
```

If editable install fails because the system Python is locked down, create a virtual environment first:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
```

## Configure The Skill

The canonical skill directory is:

```text
skill/interviewforge/
```

The skill entrypoint is:

```text
skill/interviewforge/SKILL.md
```

Prefer symlinks over copies so updates in the repository are immediately visible to the agent runtime.

### Codex

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)/skill/interviewforge" ~/.codex/skills/interviewforge
```

If the Codex client supports project-level shared skills, this is also valid:

```bash
mkdir -p .agents/skills
ln -s "$(pwd)/skill/interviewforge" .agents/skills/interviewforge
```

### Claude Code

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skill/interviewforge" ~/.claude/skills/interviewforge
```

Project-level install:

```bash
mkdir -p .claude/skills
ln -s "$(pwd)/skill/interviewforge" .claude/skills/interviewforge
```

### OpenCode

```bash
mkdir -p ~/.config/opencode/skills
ln -s "$(pwd)/skill/interviewforge" ~/.config/opencode/skills/interviewforge
```

Project-level install:

```bash
mkdir -p .opencode/skills
ln -s "$(pwd)/skill/interviewforge" .opencode/skills/interviewforge
```

OpenCode can also reuse common agent skill roots such as `.agents/skills` or `.claude/skills` when configured that way.

### Qwen Code

```bash
mkdir -p ~/.qwen/skills
ln -s "$(pwd)/skill/interviewforge" ~/.qwen/skills/interviewforge
```

If using a Qwen extension layout, place or symlink `skill/interviewforge/` under that extension's `skills/` directory.

### GitHub Copilot

For repository-level Agent Skills:

```bash
mkdir -p .github/skills .agents/skills
ln -s "$(pwd)/skill/interviewforge" .github/skills/interviewforge
ln -s "$(pwd)/skill/interviewforge" .agents/skills/interviewforge
```

For user-level skills:

```bash
mkdir -p ~/.copilot/skills
ln -s "$(pwd)/skill/interviewforge" ~/.copilot/skills/interviewforge
```

### Gemini CLI

Gemini CLI does not need to copy the skill if project instructions can reference it. Add this to `GEMINI.md` or a `.gemini/commands/*.toml` command:

```text
For local interview recording review tasks, read and follow skill/interviewforge/SKILL.md before acting.
```

### Cursor

Add a project rule such as `.cursor/rules/interviewforge.mdc`:

```md
---
description: Use InterviewForge for local interview recording review
alwaysApply: false
---

For local interview video/audio review, read and follow `skill/interviewforge/SKILL.md`.
Use the CLI only for deterministic rendering, compilation, and validation.
```

### Aider

One-shot:

```bash
aider --read skill/interviewforge/SKILL.md
```

Or add the file to `.aider.conf.yml`:

```yaml
read:
  - skill/interviewforge/SKILL.md
```

### Cline / Roo Code / Other Agents

Add this instruction to the agent's custom instructions, rules, or mode prompt:

```text
When asked to review a local interview recording, follow skill/interviewforge/SKILL.md. Use the Python CLI for rendering and validation, and keep interview media local unless the user explicitly asks otherwise.
```

## Migration From The Old Skill Name

Early versions used the skill name `interview-video-review`. New installs should use `interviewforge`.

```bash
rm -f ~/.codex/skills/interview-video-review ~/.claude/skills/interview-video-review
ln -s "$(pwd)/skill/interviewforge" ~/.codex/skills/interviewforge
ln -s "$(pwd)/skill/interviewforge" ~/.claude/skills/interviewforge
```

## After Installation

The user can ask:

```text
使用 interviewforge skill 处理这个本地面试视频，并生成 PDF 报告。
```

Keep the default behavior local-first: do not upload interview audio, video, transcripts, screenshots, or reports unless the user explicitly requests a cloud route.
