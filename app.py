import datetime
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from openai import OpenAI

from crawler import GoogleCrawler, SearchResult


load_dotenv()

app = Flask(__name__)
app.secret_key = "keyword-search-demo"
client: OpenAI | None = None


RANGE_PRESETS = {
    "1d": 1,
    "3d": 3,
    "1m": 30,
}


@dataclass
class SearchState:
    keyword_sets: List[List[str]] = field(default_factory=list)
    range_label: str = "Custom"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    results: List[SearchResult] = field(default_factory=list)
    duration: float = 0.0


state = SearchState()


def _compute_dates(range_option: str, custom_start: str, custom_end: str) -> Tuple[str, str, str]:
    today = datetime.date.today()
    range_label = "Custom"

    if range_option in RANGE_PRESETS:
        days = RANGE_PRESETS[range_option]
        start_date = (today - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        range_label = {"1d": "最近一天", "3d": "最近三天", "1m": "最近一个月"}[range_option]
    else:
        start_date = custom_start
        end_date = custom_end

    return range_label, start_date, end_date


def _parse_keyword_sets(raw: str) -> List[List[str]]:
    keyword_lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return [line.split() for line in keyword_lines if line]


@app.route("/")
def index():
    return render_template("index.html", state=state)


@app.route("/search", methods=["POST"])
def search():
    keyword_block = request.form.get("keyword_sets", "")
    range_option = request.form.get("range_option", "custom")
    custom_start = request.form.get("start_date", "")
    custom_end = request.form.get("end_date", "")

    keyword_sets = _parse_keyword_sets(keyword_block)
    if not keyword_sets:
        flash("请至少提供一组关键字（每行一组，组内以空格分隔）。")
        return redirect(url_for("index"))

    range_label, start_date, end_date = _compute_dates(range_option, custom_start, custom_end)

    crawler = GoogleCrawler()
    results, duration = crawler.run(keyword_sets, start_date=start_date, end_date=end_date)

    state.keyword_sets = keyword_sets
    state.range_label = range_label
    state.start_date = start_date
    state.end_date = end_date
    state.results = results
    state.duration = duration

    if not results:
        flash("未获取到搜索结果，请检查关键字或稍后再试。")

    return redirect(url_for("index"))


@app.route("/analyze", methods=["POST"])
def analyze():
    question = request.form.get("question", "").strip()
    selected_ids = request.form.getlist("selected")

    if not question:
        flash("请输入提问内容。")
        return redirect(url_for("index"))

    if not selected_ids:
        flash("请至少选择一条搜索结果进行分析。")
        return redirect(url_for("index"))

    selected = []
    for sid in selected_ids:
        try:
            idx = int(sid)
            if 0 <= idx < len(state.results):
                selected.append(state.results[idx])
        except ValueError:
            continue

    answer = _ai_answer(question, selected)
    flash(answer)
    return redirect(url_for("index"))


def _ai_answer(question: str, results: List[SearchResult]) -> str:
    global client

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "未检测到 OPENAI_API_KEY 环境变量，请在环境中配置有效的 OpenAI API Key（可在 .env 文件中设置）。"

    if client is None:
        client = OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL"))

    context = []
    for res in results:
        context.append(
            f"标题：{res.title}\n来源：{res.media_cn} ({res.media_en})\n链接：{res.link}\n摘要：{res.content[:400]}"
        )

    prompt = (
        "你是一名情报分析助理，需要基于提供的搜索结果回答用户问题。"
        "请引用相关来源并用简洁的中文要点回复，最后附上你的不确定性说明。"
    )

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"用户问题：{question}\n可用资料：\n" + "\n\n".join(context),
                },
            ],
            temperature=0.3,
            max_tokens=500,
        )
    except Exception as exc:  # pragma: no cover - runtime guard
        return f"调用 OpenAI 接口失败：{exc}"

    return completion.choices[0].message.content if completion.choices else "未能生成有效回答。"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
