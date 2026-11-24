"""Validate staged commits and pull requests without model dependencies."""

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


DIRECTIONS = {
    "a": "A_prompt",
    "b": "B_few_shot",
    "c": "C_self_check",
    "d": "D_multi_generation",
}
MAX_FILE_BYTES = 5 * 1024 * 1024
GENERATED_JSON = {"qwen_trial_results.json", "predictions.jsonl"}
PRIVATE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
WEIGHT_SUFFIXES = {".safetensors", ".gguf", ".pt", ".pth", ".ckpt", ".onnx", ".bin"}
LOCAL_DIRS = {
    ".venv", ".uv-cache", ".uv-python", ".hf-cache", ".qwen-deps", ".ceval-deps",
    ".runtime", "__pycache__", ".pytest_cache", "models",
}


def git(*args):
    return subprocess.check_output(["git", *args])


def changed_files(base):
    revs = ["--cached"] if base is None else [base, "HEAD"]
    raw = git("diff", "--raw", "--no-abbrev", "--no-renames", "-z", *revs, "--")
    parts = raw.split(b"\0")
    for index in range(0, len(parts) - 1, 2):
        _, mode, _, oid, status = parts[index].decode("ascii").split()
        path = parts[index + 1].decode("utf-8", errors="surrogateescape")
        yield path, mode, oid, status


def is_local_artifact(path):
    parts = PurePosixPath(path.lower()).parts
    name = parts[-1]
    env_file = name == ".env" or (name.startswith(".env.") and name != ".env.example")
    raw_run = parts[0] == "runs" and name != ".gitkeep"
    return (
        any(part in LOCAL_DIRS for part in parts[:-1])
        or parts[:3] == ("data", "ceval", "source")
        or raw_run or env_file or name.startswith("~$")
        or name in GENERATED_JSON or name in {"id_rsa", "id_ed25519", "credentials.json"}
        or PurePosixPath(name).suffix in PRIVATE_SUFFIXES | WEIGHT_SUFFIXES
    )


def branch_scope(branch):
    experiment = re.fullmatch(r"exp/([abcd])/[a-z0-9][a-z0-9-]*", branch)
    if experiment:
        return DIRECTIONS[experiment.group(1)]
    if re.fullmatch(r"common/[a-z0-9][a-z0-9-]*", branch):
        return None
    raise ValueError("Use exp/a/<task> through exp/d/<task>, or common/<task>.")


def check_files(base, direction):
    errors = []
    for path, mode, oid, status in changed_files(base):
        if direction and not path.startswith(
            (f"experiments/{direction}/", f"analysis/{direction}/")
        ):
            errors.append(f"{path}: outside {direction}; use a separate common branch for shared changes.")
        if status == "D":
            continue
        if mode not in {"100644", "100755"}:
            errors.append(f"{path}: only regular files are allowed.")
            continue
        if is_local_artifact(path):
            errors.append(f"{path}: local artifacts or credentials must stay out of Git.")
            continue
        if int(git("cat-file", "-s", oid)) > MAX_FILE_BYTES:
            errors.append(f"{path}: exceeds the 5 MiB per-file limit.")
            continue
        if Path(path).suffix == ".py":
            try:
                compile(git("cat-file", "blob", oid), path, "exec")
            except SyntaxError as exc:
                errors.append(f"{path}:{exc.lineno}: {exc.msg}")
    return errors


def check_dataset(staged):
    ref = ":" if staged else "HEAD:"

    def read(name):
        return git("show", f"{ref}data/ceval/{name}").decode("utf-8")

    def key(row):
        return row["subject"], row["split"], row["id"]

    manifest = json.loads(read("manifest.json"))
    questions = [json.loads(line) for line in read("questions.jsonl").splitlines()]
    answers = [json.loads(line) for line in read("answers.jsonl").splitlines()]
    question_keys = list(map(key, questions))
    answer_keys = set(map(key, answers))
    counts = Counter(row["subject"] for row in questions)
    if (
        len(question_keys) < 200 or len(counts) < 5 or min(counts.values()) < 20
        or len(question_keys) != manifest["total"]
        or question_keys != list(map(key, manifest["items"]))
        or len(answers) != len(question_keys)
        or len(answer_keys) != len(question_keys)
        or set(question_keys) != answer_keys
        or any(row["answer"] not in ("A", "B", "C", "D") for row in answers)
        or any(
            not row["question"].strip() or set(row["choices"]) != set("ABCD")
            or any(not choice.strip() for choice in row["choices"].values())
            for row in questions
        )
    ):
        raise ValueError("Questions, answer keys and manifest do not describe the same valid subset.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--staged", action="store_true")
    modes.add_argument("--base", help="Base commit for comparing the current merge result.")
    parser.add_argument("--branch", help="Pull request source branch name.")
    args = parser.parse_args()
    if args.base and not args.branch:
        parser.error("--base requires --branch")
    try:
        branch = (
            git("branch", "--show-current").decode().strip() if args.staged else args.branch
        )
        errors = check_files(args.base, branch_scope(branch))
        check_dataset(args.staged)
    except (ValueError, KeyError, TypeError, AttributeError, subprocess.CalledProcessError) as exc:
        print(f"Repository check failed: {exc}", file=sys.stderr)
        return 1
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Repository checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
