import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup


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
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
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

        url = "https://duckduckgo.com/html/"
        params = {"q": query, "kl": "us-en"}

        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
        except requests.RequestException:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select(".result__a")

        search_results: List[SearchResult] = []
        for link_el in items[:10]:
            href = link_el.get("href")
            title = link_el.get_text(strip=True)
            if not href or not title:
                continue

            cleaned_link = self._clean_link(href)
            extracted = self._extract_content(cleaned_link, title)
            if extracted:
                search_results.append(extracted)

        return search_results

    def _clean_link(self, link: str) -> str:
        if "duckduckgo.com/l/?uddg=" in link:
            parsed = urllib.parse.urlparse(link)
            params = urllib.parse.parse_qs(parsed.query)
            if "uddg" in params:
                try:
                    return urllib.parse.unquote(params["uddg"][0])
                except Exception:
                    return link
        return link

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
