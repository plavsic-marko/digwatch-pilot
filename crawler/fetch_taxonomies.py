import json
import sys
import time
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter, Retry

BASE = "https://dig.watch/wp-json/wp/v2"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CATS_PATH = OUT_DIR / "categories.json"
TAGS_PATH = OUT_DIR / "tags.json"

MAP_PATH = OUT_DIR / "taxonomy_map.json"


def sess():
    s = requests.Session()
    r = Retry(total=6, backoff_factor=0.6, status_forcelist=(
        429, 500, 502, 503, 504), allowed_methods=frozenset(["GET"]))
    s.mount("https://", HTTPAdapter(max_retries=r))
    s.headers.update({"User-Agent": "DigwatchPilot/Taxonomies/1.1"})
    return s


def fetch_collection(url, name):
    s = sess()
    page, per_page = 1, 100
    all_items = []
    print(f"➡️  Fetching {name} ...")
    while True:
        params = {"per_page": per_page, "page": page,
                  "orderby": "id", "order": "asc", "hide_empty": "false"}
        try:
            r = s.get(url, params=params, timeout=60)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"   ⚠️  {name} page {page} failed: {e}")
            # mala pauza pa probaj sledeću; izaći ćemo ako dobijemo praznu listu
            time.sleep(0.8)
            page += 1
            continue
        try:
            arr = r.json()
        except ValueError:
            arr = []
        n = len(arr) if isinstance(arr, list) else 0
        print(f"   ✅ {name} page {page}: {n} items")
        if not isinstance(arr, list) or n == 0:
            break
        all_items.extend(arr)
        if n < per_page:
            break
        page += 1
        time.sleep(0.25)
    print(f"✅ {name} total: {len(all_items)}\n")
    return all_items


def to_id_name_map(items):
    m = {}
    for it in items:
        _id = it.get("id")
        name = (it.get("name") or "").strip()
        if isinstance(_id, int) and name:
            m[_id] = name
    return m


def main():
    try:
        cats = fetch_collection(f"{BASE}/categories", "categories")
        tags = fetch_collection(f"{BASE}/tags", "tags")
    except Exception as e:
        print("GREŠKA pri fetch-u:", e)
        sys.exit(1)

    CATS_PATH.write_text(json.dumps(
        cats, ensure_ascii=False, indent=2), encoding="utf-8")
    TAGS_PATH.write_text(json.dumps(
        tags, ensure_ascii=False, indent=2), encoding="utf-8")

    cat_map = to_id_name_map(cats)
    tag_map = to_id_name_map(tags)

    MAP_PATH.write_text(json.dumps(
        {"categories": cat_map, "tags": tag_map}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"📦 Sačuvano:")
    print(f"   - {CATS_PATH}  ({len(cats)} raw)")
    print(f"   - {TAGS_PATH}  ({len(tags)} raw)")
    print(f"   - {MAP_PATH}   (cats: {len(cat_map)}, tags: {len(tag_map)})")


if __name__ == "__main__":
    main()
