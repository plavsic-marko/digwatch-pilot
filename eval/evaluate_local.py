import json
import re
import sys
from pathlib import Path

DATA = Path("data/processed/updates_paragraphs.jsonl")
TEST = Path("eval/test_queries.jsonl")
TOKEN = re.compile(r"[A-Za-zÀ-ž0-9]+")


def norm(x): return " ".join(TOKEN.findall((x or "").lower()))


def score(text, q_terms):
    t = norm(text)
    return sum(t.count(tk) for tk in q_terms)


def search_top(query, k=5):
    q_terms = [t.lower() for t in TOKEN.findall(query)]
    rows = []
    with DATA.open("r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            blob = " ".join([
                rec.get("title") or "",
                rec.get("section_title") or "",
                rec.get("subsection_title") or "",
                rec.get("text") or "",
            ])
            sc = score(blob, q_terms)
            if sc > 0:
                rows.append((sc, rec))
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows[:k]


def main():
    assert DATA.exists(), f"Nema {DATA}"
    assert TEST.exists(), f"Nema {TEST}"

    total, hits = 0, 0
    with TEST.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            q = case["q"]
            top_k = int(case.get("top_k", 5))
            want_url = (case.get("expect_url_contains") or "").lower()
            want_sub = (case.get("expect_substring") or "").lower()

            results = search_top(q, k=top_k)
            ok = False
            for sc, rec in results:
                url = (rec.get("url") or "").lower()
                text = norm(rec.get("text") or "")
                if want_url and want_url in url:
                    ok = True
                    break
                if want_sub and want_sub in text:
                    ok = True
                    break

            total += 1
            hits += 1 if ok else 0
            print(f"\nQ: {q} | top_k={top_k} | PASS={ok}")
            for sc, rec in results:
                print(
                    f"  [score={sc}] {rec.get('title')}  |  {rec.get('url')}")

    acc = hits / total if total else 0.0
    print(f"\nSummary: {hits}/{total} passed  (acc={acc:.2f})")


if __name__ == "__main__":
    main()
