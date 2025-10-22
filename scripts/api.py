
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from scripts.weaviate_client import WVT

app = FastAPI(title="Digwatch Retriever API", version="1.0")


@app.get("/healthz")
def healthz():
    try:
        _ = WVT.schema.get()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Weaviate not reachable: {e}")


def _dw_snippet(s: str, n: int = 700) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def _as_update(r: dict) -> dict:
    arr = r.get("updateRef") or []
    return arr[0] if arr else {}


def _match_filters(
    r: dict,
    dt_from: Optional[str],
    dt_to: Optional[str],
    quarter: Optional[str],
) -> bool:
    d = _as_update(r)
    eff = (d.get("effective_date") or "").strip()
    qtr = (d.get("quarter") or "").strip()
    if quarter and quarter != qtr:
        return False
    if dt_from and (not eff or eff < dt_from):
        return False
    if dt_to and (not eff or eff > dt_to):
        return False
    return True


@app.get("/retrieve_digwatch")
def retrieve_digwatch(
    q: str = Query(..., description="Query string"),
    k: int = Query(5, ge=1, le=20, description="Top-K jedinstvenih URL-ova"),
    alpha: float = Query(0.35, ge=0.0, le=1.0, description="Hybrid alpha"),
    date_from: Optional[str] = Query(
        None, alias="from", description="ISO npr. 2024-01-01"),
    date_to: Optional[str] = Query(
        None, alias="to", description="ISO npr. 2024-12-31"),
    quarter: Optional[str] = Query(None, description="npr. 2025-Q2"),
    bm25: bool = Query(False, description="True=BM25, False=Hybrid"),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    fetch = max(50, k * 12)
    fields = [
        "title",
        "url",
        "text",
        "section_title",
        "subsection_title",
        'updateRef { ... on DigwatchUpdate { url title effective_date quarter tag_names category_names } }',
    ]

    # 1) Weaviate upit
    try:
        qobj = WVT.query.get("DigwatchParagraph", fields).with_limit(fetch)
        if bm25:
            qobj = qobj.with_bm25(query=q)
        else:
            qobj = qobj.with_hybrid(query=q, alpha=alpha)
        rows = qobj.do()["data"]["Get"]["DigwatchParagraph"] or []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Weaviate query failed: {e}")

    # 2) (opciono) filter po meta (iz updateRef)
    if date_from or date_to or quarter:
        rows = [r for r in rows if _match_filters(
            r, date_from, date_to, quarter)]

    # 3) dedupe po URL-u i top-K
    seen, picked = set(), []
    for r in rows:
        u = (r.get("url") or "").rstrip("/")
        if not u or u in seen:
            continue
        seen.add(u)
        picked.append(r)
        if len(picked) >= k:
            break

    # 4) izlaz (kompatibilno sa Dify /retrieve stilom)
    context, src, meta = [], [], []
    for r in picked:
        doc = _as_update(r)
        context.append(_dw_snippet(r.get("text") or ""))
        src.append(r.get("url"))
        meta.append({
            "title": r.get("title"),
            "section": r.get("section_title"),
            "subsection": r.get("subsection_title"),
            "effective_date": doc.get("effective_date"),
            "quarter": doc.get("quarter"),
            "doc_title": doc.get("title"),
            "doc_url": doc.get("url"),
            "tags": doc.get("tag_names") or [],
            "categories": doc.get("category_names") or [],
        })

    return JSONResponse({
        "query": q,
        "mode": "digwatch_paras",
        "alpha": alpha,
        "k": k,
        "filters": {"from": date_from, "to": date_to, "quarter": quarter, "bm25": bm25},
        "count": len(context),
        "context": context,
        "source_urls": src,
        "meta": meta
    })
