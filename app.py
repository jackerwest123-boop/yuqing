import datetime
import os
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from openai import OpenAI

from crawler import GoogleCrawler, SearchResult


app = Flask(__name__)
app.secret_key = "keyword-search-demo"


RANGE_PRESETS = {
    "1d": 1,
    "3d": 3,
    "1m": 30,
}


@dataclass
class SearchState:
    keyword_sets: List[List[str]] = field(default_factory=list)
    range_option: str = "1d"
    range_label: str = "最近一天"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    results: List[SearchResult] = field(default_factory=list)
    duration: float = 0.0


def _compute_dates(range_option: str, custom_start: str, custom_end: str) -> Tuple[str, str, str, str]:
    today = datetime.date.today()
    range_label = "Custom"

    if range_option in RANGE_PRESETS:
        days = RANGE_PRESETS[range_option]
        start_date = (today - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        range_label = {"1d": "最近一天", "3d": "最近三天", "1m": "最近一个月"}[range_option]
    else:
        # 确保自定义日期有值，默认使用今天
        start_date = custom_start or today.strftime("%Y-%m-%d")
        end_date = custom_end or today.strftime("%Y-%m-%d")

    return range_option, range_label, start_date, end_date


def _parse_keyword_sets(raw: str) -> List[List[str]]:
    keyword_lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return [line.split() for line in keyword_lines if line]


# 全局搜索状态
state = SearchState()

# 初始化默认日期范围
_, state.range_label, state.start_date, state.end_date = _compute_dates(
    state.range_option, "", ""
)


def _load_demo_state():
    today = datetime.date.today().strftime("%Y-%m-%d")
    demo_results = [
        SearchResult(
            title="示例：AI 驱动的安全情报分析",
            author="示例作者",
            published_at=today,
            media_cn="路透社",
            media_en="reuters.com",
            content=(
                "这是一段用于预览界面的示例正文，展示了搜索结果的排版、媒体中英文名、"
                "作者、发布时间以及摘要截断的效果。使用“快速预览”即可无需运行爬虫直接查看界面。"
            ),
            link="https://www.reuters.com/example",
            elapsed=0.05,
        ),
        SearchResult(
            title="示例：供应链风险监测周报",
            author="示例作者",
            published_at=today,
            media_cn="纽约时报",
            media_en="nytimes.com",
            content=(
                "第二条示例结果，便于快速对比列表样式、勾选框、多条结果展示以及 AI 分析表单。"
                "真实搜索时会由爬虫自动填充。"
            ),
            link="https://www.nytimes.com/example",
            elapsed=0.04,
        ),
    ]

    state.keyword_sets = [["示例", "AI"], ["供应链", "风险"]]
    state.range_option = "demo"
    state.range_label = "示例数据"
    state.start_date = today
    state.end_date = today
    state.results = demo_results
    state.duration = 0.0


@app.route("/")
def index():
    if request.args.get("demo"):
        _load_demo_state()
        flash("已加载示例数据，可直接预览界面，无需运行爬虫。")
    return render_template("index.html", state=state)


@app.route("/demo")
def demo():
    _load_demo_state()
    flash("已加载示例数据，可直接预览界面，无需运行爬虫。")
    return redirect(url_for("index"))


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

    range_option, range_label, start_date, end_date = _compute_dates(
        range_option, custom_start, custom_end
    )

    # 先保留用户输入的搜索配置，即使爬虫失败也能在页面上回显，便于调整后重试
    state.keyword_sets = keyword_sets
    state.range_option = range_option
    state.range_label = range_label
    state.start_date = start_date
    state.end_date = end_date

    try:
        crawler = GoogleCrawler()
        results, duration = crawler.run(
            keyword_sets, start_date=start_date, end_date=end_date
        )
    except RuntimeError as exc:
        flash(str(exc))
        return redirect(url_for("index"))

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

    try:
        answer = _ai_answer(question, selected)
        flash(answer)
    except RuntimeError as exc:
        flash(str(exc))
    except Exception:
        flash("AI 分析失败，请检查 OpenAI 配置或稍后再试。")
    return redirect(url_for("index"))


@app.route("/.well-known/appspecific/com.chrome.devtools.json")
def chrome_devtools_probe():
    """避免浏览器探测请求报 404，返回空配置。"""
    return jsonify({"status": "ok"})


def _ai_answer(question: str, results: List[SearchResult]) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY 环境变量，无法调用 AI 分析。")

    client = OpenAI(api_key=api_key)

    context_lines = []
    for res in results:
        summary = res.content[:400].replace("\n", " ") + ("..." if len(res.content) > 400 else "")
        context_lines.append(
            f"标题：{res.title}\n媒体：{res.media_cn} ({res.media_en})\n时间：{res.published_at}\n摘要：{summary}"
        )

    context_text = "\n\n".join(context_lines)

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "你是安全情报分析助手，请用简洁的中文总结，并给出可执行建议。",
            },
            {
                "role": "user",
                "content": (
                    "请基于以下检索到的情报回答问题。" "\n\n" f"问题：{question}\n\n情报：\n{context_text}"
                ),
            },
        ],
        temperature=0.4,
        max_tokens=600,
    )

    return completion.choices[0].message.content.strip()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
