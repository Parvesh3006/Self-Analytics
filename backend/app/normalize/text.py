import html as html_lib
import re
import unicodedata

from bs4 import BeautifulSoup

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def fold(value: str) -> str:
    """Lower-case and strip accents: 'Zürich' -> 'zurich'."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def norm_key(value: str) -> str:
    """Comparison key: folded, punctuation collapsed to single spaces."""
    return _NON_ALNUM.sub(" ", fold(value)).strip()


def html_to_text(value: str | None) -> str:
    """Convert posting HTML to readable text, keeping paragraphs and list items on their own lines."""
    if not value:
        return ""
    # Some APIs double-escape their HTML.
    if "&lt;" in value and "<" not in value:
        value = html_lib.unescape(value)
    soup = BeautifulSoup(value, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(["br", "p", "li", "div", "h1", "h2", "h3", "h4", "tr"]):
        tag.insert_before("\n")
    text = soup.get_text()
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n\s*(\n\s*)+", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()
