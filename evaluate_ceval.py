import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer

from qwen_smoke_test import generate

ROOT = Path(__file__).resolve().parent
PROMPT = "请回答下面的中文四选一题。只输出一行，格式为“最终答案：A”，将 A 替换为你的选项。"
STRICT_PROMPT = "请回答下面的中文四选一题。只输出一行 `最终答案：X`，X 必须是 A、B、C、D 之一，选项后不加文字或标点。"
ANSWER = re.compile(r"最终答案[:：][ \t]*([A-D])")


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def key(row):
    return row["subject"], row["split"], row["id"]


def summarize(rows):
    n = len(rows)
    seconds = sum(row["seconds"] for row in rows)
    return {
        "count": n, "correct": sum(row["correct"] for row in rows),
        "accuracy": sum(row["correct"] for row in rows) / n,
        "format_valid_rate": sum(row["prediction"] is not None for row in rows) / n,
        "length_limit_rate": sum(row["length_limit"] for row in rows) / n,
        "calls": n, "total_seconds": round(seconds, 4),
        "mean_seconds": round(seconds / n, 4),
        "mean_generated_tokens": sum(row["generated_tokens"] for row in rows) / n,
        "peak_cuda_allocated_mib": max(row["peak_cuda_allocated_mib"] for row in rows),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--owner", default=None)
    parser.add_argument("--variant", choices=("baseline", "strict-prompt"), default="baseline")
    args = parser.parse_args()
    prompt_instruction = STRICT_PROMPT if args.variant == "strict-prompt" else PROMPT
    data = ROOT / "data" / "ceval"
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    questions = read_jsonl(data / "questions.jsonl")
    answer_rows = read_jsonl(data / "answers.jsonl")
    answers = {key(row): row["answer"] for row in answer_rows}
    if (len(questions) != 200 or len(answer_rows) != 200 or len(answers) != 200
            or list(map(key, questions)) != list(map(key, manifest["items"]))
            or {key(row) for row in questions} != answers.keys()
            or any(answer not in ("A", "B", "C", "D") for answer in answers.values())):
        raise ValueError("Question, manifest and answer IDs must agree.")
    if args.smoke:
        questions = list({row["subject"]: row for row in reversed(questions)}.values())
    torch.manual_seed(manifest["seed"])
    model_dir = ROOT / "models" / "Qwen2.5-0.5B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_dir, dtype=torch.float16, local_files_only=True, use_safetensors=True,
    ).to("cuda").eval()
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
    )
    output = ROOT / "runs" / (
        f"{args.variant}{'-smoke' if args.smoke else ''}-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    output.mkdir(parents=True)
    config = {
        "run_id": output.name, "owner": args.owner,
        "commit": git.stdout.strip() if git.returncode == 0 else None,
        "dataset": manifest["name"], "dataset_revision": manifest["revision"],
        "seed": manifest["seed"], "model": model_dir.name,
        "model_revision": (model_dir / "revision.txt").read_text().strip(),
        "dataset_sha256": {name: hashlib.sha256((data / name).read_bytes()).hexdigest()
                           for name in ("manifest.json", "questions.jsonl", "answers.jsonl")},
        "torch": str(torch.__version__), "transformers": transformers.__version__,
        "device": torch.cuda.get_device_name(), "dtype": "float16",
        "threads": torch.get_num_threads(), "interop_threads": torch.get_num_interop_threads(),
        "prompt": prompt_instruction, "answer_regex": ANSWER.pattern, "do_sample": False,
        "max_new_tokens": 64, "timing": "Tokenization through decoding; no warm-up.",
    }
    (output / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    results = []
    with (output / "predictions.jsonl").open("x", encoding="utf-8") as log:
        for row in questions:
            choices = "\n".join(f"{letter}. {row['choices'][letter]}" for letter in "ABCD")
            prompt = f"{prompt_instruction}\n\n{row['question']}\n{choices}"
            messages = [{"role": "user", "content": prompt}]
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            raw, metrics = generate(model, tokenizer, "cuda", prompt)
            match = ANSWER.fullmatch(raw.strip())
            prediction = match[1] if match else None
            reference = answers[key(row)]
            length_limit = metrics["generated_tokens"] == 64
            result = {
                "subject": row["subject"], "split": row["split"], "id": row["id"],
                "input": rendered, "output": raw, "prediction": prediction,
                "reference": reference, "correct": prediction == reference,
                "length_limit": length_limit,
                "status": [flag for flag, active in (
                    ("parse_failed", prediction is None), ("length_limit", length_limit),
                ) if active],
                **metrics,
            }
            log.write(json.dumps(result, ensure_ascii=False) + "\n")
            log.flush()
            results.append(result)
            if len(results) % 20 == 0:
                print(f"{len(results)}/{len(questions)}", flush=True)
    summary = {
        "overall": summarize(results),
        "by_subject": {subject: summarize([r for r in results if r["subject"] == subject])
                       for subject in dict.fromkeys(r["subject"] for r in results)},
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(output)
    print(json.dumps(summary["overall"]))


if __name__ == "__main__":
    main()
