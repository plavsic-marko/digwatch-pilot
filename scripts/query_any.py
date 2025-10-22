from pprint import pprint
from scripts.weaviate_client import WVT

PARA_CLASS = "DigwatchParagraph"
DOC_CLASS = "DigwatchUpdate"

PARA_FIELDS = ["title", "url", "text", "section_title", "subsection_title"]
DOC_FIELDS = ["url", "title", "effective_date", "quarter"]


def get_any_paragraphs(limit=5):
    res = (
        WVT.query
        .get(PARA_CLASS, PARA_FIELDS + ["_additional { id }"])
        .with_limit(limit)
        .do()
    )
    return res.get("data", {}).get("Get", {}).get(PARA_CLASS, []) or []


def aggregate_meta_count():
    res = (
        WVT.query
        .aggregate(PARA_CLASS)
        .with_meta_count()
        .do()
    )
    return res.get("data", {}).get("Aggregate", {}).get(PARA_CLASS, [{}])[0].get("meta", {})


def get_any_updates(limit=5):
    res = (
        WVT.query
        .get(DOC_CLASS, DOC_FIELDS + ["_additional { id }"])
        .with_limit(limit)
        .do()
    )
    return res.get("data", {}).get("Get", {}).get(DOC_CLASS, []) or []


if __name__ == "__main__":
    print("== A) Get any 5 with _additional{id} ==")
    rows = get_any_paragraphs(5)
    print(f"count: {len(rows)}")
    for i, r in enumerate(rows, 1):
        rid = (r.get("_additional") or {}).get("id")
        print(f"{i} {rid} | {r.get('title') or ''} | {r.get('url') or ''}")

    print("\n== B) Aggregate meta-count (kontrola) ==")
    pprint({"Aggregate": {PARA_CLASS: [{"meta": aggregate_meta_count()}]}})

    print(f"\n== C) Get from {DOC_CLASS} (5 kom) ==")
    docs = get_any_updates(5)
    print(f"count: {len(docs)}")
    for i, d in enumerate(docs, 1):
        rid = (d.get("_additional") or {}).get("id")
        eff = d.get("effective_date") or ""
        qtr = d.get("quarter") or ""
        print(
            f"{i} {rid} | {d.get('title') or ''} | {d.get('url') or ''} | {eff} | {qtr}")
