from pathlib import Path
import json
import uuid
from collections import defaultdict

from scripts.weaviate_client import WVT

DATA = Path("data/processed/updates_paragraphs.jsonl")

DOC_CLASS = "DigwatchUpdate"
PARA_CLASS = "DigwatchParagraph"


def doc_uuid(url: str) -> str:
    """Stabilan UUID po URL-u dokumenta."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


def para_uuid(url: str, idx: int) -> str:
    """Stabilan UUID po URL-u + lokalnom indeksu pasusa."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{url}#{idx}"))


def main():
    assert DATA.exists(), f"Nema {DATA}"

    by_url = defaultdict(list)
    with DATA.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            url = (obj.get("url") or "").rstrip("/")
            by_url[url].append(obj)

    docs = []
    for url, rows in by_url.items():
        any_row = rows[0]
        docs.append((
            doc_uuid(url),
            {
                "url":             url,
                "title":           any_row.get("title") or "",
                "date":            any_row.get("date"),
                "modified":        any_row.get("modified"),
                "effective_date":  any_row.get("effective_date"),
                "quarter":         any_row.get("quarter"),
                "category_names":  any_row.get("category_names") or [],
                "tag_names":       any_row.get("tag_names") or [],
                "source":          any_row.get("source") or "dig.watch",
            }
        ))

    with WVT.batch as b:
        b.batch_size = 200
        for duid, props in docs:
            WVT.batch.add_data_object(
                data_object=props,
                class_name=DOC_CLASS,
                uuid=duid
            )
    print(f" Documents upserted: {len(docs)}")

    n_all = sum(len(rows) for rows in by_url.values())
    total = 0

    with WVT.batch as b:
        b.batch_size = 200
        for url, rows in by_url.items():
            duid = doc_uuid(url)
            for i, rec in enumerate(rows):
                puid = para_uuid(url, i)
                para_props = {
                    "url":               url,
                    "title":             rec.get("title") or "",
                    "section_title":     rec.get("section_title"),
                    "subsection_title":  rec.get("subsection_title"),
                    "text":              rec.get("text"),
                    "node_type":         rec.get("node_type") or "paragraph",
                }

                WVT.batch.add_data_object(
                    data_object=para_props,
                    class_name=PARA_CLASS,
                    uuid=puid
                )

                WVT.batch.add_reference(
                    from_object_class_name=PARA_CLASS,
                    from_object_uuid=puid,
                    from_property_name="updateRef",
                    to_object_uuid=duid
                )

                total += 1
                if total % 1000 == 0:
                    print(f"… paragraphs: {total}/{n_all} ({total/n_all:.1%})")

    print(f" Ingest done. Paragraphs: {total}, Updates: {len(docs)}")


if __name__ == "__main__":
    main()
