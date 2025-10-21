import json
import time
import sys
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter, Retry

BASE = "https://dig.watch/wp-json/wp/v2/updates"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ALL_PATH = OUT_DIR / "updates_all.json"
STATE_PATH = OUT_DIR / "updates_state.json"

FIELDS = ["id", "date", "modified", "link", "slug", "status", "type",
          "author", "title", "content", "excerpt", "categories", "tags"]


def sess():
    s = requests.Session()
    r = Retry(total=6, backoff_factor=0.8, status_forcelist=(429, 500, 502, 503, 504),
              allowed_methods=frozenset(["GET"]))
    s.mount("https://", HTTPAdapter(max_retries=r))
    s.headers.update({"User-Agent": "DigwatchPilot/1.0"})
    return s


def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"next_page": 1}


def save_state(state):
    STATE_PATH.write_text(json.dumps(
        state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_existing():
    if ALL_PATH.exists():
        try:
            return json.loads(ALL_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def main():
    s = sess()
    existing = load_existing()
    have = {it.get("id") for it in existing if isinstance(it.get("id"), int)}
    state = load_state()
    page = int(state.get("next_page", 1))
    added_total = 0

    while True:
        params = {
            "per_page": 100,
            "page": page,
            "status": "publish",
            "_embed": "1",
            "_fields": ",".join(FIELDS+["_embedded"]),
            "orderby": "date",
            "order": "desc",
        }
        try:
            r = s.get(BASE, params=params, timeout=60)
            r.raise_for_status()
            arr = r.json() if isinstance(r.json(), list) else []
        except Exception as e:
            print(f" Greška na strani {page}: {e}")

            save_state({"next_page": page})
            sys.exit(1)

        n = len(arr)
        print(f"Strana {page}: {n} zapisa")
        if n == 0:
            break

        added = 0
        for raw in arr:
            pid = raw.get("id")
            if isinstance(pid, int) and pid not in have:
                existing.append(raw)
                have.add(pid)
                added += 1
        added_total += added

        ALL_PATH.write_text(json.dumps(
            existing, ensure_ascii=False, indent=2), encoding="utf-8")
        page += 1
        save_state({"next_page": page})
        time.sleep(0.25)

    print(f"\nOK: ukupno u ALL: {len(existing)} | novo dodato: {added_total}")

    save_state({"next_page": page})
    print(f"Raw izlaz: {ALL_PATH}")


if __name__ == "__main__":
    main()
