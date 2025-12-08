# 情报搜索助手

一个基于 Flask 的小型网页工具，用于按关键字组合搜索情报，并支持时间范围过滤和在线 AI 分析。核心爬虫逻辑使用 DuckDuckGo HTML 结果，避免依赖浏览器驱动。

## 特性
- 关键字随机组合：输入关键词后，一键随机生成或洗牌组合。
- 时间范围预设：最近一天、三天、一个月或自定义时间段。
- 搜索结果展示：标题、作者、时间、媒体中英文名、正文摘要和加载耗时。
- AI 分析接口：在当前搜索结果中勾选条目后，提交问题可获得基于上下文的在线 OpenAI 分析回答。

## 本地运行
1. 安装依赖
   ```bash
    pip install -r requirements.txt
   ```
2. 启动服务
   ```bash
    export OPENAI_API_KEY=你的 OpenAI Key
    python app.py
   ```
3. 浏览器访问 `http://localhost:5000`。

> 说明：爬虫基于 HTTP 请求解析 DuckDuckGo 结果，无需浏览器或驱动。但 OpenAI 分析需要在环境变量中配置 `OPENAI_API_KEY`。
