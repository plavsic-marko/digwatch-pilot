# digwatch-pilot — README 

Minimalni vodič za pokretanje **RAG pipeline-a za dig.watch Updates** i generisanje **Swiss Digital Policy Newsletter-a** na lokalnoj mašini (Windows, VS Code/CMD).

---

## 0) Pregled

### RAG pipeline

1. **Crawler (taxonomy + updates)** → preuzmi kategorije/tagove i sve `updates` zapise sa dig.watch.
2. **Chunker** → očisti HTML i podeli na pasuse (dodaje meta: `quarter`, `effective_date`, `tags`, `categories`).
3. **Schema** → kreiraj klase u Weaviate (`DigwatchUpdate`, `DigwatchParagraph`).
4. **Ingest** → upiši dokumente i pasuse u Weaviate sa relacijama (`updateRef`).
5. **Query** → sanity check (BM25 ili hibrid).
6. **Eval (opciono)** → lokalno testiranje na JSONL upitima.

### Newsletter pipeline

1. **Fetch iz baze** → koristeći lokalni API endpoint `/retrieve_digwatch` koji vraća rezultate iz Weaviate baze.
2. \*\*Python skripta \*\***`make_newsletter.py`** → nalazi se u folderu `newsletter/`. Skripta povlači ažuriranja, normalizuje podatke i priprema ih za LLM.
3. **LLM generacija** → koristi se OpenAI model (npr. `gpt-4o`) za formiranje newslettera u JSON strukturi.
4. **Izlaz** → čuvanje u JSON i Markdown formatima. Markdown se može lako konvertovati u Word ili PDF.

Struktura izlaza newslettera:

- Naslov
- Uvod
- EU sekcija
- Global sekcija
- Zaključak

Format je preuzet prema zahtevima koje je definisala Sorina.

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

Output: `data/raw/taxonomy_map.json`

### (b) Collect updates (full crawl)

```bash
python crawler/collect_updates_full.py
```

Output: `data/raw/updates_all.json`, `data/raw/updates_state.json`

### (c) Chunk updates

```bash
python chunker/chunk_updates_v1.py
```

Output: `data/processed/updates_paragraphs.jsonl`

### (d) Create schema (Weaviate)

```bash
python scripts/create_schema_digwatch.py
```

Kreira klase `DigwatchUpdate` i `DigwatchParagraph`.

### (e) Ingest hierarchy

```bash
python scripts/ingest_hierarchy_digwatch.py
```

Output primer:

```
Ingest done. Paragraphs: 75501, Updates: 24091
```

### (f) Query sanity check

```bash
python scripts/query_weaviate.py "AI Act" --alpha 0.35 --k 5
```

### (g) (Opcionalno) Lokalni offline check

```bash
python search_jsonl.py "AI Act"
```

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
  ├─ debug_query.py
  └─ weaviate_client.py   

newsletter/
  └─ make_newsletter.py   

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

## 4) Newsletter korišćenje

### (a) Podesi parametre

U `newsletter/make_newsletter.py` na vrhu:

```python
PARAMS = {
    "q": "*",   # ili npr. "AI Act" za fokusiranu temu
    "k": 20,
    "alpha": 0.35
}
```

### (b) Pokreni

Iz root-a projekta:

```bash
python newsletter/make_newsletter.py
```

Iz foldera `newsletter/`:

```bash
python make_newsletter.py
```

### (c) Output

```
[DONE] Saved:
  JSON: newsletter_Q3_2025_20251022_2226.json
  MD:   newsletter_Q3_2025_20251022_2226.md
```

### (d) Konverzija

```bash
pandoc newsletter_Q3_2025_*.md -o newsletter_Q3_2025.docx
pandoc newsletter_Q3_2025_*.md -o newsletter_Q3_2025.pdf
```

---

## 5) Napomene



- Skripta koristi `.env` fajl za čitanje OpenAI API ključa (`OPENAI_API_KEY`).
- Broj povučenih vesti (`k`) treba držati razumnim (10–20) da se izbegnu greške 422.
- Newsletter je zamišljen kao kvartalni (Q1–Q4), ali query može biti prilagođen (tematski ili vremenski).

---

👉 TL;DR koraci:\
`fetch_taxonomies → collect_updates_full → chunk_updates_v1 → create_schema_digwatch → ingest_hierarchy_digwatch → query_weaviate → make_newsletter`

