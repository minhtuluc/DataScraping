import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode

from .access import Access
from .contracts import CollectionError, Document


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0
        self.cells = 0
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if self.hidden:
            return
        if tag == 'tr':
            self.cells = 0
        if tag in {'td', 'th'}:
            if self.cells:
                self.parts.append(': ' if self.cells == 1 else ' | ')
            self.cells += 1
            self.in_cell = True
        elif tag in {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "table"}:
            self.parts.append(' ' if self.in_cell else '\n')

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1
            return
        if self.hidden:
            return
        if tag in {'td', 'th'}:
            self.in_cell = False
        elif tag in {'p', 'div', 'tr', 'li', 'h1', 'h2', 'h3', 'table'}:
            self.parts.append(' ' if self.in_cell else '\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(re.sub(r'\s+', ' ', data))


def html_text(html: str) -> str:
    parser = TextParser()
    parser.feed(html)
    return "\n".join(re.sub(r'[ \t]+', ' ', line).strip() for line in "".join(parser.parts).splitlines() if line.strip())


class FixtureSource:
    def __init__(self, base: Path):
        self.base = base

    def collect(self, config: dict) -> list[Document]:
        path = (self.base / config["path"]).resolve()
        return [Document(path.as_uri(), path.read_text(encoding="utf-8"), config.get("language", "und"))]


class HtmlSource:
    def __init__(self, access: Access):
        self.access = access
        self.issues = []

    def collect(self, config: dict) -> list[Document]:
        url = config["url"]
        return [Document(url, html_text(self.access.get(url)), config.get("language", "und"))]


class WikipediaSource:
    """Collect explicitly named pages linked from one entity's base article."""
    def __init__(self, access: Access):
        self.access = access
        self.issues: list[dict] = []

    def _parse(self, language: str, title: str) -> dict:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,19}", language):
            raise CollectionError("Invalid Wikipedia language code")
        url = f"https://{language}.wikipedia.org/w/api.php?" + urlencode({
            "action": "parse", "page": title, "prop": "text|revid|langlinks",
            "format": "json", "formatversion": 2, "redirects": 1, "maxlag": 5,
        })
        data = json.loads(self.access.get(url))
        if not isinstance(data, dict) or "error" in data or "parse" not in data:
            raise CollectionError("Wikipedia API error (including missing page or maxlag); no retry")
        article = data['parse']
        if (not isinstance(article, dict) or not isinstance(article.get('text'), str)
                or type(article.get('revid')) is not int or article['revid'] <= 0):
            raise CollectionError('Wikipedia response missing valid text/revision')
        return article

    def collect(self, config: dict) -> list[Document]:
        self.issues = []
        language = config.get("language", "en")
        base = self._parse(language, config["title"])
        articles = [(language, base)]
        links = {link["lang"]: link.get("title", link.get("*")) for link in base.get("langlinks", [])}
        for lang in dict.fromkeys(config.get("languages", [])):
            if lang == language:
                continue
            if lang not in links:
                self.issues.append({'language': lang, 'message': 'Requested translation not available'})
                continue
            try:
                articles.append((lang, self._parse(lang, links[lang])))
            except (CollectionError, ValueError, OSError, TypeError, KeyError) as exc:
                self.issues.append({'language': lang, 'message': str(exc)})
        return [Document(
            f"https://{lang}.wikipedia.org/w/index.php?oldid={article['revid']}",
            html_text(article["text"]), lang, str(article["revid"]),
        ) for lang, article in articles]


def make_source(kind: str, base: Path, access: Access):
    return {"fixture": lambda: FixtureSource(base), "html": lambda: HtmlSource(access),
            "wikipedia": lambda: WikipediaSource(access)}[kind]()
