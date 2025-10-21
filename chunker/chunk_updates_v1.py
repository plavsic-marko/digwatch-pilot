from pathlib import Path
import json
import re
import html
from bs4 import BeautifulSoup
from datetime import datetime

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "updates_all.json"
TAX = Path(__file__).resolve().parents[1] / \
    "data" / "raw" / "taxonomy_map.json"
OUT = Path(__file__).resolve().parents[1] / \
    "data" / "processed" / "updates_paragraphs.jsonl"
OUT.parent.mkdir(parents=True, exist_ok=True)

BLACKLIST_PHRASES = [
    "share this", "subscribe", "newsletter", "leave a comment",
    "next post", "previous post", "related posts", "read more",
    "cookie", "privacy policy", "terms of use",
    "would you like to learn more about ai, tech and digital diplomacy",
    "ask our diplo chatbot",
]
MIN_WORDS = 12
TOKEN_RE = re.compile(r"[A-Za-zÀ-ž0-9]+")


def words_count(txt: str) -> int:
    return len(TOKEN_RE.findall(txt or ""))


def clean_text(txt: str) -> str:
    if not txt:
        return ""
    txt = html.unescape(txt).replace("\xa0", " ")
    txt = re.sub(r"\s+", " ", txt, flags=re.MULTILINE).strip()
    return txt


def is_blacklisted(txt: str) -> bool:
    low = (txt or "").lower()
    return any(ph in low for ph in BLACKLIST_PHRASES)


def table_to_lines(tbl) -> list[str]:
    lines, headers = [], []
    for th in tbl.find_all("th"):
        hdr = clean_text(th.get_text(" ", strip=True))
        if hdr:
            headers.append(hdr)
    if headers:
        lines.append(" | ".join(headers))
    for tr in tbl.find_all("tr"):
        cells = []
        for cell in tr.find_all(["td", "th"]):
            val = clean_text(cell.get_text(" ", strip=True))
            if val:
                cells.append(val)
        if cells:
            lines.append(" | ".join(cells))
    return [ln for ln in lines if ln]


def list_to_paragraph(ul_or_ol) -> str:
    items = []
    for li in ul_or_ol.find_all("li", recursive=False):
        t = clean_text(li.get_text(" ", strip=True))
        if t:
            items.append(f"• {t}")
    return " ".join(items) if items else ""


def extract_chunks_from_html(html_in: str):
    soup = BeautifulSoup(html_in or "", "lxml")
    for tag in soup(["script", "style", "iframe", "noscript"]):
        tag.decompose()
    chunks, h2, h3 = [], None, None
    for el in soup.find_all(["h2", "h3", "p", "ul", "ol", "blockquote", "table"]):
        name = el.name.lower()
        if name == "h2":
            h2, h3 = clean_text(el.get_text(" ", strip=True)), None
            continue
        if name == "h3":
            h3 = clean_text(el.get_text(" ", strip=True))
            continue
        if name == "p":
            text = clean_text(el.get_text(" ", strip=True))
            if text:
                chunks.append(
                    {"section_title": h2, "subsection_title": h3, "paragraph_text": text})
            continue
        if name == "blockquote":
            text = clean_text(el.get_text(" ", strip=True))
            if text:
                chunks.append(
                    {"section_title": h2, "subsection_title": h3, "paragraph_text": text})
            continue
        if name in ("ul", "ol"):
            text = clean_text(list_to_paragraph(el))
            if text:
                chunks.append(
                    {"section_title": h2, "subsection_title": h3, "paragraph_text": text})
            continue
        if name == "table":
            for ln in table_to_lines(el):
                ln = clean_text(ln)
                if ln:
                    chunks.append(
                        {"section_title": h2, "subsection_title": h3, "paragraph_text": ln})
            continue
    if not chunks:
        for p in soup.find_all("p"):
            text = clean_text(p.get_text(" ", strip=True))
            if text:
                chunks.append(
                    {"section_title": None, "subsection_title": None, "paragraph_text": text})
    return chunks


def to_quarter(iso_dt: str) -> str | None:
    try:
        dt = datetime.fromisoformat(iso_dt.replace("Z", "+00:00"))
        q = (dt.month - 1) // 3 + 1
        return f"{dt.year}-Q{q}"
    except Exception:
        return None


def newer(a: str | None, b: str | None) -> str | None:
    """Vrati noviji ISO string između a i b (ili prvo dostupno)."""
    def parse(x):
        try:
            return datetime.fromisoformat(x.replace("Z", "+00:00"))
        except Exception:
            return None
    da, db = parse(a) if a else None, parse(b) if b else None
    if da and db:
        return a if da >= db else b
    return a or b


def main():
    assert RAW.exists(), f"Nema ulaza: {RAW}"
    cat_map, tag_map = {}, {}
    if TAX.exists():
        tax = json.loads(TAX.read_text(encoding="utf-8"))
        cat_map = tax.get("categories") or {}
        tag_map = tax.get("tags") or {}

    posts = json.loads(RAW.read_text(encoding="utf-8"))

    wrote, skipped_paras = 0, 0
    with OUT.open("w", encoding="utf-8") as f:
        for p in posts:
            title = clean_text(((p.get("title") or {}).get("rendered")) or "")
            url = (p.get("link") or "").strip().rstrip("/")
            date = (p.get("date") or "").strip()
            modified = (p.get("modified") or "").strip()
            html_body = (p.get("content") or {}).get("rendered") or ""

            cat_ids = p.get("categories") or []
            tag_ids = p.get("tags") or []
            cat_names = [cat_map.get(cid)
                         for cid in cat_ids if cat_map.get(cid)]
            tag_names = [tag_map.get(tid)
                         for tid in tag_ids if tag_map.get(tid)]

            effective_date = newer(modified, date) or date or modified or ""
            quarter = to_quarter(effective_date or date)

            for ch in extract_chunks_from_html(html_body):
                text = ch.get("paragraph_text") or ""
                if is_blacklisted(text) or words_count(text) < MIN_WORDS:
                    skipped_paras += 1
                    continue

                rec = {
                    "source": "dig.watch",
                    "node_type": "paragraph",
                    "title": title,
                    "url": url,
                    "date": date,
                    "modified": modified,
                    "effective_date": effective_date,
                    "quarter": quarter,
                    "section_title": ch.get("section_title"),
                    "subsection_title": ch.get("subsection_title"),
                    "text": text,
                    "category_names": cat_names,
                    "tag_names": tag_names,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                wrote += 1
    print(f"V1.1 → {OUT} | zapisa: {wrote} | preskočeno: {skipped_paras}")


if __name__ == "__main__":
    main()
