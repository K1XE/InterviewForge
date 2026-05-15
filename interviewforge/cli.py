from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PROJECT_ROOT / "skill" / "interview-video-review"
PIPELINE = SKILL_DIR / "scripts" / "local_interview_pipeline.py"
RENDERER = SKILL_DIR / "scripts" / "render_interview_tex.py"
TEMPLATE = SKILL_DIR / "assets" / "interview-review-template.tex"
EXAMPLE_DIR = PROJECT_ROOT / "examples" / "minimal"


def run(cmd: list[str], cwd: Path | None = None) -> int:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None)


def ensure_support(workdir: Path) -> Path:
    support = workdir / "supporting_files"
    support.mkdir(parents=True, exist_ok=True)
    return support


def cmd_pipeline(args: argparse.Namespace) -> int:
    return run([sys.executable, str(PIPELINE), *args.pipeline_args])


def cmd_init(args: argparse.Namespace) -> int:
    cmd = [sys.executable, str(PIPELINE), "init-run", "--workdir", args.workdir]
    if args.input:
        cmd.extend(["--input", args.input])
    return run(cmd)


def cmd_render(args: argparse.Namespace) -> int:
    workdir = Path(args.workdir).expanduser().resolve()
    support = ensure_support(workdir)
    review_plan = Path(args.review_plan).expanduser().resolve() if args.review_plan else support / "review_plan.json"
    tex = support / "interview_review.tex"
    rc = run([sys.executable, str(RENDERER), "--review-plan", str(review_plan), "--template", str(TEMPLATE), "--out", str(tex)])
    if rc:
        return rc
    if not args.no_compile:
        rc = run([sys.executable, str(PIPELINE), "compile-pdf", "--tex", str(tex)])
        if rc:
            return rc
        rc = run([sys.executable, str(PIPELINE), "finalize-layout", "--workdir", str(workdir)])
    return rc


def cmd_validate(args: argparse.Namespace) -> int:
    return run([sys.executable, str(PIPELINE), "validate-report", "--workdir", args.workdir])


def cmd_sample(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser().resolve()
    support = ensure_support(out)
    shutil.copy2(EXAMPLE_DIR / "review_plan.sample.json", support / "review_plan.json")
    shutil.copy2(EXAMPLE_DIR / "transcript.sample.json", support / "transcript_normalized.json")
    candidates = EXAMPLE_DIR / "question_candidates.sample.json"
    if candidates.exists():
        shutil.copy2(candidates, support / "question_candidates.json")
    rc = cmd_render(argparse.Namespace(workdir=str(out), review_plan=None, no_compile=args.no_compile))
    if rc:
        return rc
    if not args.no_validate:
        return cmd_validate(argparse.Namespace(workdir=str(out)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="interviewforge", description="Local-first interview recording review reports.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize a clean InterviewForge run directory.")
    p_init.add_argument("--workdir", required=True)
    p_init.add_argument("--input")
    p_init.set_defaults(func=cmd_init)

    p_pipeline = sub.add_parser("pipeline", help="Pass through to the bundled deterministic pipeline.")
    p_pipeline.add_argument("pipeline_args", nargs=argparse.REMAINDER)
    p_pipeline.set_defaults(func=cmd_pipeline)

    p_render = sub.add_parser("render", help="Render and optionally compile a review_plan.json into PDF.")
    p_render.add_argument("--workdir", required=True)
    p_render.add_argument("--review-plan")
    p_render.add_argument("--no-compile", action="store_true")
    p_render.set_defaults(func=cmd_render)

    p_validate = sub.add_parser("validate", help="Validate a generated report.")
    p_validate.add_argument("--workdir", required=True)
    p_validate.set_defaults(func=cmd_validate)

    p_sample = sub.add_parser("sample", help="Create and validate a fictional minimal sample report.")
    p_sample.add_argument("--out", required=True)
    p_sample.add_argument("--no-compile", action="store_true")
    p_sample.add_argument("--no-validate", action="store_true")
    p_sample.set_defaults(func=cmd_sample)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
