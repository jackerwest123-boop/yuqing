import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import List, Tuple

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


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
    """A light wrapper around the provided Selenium workflow."""

    def __init__(self, headless: bool = True):
        self.driver = self._init_driver(headless=headless)

    def _init_driver(self, headless: bool = True):
        options = Options()
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-insecure-localhost")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--lang=en-US")
        if headless:
            options.add_argument("--headless=new")

        try:
            return webdriver.Chrome(options=options)
        except WebDriverException as exc:  # pragma: no cover - runtime guard
            raise RuntimeError(
                "无法初始化 ChromeDriver，请确认已安装 Chrome 浏览器（支持无头模式）并允许在当前环境运行。"
            ) from exc

    def run(self, keyword_sets: List[List[str]], start_date: str, end_date: str) -> Tuple[List[SearchResult], float]:
        results: List[SearchResult] = []
        start_ts = time.time()

        for keywords in keyword_sets:
            self._google_search(keywords, start_date, end_date)
            links = self._get_search_results()
            for link in links:
                extracted = self._extract_content(link)
                if extracted:
                    results.append(extracted)

        return results, time.time() - start_ts

    def _google_search(self, keywords: List[str], start_date: str, end_date: str):
        query = " ".join([f'"{kw}"' for kw in keywords])
        query = urllib.parse.quote(query)

        url = f"https://www.google.com/search?q={query}&num=30&hl=en"
        self.driver.get(url)

        WebDriverWait(self.driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h3"))
        )

        try:
            tools_btn = WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and .='Tools']"))
            )
            tools_btn.click()
            time.sleep(0.5)

            time_btn = WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and .='Any time']"))
            )
            time_btn.click()
            time.sleep(0.5)

            custom_range_btn = WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(),'Custom range')]"))
            )
            custom_range_btn.click()
            time.sleep(0.5)

            start_input = WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@aria-label='Start date']"))
            )
            start_input.clear()
            start_input.send_keys(start_date)

            end_input = WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@aria-label='End date']"))
            )
            end_input.clear()
            end_input.send_keys(end_date)

            apply_btn = WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@value='Apply']"))
            )
            apply_btn.click()
            time.sleep(1)
        except Exception:  # pragma: no cover - best effort
            pass

    def _get_search_results(self) -> List[str]:
        WebDriverWait(self.driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "h3"))
        )

        elements = self.driver.find_elements(By.CSS_SELECTOR, "h3")
        links: List[str] = []

        for el in elements:
            try:
                link = el.find_element(By.XPATH, "..").get_attribute("href")
                if link:
                    links.append(link)
            except Exception:
                continue

        valid_links = [
            l
            for l in links
            if isinstance(l, str)
            and "wikipedia.org" not in l
            and "youtube.com" not in l
            and "instagram.com" not in l
            and not re.search(r"[\u4e00-\u9fa5]", l)
        ]

        return valid_links[:10]

    def _extract_content(self, link: str) -> SearchResult | None:
        start_t = time.time()

        try:
            self.driver.get(link)
            time.sleep(2)

            title = self.driver.title

            try:
                time_el = self.driver.find_element(By.CSS_SELECTOR, "time")
                time_text = time_el.text
            except Exception:
                time_text = "未找到发布时间"

            p_tags = self.driver.find_elements(By.TAG_NAME, "p")
            content = "\n".join([p.text for p in p_tags if p.text.strip()])

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
        except Exception:
            return None

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

    def __del__(self):  # pragma: no cover - destructor safety
        try:
            self.driver.quit()
        except Exception:
            pass
