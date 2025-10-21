# digwatch-pilot — README (V2)

Minimalni vodič za pokretanje **RAG pipeline-a za dig.watch Updates** na lokalnoj mašini (Windows, VS Code/CMD).

---

## 0) Pregled

Tok rada (V2):

1. **Crawler (taxonomy + updates)** → preuzmi kategorije/tagove i sve `updates` zapise sa dig.watch.
2. **Chunker** → očisti HTML i podeli na pasuse (dodaje meta: `quarter`, `effective_date`, `tags`, `categories`).
3. **Schema** → kreiraj klase u Weaviate (`DigwatchUpdate`, `DigwatchParagraph`).
4. **Ingest** → upiši dokumente i pasuse u Weaviate sa relacijama (`updateRef`).
5. **Query** → sanity check (BM25 ili hibrid).
6. **Eval (opciono)** → lokalno testiranje na JSONL upitima.

---

## 1) Prerekviziti

- Python 3.10+
- Virtuelno okruženje (`venv/`)
- Docker sa Weaviate + `text2vec-transformers` modelom (npr. `all-MiniLM-L6-v2`)

Pokreni Weaviate:

```bash
docker run -d --name weaviate \
  -p 8080:8080 -e QUERY_DEFAULTS_LIMIT=20 \
  -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
  -e PERSISTENCE_DATA_PATH="/var/lib/weaviate" \
  semitechnologies/weaviate:1.25.8
```

---

## 2) Brzi start — komande (redom)

### (a) Fetch taxonomy

```bash
python crawler/fetch_taxonomies.py
```

Output:

- `data/raw/categories.json`
- `data/raw/taxonomy_map.json`

---

### (b) Collect updates (full crawl)

```bash
python crawler/collect_updates_full.py
```

Output:

- `data/raw/updates_all.json`
- `data/raw/updates_state.json`

Ako dobiješ `400 Bad Request` na zadnjoj stranici → znači da je kraj paginacije.

---

### (c) Chunk updates

```bash
python chunker/chunk_updates_v1.py
```

Output:

- `data/processed/updates_paragraphs.jsonl`

Dodaje polja: `quarter`, `effective_date`, `tag_names`, `category_names`.

---

### (d) Create schema (Weaviate)

```bash
python scripts/create_schema_digwatch.py
```

Kreira:

- `DigwatchUpdate` (document-level meta)
- `DigwatchParagraph` (pasus-level) sa `updateRef` relacijom

---

### (e) Ingest hierarchy

```bash
python scripts/ingest_hierarchy_digwatch.py
```

Output primer:

```
 Ingest done. Paragraphs: 75501, Updates: 24091
```

---

### (f) Query sanity check

```bash
python scripts/query_weaviate.py "AI Act" --alpha 0.35 --k 5
```

Output: prikazuje naslove, linkove i isečke.

---

### (g) (Opcionalno) Lokalni offline check

```bash
python search_jsonl.py "AI Act"
```

Radi pretragu direktno po `updates_paragraphs.jsonl`.

---

## 3) Struktura projekta

```
crawler/
  ├─ fetch_taxonomies.py
  └─ collect_updates_full.py

chunker/
  └─ chunk_updates_v1.py

scripts/
  ├─ create_schema_digwatch.py
  ├─ ingest_hierarchy_digwatch.py
  ├─ query_weaviate.py
  ├─ query_any.py
  └─ debug_query.py

eval/
  ├─ test_queries.jsonl
  └─ evaluate_local.py

data/
  ├─ raw/
  │   ├─ taxonomy_map.json
  │   ├─ updates_all.json
  │   └─ updates_state.json
  └─ processed/
      └─ updates_paragraphs.jsonl

api.py              # FastAPI servis (/healthz, /retrieve_digwatch)
requirements.txt    # Python zavisnosti
README.md           # ovaj fajl
```

---

👉 TL;DR koraci:  
`fetch_taxonomies → collect_updates_full → chunk_updates_v1 → create_schema_digwatch → ingest_hierarchy_digwatch → query_weaviate`
