import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq


REVISION = "617524a00b307ff6f9933702f724131fe12ca7ce"
DATASET = "https://huggingface.co/datasets/ceval/ceval-exam"
SEED = 20261123
PER_SUBJECT = 40
SPLIT = "test"
SUBJECTS = (
    "computer_network",
    "high_school_mathematics",
    "high_school_geography",
    "chinese_language_and_literature",
    "accountant",
)
ROOT = Path(__file__).resolve().parent / "data" / "ceval"


def main():
    items = []
    sources = []
    for subject in SUBJECTS:
        relative = f"{subject}/{SPLIT}-00000-of-00001.parquet"
        path = ROOT / "source" / REVISION / relative
        rows = pq.read_table(path).to_pylist()
        eligible = [
            row for row in rows
            if row["answer"] in ("A", "B", "C", "D")
            and all(isinstance(row[field], str) and row[field].strip()
                    for field in ("question", "A", "B", "C", "D"))
        ]
        if len(eligible) < PER_SUBJECT or len({row["id"] for row in eligible}) != len(eligible):
            raise ValueError(f"{subject}: insufficient eligible rows or duplicate IDs")

        def sample_key(row):
            key = f"{SEED}:{subject}:{SPLIT}:{row['id']}"
            return hashlib.sha256(key.encode()).digest(), row["id"]

        selected = sorted(eligible, key=sample_key)[:PER_SUBJECT]
        for row in selected:
            items.append({
                "subject": subject,
                "split": SPLIT,
                "id": row["id"],
                "question": row["question"],
                "choices": {key: row[key] for key in "ABCD"},
                "answer": row["answer"],
            })
        sources.append({
            "subject": subject,
            "split": SPLIT,
            "url": f"{DATASET}/resolve/{REVISION}/{relative}",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "available": len(rows),
            "eligible": len(eligible),
            "selected": len(selected),
        })

    manifest = {
        "name": "C-Eval 本组自选子集",
        "dataset": DATASET,
        "revision": REVISION,
        "license": "CC BY-NC-SA 4.0",
        "seed": SEED,
        "selection": "Per subject, keep complete labeled rows; sort SHA-256 of seed:subject:split:id, then ID; take the first 40.",
        "subject_rationale": "Equal representation for computing, mathematics, geography, literature and professional accounting.",
        "total": len(items),
        "sources": sources,
        "items": [{key: item[key] for key in ("subject", "split", "id")} for item in items],
    }
    (ROOT / "manifest.json").write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    )
    (ROOT / "questions.jsonl").write_bytes(
        "".join(json.dumps({key: value for key, value in item.items() if key != "answer"},
                           ensure_ascii=False) + "\n" for item in items).encode()
    )
    (ROOT / "answers.jsonl").write_bytes(
        "".join(json.dumps({key: item[key] for key in ("subject", "split", "id", "answer")},
                           ensure_ascii=False) + "\n" for item in items).encode()
    )
    for source in sources:
        print(f"{source['subject']}: {source['selected']}/{source['eligible']} eligible")
    print(f"Total: {len(items)}")


if __name__ == "__main__":
    main()
