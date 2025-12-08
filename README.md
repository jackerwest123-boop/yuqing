# 情报搜索助手

一个基于 Flask 的小型网页工具，用于按关键字组合搜索情报，并支持时间范围过滤与 OpenAI 实时分析。核心爬虫逻辑来源于提供的 Selenium 示例。

## 特性
- 关键字随机组合：输入关键词后，一键随机生成或洗牌组合。
- 时间范围预设：最近一天、三天、一个月或自定义时间段。
- 搜索结果展示：标题、作者、时间、媒体中英文名、正文摘要和加载耗时。
- AI 分析接口：在当前搜索结果中勾选条目后，提交问题通过 OpenAI 接口给出中文分析与建议。

## 本地运行
1. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```
2. 启动服务
   ```bash
   python app.py
   ```
3. 浏览器访问 `http://localhost:5000`。

> AI 分析需要设置环境变量 `OPENAI_API_KEY`，默认使用 `gpt-4o-mini` 模型。示例：
> ```bash
> export OPENAI_API_KEY=sk-xxx
> python app.py
> ```

> 想快速预览界面而不运行爬虫？
> - 直接访问 `http://localhost:5000/?demo=1` 可自动加载示例数据。
> - 或者在页面点击“快速预览”按钮，同样会填充示例结果，立即查看列表与 AI 提问流程。

> 说明：爬虫依赖本地可用的 Chrome 与 ChromeDriver（Selenium Manager 自动匹配），默认使用无头模式并关闭图片加速页面加载。如果浏览器不可用或被安全策略限制，会在页面顶部提示初始化失败。
