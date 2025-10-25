# make_newsletter.py
import os
import json
import datetime as dt
from typing import List, Dict, Any, Optional  # NEW
import requests
from dotenv import load_dotenv
import shutil  # NEW

load_dotenv()  # učitaj .env (OPENAI_API_KEY, po želji i druge)

# ============ KONFIG ============
TOOL_URL = "http://localhost:8000/retrieve_digwatch"  # tvoj custom Tool endpoint

# Q3 2025 (po potrebi promeni opseg ili query)
PARAMS = {
    "q": "*",        # npr. "AI Act" / "cybersecurity" za fokus
    "k": 20,         # koliko vesti da povučemo
    "alpha": 0.35,   # ako tvoj endpoint koristi hybrid parametar
    # "quarter": "2025-Q3",  # uključi ako tvoj endpoint podržava ovaj filter
}

# Newsletter meta
QUARTER = "Q3"
YEAR = "2025"
NEWSLETTER_TITLE = f"Swiss Digital Policy Newsletter – {QUARTER} {YEAR}"

# LLM model
OPENAI_MODEL = "gpt-4o"  # po potrebi izmeni
# ================================

# ---------- OpenAI minimal klijent ----------
try:
    from openai import OpenAI
    _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    _client = None
    print("[WARN] OpenAI client not initialized. Set OPENAI_API_KEY and install `openai` package.")


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _call_tool(params: Dict[str, Any]) -> Any:
    """Jedan poziv tvog Tool-a (GET)."""
    r = requests.get(TOOL_URL, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_updates() -> List[Dict[str, Any]]:
    """
    Zove tvoj custom Tool i vraća listu updejta normalizovanih polja:
    - title, url, date, snippet
    Pokušava da iskoristi `meta` i `source_urls` (ako postoje),
    a u fallback-u izvuče iz `context`.
    """
    # Primarni pokušaj
    try:
        data = _call_tool(PARAMS)
    except requests.HTTPError as e:
        # Ako API vrati 422 (npr. ne podržava neki parametar), pokušaj “fallback” bez svega što nije q/k/alpha/quarter
        if e.response is not None and e.response.status_code == 422:
            fallback = {k: v for k, v in PARAMS.items() if k in (
                "q", "k", "alpha", "quarter")}
            data = _call_tool(fallback)
        else:
            raise

    items: List[Dict[str, Any]] = []

    # Očekivani format:
    # {
    #   "context": [...],
    #   "source_urls": [...],
    #   "meta": [{ "title": ..., "effective_date": ..., "doc_url": ... }, ...]
    # }
    if isinstance(data, dict):
        context = data.get("context")
        srcs = data.get("source_urls")
        meta = data.get("meta")

        if isinstance(meta, list) and (context or srcs):
            n = max(len(meta), len(context or []), len(srcs or []))
            for i in range(n):
                m = meta[i] if i < len(meta) else {}
                snippet = (context[i] if (
                    context and i < len(context)) else None)
                url = m.get("doc_url") or (srcs[i] if (
                    srcs and i < len(srcs)) else None)
                date = m.get("effective_date") or m.get("date")

                items.append({
                    "title": m.get("title"),
                    "url": url,
                    "date": date,
                    "snippet": (snippet or "")[:1200]
                })
            return items

        # Ako nema meta/source_urls, ali ima "context"
        if "context" in data and isinstance(data["context"], list):
            for txt in data["context"]:
                items.append({
                    "title": None,
                    "url": None,
                    "date": None,
                    "snippet": _safe_str(txt)[:1200]
                })
            return items

    # Ako je lista objekata [{title,url,text,date,...}, ...]
    if isinstance(data, list):
        for it in data:
            items.append({
                "title": it.get("title") or it.get("heading"),
                "url": it.get("url") or it.get("link"),
                "date": it.get("date") or it.get("published_at"),
                "snippet": (it.get("text") or it.get("snippet") or it.get("summary") or "")[:1200]
            })
        return items

    # Fallback — upiši sve raw
    items.append({
        "title": None,
        "url": None,
        "date": None,
        "snippet": json.dumps(data)[:1200]
    })
    return items


def build_prompt(items: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Priprema system + user prompt: tražimo JSON newslettera (EU + Global)
    sa briefovima u formatu: title, summary, relevance.
    """
    compact_sources = []
    for it in items:
        compact_sources.append({
            "title": it.get("title"),
            "url": it.get("url"),
            "date": it.get("date"),
            "snippet": it.get("snippet")[:800] if it.get("snippet") else None
        })

    system_prompt = """
You are an expert policy analyst for Swiss cantonal and local IT authorities.
Using the provided sources, produce a QUARTERLY newsletter focusing on EU and global digital policy developments
relevant to Swiss public administration (interoperability, compliance, procurement, risk).

Return STRICT JSON with this schema:
{
  "newsletter_title": "string",
  "introduction": "string (2-3 short paragraphs)",
  "sections": [
    {
      "section_name": "European Union",
      "briefs": [
        {
          "title": "string",
          "summary": "string (what happened, who, when, how)",
          "relevance": "string (why Swiss cantonal/local authorities should care)"
        }
      ]
    },
    {
      "section_name": "Global",
      "briefs": [
        {
          "title": "string",
          "summary": "string",
          "relevance": "string"
        }
      ]
    }
  ],
  "conclusion": "string (key takeaways for Swiss administration)"
}

Rules:
- Be concise and concrete.
- Prefer developments from the last 3 months.
- Never invent links or dates; if unknown, omit.
- If sources lack enough EU vs Global coverage, do best effort with what's available.
- Do NOT include anything except valid JSON.
""".strip()

    user_prompt = json.dumps({
        "newsletter_title": NEWSLETTER_TITLE,
        "time_window_hint": f"{QUARTER} {YEAR}",
        "sources": compact_sources
    }, ensure_ascii=False)

    return {"system": system_prompt, "user": user_prompt}


def call_openai_json(system: str, user: str) -> Dict[str, Any]:
    """
    Poziv OpenAI chat completions sa JSON-only output očekivanjem.
    """
    if _client is None:
        raise RuntimeError(
            "OpenAI client not initialized. Ensure OPENAI_API_KEY and `openai` package."
        )

    resp = _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    content = resp.choices[0].message.content
    return json.loads(content)


def render_markdown(news_json: Dict[str, Any]) -> str:
    """
    Pretvara JSON newsletter u Markdown (za pregled / export).
    """
    md: List[str] = []
    md.append(f"# {news_json.get('newsletter_title', NEWSLETTER_TITLE)}")
    md.append("")
    md.append("## Introduction")
    md.append(_safe_str(news_json.get("introduction", "")).strip())
    md.append("\n---\n")

    sections = news_json.get("sections", []) or []
    for section in sections:
        md.append(
            f"## Key Developments – {_safe_str(section.get('section_name', 'Section'))}")
        md.append("")
        for brief in section.get("briefs", []) or []:
            md.append(f"### {_safe_str(brief.get('title', 'Untitled'))}")
            md.append("**Summary:**  ")
            md.append(_safe_str(brief.get("summary", "")).strip() + "\n")
            md.append("**Relevance for Swiss public administration:**  ")
            # NOTE: keep as-is if already correct
            md.append(_safe_str(brief.get("relevance", "")).strip() + "\n")
            md.append("---\n")

    md.append("## Conclusion")
    md.append(_safe_str(news_json.get("conclusion", "")).strip())
    md.append("")
    return "\n".join(md)

# NEW: PDF render iz Markdowna pomoću pypandoc (bezbedan fallback)


def render_pdf_from_markdown(md_path: str) -> Optional[str]:
    """
    Pokušaj da konvertuje Markdown u PDF pomoću pypandoc.
    Vraća putanju do PDF fajla ili None ako nije moguće (pypandoc/pandoc nisu instalirani).
    """
    try:
        import pypandoc  # type: ignore
    except Exception:
        print(
            "[INFO] pypandoc nije instaliran. Preskačem PDF export. (pip install pypandoc)")
        return None

    if shutil.which("pandoc") is None:
        print("[INFO] `pandoc` nije pronađen u PATH-u. Preskačem PDF export. (install: https://pandoc.org/install.html)")
        return None

    pdf_path = os.path.splitext(md_path)[0] + ".pdf"
    try:
        pypandoc.convert_file(md_path, "pdf", outputfile=pdf_path)
        return pdf_path
    except Exception as e:
        print(f"[WARN] PDF export nije uspeo: {e}")
        return None


def save_outputs(news_json: Dict[str, Any]) -> Dict[str, str]:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M")
    json_path = f"newsletter_{QUARTER}_{YEAR}_{ts}.json"
    md_path = f"newsletter_{QUARTER}_{YEAR}_{ts}.md"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(news_json, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(news_json))

    # NEW: automatski PDF iz MD (ako moguće)
    pdf_path = render_pdf_from_markdown(md_path)
    out = {"json": json_path, "md": md_path}
    if pdf_path:
        out["pdf"] = pdf_path
    return out


def main():
    print("[1/4] Fetching updates from custom Tool...")
    items = fetch_updates()
    if not items:
        print("No items fetched. Check TOOL_URL/params.")
        return
    print(f"[OK] Got {len(items)} items.")

    print("[2/4] Building prompts...")
    prompts = build_prompt(items)

    print("[3/4] Calling LLM...")
    news_json = call_openai_json(prompts["system"], prompts["user"])

    print("[4/4] Saving outputs...")
    paths = save_outputs(news_json)
    print(f"[DONE] Saved:\n  JSON: {paths['json']}\n  MD:   {paths['md']}")
    if "pdf" in paths:
        print(f"  PDF:  {paths['pdf']}")
    else:
        print("Tip: PDF export preskočen (instaliraj `pandoc` i `pypandoc` ili koristi 'Print to PDF').")


if __name__ == "__main__":
    main()
