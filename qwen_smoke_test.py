import argparse
import json
from time import perf_counter
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


TRIAL_QUESTIONS = (
    "中国的首都是哪里？ A. 上海 B. 北京 C. 广州 D. 南京",
    "12 乘以 8 等于多少？ A. 80 B. 86 C. 96 D. 108",
    "通常所说的红色行星是哪一颗？ A. 火星 B. 木星 C. 水星 D. 海王星",
    "《西游记》的作者通常被认为是谁？ A. 罗贯中 B. 曹雪芹 C. 施耐庵 D. 吴承恩",
    "植物光合作用主要从空气中吸收哪种气体？ A. 氧气 B. 氮气 C. 二氧化碳 D. 氦气",
)


def main():
    parser = argparse.ArgumentParser(description="Run Qwen2.5-0.5B-Instruct locally.")
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    parser.add_argument("--prompt", default="中国的首都是哪里？请只回答城市名。")
    parser.add_argument("--trial", action="store_true")
    args = parser.parse_args()

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA is unavailable in this PyTorch environment.")
    dtype = torch.float16 if device == "cuda" else torch.float32

    model_dir = Path(__file__).resolve().parent / "models" / "Qwen2.5-0.5B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_dir, dtype=dtype, local_files_only=True, use_safetensors=True
    ).to(device).eval()
    if args.trial:
        records = []
        for index, question in enumerate(TRIAL_QUESTIONS, 1):
            answer, metrics = generate(
                model, tokenizer, device,
                question + "\n请只输出一行，格式为：最终答案：A（把 A 换成正确选项）。",
            )
            records.append({"id": index, "question": question, "answer": answer, **metrics})
        report = {
            "model": model_dir.name,
            "revision": (model_dir / "revision.txt").read_text().strip(),
            "torch": str(torch.__version__),
            "device": torch.cuda.get_device_name() if device == "cuda" else device,
            "dtype": str(dtype),
            "timing": "Tokenization through decoding, excluding model loading; no warm-up.",
            "memory": "PyTorch peak CUDA allocated/reserved memory, including resident model.",
            "records": records,
        }
        path = Path(__file__).resolve().parent / "qwen_trial_results.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path)
        return
    answer, _ = generate(model, tokenizer, device, args.prompt)
    print(f"device={device}, dtype={dtype}")
    print(answer)


def generate(model, tokenizer, device, prompt):
    if device == "cuda":
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
    start = perf_counter()
    inputs = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(device)
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=64, do_sample=False,
                                temperature=None, top_p=None, top_k=None)
    generated = output[0, inputs.input_ids.shape[1]:].tolist()
    answer = tokenizer.decode(generated, skip_special_tokens=True)
    metrics = {
        "seconds": round(perf_counter() - start, 4),
        "generated_tokens": len(generated),
        "visible_chars": len(answer),
    }
    if device == "cuda":
        metrics["peak_cuda_allocated_mib"] = round(torch.cuda.max_memory_allocated() / 2**20, 2)
        metrics["peak_cuda_reserved_mib"] = round(torch.cuda.max_memory_reserved() / 2**20, 2)
    return answer, metrics


if __name__ == "__main__":
    main()
