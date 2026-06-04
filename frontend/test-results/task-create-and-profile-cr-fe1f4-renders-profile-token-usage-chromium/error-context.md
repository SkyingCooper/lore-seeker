# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: task-create-and-profile.spec.ts >> creates a task and renders profile token usage
- Location: tests/e2e/task-create-and-profile.spec.ts:15:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('h1').filter({ hasText: /新建任务|New Task/ })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for locator('h1').filter({ hasText: /新建任务|New Task/ })

```

# Page snapshot

```yaml
- generic [ref=e5]:
  - complementary [ref=e6]:
    - generic [ref=e8]:
      - generic [ref=e9]:
        - generic [ref=e10]:
          - img "Lore Seeker" [ref=e11]
          - img "Lore Seeker" [ref=e12]
        - button "G" [ref=e14]:
          - generic [ref=e15]: G
          - img [ref=e16]
      - generic [ref=e19]:
        - button [ref=e20]:
          - img [ref=e21]
        - button [ref=e24]:
          - img [ref=e25]
        - button [ref=e28]:
          - img [ref=e29]
        - button [ref=e32]:
          - img [ref=e33]
        - button [ref=e36]:
          - img [ref=e37]
        - button [ref=e41]:
          - img [ref=e42]
      - generic [ref=e46]:
        - button "任务" [ref=e47]:
          - img [ref=e48]
          - generic [ref=e51]: 任务
        - button "知识库" [ref=e52]:
          - img [ref=e53]
          - generic [ref=e56]: 知识库
        - button "帮助" [ref=e57]:
          - img [ref=e58]
          - generic [ref=e61]: 帮助
        - button "垃圾箱" [ref=e62]:
          - img [ref=e63]
          - generic [ref=e66]: 垃圾箱
      - generic [ref=e67]:
        - generic [ref=e68]:
          - button "我的分类" [ref=e69]:
            - img [ref=e70]
            - generic [ref=e72]: 我的分类
          - button [ref=e73]:
            - img [ref=e74]
        - generic [ref=e78]:
          - button "从电脑桌面端开始吧！" [ref=e79]:
            - img [ref=e80]
            - generic [ref=e83]: 从电脑桌面端开始吧！
          - button "Weekly To-do List" [ref=e84]:
            - img [ref=e85]
            - generic [ref=e88]: Weekly To-do List
          - button "Monthly Budget" [ref=e89]:
            - img [ref=e90]
            - generic [ref=e93]: Monthly Budget
      - generic [ref=e94]:
        - button "开启对话" [ref=e95]:
          - img [ref=e97]
          - generic [ref=e99]: 开启对话
        - button [ref=e100]:
          - img [ref=e101]
  - generic [ref=e108]:
    - banner [ref=e109]:
      - heading "新建任务" [level=1] [ref=e110]
      - paragraph [ref=e111]: 设置搜索主题、关键词、来源和目标，创建自动化知识收集任务。
    - generic [ref=e113]:
      - generic [ref=e114]:
        - text: 主题来源
        - generic [ref=e115]:
          - generic [ref=e116] [cursor=pointer]:
            - generic [ref=e117]:
              - radio "选择已有主题"
            - generic [ref=e119]: 选择已有主题
          - generic [ref=e120] [cursor=pointer]:
            - generic [ref=e121]:
              - radio "创建新主题" [checked]
            - generic [ref=e123]: 创建新主题
      - generic [ref=e124]:
        - generic [ref=e125]: 主题名称 *
        - generic [ref=e128]:
          - textbox "如：Rust 异步编程最佳实践" [ref=e129]
          - generic:
            - generic: 如：Rust 异步编程最佳实践
      - generic [ref=e130]:
        - text: 关键词
        - button [ref=e131] [cursor=pointer]:
          - img [ref=e134]
      - generic [ref=e136]:
        - text: 描述
        - generic [ref=e138]:
          - textbox "关于搜索主题的说明，如：关注技术实现、行业应用等" [ref=e139]
          - generic: 关于搜索主题的说明，如：关注技术实现、行业应用等
      - generic [ref=e140]:
        - text: 搜索方式
        - generic [ref=e141]:
          - generic [ref=e142] [cursor=pointer]:
            - generic [ref=e143]:
              - radio "混合" [checked]
            - generic [ref=e145]: 混合
          - generic [ref=e146] [cursor=pointer]:
            - generic [ref=e147]:
              - radio "API 搜索"
            - generic [ref=e149]: API 搜索
          - generic [ref=e150] [cursor=pointer]:
            - generic [ref=e151]:
              - radio "爬虫"
            - generic [ref=e153]: 爬虫
      - generic [ref=e154]:
        - text: 搜索频率
        - generic [ref=e157] [cursor=pointer]:
          - generic "仅一次" [ref=e158]:
            - generic [ref=e159]: 仅一次
          - img "loading" [ref=e160]:
            - img [ref=e165]
      - generic [ref=e167]:
        - text: 来源网站（可选，最多5个）
        - generic [ref=e168]:
          - generic [ref=e169]:
            - generic [ref=e170]: 代码托管
            - generic [ref=e171]:
              - button "GitHub" [ref=e172]
              - button "GitLab" [ref=e173]
              - button "Gitee" [ref=e174]
              - button "Bitbucket" [ref=e175]
              - button "SourceForge" [ref=e176]
              - button "GitCode" [ref=e177]
              - button "Coding.net" [ref=e178]
          - generic [ref=e179]:
            - generic [ref=e180]: 技术社区
            - generic [ref=e181]:
              - button "Stack Overflow" [ref=e182]
              - button "Reddit" [ref=e183]
              - button "Hacker News" [ref=e184]
              - button "Dev.to" [ref=e185]
              - button "知乎" [ref=e186]
              - button "掘金" [ref=e187]
              - button "SegmentFault" [ref=e188]
              - button "CSDN" [ref=e189]
          - generic [ref=e190]:
            - generic [ref=e191]: 学术论文
            - generic [ref=e192]:
              - button "arXiv" [ref=e193]
              - button "PubMed" [ref=e194]
              - button "Google Scholar" [ref=e195]
              - button "IEEE Xplore" [ref=e196]
              - button "ACM DL" [ref=e197]
              - button "Semantic Scholar" [ref=e198]
              - button "知网" [ref=e199]
          - generic [ref=e200]:
            - generic [ref=e201]: 开源基金会
            - generic [ref=e202]:
              - button "Apache Projects" [ref=e203]
              - button "Linux Foundation" [ref=e204]
              - button "CNCF" [ref=e205]
              - button "Python.org" [ref=e206]
              - button "Rust社区" [ref=e207]
              - button "Eclipse Foundation" [ref=e208]
              - button "OpenJS Foundation" [ref=e209]
          - generic [ref=e210]:
            - generic [ref=e211]: 新闻资讯
            - generic [ref=e212]:
              - button "TechCrunch" [ref=e213]
              - button "V2EX" [ref=e214]
              - button "Product Hunt" [ref=e215]
              - button "HackerNoon" [ref=e216]
              - button "36氪" [ref=e217]
              - button "少数派" [ref=e218]
              - button "The Verge" [ref=e219]
          - generic [ref=e220]:
            - generic [ref=e223]:
              - textbox "自定义网址，分号隔开" [ref=e224]
              - generic:
                - generic: 自定义网址，分号隔开
            - paragraph [ref=e225]: 如 https://example.com; https://blog.example.com
      - button "创建任务" [ref=e227] [cursor=pointer]:
        - generic [ref=e228]: 创建任务
```

# Test source

```ts
  1  | import type { Page } from '@playwright/test'
  2  | import { expect } from '@playwright/test'
  3  | 
  4  | export class TaskCreatePage {
  5  |   constructor(private readonly page: Page) {}
  6  | 
  7  |   async goto() {
  8  |     await this.page.goto('/tasks/new')
> 9  |     await expect(this.page.locator('h1', { hasText: /新建任务|New Task/ })).toBeVisible()
     |                                                                         ^ Error: expect(locator).toBeVisible() failed
  10 |   }
  11 | 
  12 |   async fillBasicForm(title: string, description: string) {
  13 |     await this.page.getByTestId('task-topic-title').locator('input').fill(title)
  14 |     await this.page.getByTestId('task-description').locator('textarea').fill(description)
  15 |   }
  16 | 
  17 |   async submit() {
  18 |     await this.page.getByTestId('task-submit').click()
  19 |   }
  20 | }
  21 | 
```