import re
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate

USER_ID     = "140019807"
README_PATH = "README.md"
HEADERS     = {"User-Agent": "Mozilla/5.0 (compatible; GoodReads-README-Bot/1.0)"}


# ── fetch ────────────────────────────────────────────────────────────────────

def fetch_rss(shelf, limit=10, sort=None):
    url = (
        f"https://www.goodreads.com/review/list_rss/{USER_ID}"
        f"?shelf={shelf}&per_page={limit}"
    )
    if sort:
        url += f"&sort={sort}&order=d"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


# ── parse ────────────────────────────────────────────────────────────────────

def to_stars(rating_str):
    try:
        n = int(rating_str or 0)
        return "⭐" * n if n > 0 else "—"
    except ValueError:
        return "—"

def parse_date(date_str):
    """Parse an RFC 2822 date string into a sortable tuple. Returns (0,) on failure."""
    try:
        t = parsedate(date_str.strip())
        return t[:6] if t else (0,)
    except Exception:
        return (0,)

def parse_items(xml_bytes, sort_by_read_date=False):
    root  = ET.fromstring(xml_bytes)
    books = []
    for item in root.findall(".//item"):
        raw   = item.findtext("title", "").strip()
        # GoodReads occasionally embeds author in title: "Title\n  by Author"
        title = raw.split("\n")[0].strip()
        books.append({
            "title":   title,
            "author":  item.findtext("author_name", "Unknown").strip(),
            "link":    item.findtext("link", "").strip(),
            "rating":  to_stars(item.findtext("user_rating", "0")),
            "read_at": item.findtext("user_read_at", "").strip(),
        })
    if sort_by_read_date:
        books.sort(key=lambda b: parse_date(b["read_at"]), reverse=True)
    return books


# ── render ───────────────────────────────────────────────────────────────────

def render_currently_reading(books):
    if not books:
        return "_Nothing on the shelf right now._\n"
    rows = ["| Book | Author |", "| ---- | ------ |"]
    for b in books:
        rows.append(f"| [{b['title']}]({b['link']}) | {b['author']} |")
    return "\n".join(rows) + "\n"

def render_recently_finished(books):
    if not books:
        return "_No books logged yet._\n"
    rows = ["| Book | Author | Rating |", "| ---- | ------ | ------ |"]
    for b in books:
        rows.append(f"| [{b['title']}]({b['link']}) | {b['author']} | {b['rating']} |")
    return "\n".join(rows) + "\n"


# ── patch README ─────────────────────────────────────────────────────────────

def patch_readme(marker, content):
    with open(README_PATH, encoding="utf-8") as f:
        text = f.read()

    start   = f"<!-- {marker}:START -->"
    end     = f"<!-- {marker}:END -->"
    pattern = re.compile(
        rf"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL
    )

    if not pattern.search(text):
        print(f"  ⚠  marker {marker!r} not found in README — skipping")
        return

    updated = pattern.sub(f"{start}\n{content}{end}", text)
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"  ✓  patched {marker}")


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("→ currently-reading shelf")
    currently = parse_items(fetch_rss("currently-reading", limit=10))
    print(f"  {len(currently)} book(s) found")

    print("→ read shelf")
    # sort=date_read in the URL asks GoodReads to order by read date server-side;
    # sort_by_read_date=True re-sorts on our end as a fallback using user_read_at.
    finished = parse_items(
        fetch_rss("read", limit=10, sort="date_read"),
        sort_by_read_date=True,
    )
    finished = finished[:5]   # keep only the 5 most recent after sorting
    print(f"  {len(finished)} book(s) found")

    patch_readme("GOODREADS-CURRENTLY-READING", render_currently_reading(currently))
    patch_readme("GOODREADS-READ",              render_recently_finished(finished))

    print("Done.")
