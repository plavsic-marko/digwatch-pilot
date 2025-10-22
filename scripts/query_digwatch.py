# Hybrid/BM25 upit nad DigwatchParagraph + cross-ref updateRef (effective_date, quarter).
# Opcioni filteri: --from 2024-01-01 --to 2024-12-31 --quarter 2025-Q2

import argparse
from scripts.weaviate_client import WVT

PARA_CLASS = "DigwatchParagraph"

FIELDS = [
    "title",
    "url",
    "text",
    "section_title",
    "subsection_title",
    'updateRef { ... on DigwatchUpdate { url effective_date quarter tag_names category_names title } }',
]


def dedupe_by_url(rows, k):
    seen, out = set(), []
    for r in rows:
        u = (r.get("url") or "").rstrip("/")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(r)
        if len(out) >= k:
            break
    return out


def snippet(s: str, n=220) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def as_doc(r):
    """Izvuci doc meta iz updateRef (prvi objekat)."""
    arr = r.get("updateRef") or []
    return arr[0] if arr else {}


def match_filters(r, dt_from, dt_to, quarter):
    d = as_doc(r)
    eff = (d.get("effective_date") or "").strip()
    qtr = (d.get("quarter") or "").strip()

    if quarter and quarter != qtr:
        return False

    if dt_from and (not eff or eff < dt_from):
        return False
    if dt_to and (not eff or eff > dt_to):
        return False
    return True


def run(q, k, alpha, use_hybrid=True):
    fetch = max(50, k * 12)
    qobj = (
        WVT.query
        .get(PARA_CLASS, FIELDS)
        .with_limit(fetch)
    )
    if use_hybrid:
        qobj = qobj.with_hybrid(query=q, alpha=alpha)
    else:
        qobj = qobj.with_bm25(query=q)
    res = qobj.do()
    return res.get("data", {}).get("Get", {}).get(PARA_CLASS, []) or []


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+", help="Upit (query)")
    ap.add_argument("--k", type=int, default=10,
                    help="Broj jedinstvenih URL-ova")
    ap.add_argument("--alpha", type=float, default=0.35, help="Hybrid alpha")
    ap.add_argument("--bm25", action="store_true",
                    help="Koristi BM25 umesto hybrid")
    ap.add_argument("--from", dest="date_from", default=None,
                    help="ISO datum od, npr. 2024-01-01")
    ap.add_argument("--to", dest="date_to", default=None,
                    help="ISO datum do, npr. 2024-12-31")
    ap.add_argument("--quarter", dest="quarter",
                    default=None, help="npr. 2025-Q2")
    args = ap.parse_args()

    q = " ".join(args.query).strip()
    rows = run(q, args.k, args.alpha, use_hybrid=not args.bm25)

    filtered = [r for r in rows if match_filters(
        r, args.date_from, args.date_to, args.quarter)]
    hits = dedupe_by_url(filtered or rows, args.k)

    if not hits:
        print("(no hits)")
        raise SystemExit(0)

    print("Q:", q)
    for i, h in enumerate(hits, 1):
        doc = as_doc(h)
        eff = doc.get("effective_date") or ""
        qtr = doc.get("quarter") or ""
        print(f"{i}. {h.get('url') or ''}")
        print(f"   title: {h.get('title') or ''}")
        sec = h.get("section_title") or ""
        sub = h.get("subsection_title") or ""
        if sec or sub:
            print(f"   section: {sec} | {sub}")
        if eff or qtr:
            print(f"   meta: effective_date={eff} | quarter={qtr}")
        print(f"   → {snippet(h.get('text'))}")
