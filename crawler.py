import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup
from requests_html import HTMLSession


@dataclass
class SearchResult:
    title: str
    author: str
    published_at: str
    media_cn: str
    media_en: str
    content: str
    link: str
    elapsed: float


class GoogleCrawler:
    """A lightweight crawler that uses DuckDuckGo HTML search for speed."""

    def __init__(self):
        self.session = HTMLSession()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0 Safari/537.36"
                ),
            }
        )

    def run(self, keyword_sets: List[List[str]], start_date: str, end_date: str) -> Tuple[List[SearchResult], float]:
        results: List[SearchResult] = []
        start_ts = time.time()

        for keywords in keyword_sets:
            results.extend(self._search_keywords(keywords, start_date, end_date))

        return results, time.time() - start_ts

    def _search_keywords(self, keywords: List[str], start_date: str, end_date: str) -> List[SearchResult]:
        quoted = " ".join([f'"{kw}"' for kw in keywords])
        date_hint = self._build_date_hint(start_date, end_date)
        query = f"{quoted} {date_hint}".strip()

        items = self._fetch_result_links(query)

        search_results: List[SearchResult] = []
        for link_el in items[:10]:
            href = self._get_attr(link_el, "href")
            title = self._get_text(link_el)
            if not href or not title:
                continue

            cleaned_link = self._clean_link(href)
            extracted = self._extract_content(cleaned_link, title)
            if extracted:
                search_results.append(extracted)
                continue

            fallback = self._build_fallback_result(link_el, cleaned_link, title)
            if fallback:
                search_results.append(fallback)

        return search_results

    def _fetch_result_links(self, query: str) -> List:
        """Try a rendered DuckDuckGo page first, then multiple HTML fallbacks."""

        rendered_items: List = []
        try:
            resp = self.session.get(
                "https://duckduckgo.com/", params={"q": query, "ia": "web"}, timeout=15
            )
            resp.html.render(timeout=20, sleep=1)
            rendered_items = resp.html.find("a.result__a")
        except Exception:
            rendered_items = []

        if rendered_items:
            return rendered_items

        endpoints = [
            ("https://duckduckgo.com/html/", ".result__a"),
            ("https://html.duckduckgo.com/html/", ".result__a"),
            ("https://duckduckgo.com/lite/", "a.result-link"),
        ]
        params = {"q": query, "kl": "us-en"}

        for url, selector in endpoints:
            try:
                resp = self.session.get(url, params=params, timeout=10)
                resp.raise_for_status()
            except requests.RequestException:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select(selector)
            if items:
                return items

        return []

    def _get_attr(self, link_el, attr: str):
        if hasattr(link_el, "attrs"):
            return link_el.attrs.get(attr)
        if hasattr(link_el, "get"):
            return link_el.get(attr)
        return None

    def _get_text(self, link_el) -> str:
        if hasattr(link_el, "text") and getattr(link_el, "text"):
            return link_el.text.strip()
        if hasattr(link_el, "get_text"):
            return link_el.get_text(strip=True)
        return ""

    def _clean_link(self, link: str) -> str:
        if link.startswith("/l/?"):
            link = f"https://duckduckgo.com{link}"

        parsed = urllib.parse.urlparse(link)
        params = urllib.parse.parse_qs(parsed.query)

        if "uddg" in params and params["uddg"]:
            try:
                return urllib.parse.unquote(params["uddg"][0])
            except Exception:
                return link

        return link

    def _build_fallback_result(self, link_el, link: str, title: str) -> SearchResult | None:
        snippet = self._find_snippet_text(link_el)
        media_cn, media_en = self._guess_media_names(link)

        return SearchResult(
            title=title,
            author="未知作者",
            published_at="未找到发布时间",
            media_cn=media_cn,
            media_en=media_en,
            content=snippet or "未能抓取到正文内容。",
            link=link,
            elapsed=0.0,
        )

    def _find_snippet_text(self, link_el) -> str:
        if type(link_el).__module__.startswith("requests_html"):
            ancestors = [link_el]
            try:
                parent = link_el.element.getparent()
                if parent is not None:
                    ancestors.append(parent)
                    grand = parent.getparent()
                    if grand is not None:
                        ancestors.append(grand)
            except Exception:
                pass

            for anc in ancestors:
                for selector in [".result__snippet", "p"]:
                    try:
                        found = anc.find(selector, first=True)
                        if found and getattr(found, "text", ""):
                            return found.text.strip()
                    except Exception:
                        continue

                if hasattr(anc, "text") and anc.text:
                    return anc.text.strip()

            return ""

        for ancestor in [link_el, link_el.parent, getattr(link_el, "parent", None) and link_el.parent.parent]:
            if not ancestor:
                continue

            snippet_node = ancestor.find(class_=re.compile("snippet", re.IGNORECASE))
            if snippet_node and snippet_node.get_text(strip=True):
                return snippet_node.get_text(strip=True)

            snippet_node = ancestor.find("p")
            if snippet_node and snippet_node.get_text(strip=True):
                return snippet_node.get_text(strip=True)

        return ""

    def _extract_content(self, link: str, title: str) -> SearchResult | None:
        start_t = time.time()

        try:
            resp = self.session.get(link, timeout=8)
            resp.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        content = "\n".join(paragraphs[:10])

        time_text = self._find_time_text(soup)
        media_cn, media_en = self._guess_media_names(link)

        return SearchResult(
            title=title,
            author="未知作者",
            published_at=time_text,
            media_cn=media_cn,
            media_en=media_en,
            content=content,
            link=link,
            elapsed=time.time() - start_t,
        )

    def _find_time_text(self, soup: BeautifulSoup) -> str:
        time_tag = soup.find("time")
        if time_tag and time_tag.get_text(strip=True):
            return time_tag.get_text(strip=True)

        meta_time = soup.find("meta", attrs={"property": "article:published_time"})
        if meta_time and meta_time.get("content"):
            return meta_time.get("content")

        meta_date = soup.find("meta", attrs={"name": "date"})
        if meta_date and meta_date.get("content"):
            return meta_date.get("content")

        return "未找到发布时间"

    def _guess_media_names(self, link: str) -> Tuple[str, str]:
        match = re.search(r"https?://([^/]+)/", link)
        domain = match.group(1) if match else link
        media_en = domain
        media_cn = {
            "reuters.com": "路透社",
            "apnews.com": "美联社",
            "bloomberg.com": "彭博社",
            "nytimes.com": "纽约时报",
        }.get(domain, "未知媒体")
        return media_cn, media_en

    def _build_date_hint(self, start_date: str, end_date: str) -> str:
        if start_date and end_date:
            return f"after:{start_date} before:{end_date}"
        return ""
