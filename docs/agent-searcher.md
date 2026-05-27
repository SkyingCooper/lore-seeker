# 搜索 Agent (Searcher)

## 职责

接收规划 Agent 生成的子查询列表和主题配置，通过搜索 API 或爬虫采集原始内容，返回去重后的结果列表。

## 搜索模式

| 模式 | 触发条件 | 说明 |
|---|---|---|
| `api` | 默认 | 调用搜索 API，速度快，结果质量稳定 |
| `crawl` | 用户指定目标网站时 | Playwright 爬取指定 URL，获取全文 |
| `both` | 用户选择混合模式 | API 先行采集，爬虫补充深度内容 |

## 搜索 API 路由

支持三个提供商，通过 `config.toml` 的 `[search] api_provider` 切换：

| 提供商 | 特点 | 适用场景 |
|---|---|---|
| Tavily | 专为 AI 设计，返回结构化摘要 | 默认推荐 |
| SerpAPI | Google 结果，覆盖面广 | 需要 Google 质量时 |
| Bing | 微软搜索，有官方 API | 国内访问稳定性更好 |

**指定域名过滤**：当用户配置了 `target_sites` 时，API 搜索会附加 `site:` 过滤参数，将结果限定在指定域名内。

## 爬虫策略

使用 Playwright 无头 Chromium，处理 JS 渲染页面：

- 每次任务最多爬取 5 个站点（防止超时）
- 超时设置：15 秒/页面
- 提取策略：`BeautifulSoup` 解析 HTML，`get_text()` 提取纯文本，截取前 3000 字符
- 等待策略：`wait_until="domcontentloaded"`，不等待所有资源加载完成

**待优化**：当前爬虫只抓首页，后续可增加站内链接跟踪（深度爬取）。

## 去重逻辑

按 `url` 字段去重，保留第一次出现的结果。API 结果和爬虫结果合并后统一去重。

## 输出格式

```python
[
  {
    "title": "文章标题",
    "url": "https://...",
    "content": "正文摘要或全文（截断）"
  },
  ...
]
```

## 相关文件

- `backend/agents/searcher.py` — 节点实现
- `backend/services/search_service.py` — API 搜索 + 爬虫实现

---

## 2025-05-27 — 初始设计

**背景**：需要支持多搜索源，且用户可以指定目标网站。

**决策**：搜索逻辑下沉到 `search_service.py`，Agent 节点只做模式路由和去重，保持薄层。

**放弃的方案**：
- 直接在 Agent 节点里写搜索逻辑：难以单独测试，也难以复用

**影响范围**：`agents/searcher.py`、`services/search_service.py`
