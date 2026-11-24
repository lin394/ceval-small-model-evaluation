import hashlib
import io
import json
import unicodedata
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parent / "data" / "ceval"


def main():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    questions = [json.loads(line) for line in
                 (ROOT / "questions.jsonl").read_text(encoding="utf-8").splitlines()]
    evaluation_texts = {
        "".join(unicodedata.normalize("NFKC", row["question"]).split())
        for row in questions
    }
    revision = manifest["revision"]
    examples = []
    for subject in dict.fromkeys(row["subject"] for row in questions):
        relative = f"{subject}/dev-00000-of-00001.parquet"
        url = f"{manifest['dataset']}/resolve/{revision}/{relative}"
        source = ROOT / "source" / revision / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            content = urllib.request.urlopen(url, timeout=120).read()
            pq.read_table(io.BytesIO(content))
            source.write_bytes(content)
        rows = sorted(pq.read_table(source).to_pylist(), key=lambda row: row["id"])
        selected = []
        seen = set(evaluation_texts)
        for row in rows:
            text = "".join(unicodedata.normalize("NFKC", row["question"]).split())
            complete = all(isinstance(row[field], str) and row[field].strip()
                           for field in ("question", "A", "B", "C", "D"))
            if not complete or row["answer"] not in ("A", "B", "C", "D") or text in seen:
                continue
            seen.add(text)
            selected.append({
                "subject": subject, "split": "dev", "id": row["id"],
                "question": row["question"],
                "choices": {letter: row[letter] for letter in "ABCD"},
                "answer": row["answer"], "dataset_revision": revision,
                "source_url": url,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            })
            if len(selected) == 2:
                break
        if len(selected) != 2:
            raise ValueError(f"{subject}: need two complete, non-overlapping dev examples")
        examples.extend(selected)
    content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in examples)
    output = ROOT / "few_shot_examples.jsonl"
    temporary = output.with_suffix(".jsonl.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(output)
    print(f"Saved {len(examples)} examples to {output}")


if __name__ == "__main__":
    main()
