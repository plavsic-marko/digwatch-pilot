import json
from weaviate_client import WVT as client


CLASS = "DigwatchParagraph"
FIELDS = ["title", "url", "text", "section_title",
          "subsection_title", "effective_date", "quarter"]


def pretty(x):
    print(json.dumps(x, indent=2)[:2000])


def main():

    print("== 1) Jedan proizvoljan objekat ==")
    try:
        r = client.query.get(CLASS, FIELDS).with_limit(1).do()
        hits = r.get("data", {}).get("Get", {}).get(CLASS, [])
        if not hits:
            print(
                " Nema ni jednog objekta u get(limit=1) (čudno, a meta-count je >0).")
        else:
            h = hits[0]
            print(
                f"title: {h.get('title')}\nurl: {h.get('url')}\nquarter: {h.get('quarter')}\n")
            snippet = (h.get("text") or "")[:300].replace("\n", " ")
            print("text:", snippet, "...\n")
    except Exception as e:
        print(" Greška na get(limit=1):", e)

    print("== 2) BM25 test na trivijalni upit 'data' ==")
    try:
        r2 = (client.query
              .get(CLASS, FIELDS)
              .with_bm25(
                  query="data",
                  properties=["text", "title",
                              "section_title", "subsection_title"]
              )
              .with_limit(3)
              .do())
        hits2 = r2.get("data", {}).get("Get", {}).get(CLASS, [])
        if not hits2:
            print(" BM25('data') nema hitova.")
        else:
            for i, h in enumerate(hits2, 1):
                print(f"{i}. {h.get('title')} | {h.get('url')}")
    except Exception as e:
        print(" Greška na BM25:", e)

    print("== 3) Schema klase (da proverimo polja / inverted index) ==")
    try:
        schema = client.schema.get()

        classes = schema.get("classes", [])
        ours = [c for c in classes if c.get("class") == CLASS]
        pretty(ours[0] if ours else {"note": "class not found"})
    except Exception as e:
        print(" Greška pri dohvaćanju šeme:", e)


if __name__ == "__main__":
    main()
